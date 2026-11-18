"""Protocol-2 logical accesses and versioned copy dependencies for tutorial cases."""

from access import DTYPE_BYTES, all_programs, program_accesses


def need(condition, message):
    if not condition:
        raise ValueError(message)


def overlap(a, b):
    return max(a["start"], b["start"]) < min(a["end"], b["end"])


def check_trace(trace, step, case):
    need(trace.get("protocol") == 2, "trace protocol must be 2")
    events, views, arguments = trace["events"], trace["views"], trace["arguments"]
    need(not any(e["kind"] in ("bounds_violation", "trap") for e in events), "invalid access or trap")
    guards = [e for e in events if e["kind"] == "guard_check"]
    need(bool(guards) and all(e.get("ok") is True for e in guards), "missing/failed guard checks")
    buffers = step["buffers"]

    def root(binding, seen=()):
        need(binding in buffers and binding not in seen, "invalid buffer alias")
        alias = buffers[binding].get("alias_of")
        if alias:
            need(alias in buffers and buffers[binding]["dtype"] == buffers[alias]["dtype"] and
                 len(buffers[binding]["values"]) == len(buffers[alias]["values"]),
                 "this test subset only declares equal-dtype, equal-length in-place aliases")
        return root(alias, seen + (binding,)) if alias else binding

    physical, identities = {}, {}
    for name, view in views.items():
        binding = view["binding"]; need(binding in buffers, "unknown view binding")
        indices = view["indices"]; width = DTYPE_BYTES[buffers[binding]["dtype"]]
        need(len(indices) == len(set(indices)) and all(type(i) is int and 0 <= i < len(buffers[binding]["values"])
                                                     for i in indices), "view indices exceed allocation")
        need(type(view["address"]) is int and 0 <= view["address"] and
             view["address"] + len(indices) * width <= 1 << 32 and view["address"] % width == 0,
             "invalid view address")
        need(type(view["generation"]) is int and view["generation"] >= 0 and bool(view["allocation"]),
             "missing allocation identity/generation")
        need(view["region"] in ("shared", "dram", "hbf", "dtcm"), "unknown view region")
        need((type(view["owner"]) is int and view["owner"] >= 0) if view["region"] == "dtcm"
             else view["owner"] is None, "invalid region owner")
        cells = {}
        for ordinal, index in enumerate(indices):
            cell = (view["region"], view["owner"], view["address"] + ordinal * width)
            cells[index] = {(cell[0], cell[1], cell[2] + byte) for byte in range(width)}
            for byte_cell in cells[index]:
                identity_key = (view["generation"], byte_cell)
                identity = (root(binding), index)
                need(identity_key not in identities or identities[identity_key] == identity,
                     "overlapping views disagree on logical identity")
                identities[identity_key] = identity
        physical[name] = cells
    need(set(arguments) == set(buffers), "initial argument views are incomplete")
    for binding, name in arguments.items():
        need(name in views, "unknown argument view")
        v = views[name]
        need(v["binding"] == binding and v["region"] == buffers[binding]["region"] and
             v["generation"] == 0 and v["indices"] == list(range(len(buffers[binding]["values"]))),
             "argument view does not describe the declared buffer")
        if v["region"] == "dtcm":
            need(v["owner"] == buffers[binding].get("owner"), "argument owner mismatch")
        if buffers[binding].get("alias_of"):
            other = views[arguments[buffers[binding]["alias_of"]]]
            need((v["region"], v["owner"], v["address"], v["allocation"], v["generation"]) ==
                 (other["region"], other["owner"], other["address"], other["allocation"], other["generation"]),
                 "alias binding does not share storage")

    launches = [e for e in events if e["kind"] == "launch"]
    transfers = [e for e in events if e["kind"] == "dma"]
    operations = launches + transfers
    need(all(isinstance(e.get("id"), str) and e["id"] for e in operations), "operation ID missing")
    need(len({e["id"] for e in operations}) == len(operations), "duplicate operation ID")
    need(all(type(e["start"]) is int and type(e["end"]) is int and 0 <= e["start"] < e["end"]
             for e in operations), "invalid execution interval")
    by_launch = {e["id"]: e for e in launches}
    programs = [tuple(e["program"]) for e in launches]
    need(len(programs) == len(set(programs)) and set(programs) == set(all_programs(step)),
         "grid has missing/duplicate programs")
    cores = {i for i in range(case["core_mask"].bit_length()) if case["core_mask"] & (1 << i)}
    need(all(e["core"] in cores for e in operations), "operation uses an unavailable core")
    if "schedule" in case["features"] and len(programs) >= len(cores):
        need({e["core"] for e in launches} == cores, "requested cores were not exercised")
    for i, a in enumerate(launches):
        need(not any(a["core"] == b["core"] and overlap(a, b) for b in launches[i + 1:]),
             "two programs overlap on one core")

    def ref_key(ref):
        need(ref["view"] in views and type(ref["version"]) is int and ref["version"] >= 0,
             "invalid view/version reference")
        return ref["view"], ref["version"]

    def cells_for(ref, indices=None):
        name, _ = ref_key(ref)
        selected = views[name]["indices"] if indices is None else indices
        need(set(selected) <= set(views[name]["indices"]), "access outside view")
        return set().union(*(physical[name][i] for i in selected)) if selected else set()

    producers, writes, reads = {}, [], []

    def produce(ref, op):
        key = ref_key(ref)
        need(key[1] > 0 and key not in producers, "output version is missing or produced twice")
        need(views[key[0]]["region"] != "hbf", "write to read-only HBF")
        producers[key] = op
        writes.append((op, cells_for(ref)))

    for launch in launches:
        for ref in launch["writes"]:
            produce(ref, launch)
    for transfer in transfers:
        src, dst = transfer["src"], transfer["dst"]
        sv, dv = views[ref_key(src)[0]], views[ref_key(dst)[0]]
        width = DTYPE_BYTES[buffers[sv["binding"]]["dtype"]]
        need(root(sv["binding"]) == root(dv["binding"]) and sv["indices"] == dv["indices"] and
             width == DTYPE_BYTES[buffers[dv["binding"]]["dtype"]], "copy changes tensor identity/range")
        need(transfer["source"] == sv["region"] and transfer["destination"] == dv["region"],
             "DMA regions disagree with views")
        need(transfer["success"] is True and transfer["bytes"] == len(sv["indices"]) * width and
             transfer["bytes"] > 0 and transfer["bytes"] % 4 == 0 and
             sv["address"] % 4 == 0 and dv["address"] % 4 == 0, "invalid DMA size/alignment/completion")
        need(not cells_for(src) & cells_for(dst), "overlapping DMA is unsupported")
        for view in (sv, dv):
            need(view["region"] != "dtcm" or view["owner"] == transfer["core"], "DMA private owner mismatch")
        produce(dst, transfer)
        reads.append((src, transfer, cells_for(src)))
        need(not any(transfer["core"] == e["core"] and overlap(transfer, e) for e in launches),
             "same-core DMA/kernel overlap is not enabled")

    seen = {e["id"]: {} for e in launches}
    written = {e["id"]: {} for e in launches}
    for access in (e for e in events if e["kind"] == "access"):
        need(access["launch"] in by_launch, "access has no owning launch")
        launch = by_launch[access["launch"]]
        binding, mode = access["binding"], access["mode"]
        need(mode in ("read", "write"), "access direction missing")
        first, count = access["index"], access["count"]
        need(type(first) is int and type(count) is int and count > 0, "invalid logical access range")
        indices = set(range(first, first + count))
        contract = program_accesses(step, launch["program"])
        need(indices <= contract.get((binding, mode), set()), "access violates mask/stride/direction")
        ref = {"view": access["view"], "version": access["version"]}; key = ref_key(ref)
        view = views[key[0]]
        need(view["binding"] == binding, "logical access binding differs from its view")
        need(view["region"] != "dtcm" or view["owner"] == launch["core"], "kernel private owner mismatch")
        declared = launch["reads" if mode == "read" else "writes"]
        need(key in {ref_key(r) for r in declared}, "access version not declared by launch")
        cells = cells_for(ref, indices)
        seen[launch["id"]].setdefault((binding, mode), set()).update(indices)
        if mode == "read":
            reads.append((ref, launch, cells))
        else:
            written[launch["id"]].setdefault(key, set()).update(indices)
    for launch in launches:
        contract = program_accesses(step, launch["program"])
        need(seen[launch["id"]] == contract, "logical access trace is incomplete")
        need({ref_key(r) for r in launch["reads"]} ==
             {ref_key({"view": e["view"], "version": e["version"]}) for e in events
              if e["kind"] == "access" and e["launch"] == launch["id"] and e["mode"] == "read"},
             "unused or missing kernel read reference")
        for ref in launch["writes"]:
            need(written[launch["id"]].get(ref_key(ref), set()) == set(views[ref["view"]]["indices"]),
                 "kernel output version includes unwritten elements")

    for ref, consumer, cells in reads:
        key = ref_key(ref)
        if key[1] == 0:
            view = views[key[0]]
            argument = arguments[view["binding"]]
            need(view["generation"] == 0 and all(physical[key[0]][i] == physical[argument][i]
                                                 for i in view["indices"]),
                 "local replica has no producing copy")
            ready, producer_id = 0, None
        else:
            need(key in producers, "missing producer for data version")
            producer = producers[key]; ready, producer_id = producer["end"], producer["id"]
        need(ready <= consumer["start"], "consumer starts before its producer completes")
        for other, touched in writes:
            if other["id"] not in (producer_id, consumer["id"]) and cells & touched:
                need(other["end"] <= ready or other["start"] >= consumer["end"],
                     "stale version, premature buffer reuse, or write during consumption")

    if "dma" in case["features"]:
        need(bool(transfers), "no DMA evidence")
        for i, transfer in enumerate(transfers):
            need(not any(overlap(transfer, other) for other in transfers[i + 1:]), "single DMA channel is oversubscribed")
        edges = {(e["source"], e["destination"]) for e in transfers}
        path = case.get("storage_path", ["dram", "dtcm", "dram"])
        need(set(zip(path, path[1:])) <= edges, "missing storage path edges")
        for launch in launches:
            need(all(views[r["view"]]["region"] == "dtcm" for r in launch["reads"] + launch["writes"]),
                 "kernel bypasses its planned local replicas")
            for ref in launch["reads"]:
                producer = producers.get(ref_key(ref))
                need(producer is not None and producer["kind"] == "dma", "kernel input was not moved to local memory")
            for ref in launch["writes"]:
                pending, found, visited = [ref_key(ref)], set(), set()
                while pending:
                    key = pending.pop()
                    need(key not in visited, "copy dependency cycle")
                    visited.add(key)
                    for transfer in transfers:
                        if ref_key(transfer["src"]) == key:
                            destination = views[transfer["dst"]["view"]]
                            if destination["region"] == buffers[destination["binding"]]["region"]:
                                argument = arguments[destination["binding"]]
                                expected_cells = set().union(*(physical[argument][i] for i in destination["indices"]))
                                need(cells_for(transfer["dst"]) == expected_cells,
                                     "writeback misses the actual output allocation")
                                found |= set(destination["indices"])
                            else:
                                pending.append(ref_key(transfer["dst"]))
                need(set(views[ref["view"]]["indices"]) <= found, "kernel output was not written back")
    for feature in ("rvv", "zvt"):
        if feature in case["features"]:
            matching = [e for e in events if e["kind"] == feature]
            need(bool(matching), "no executed " + feature + " evidence")
            for event in matching:
                need(event["launch"] in by_launch and type(event["pc"]) is int, "instruction lacks kernel identity/PC")
                launch = by_launch[event["launch"]]
                need(event["core"] == launch["core"] and launch["start"] <= event["cycle"] < launch["end"],
                     "instruction is outside its owning execution interval")
    if "overlap" in case["features"]:
        need(any(t["core"] != e["core"] and overlap(t, e) for t in transfers for e in launches),
             "no cross-core transfer/compute overlap")
