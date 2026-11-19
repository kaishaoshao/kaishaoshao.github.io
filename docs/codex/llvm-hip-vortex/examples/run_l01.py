#!/usr/bin/env python3
"""Run the L01 front-end observations; this does not execute a GPU kernel."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", required=True, help="clang++ to observe")
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    compiler = shutil.which(args.clang)
    if compiler is None:
        parser.error(f"compiler not found: {args.clang}")
    compiler = str(Path(compiler).absolute())
    fixtures = Path(__file__).resolve().parent / "l01"
    args.output_root.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="run-", dir=args.output_root.resolve()))
    inputs = output / "inputs"
    inputs.mkdir()
    fingerprints = {}
    for source in sorted(fixtures.glob("*.hip")):
        shutil.copy2(source, inputs / source.name)
        fingerprints[source.name] = hashlib.sha256(source.read_bytes()).hexdigest()

    host = ["-x", "hip", "--offload-host-only", "-nogpuinc", "-nogpulib"]
    device = [
        "-cc1", "-triple", "riscv64-unknown-elf", "-target-cpu", "generic-rv64",
        "-target-feature", "+m", "-target-feature", "+f", "-target-feature", "+d",
        "-target-abi", "lp64d", "-x", "hip", "-fcuda-is-device",
    ]
    report = {
        "scope": "L01 front-end observation only",
        "simx_executed": False,
        "compiler": compiler,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "fixtures_sha256": fingerprints,
        "checks": [],
    }

    def check(name, options, expected_failure=False, required=(), stdout_file=None):
        command = [compiler, *options]
        (output / f"{name}.command.txt").write_text(shlex.join(command) + "\n")
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            stdout, stderr, code = result.stdout, result.stderr, result.returncode
        except (OSError, subprocess.TimeoutExpired) as error:
            stdout, stderr, code = "", str(error), None
        (output / (stdout_file or f"{name}.stdout.txt")).write_text(stdout)
        (output / f"{name}.stderr.txt").write_text(stderr)
        valid_exit = (code is not None and code > 0) if expected_failure else code == 0
        combined = stdout + "\n" + stderr
        passed = valid_exit and all(re.search(pattern, combined) for pattern in required)
        report["checks"].append({
            "name": name, "command": command, "returncode": code,
            "expected_failure": expected_failure, "passed": passed,
        })
        print(f"{'PASS' if passed else 'FAIL'} {name} (exit={code})")
        return stdout, passed

    version, _ = check("version", ["--version"], required=(r"clang version",))
    report["compiler_version"] = version.strip()
    attributes = str(inputs / "attributes.hip")
    check("preprocess", [*host, "-E", "-P", attributes],
          required=(r"__attribute__\s*\(\(global\)\)", r"store42"),
          stdout_file="attributes.ii")
    check("attributes-ast", [*host, "-fsyntax-only", "-Xclang", "-ast-dump", attributes],
          required=(r"CUDAGlobalAttr", r"CUDADeviceAttr", r"store42", r"twice"),
          stdout_file="attributes.ast.txt")
    check("host-to-device", [*host, "-fsyntax-only", str(inputs / "illegal-host-call.hip")],
          expected_failure=True,
          required=(r"error:", r"device_only", r"call to __device__ function from __host__ function"))
    check("device-to-host", [*device, "-fsyntax-only", str(inputs / "illegal-device-call.hip")],
          expected_failure=True,
          required=(r"error:", r"host_only", r"call to __host__ function from __(?:global|device)__ function"))
    check("launch-ast", [*host, "-fsyntax-only", "-Xclang", "-ast-dump",
                         str(inputs / "launch-ast.hip")],
          required=(r"CUDAKernelCallExpr", r"__hipPushCallConfiguration"),
          stdout_file="launch.ast.txt")
    _, ir_ok = check("device-ir", [*device, "-emit-llvm", "-O0", "-o", "-", attributes],
                     required=(r'target triple = "riscv64-', r"store i32 42", r"define.*store42"),
                     stdout_file="device.ll")
    if ir_ok:
        ir = (output / "device.ll").read_text()
        report["observed_ir_attributes"] = [
            line for line in ir.splitlines() if line.startswith("attributes #")
        ]
    report["passed"] = all(row["passed"] for row in report["checks"])
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"Evidence: {output}")
    print("Scope: front-end observations; no Vortex device execution.")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
