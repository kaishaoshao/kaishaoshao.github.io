"""Host-only tests for references and evidence validation, never Coral execution proof."""

import ast
import copy
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

from run_stage import artifact, check_elf, check_trace, check_values, digest, request_for, verify_response
from suite import cases, inventory, vector

HERE = Path(__file__).resolve().parent


class TutorialContractTests(unittest.TestCase):
    def test_sources_and_stage_coverage(self):
        items = cases()
        self.assertEqual(len({c["id"] for c in items}), len(items))
        self.assertEqual({c["stage"] for c in items}, {f"S{i}" for i in range(10)})
        names = {n.name for n in ast.parse((HERE / "kernels.py").read_text()).body if isinstance(n, ast.FunctionDef)}
        self.assertEqual({s["kernel"] for c in items for s in c["steps"]}, names)
        plan = json.loads((HERE.parent / "plan.json").read_text(encoding="utf-8"))
        if "syntax_stages" in plan:
            for row, actual in zip(plan["syntax_stages"], inventory()):
                self.assertEqual(row["stage"], actual["stage"])
                self.assertEqual(row["case_ids"], actual["case_ids"])
        for case in items:
            for item in case["steps"]:
                for name, expected in item["expected"].items():
                    self.assertEqual(len(expected), len(item["buffers"][name]["values"]))

    def test_reference_boundaries_and_padding(self):
        by_id = {c["id"]: c for c in cases()}
        self.assertEqual(by_id["S1.wrap"]["steps"][0]["expected"]["Y"], [-2147483648])
        self.assertEqual(by_id["S2.mask.n0.b16"]["steps"][0]["expected"]["Y"], [])
        self.assertEqual(by_id["S2.other"]["steps"][0]["expected"]["Y"], [3, 4, 5] + [7] * 13)
        padded = by_id["S4.stride-broadcast"]["steps"][0]["expected"]["Y"]
        self.assertEqual(padded[:9], [0, 1, 2, 3, 4, 5, 6, 1515870810, 1515870810])
        self.assertEqual(by_id["S4.loop.r0"]["steps"][0]["expected"]["Y"], [0] * 5)
        self.assertEqual(by_id["S4.while.1"]["steps"][0]["expected"]["Y"], [15])

    def test_requests_do_not_disclose_reference_outputs(self):
        case = cases()[1]
        first = request_for(case, "first")
        second = request_for(case, "second")
        self.assertNotIn("expected", first["steps"][0])
        self.assertEqual(first["steps"][0]["output_bindings"], ["Y"])
        self.assertNotEqual(first["request_sha256"], second["request_sha256"])
        self.assertIn("expected", case["steps"][0])

    def test_values_reject_wrong_shape_bool_and_nonfinite(self):
        for wrong in ([1], [1, 9], [True, 2]):
            with self.assertRaises(ValueError): check_values({"Y": wrong}, {"Y": [1, 2]})
        with self.assertRaises(ValueError): check_values({"Y": [float("nan")]}, {"Y": [0.0]})
        check_values({"Y": [0.5000001]}, {"Y": [0.5]}, {"rtol": 1e-5, "atol": 1e-6})

    def test_elf_rejects_placeholder_truncation_and_bad_entry(self):
        good = bytearray(88)
        good[:7] = b"\x7fELF\x01\x01\x01"
        struct.pack_into("<HHIIIIIHHHHHH", good, 16, 2, 243, 1, 0x1000, 52, 0, 0, 52, 32, 1, 0, 0, 0)
        struct.pack_into("<IIIIIIII", good, 52, 1, 84, 0x1000, 0x1000, 4, 4, 5, 1)
        check_elf(good)
        for wrong in (b"/* Coral Binary */", good[:60], good[:84]):
            with self.assertRaises(ValueError): check_elf(wrong)
        struct.pack_into("<I", good, 24, 0x2000)
        with self.assertRaises(ValueError): check_elf(good)

    def test_artifact_hash_and_directory_are_checked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / "ok").write_bytes(b"real data")
            records = {"data": {"path": "ok", "sha256": digest(b"real data")}}
            self.assertEqual(artifact(records, "data", root), b"real data")
            records["data"]["sha256"] = "wrong"
            with self.assertRaises(ValueError): artifact(records, "data", root)
            records["data"]["path"] = "../outside"
            with self.assertRaises(ValueError): artifact(records, "data", root)

    def test_grid_tail_and_same_core_exclusion(self):
        item = vector(3, 16); case = {"core_mask": 1, "features": []}
        trace = {"events": [{"kind": "guard_check", "ok": True},
                            {"kind": "launch", "program": [0, 0, 0], "core": 0, "start": 2, "end": 10},
                            {"kind": "access", "binding": "Y", "index": 0, "count": 3}]}
        check_trace(trace, item, case)
        bad = copy.deepcopy(trace); bad["events"].append(copy.deepcopy(bad["events"][1]))
        with self.assertRaises(ValueError): check_trace(bad, item, case)
        bad = copy.deepcopy(trace); bad["events"][1]["core"] = 3
        with self.assertRaises(ValueError): check_trace(bad, item, case)
        bad = copy.deepcopy(trace); bad["events"][2]["count"] = 16
        with self.assertRaises(ValueError): check_trace(bad, item, case)
        bad = copy.deepcopy(trace); bad["events"].extend([
            {"kind": "dma", "source": "dram", "destination": "dtcm", "core": 0,
             "start": 1, "end": 5, "bytes": 4, "success": True},
            {"kind": "dma", "source": "dtcm", "destination": "dram", "core": 0,
             "start": 11, "end": 12, "bytes": 4, "success": True}])
        with self.assertRaises(ValueError): check_trace(bad, item, {"core_mask": 1, "features": ["dma"]})

    def test_rejects_old_response_and_empty_success(self):
        case = cases()[1]; request = request_for(case)
        for response in ({}, {"protocol": 1, "nonce": "old", "status": "ok"},
                         {"protocol": 1, "nonce": request["nonce"], "request_sha256": request["request_sha256"],
                          "status": "ok", "results": []}):
            with tempfile.TemporaryDirectory() as temp:
                with self.assertRaises(ValueError): verify_response(case, request, response, Path(temp))

    def test_missing_adapter_does_not_skip_or_pass(self):
        process = subprocess.run([sys.executable, str(HERE / "run_stage.py"), "--stage", "S1"],
                                 capture_output=True, text=True, check=False)
        self.assertEqual(process.returncode, 2)
        self.assertNotIn("PASS", process.stdout)

    def test_emit_only_has_no_execution_success(self):
        with tempfile.TemporaryDirectory() as temp:
            process = subprocess.run([sys.executable, str(HERE / "run_stage.py"), "--stage", "S1",
                                      "--emit-only", "--output", temp], capture_output=True, text=True, check=False)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn("PREPARED", process.stdout)
            self.assertNotIn("PASS", process.stdout)
            summaries = list(Path(temp).glob("*/summary.json"))
            self.assertEqual(len(summaries), 1)
            rows = json.loads(summaries[0].read_text())
            self.assertEqual({row["status"] for row in rows}, {"prepared"})

    def test_frontend_report_is_not_an_execution_report(self):
        # Synthetic files below test only validator behavior, never source reachability or hardware.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            def record(name, content):
                raw = content.encode(); (root / name).write_bytes(raw)
                return {"path": name, "sha256": digest(raw)}

            case = copy.deepcopy(cases()[0]); request = request_for(case)
            build = {k: "unit-fixture" for k in ("triton_commit", "llvm_commit", "coral_commit", "abi", "target")}
            build.update(kernel_source_sha256=request["kernel_source_sha256"], pipeline="current-mainline")
            response = {"protocol": 1, "nonce": request["nonce"], "request_sha256": request["request_sha256"],
                        "status": "ok", "artifacts": {"build": record("build.json", json.dumps(build))},
                        "results": [{"artifacts": {"ttir": record("sample.ttir", "tt.func @unit { tt.load }"),
                                                   "verification": record("verify.json", '{"ttir":true}')}}]}
            verify_response(case, request, response, root)
            case["mode"] = "aot"
            with self.assertRaisesRegex(ValueError, "not Coral execution"):
                verify_response(case, request, response, root)
            case["mode"] = "frontend"; build["pipeline"] = "old-reference"
            response["artifacts"]["build"] = record("build.json", json.dumps(build))
            with self.assertRaisesRegex(ValueError, "current mainline"):
                verify_response(case, request, response, root)


if __name__ == "__main__":
    unittest.main()
