"""Check the single plan data source against Markdown, case inventory and optional XLSX."""

import argparse
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

from abi import CAPACITY, FRAME_SIZE
from suite import cases, inventory

HERE = Path(__file__).resolve().parent


def normalized(value):
    return re.sub(r"\s+", " ", str(value).replace("`", "").replace("\\|", "|")).strip()


def validate_plan(folder=HERE.parent, *, workbook=False):
    data = json.loads((folder / "plan.json").read_text(encoding="utf-8"))
    md = (folder / "plan.md").read_text(encoding="utf-8")
    lines = {normalized(line) for line in md.splitlines()}

    def row_present(row):
        rendered = "| " + " | ".join(str(v).replace("|", "\\|").replace("\n", "<br>") for v in row) + " |"
        if normalized(rendered) not in lines:
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
    actual = inventory()
    if len(actual) != len(data["syntax_stages"]):
        raise ValueError("stage inventory length differs")
    for planned, observed in zip(data["syntax_stages"], actual):
        if any(planned[key] != observed[key] for key in ("stage", "case_ids", "kernels")):
            raise ValueError("stage inventory differs: " + observed["stage"])
    for version in (2, 3):
        abi = data["abi_contract"][str(version)]
        if (abi["bindings"], abi["scalars"]) != CAPACITY[version] or abi["size"] != FRAME_SIZE[version]:
            raise ValueError("ABI codec/document capacity differs")
    prose = re.sub(r"```[\s\S]*?```", "", md)
    prose = re.sub(r"`[^`\n]*`", "", prose)
    for target in re.findall(r"\]\(([^)]+)\)", prose):
        if not re.match(r"[a-z]+://|#", target) and not (folder / target.split("#")[0]).exists():
            raise ValueError("broken relative link: " + target)
    if sum(line.startswith("```") for line in md.splitlines()) % 2:
        raise ValueError("unbalanced Markdown fences")
    if workbook:
        ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        with zipfile.ZipFile(folder / "tasks.xlsx") as archive:
            strings = ["".join(x.itertext()) for x in ET.fromstring(archive.read("xl/sharedStrings.xml"))]
            for number, key, columns, start in ((1, "tasks", "ABCDEFGHIJ", 9), (2, "phases", "ABCDEFG", 9),
                                                (3, "dialects", "ABCDEFGH", 9), (4, "contracts", "ABCDE", 9)):
                tree = ET.fromstring(archive.read(f"xl/worksheets/sheet{number}.xml"))
                values = {}
                for cell in tree.findall("s:sheetData/s:row/s:c", ns):
                    value = cell.find("s:v", ns)
                    if value is not None:
                        values[cell.get("r")] = strings[int(value.text)] if cell.get("t") == "s" else value.text
                for index, row in enumerate(data[key], start):
                    if [values.get(f"{col}{index}", "") for col in columns] != [str(v) for v in row]:
                        raise ValueError("XLSX/data mismatch: " + str(row[0]))
                if key == "dialects":
                    for index, row in enumerate(data["syntax_whitelist"], 24):
                        if [values.get(f"{col}{index}", "") for col in "ABCDE"] != [str(v) for v in row]:
                            raise ValueError("XLSX syntax whitelist differs: " + str(row[0]))
                if key == "phases":
                    for index, stage in enumerate(data["syntax_stages"], 35):
                        row = [stage["stage"], stage["syntax"], stage["dialects"], len(stage["case_ids"]),
                               stage["positive_boundary"], stage["negative"], stage["exercise"]]
                        if [values.get(f"{col}{index}", "") for col in "ABCDEFG"] != [str(v) for v in row]:
                            raise ValueError("XLSX lesson inventory differs: " + stage["stage"])
                if key == "contracts":
                    for index, row in enumerate(data["abi_contract"]["3"]["fields"], 74):
                        if [values.get(f"{col}{index}", "") for col in "ABCD"] != [str(v) for v in row]:
                            raise ValueError("XLSX ABI layout differs: " + row[0])
    return {"tasks": len(tasks), "cases": len(cases()), "stages": len(actual), "consistent": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", action="store_true")
    args = parser.parse_args()
    print(json.dumps(validate_plan(workbook=args.workbook), ensure_ascii=False))
