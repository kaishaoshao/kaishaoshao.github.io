"""Run tutorial cases through a user-supplied Coral adapter; missing evidence fails."""

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import sys
import uuid

from suite import cases
from access import select_cases
from trace_contract import check_trace

HERE = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def request_for(case, nonce=None):
    request = copy.deepcopy(case)
    for item in request["steps"]:
        item["output_bindings"] = list(item.pop("expected"))
    request.setdefault("abi_version", 2)
    request.update(protocol=2, nonce=nonce or uuid.uuid4().hex, pipeline="current-mainline",
                   kernel_source_sha256=digest((HERE / "kernels.py").read_bytes()))
    encoded = json.dumps(request, sort_keys=True, allow_nan=False).encode()
    request["request_sha256"] = digest(encoded)
    return request


def require(condition, message):
    if not condition:
        raise ValueError(message)


def artifact(records, name, root):
    require(name in records, "missing artifact: " + name)
    record = records[name]
    path = (root / record["path"]).resolve()
    require(path.is_relative_to(root.resolve()), "artifact escapes case directory")
    data = path.read_bytes()
    require(bool(data), "empty artifact: " + name)
    require(digest(data) == record["sha256"], "artifact hash mismatch: " + name)
    return data


def check_elf(data):
    require(len(data) >= 52 and data[:7] == b"\x7fELF\x01\x01\x01", "not ELF32 little endian")
    header = struct.unpack_from("<HHIIIIIHHHHHH", data, 16)
    kind, machine, version, entry, offset = header[:5]
    phsize, phcount = header[8:10]
    require(kind == 2 and machine == 243 and version == 1, "not a static RISC-V executable")
    require(phsize == 32 and phcount > 0 and offset >= 52, "invalid program header table")
    require(offset + phsize * phcount <= len(data), "truncated program headers")
    executable = False
    for index in range(phcount):
        typ, pos, va, pa, filesz, memsz, flags, align = struct.unpack_from("<IIIIIIII", data, offset + index * phsize)
        require(typ not in (2, 3), "dynamic/interpreter segment is outside the first static ABI")
        if typ != 1:
            continue
        require(filesz <= memsz and pos + filesz <= len(data), "invalid load segment")
        require(va + memsz <= 1 << 32 and pa + memsz <= 1 << 32, "segment address overflow")
        require(align in (0, 1) or (align & (align - 1) == 0 and (va - pos) % align == 0), "invalid segment alignment")
        executable |= bool(flags & 1 and va <= entry < va + memsz)
    require(executable, "entry is not inside an executable load segment")


def check_values(actual, expected, tolerance=None):
    require(set(actual) == set(expected), "output binding set differs")
    for binding, values in expected.items():
        observed = actual[binding]
        require(len(observed) == len(values), "output length differs: " + binding)
        for index, (got, want) in enumerate(zip(observed, values)):
            require(type(got) in (int, float), "output is not numeric")
            if type(want) is int:
                equal = type(got) is int and got == want
            else:
                tol = tolerance or {"rtol": 0.0, "atol": 0.0}
                equal = math.isfinite(got) and math.isclose(got, want, rel_tol=tol["rtol"], abs_tol=tol["atol"])
            require(equal, f"{binding}[{index}]: {got!r} != {want!r}")


def verify_response(case, request, response, root):
    require(response.get("protocol") == 2, "response protocol mismatch")
    require(response.get("nonce") == request["nonce"] and
            response.get("request_sha256") == request["request_sha256"], "stale or mismatched response")
    records = response.get("artifacts", {})
    build = json.loads(artifact(records, "build", root))
    require(all(isinstance(build.get(k), str) and build[k].strip() for k in
                ("triton_commit", "llvm_commit", "coral_commit", "abi", "target")), "incomplete build identity")
    require(build.get("kernel_source_sha256") == request["kernel_source_sha256"], "source identity differs")
    require(build.get("pipeline") == request["pipeline"], "regression did not use the current mainline")
    if case["mode"] in ("aot", "jit"):
        require(build.get("abi_version") in (2, 3) if case["error"] == "NC_ABI_VERSION" else
                build.get("abi_version") == request["abi_version"], "runtime ABI does not match the request")
    if case["error"]:
        require(response.get("status") == "error", "expected a diagnostic")
        diagnostic = response.get("diagnostic", {})
        require(diagnostic.get("code") == case["error"] and bool(diagnostic.get("message")) and
                bool(diagnostic.get("stage")), "wrong/incomplete diagnostic")
        trace = json.loads(artifact(records, "trace", root))
        require(trace.get("protocol") == 2, "trace protocol must be 2")
        if case["error"] == "NC_DMA_ERROR":
            require(any(e["kind"] == "dma_error" and e["completed_bytes"] > 0 for e in trace["events"]),
                    "missing injected partial DMA failure")
            require(response.get("quiescent") is True, "failed resources have not stopped")
            recovery = json.loads(artifact(records, "recovery", root))
            require(recovery.get("old_handles_invalid") is True and recovery.get("restart_verified") is True,
                    "recovery/restart evidence missing")
        else:
            require(not any(e["kind"] in ("launch", "dma", "access") for e in trace["events"]),
                    "invalid request executed work before validation")
        return
    require(response.get("status") == "ok", "adapter reported failure")
    results = response.get("results", [])
    require(len(results) == len(case["steps"]), "missing step results")
    cache_keys = []
    for index, (source, result) in enumerate(zip(case["steps"], results)):
        records = result.get("artifacts", {})
        if not case.get("zero_launch"):
            ttir = artifact(records, "ttir", root).decode()
            require(re.search(r"tt\.func\s+(?:public\s+)?@" + re.escape(source["kernel"]) + r"\b", ttir) is not None,
                    "TTIR does not contain the source kernel")
            require("tt.return" in ttir, "TTIR return missing")
            if source["kernel"] == "empty_kernel":
                require("tt.load" not in ttir and "tt.store" not in ttir, "empty kernel unexpectedly accesses memory")
            else:
                require("tt.store" in ttir, "TTIR store missing")
            verification = json.loads(artifact(records, "verification", root))
            require(verification.get("ttir") is True, "TTIR verifier did not pass")
        if case["mode"] == "frontend":
            continue
        if case["mode"] == "ir":
            lowered = artifact(records, "llvm_dialect", root).decode()
            require("llvm.func" in lowered and "llvm.return" in lowered and "tt.func" not in lowered,
                    "LLVM dialect checkpoint is incomplete")
            require(verification.get("llvm_dialect") is True, "LLVM dialect verifier did not pass")
            continue
        require(result.get("execution") in ("rtl", "device"), "not Coral execution")
        invocation = json.loads(artifact(records, "invocation", root))
        require(invocation.get("protocol") == 2 and invocation.get("backend") == "coral" and
                invocation.get("api") == ("kernel[grid](...)" if case["mode"] == "jit" else "aot_bridge") and
                invocation.get("kernel") == source["kernel"] and invocation.get("grid") == source["grid"] and
                invocation.get("step") == index and invocation.get("request_sha256") == request["request_sha256"],
                "invocation does not prove the requested AOT/JIT route")
        # A zero grid may return without compiling or launching any ELF.
        if not case.get("zero_launch"):
            check_elf(artifact(records, "elf", root))
            require(invocation.get("compiled_elf_sha256") == records["elf"]["sha256"], "invoked ELF differs from compiled ELF")
            artifact(records, "llir", root)
            require(verification.get("llvm") is True and verification.get("elf") is True, "LLVM/ELF checks missing")
        if "structured" in case["features"]:
            structured = artifact(records, "structured", root).decode()
            bufferized = artifact(records, "bufferized", root).decode()
            require("memref" in bufferized or "llvm" in bufferized, "bufferized checkpoint missing")
            if source["kernel"] == "strided_bias":
                require("linalg." in structured, "structured tensor computation missing")
        if any(x in case["features"] for x in ("rvv", "zvt")):
            artifact(records, "disassembly", root)
        trace = json.loads(artifact(records, "trace", root))
        check_trace(trace, source, case)
        check_values(result.get("outputs", {}), source["expected"], case.get("tolerance"))
        if "cache_pattern" in case:
            require(result.get("cache_hit") is case["cache_pattern"][index], "cache hit pattern differs")
            require(bool(result.get("kernel_cache_key")), "cache key missing")
            cache_keys.append(result["kernel_cache_key"])
        if case.get("compare_single_buffer"):
            comparison = json.loads(artifact(records, "single_buffer_comparison", root))
            check_values(comparison["outputs"], source["expected"])
            require(all(type(comparison.get(k)) is int and comparison[k] > 0 for k in
                        ("single_cycles", "double_cycles")), "comparison cycle counters missing")
    if cache_keys:
        require(cache_keys[0] == cache_keys[1] and cache_keys[1] != cache_keys[2], "specialization cache identity differs")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=[f"S{i}" for i in range(10)], required=True)
    parser.add_argument("--cumulative", action="store_true")
    parser.add_argument("--include-optional", action="store_true")
    parser.add_argument("--case", action="append", default=[], help="select an exact case ID; repeat to select several")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--emit-only", action="store_true", help="write adapter requests without compiling or executing")
    parser.add_argument("--adapter", type=Path, help="Python script: --request FILE --response FILE")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--capabilities", type=Path, help="optional per-target JSON manifest with validated_capabilities")
    args = parser.parse_args()
    if args.capabilities:
        capabilities = json.loads(args.capabilities.read_text(encoding="utf-8"))["validated_capabilities"]
    else:
        capabilities = json.loads((HERE.parent / "plan.json").read_text(encoding="utf-8"))["testing"]["validated_capabilities"]
    selected = select_cases(cases(), args.stage, cumulative=args.cumulative, ids=args.case,
                            include_optional=args.include_optional, validated=capabilities)
    if args.list:
        print(json.dumps([{k: c[k] for k in ("id", "mode", "features", "error")} for c in selected], indent=2))
        return 0
    if not args.output:
        parser.error("--output is required for requests and execution evidence")
    if not args.emit_only and (not args.adapter or not args.adapter.is_file()):
        parser.error("real runs require --adapter existing_script.py and --output directory; no fallback is provided")
    require(args.timeout > 0, "timeout must be positive")
    run_dir = args.output.resolve() / uuid.uuid4().hex
    run_dir.mkdir(parents=True)
    summary = []
    for case in selected:
        root = run_dir / case["id"]; root.mkdir()
        request = request_for(case)
        request_path, response_path = root / "request.json", root / "response.json"
        request_path.write_text(json.dumps(request, indent=2, allow_nan=False), encoding="utf-8")
        if args.emit_only:
            summary.append({"id": case["id"], "mode": case["mode"], "status": "prepared"})
            print("PREPARED", case["id"], "[no compilation or execution]")
            continue
        with (root / "adapter.log").open("w", encoding="utf-8") as log:
            completed = subprocess.run([sys.executable, str(args.adapter.resolve()), "--request", str(request_path),
                                        "--response", str(response_path)], stdout=log, stderr=subprocess.STDOUT,
                                       timeout=args.timeout, check=False)
        require(completed.returncode == 0, f"adapter failed for {case['id']}; see {root / 'adapter.log'}")
        verify_response(case, request, json.loads(response_path.read_text(encoding="utf-8")), root)
        summary.append({"id": case["id"], "mode": case["mode"], "status": "pass"})
        print("PASS", case["id"], "[" + case["mode"] + "]")
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("Requests only:" if args.emit_only else "Evidence:", run_dir)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, KeyError, OSError, TypeError, subprocess.TimeoutExpired) as error:
        print("FAIL:", error, file=sys.stderr)
        sys.exit(1)
