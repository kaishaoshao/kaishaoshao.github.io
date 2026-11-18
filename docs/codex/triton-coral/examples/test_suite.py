"""Host-only regressions. Synthetic fixtures never certify Coral execution."""

import ast
import copy
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

from abi import pack_frame, unpack_frame
from check_plan import validate_plan
from access import all_programs, program_accesses, select_cases
from jit_entry import call_kernel
from run_stage import artifact, check_elf, check_trace, check_values, digest, request_for, verify_response
from suite import cases, inventory, vector

HERE = Path(__file__).resolve().parent


def _runs(indices):
    groups = []
    for i in sorted(indices):
        if not groups or groups[-1][-1] + 1 != i:
            groups.append([])
        groups[-1].append(i)
    return groups


def _synthetic_trace(step, case, local=False):
    """Only validator unit fixtures; never use this as a device adapter."""
    views, arguments, events = {}, {}, [{"kind": "guard_check", "ok": True}]
    bases = {"shared": 0x20000000, "dram": 0x60000000, "hbf": 0x80000000, "dtcm": 0x10000}
    width = {"i32": 4, "f32": 4, "bf16": 2, "i8": 1}

    def view(name, binding, indices, region, address, owner=None, generation=0):
        views[name] = {"binding": binding, "indices": list(indices), "region": region, "address": address,
                       "owner": owner, "generation": generation, "allocation": f"{region}/{owner}/{address}"}
        return name

    for ordinal, (binding, buffer) in enumerate(step["buffers"].items()):
        name = "arg/" + binding; region = buffer["region"]
        address = bases[region] + ordinal * 0x10000
        if buffer.get("alias_of"):
            address = views[arguments[buffer["alias_of"]]]["address"]
        arguments[binding] = view(name, binding, range(len(buffer["values"])), region, address,
                                  buffer.get("owner") if region == "dtcm" else None)
    cursor = 1
    cores = [i for i in range(case["core_mask"].bit_length()) if case["core_mask"] & (1 << i)]

    def copy_to(src, dst, core):
        nonlocal cursor
        binding = views[src["view"]]["binding"]
        event = {"kind": "dma", "id": "dma/" + str(len(events)), "core": core,
                 "source": views[src["view"]]["region"], "destination": views[dst["view"]]["region"],
                 "src": src, "dst": dst, "start": cursor, "end": cursor + 2, "success": True,
                 "bytes": len(views[src["view"]]["indices"]) * width[step["buffers"][binding]["dtype"]]}
        cursor += 2; events.append(event)

    for ordinal, program in enumerate(all_programs(step)):
        core = cores[ordinal % len(cores)]; identity = "kernel/" + str(ordinal)
        contract = program_accesses(step, program); reads, writes, accesses, outputs = [], [], [], []
        for group_no, ((binding, mode), indices) in enumerate(contract.items()):
            for segment_no, group in enumerate(_runs(indices)):
                arg = views[arguments[binding]]; element_bytes = width[step["buffers"][binding]["dtype"]]
                global_name = view(f"{identity}/{binding}/{mode}/{segment_no}/global", binding, group,
                                   arg["region"], arg["address"] + group[0] * element_bytes, arg["owner"])
                if local:
                    local_name = view(f"{identity}/{binding}/{mode}/{segment_no}/local", binding, group, "dtcm",
                                      (0x10100 if mode == "read" else 0x15000) + group_no * 0x400 + segment_no * 0x100,
                                      core, ordinal + 1)
                    ref = {"view": local_name, "version": 1}
                    if mode == "read":
                        previous = {"view": global_name, "version": 0}
                        if arg["region"] == "hbf":
                            stage = view(global_name + "/stage", binding, group, "dram",
                                         0x61000000 + ordinal * 0x10000 + segment_no * 0x400)
                            staged = {"view": stage, "version": 1}
                            copy_to(previous, staged, core); previous = staged
                        copy_to(previous, ref, core)
                    else:
                        outputs.append((ref, {"view": global_name, "version": 1}))
                else:
                    ref = {"view": global_name, "version": 0 if mode == "read" else 1}
                (reads if mode == "read" else writes).append(ref)
                accesses.append({"kind": "access", "launch": identity, "binding": binding, "mode": mode,
                                 "index": group[0], "count": len(group), **ref})
        launch = {"kind": "launch", "id": identity, "program": list(program), "core": core,
                  "start": cursor + 1, "end": cursor + 5, "reads": reads, "writes": writes}
        cursor += 6; events.append(launch); events.extend(accesses)
        for src, dst in outputs:
            copy_to(src, dst, core)
    return {"protocol": 2, "views": views, "arguments": arguments, "events": events}


def _elf():
    data = bytearray(88); data[:7] = b"\x7fELF\x01\x01\x01"
    struct.pack_into("<HHIIIIIHHHHHH", data, 16, 2, 243, 1, 0x1000, 52, 0, 0, 52, 32, 1, 0, 0, 0)
    struct.pack_into("<IIIIIIII", data, 52, 1, 84, 0x1000, 0x1000, 4, 4, 5, 1)
    return bytes(data)


class TutorialContractTests(unittest.TestCase):
    def setUp(self):
        self.by_id = {c["id"]: c for c in cases()}

    def test_sources_and_stage_coverage(self):
        items = cases(); self.assertEqual(len(self.by_id), len(items))
        self.assertEqual({c["stage"] for c in items}, {f"S{i}" for i in range(10)})
        names = {n.name for n in ast.parse((HERE / "kernels.py").read_text()).body if isinstance(n, ast.FunctionDef)}
        self.assertEqual({s["kernel"] for c in items for s in c["steps"]}, names)
        plan = json.loads((HERE.parent / "plan.json").read_text(encoding="utf-8"))
        self.assertEqual(len(plan["syntax_stages"]), len(inventory()))
        for row, actual in zip(plan["syntax_stages"], inventory()):
            self.assertEqual(row["stage"], actual["stage"])
            self.assertEqual(row["case_ids"], actual["case_ids"])
        for case in items:
            for item in case["steps"]:
                for name, expected in item["expected"].items():
                    self.assertEqual(len(expected), len(item["buffers"][name]["values"]))

    def test_reference_boundaries_and_padding(self):
        self.assertEqual(self.by_id["S1.wrap"]["steps"][0]["expected"]["Y"], [-2147483648])
        self.assertEqual(self.by_id["S2.mask.n0.b16"]["steps"][0]["expected"]["Y"], [])
        self.assertEqual(self.by_id["S2.other"]["steps"][0]["expected"]["Y"], [3, 4, 5] + [7] * 13)
        self.assertEqual(self.by_id["S4.stride-broadcast"]["steps"][0]["expected"]["Y"][:9],
                         [0, 1, 2, 3, 4, 5, 6, 1515870810, 1515870810])
        self.assertEqual(self.by_id["S4.loop.r0"]["steps"][0]["expected"]["Y"], [0] * 5)
        self.assertEqual(self.by_id["S3.abi-v3"]["steps"][0]["expected"]["Y"], [11])

    def test_plan_data_markdown_and_abi_agree(self):
        self.assertTrue(validate_plan()["consistent"])

    def test_plan_checker_detects_scope_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = json.loads((HERE.parent / "plan.json").read_text(encoding="utf-8"))
            data["tasks"][0][7] += " accidental changed requirement"
            (root / "plan.json").write_text(json.dumps(data), encoding="utf-8")
            (root / "plan.md").write_text((HERE.parent / "plan.md").read_text(encoding="utf-8"), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Markdown/data mismatch"):
                validate_plan(root)

    def test_request_hides_reference_values(self):
        first = request_for(self.by_id["S1.copy"], "first")
        self.assertEqual(first["protocol"], 2)
        self.assertNotIn("expected", first["steps"][0]); self.assertEqual(first["steps"][0]["output_bindings"], ["Y"])
        self.assertNotEqual(first["request_sha256"], request_for(self.by_id["S1.copy"], "second")["request_sha256"])

    def test_access_oracle_known_masks_and_strides(self):
        vector_step = self.by_id["S2.mask.n37.b16"]["steps"][0]
        self.assertEqual(program_accesses(vector_step, [1, 0, 0]),
                         {("X", "read"): set(range(16, 32)), ("Y", "write"): set(range(16, 32))})
        strided = self.by_id["S4.stride-broadcast"]["steps"][0]
        self.assertEqual(program_accesses(strided, [1, 0, 0]),
                         {("X", "read"): set(range(44, 51)), ("Bias", "read"): set(range(7)),
                          ("Y", "write"): set(range(36, 43))})
        matrix = self.by_id["S8.dot.17x19x35.mask1"]["steps"][0]
        actual = program_accesses(matrix, [1, 1, 0])
        self.assertEqual(actual[("A", "read")], set(range(640, 675)))
        self.assertEqual(actual[("C", "write")], {368, 369, 370})
        self.assertEqual(len(actual[("B", "read")]), 105)

    def test_values_reject_wrong_shape_bool_and_nan(self):
        for wrong in ([1], [1, 9], [True, 2]):
            with self.assertRaises(ValueError): check_values({"Y": wrong}, {"Y": [1, 2]})
        with self.assertRaises(ValueError): check_values({"Y": [float("nan")]}, {"Y": [0.0]})
        check_values({"Y": [0.5000001]}, {"Y": [0.5]}, {"rtol": 1e-5, "atol": 1e-6})

    def test_elf_placeholder_truncation_and_entry(self):
        good = bytearray(_elf()); check_elf(good)
        for wrong in (b"/* Coral Binary */", good[:60], good[:84]):
            with self.assertRaises(ValueError): check_elf(wrong)
        struct.pack_into("<I", good, 24, 0x2000)
        with self.assertRaises(ValueError): check_elf(good)

    def test_artifact_hash_and_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / "ok").write_bytes(b"data")
            records = {"data": {"path": "ok", "sha256": digest(b"data")}}
            self.assertEqual(artifact(records, "data", root), b"data")
            records["data"]["sha256"] = "wrong"
            with self.assertRaises(ValueError): artifact(records, "data", root)
            records["data"]["path"] = "../outside"
            with self.assertRaises(ValueError): artifact(records, "data", root)

    def test_v2_layout_and_capacity(self):
        data = pack_frame(2, [0x100, 0x200], [-1], program_id=[0, 0, 0], grid=[1, 1, 1], core_id=0, done=0x300)
        self.assertEqual(len(data), 68); self.assertEqual(struct.unpack_from("<I", data, 64)[0], 0x300)
        self.assertEqual(unpack_frame(data)["scalars"][0], 0xFFFFFFFF)
        with self.assertRaises(ValueError):
            pack_frame(2, [0x100], list(range(6)), program_id=[0, 0, 0], grid=[1, 1, 1], core_id=0, done=0x300)

    def test_v3_six_scalar_roundtrip_and_offset(self):
        data = pack_frame(3, [0x100, 0x200, 0x400], list(range(6)), program_id=[1, 0, 0], grid=[2, 1, 1], core_id=1, done=0x300)
        self.assertEqual(len(data), 128); self.assertEqual(struct.unpack_from("<I", data, 44)[0], 0x300)
        self.assertEqual(list(struct.unpack_from("<6I", data, 80)), list(range(6)))
        self.assertEqual(unpack_frame(data)["scalars"], list(range(6)))

    def test_abi_rejects_size_slots_overflow_and_zero_grid(self):
        data = bytearray(pack_frame(3, [0x100], [1], program_id=[0, 0, 0], grid=[1, 1, 1], core_id=0, done=0x300))
        for offset, value in ((4, 64), (36, 9), (40, 13), (52, 7), (84, 7)):
            bad = bytearray(data); struct.pack_into("<I", bad, offset, value)
            with self.assertRaises(ValueError): unpack_frame(bad)
        for scalar, grid in ((1 << 32, [1, 1, 1]), (1, [0, 1, 1])):
            with self.assertRaises(ValueError):
                pack_frame(3, [], [scalar], program_id=[0, 0, 0], grid=grid, core_id=0, done=0x300)

    def test_legal_mask_and_zero_length_traces(self):
        for identity in ("S2.mask.n0.b16", "S2.mask.n37.b16", "S2.inplace", "S4.stride-broadcast"):
            case = self.by_id[identity]; step = case["steps"][0]
            check_trace(_synthetic_trace(step, case), step, case)

    def test_mask_rejects_read_or_write_in_padding(self):
        case = self.by_id["S4.stride-broadcast"]; step = case["steps"][0]
        for binding, index, mode in (("X", 7, "read"), ("Y", 7, "write")):
            trace = _synthetic_trace(step, case)
            trace["events"].append({"kind": "access", "launch": "kernel/0", "binding": binding,
                                    "mode": mode, "index": index, "count": 1,
                                    "view": trace["arguments"][binding], "version": 0})
            with self.assertRaisesRegex(ValueError, "mask/stride/direction"): check_trace(trace, step, case)

    def test_alias_rejects_undeclared_type_punning(self):
        case = copy.deepcopy(self.by_id["S2.inplace"]); step = case["steps"][0]
        trace = _synthetic_trace(step, case)
        step["buffers"]["Y"]["dtype"] = "i8"
        with self.assertRaisesRegex(ValueError, "equal-dtype"):
            check_trace(trace, step, case)

    def test_grid_wrong_core_missing_access_and_direction(self):
        case = self.by_id["S2.mask.n3.b16"]; step = case["steps"][0]
        trace = _synthetic_trace(step, case)
        bad = copy.deepcopy(trace); bad["events"].append(copy.deepcopy(next(e for e in bad["events"] if e["kind"] == "launch")))
        with self.assertRaises(ValueError): check_trace(bad, step, case)
        for mutate in (lambda t: next(e for e in t["events"] if e["kind"] == "launch").update(core=3),
                       lambda t: t.update(events=[e for e in t["events"] if not (e["kind"] == "access" and e["mode"] == "read")]),
                       lambda t: next(e for e in t["events"] if e["kind"] == "access").update(mode="execute")):
            bad = copy.deepcopy(trace); mutate(bad)
            with self.assertRaises(ValueError): check_trace(bad, step, case)

    def local_fixture(self):
        case = copy.deepcopy(self.by_id["S7.tiers.mask1"]); case["steps"] = [vector(3, 16, region="hbf")]
        step = case["steps"][0]
        return case, step, _synthetic_trace(step, case, local=True)

    def test_legal_dma_chain(self):
        case, step, trace = self.local_fixture(); check_trace(trace, step, case)

    def test_rejects_input_dma_after_kernel(self):
        case, step, trace = self.local_fixture()
        for i, event in enumerate(e for e in trace["events"] if e["kind"] == "dma"):
            event.update(start=100 + 3 * i, end=102 + 3 * i)
        with self.assertRaisesRegex(ValueError, "before its producer"): check_trace(trace, step, case)

    def test_rejects_output_dma_before_kernel(self):
        case, step, trace = self.local_fixture()
        output = next(e for e in trace["events"] if e["kind"] == "dma" and e["source"] == "dtcm")
        output.update(start=0, end=1)
        with self.assertRaisesRegex(ValueError, "before its producer"): check_trace(trace, step, case)

    def test_rejects_missing_version_wrong_owner_and_alignment(self):
        case, step, trace = self.local_fixture()
        for mutate in (lambda t: next(e for e in t["events"] if e["kind"] == "access" and e["mode"] == "read").update(version=99),
                       lambda t: next(v for v in t["views"].values() if v["region"] == "dtcm").update(owner=3),
                       lambda t: next(e for e in t["events"] if e["kind"] == "dma").update(bytes=11)):
            bad = copy.deepcopy(trace); mutate(bad)
            with self.assertRaises(ValueError): check_trace(bad, step, case)

    def test_rejects_stale_replica_reuse(self):
        case, step, trace = self.local_fixture()
        copied = [e for e in trace["events"] if e["kind"] == "dma" and e["destination"] == "dtcm"][0]
        overwrite = copy.deepcopy(copied); overwrite.update(id="overwrite", start=copied["end"], end=copied["end"] + 1)
        overwrite["dst"]["version"] = 2; trace["events"].append(overwrite)
        with self.assertRaisesRegex(ValueError, "stale version"): check_trace(trace, step, case)

    def test_rejects_hbf_write_and_missing_output_copy(self):
        case, step, trace = self.local_fixture()
        bad = copy.deepcopy(trace); bad["events"] = [e for e in bad["events"] if not (e["kind"] == "dma" and e["source"] == "dtcm")]
        # Retain a dtcm->dram edge for X: path presence alone must not prove Y was written back.
        original = next(e for e in trace["events"] if e["kind"] == "dma" and e["source"] == "dtcm")
        dummy = copy.deepcopy(original); dummy["id"] = "unrelated-writeback"
        dummy["src"] = copy.deepcopy(next(e for e in trace["events"] if e["kind"] == "dma" and e["destination"] == "dtcm")["dst"])
        target = "unused-dram-X"
        bad["views"][target] = copy.deepcopy(bad["views"][dummy["src"]["view"]])
        bad["views"][target].update(region="dram", owner=None, address=0x62000000, allocation="unused-X", generation=0)
        dummy["dst"] = {"view": target, "version": 1}; bad["events"].append(dummy)
        with self.assertRaisesRegex(ValueError, "written back"): check_trace(bad, step, case)
        bad = copy.deepcopy(trace)
        output = next(e for e in bad["events"] if e["kind"] == "dma" and e["source"] == "dtcm")
        bad["views"][output["dst"]["view"]]["region"] = "hbf"; output["destination"] = "hbf"
        with self.assertRaisesRegex(ValueError, "read-only HBF"): check_trace(bad, step, case)

    def test_capabilities_include_only_validated_modes(self):
        identities = {c["id"] for c in select_cases(cases(), "S6", cumulative=True, validated=["fp32.basic.aot"])}
        self.assertIn("S9.fp32", identities); self.assertNotIn("S9.bf16", identities); self.assertNotIn("S9.fp32.jit", identities)
        self.assertNotIn("S9.fp32", {c["id"] for c in select_cases(cases(), "S6", cumulative=True)})
        self.assertIn("S9.fp32.jit", {c["id"] for c in select_cases(cases(), "S9", ids=["S9.fp32.jit"])})
        with self.assertRaises(ValueError): select_cases(cases(), "S6", cumulative=True, validated=["unknown"])

    def test_new_syntax_has_jit_mirrors(self):
        for prefix in ("S4.", "S5.", "S6.", "S7.", "S8."):
            for case in cases():
                if case["id"].startswith(prefix) and case["mode"] == "aot" and not case["error"]:
                    self.assertEqual(self.by_id[case["id"] + ".jit"]["mode"], "jit")

    def test_jit_helper_uses_getitem_and_runtime_order(self):
        class Kernel:
            arg_names = ["X", "Y", "N", "DELTA", "BLOCK"]

            def __getitem__(self, grid):
                self.grid = grid

                def call(*args, **constants):
                    self.args, self.constants = args, constants
                    return type("Compiled", (), {"asm": {"elf": _elf()}})()
                return call

        kernel = Kernel(); step = vector(3, 16)
        _, record = call_kernel(kernel, step, {"X": "device-X", "Y": "device-Y"}, request_sha256="request", step_index=0)
        self.assertEqual(kernel.args, ("device-X", "device-Y", 3)); self.assertEqual(kernel.constants, {"DELTA": 1, "BLOCK": 16})
        self.assertEqual(record["api"], "kernel[grid](...)"); self.assertEqual(record["compiled_elf_sha256"], digest(_elf()))

    def _response(self, case, root):
        request = request_for(case)

        def record(name, content):
            raw = content if isinstance(content, bytes) else content.encode()
            (root / name).write_bytes(raw); return {"path": name, "sha256": digest(raw)}

        build = {k: "unit-fixture" for k in ("triton_commit", "llvm_commit", "coral_commit", "abi", "target")}
        build.update(kernel_source_sha256=request["kernel_source_sha256"], pipeline="current-mainline", abi_version=request["abi_version"])
        response = {"protocol": 2, "nonce": request["nonce"], "request_sha256": request["request_sha256"],
                    "status": "ok", "artifacts": {"build": record("build.json", json.dumps(build))}, "results": []}
        for i, step in enumerate(case["steps"]):
            empty = step["kernel"] == "empty_kernel"
            ttir = f"tt.func public @{step['kernel']} {{ " + ("" if empty else "tt.load tt.store ") + "tt.return }"
            records = {"ttir": record(f"{i}.ttir", ttir), "verification": record(f"{i}.verify.json", '{"ttir":true,"llvm":true,"elf":true,"llvm_dialect":true}')}
            result = {"artifacts": records}
            if case["mode"] == "ir":
                records["llvm_dialect"] = record(f"{i}.llvm.mlir", "llvm.func @empty_kernel { llvm.return }")
            elif case["mode"] != "frontend":
                result.update(execution="rtl", outputs=step["expected"])
                records.update(elf=record(f"{i}.elf", _elf()), llir=record(f"{i}.ll", "define void @fixture() { ret void }"),
                               trace=record(f"{i}.trace.json", json.dumps(_synthetic_trace(step, case))))
                invocation = {"protocol": 2, "api": "kernel[grid](...)" if case["mode"] == "jit" else "aot_bridge",
                              "backend": "coral", "kernel": step["kernel"], "grid": step["grid"], "step": i,
                              "request_sha256": request["request_sha256"], "compiled_elf_sha256": digest(_elf())}
                records["invocation"] = record(f"{i}.invoke.json", json.dumps(invocation))
            response["results"].append(result)
        return request, response

    def test_empty_frontend_and_llvm_only_without_device(self):
        for identity in ("S1.empty.frontend", "S1.empty.llvm"):
            with tempfile.TemporaryDirectory() as temp:
                case = self.by_id[identity]; root = Path(temp); request, response = self._response(case, root)
                verify_response(case, request, response, root)
                self.assertNotIn("execution", response["results"][0])

    def test_frontend_report_cannot_claim_device_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            case = copy.deepcopy(self.by_id["S0.frontend"]); root = Path(temp); request, response = self._response(case, root)
            verify_response(case, request, response, root)
            case["mode"] = "aot"
            with self.assertRaisesRegex(ValueError, "not Coral execution"): verify_response(case, request, response, root)

    def test_jit_case_rejects_aot_route_and_wrong_elf(self):
        with tempfile.TemporaryDirectory() as temp:
            case = self.by_id["S1.copy.jit"]; root = Path(temp); request, response = self._response(case, root)
            verify_response(case, request, response, root)
            rec = response["results"][0]["artifacts"]["invocation"]; path = root / rec["path"]
            invocation = json.loads(path.read_text()); invocation["api"] = "aot_bridge"
            raw = json.dumps(invocation).encode(); path.write_bytes(raw); rec["sha256"] = digest(raw)
            with self.assertRaisesRegex(ValueError, "AOT/JIT route"): verify_response(case, request, response, root)
            invocation.update(api="kernel[grid](...)", compiled_elf_sha256="different")
            raw = json.dumps(invocation).encode(); path.write_bytes(raw); rec["sha256"] = digest(raw)
            with self.assertRaisesRegex(ValueError, "invoked ELF"): verify_response(case, request, response, root)

    def test_rejects_stale_response_and_empty_success(self):
        case = self.by_id["S1.copy"]; request = request_for(case)
        for response in ({}, {"protocol": 2, "nonce": "old", "status": "ok"},
                         {"protocol": 2, "nonce": request["nonce"], "request_sha256": request["request_sha256"], "status": "ok"}):
            with tempfile.TemporaryDirectory() as temp:
                with self.assertRaises(ValueError): verify_response(case, request, response, Path(temp))

    def test_preflight_failure_has_no_dma_or_kernel_side_effects(self):
        with tempfile.TemporaryDirectory() as temp:
            case = self.by_id["S3.bad-buffer"]; root = Path(temp)
            request, response = self._response(case, root)
            response.update(status="error", diagnostic={"code": "NC_INVALID_BUFFER", "stage": "launch", "message": "stale handle"})
            path = root / "failure-trace.json"
            for events in ([], [{"kind": "dma"}]):
                raw = json.dumps({"protocol": 2, "events": events}).encode(); path.write_bytes(raw)
                response["artifacts"]["trace"] = {"path": path.name, "sha256": digest(raw)}
                if not events:
                    verify_response(case, request, response, root)
                else:
                    with self.assertRaisesRegex(ValueError, "before validation"):
                        verify_response(case, request, response, root)

    def test_missing_adapter_is_an_error(self):
        process = subprocess.run([sys.executable, str(HERE / "run_stage.py"), "--stage", "S1"], capture_output=True, text=True)
        self.assertEqual(process.returncode, 2); self.assertNotIn("PASS", process.stdout)

    def test_emit_only_never_reports_execution_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            process = subprocess.run([sys.executable, str(HERE / "run_stage.py"), "--stage", "S1", "--emit-only", "--output", temp], capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn("PREPARED", process.stdout); self.assertNotIn("PASS", process.stdout)
            summaries = list(Path(temp).glob("*/summary.json")); self.assertEqual(len(summaries), 1)
            self.assertEqual({r["status"] for r in json.loads(summaries[0].read_text())}, {"prepared"})


if __name__ == "__main__":
    unittest.main()
