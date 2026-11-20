"""Check the single plan data source against Markdown, case inventory and optional XLSX."""

import argparse
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

from abi import CAPACITY, FRAME_SIZE
from kernels import MODULE_KERNELS
from suite import STAGES, cases, inventory

HERE = Path(__file__).resolve().parent


def normalized(value):
    return re.sub(r"\s+", " ", str(value).replace("`", "").replace("\\|", "|")).strip()


def markdown_prose(path):
    text = path.read_text(encoding="utf-8")
    if len(re.findall(r"^\s*```", text, re.M)) % 2:
        raise ValueError("unbalanced Markdown fences: " + path.name)
    return re.sub(r"```[\s\S]*?```", "", text)


def check_links(path):
    prose = re.sub(r"`[^`\n]*`", "", markdown_prose(path))
    for target in re.findall(r"\]\(([^)]+)\)", prose):
        if re.match(r"[a-z]+://", target):
            continue
        name, _, anchor = target.partition("#")
        destination = path.parent / name if name else path
        if not destination.exists():
            raise ValueError(f"broken relative link in {path.name}: {target}")
        if anchor and destination.suffix == ".md":
            headings = re.findall(r"^#{1,6} (.+)$", markdown_prose(destination), re.M)
            anchors = {re.sub(r"[^\w\s-]", "", heading.lower()).replace(" ", "-") for heading in headings}
            if anchor not in anchors:
                raise ValueError(f"broken heading link in {path.name}: {target}")


def validate_plan(folder=HERE.parent, *, workbook=False):
    data = json.loads((folder / "plan.json").read_text(encoding="utf-8"))
    md = (folder / "plan.md").read_text(encoding="utf-8")
    lines = {normalized(line) for line in md.splitlines()}

    def row_present(row, candidates=lines):
        rendered = "| " + " | ".join(str(v).replace("|", "\\|").replace("\n", "<br>") for v in row) + " |"
        if normalized(rendered) not in candidates:
            raise ValueError("Markdown/data mismatch: " + str(row[0]))

    tasks = {r[0]: r for r in data["tasks"]}
    if len(tasks) != len(data["tasks"]):
        raise ValueError("duplicate task ID")

    def dependencies(name, active=()):
        if name not in tasks or name in active:
            raise ValueError("unknown dependency or cycle: " + name)
        found = set()
        for dep in tasks[name][4].split(","):
            if dep != "无":
                found.add(dep); found |= dependencies(dep, active + (name,))
        return found

    for name, row in tasks.items():
        dependencies(name); row_present([row[i] for i in (0, 2, 3, 4, 6, 7)])
    if dependencies("S1-06") != {"S0-01", "S0-02", "S0-03", "S1-01", "S1-02", "S1-03", "S1-04", "S1-05"}:
        raise ValueError("G1 dependencies changed")
    for row in data["phases"]:
        row_present(row[:5])
    for row in data["syntax_whitelist"]:
        row_present(row)
    for row in data["standard_test_gates"]:
        row_present(row)
    actual = inventory()
    catalog = {case["id"]: case for case in cases()}
    counts = data["testing"]["generated_counts"]
    if counts != {"kernels": len({name for stage in actual for name in stage["kernels"]}), "cases": len(catalog)}:
        raise ValueError("generated case/kernel counts differ")
    if [row[0] for row in data["standard_test_gates"]] != [stage["stage"] for stage in actual]:
        raise ValueError("standard test gates must cover each stage in order")
    if len(actual) != len(data["syntax_stages"]):
        raise ValueError("stage inventory length differs")
    host_checks = set(re.findall(r"def (test_\w+)\(", (folder / "examples/test_suite.py").read_text(encoding="utf-8")))
    checkpoint_rows = []
    for planned, observed, module in zip(data["syntax_stages"], actual, STAGES):
        if any(planned[key] != observed[key] for key in ("stage", "case_ids", "kernels")):
            raise ValueError("stage inventory differs: " + observed["stage"])
        entry = planned["lesson_entry"]
        identity = entry["case_id"]
        if identity not in observed["case_ids"] or catalog[identity]["error"]:
            raise ValueError("invalid lesson entry: " + identity)
        if entry["action"] not in ("frontend", "prepare", "dot-preview"):
            raise ValueError("unknown lesson action: " + entry["action"])
        module_kernels = MODULE_KERNELS.get(Path(entry["kernel_file"]).stem, ())
        if any(step["kernel"] not in module_kernels for step in catalog[identity]["steps"]):
            raise ValueError("lesson kernel file does not match: " + identity)
        if Path(entry["case_file"]).stem != module.__name__.split(".")[-1]:
            raise ValueError("lesson case file does not match: " + identity)
        for field in ("kernel_file", "case_file"):
            if not (folder / entry[field]).is_file():
                raise ValueError("missing lesson file: " + entry[field])
        flag = {"frontend": "", "prepare": " --emit-only", "dot-preview": " --tutorial-dot-contract"}[entry["action"]]
        if f'--stage {observed["stage"]} --case {identity}{flag} ' not in md:
            raise ValueError("lesson command differs from plan: " + identity)
        stage = observed["stage"]
        lesson, = re.findall(rf"^### {stage} [^\n]+\n(.*?)(?=^### |\Z)", md.split("### 阶段文件")[0], re.M | re.S)
        checkpoints = planned["tutorial_checkpoints"]
        if "**本阶段目标**  " + checkpoints["summary"] not in lesson:
            raise ValueError("lesson summary differs: " + stage)
        lesson_lines = {normalized(line) for line in lesson.splitlines()}
        parents = []
        for substep in checkpoints["steps"]:
            step_id, goal, tests, caution = substep
            if not all(value.strip() for value in (step_id, goal, tests, caution)):
                raise ValueError("incomplete tutorial step: " + step_id)
            parents.append(re.sub(r"[a-z]$", "", step_id))
            row_present(substep, lesson_lines)
            for ref in re.findall(r"`(S[0-9]\.[^`]+)`", tests):
                if ref not in catalog:
                    raise ValueError(f"unknown case in {step_id}: {ref}")
            for ref in re.findall(r"`(test_\w+)`", tests):
                if ref not in host_checks:
                    raise ValueError(f"unknown host test in {step_id}: {ref}")
            checkpoint_rows.append([stage, *(value.replace("`", "") for value in substep)])
        if list(dict.fromkeys(parents)) != [task for task in tasks if task.startswith(stage + "-")]:
            raise ValueError("checkpoints do not match task order: " + stage)
    if len({row[1] for row in checkpoint_rows}) != len(checkpoint_rows):
        raise ValueError("duplicate tutorial checkpoint ID")
    for version in (2, 3):
        abi = data["abi_contract"][str(version)]
        if (abi["bindings"], abi["scalars"]) != CAPACITY[version] or abi["size"] != FRAME_SIZE[version]:
            raise ValueError("ABI codec/document capacity differs")
    for name in ("plan.md", "tutorial.md"):
        check_links(folder / name)
    if workbook:
        ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        with zipfile.ZipFile(folder / "tasks.xlsx") as archive:
            strings = ["".join(x.itertext()) for x in ET.fromstring(archive.read("xl/sharedStrings.xml"))]
            for number, key, columns, start in ((1, "tasks", "ABCDEFGHIJ", 9), (2, "phases", "ABCDEFG", 9),
                                                (3, "dialects", "ABCDEFGH", 9), (4, "contracts", "ABCDE", 9),
                                                (5, "checkpoints", "ABCDE", 6)):
                tree = ET.fromstring(archive.read(f"xl/worksheets/sheet{number}.xml"))
                values = {}
                for cell in tree.findall("s:sheetData/s:row/s:c", ns):
                    value = cell.find("s:v", ns)
                    if value is not None:
                        values[cell.get("r")] = strings[int(value.text)] if cell.get("t") == "s" else value.text
                rows = checkpoint_rows if key == "checkpoints" else data[key]
                for index, row in enumerate(rows, start):
                    if [values.get(f"{col}{index}", "") for col in columns] != [str(v) for v in row]:
                        raise ValueError(f"XLSX/data mismatch: {key} row {index}")
                if key == "dialects":
                    for index, row in enumerate(data["syntax_whitelist"], 24):
                        if [values.get(f"{col}{index}", "") for col in "ABCDE"] != [str(v) for v in row]:
                            raise ValueError("XLSX syntax whitelist differs: " + str(row[0]))
                if key == "phases":
                    for index, stage in enumerate(data["syntax_stages"], 35):
                        row = [stage["stage"], stage["syntax"], stage["dialects"], len(stage["case_ids"]),
                               stage["positive_boundary"], stage["negative"], stage["exercise"], stage["lesson_entry"]["case_id"]]
                        if [values.get(f"{col}{index}", "") for col in "ABCDEFGH"] != [str(v) for v in row]:
                            raise ValueError("XLSX lesson inventory differs: " + stage["stage"])
                    for index, row in enumerate(data["standard_test_gates"], 61):
                        if [values.get(f"{col}{index}", "") for col in "ABDF"] != row:
                            raise ValueError("XLSX standard test gate differs: " + row[0])
                if key == "contracts":
                    for index, row in enumerate(data["abi_contract"]["3"]["fields"], 74):
                        if [values.get(f"{col}{index}", "") for col in "ABCD"] != [str(v) for v in row]:
                            raise ValueError("XLSX ABI layout differs: " + row[0])
    return {"tasks": len(tasks), "cases": len(catalog), "stages": len(actual),
            "checkpoints": len(checkpoint_rows), "consistent": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", action="store_true")
    args = parser.parse_args()
    print(json.dumps(validate_plan(workbook=args.workbook), ensure_ascii=False))
