#!/usr/bin/env python3
"""Check tutorial structure and inputs, without claiming compiler support."""

import ast
from pathlib import Path
import re
import unicodedata
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parent.parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def code_blocks(text):
    return re.findall(r"^```([^\n]*)\n(.*?)^```\s*$", text, re.M | re.S)


def anchors(path):
    text = re.sub(r"^```[^\n]*\n.*?^```\s*$", "", path.read_text(), flags=re.M | re.S)
    result = set(re.findall(r'<a\s+(?:id|name)="([^"]+)"', text))
    counts = {}
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*#*$", text, re.M):
        slug = "".join(
            char for char in heading.lower()
            if char in " _-" or unicodedata.category(char)[0] in "LN"
        ).replace(" ", "-")
        count = counts.get(slug, 0)
        result.add(slug if count == 0 else f"{slug}-{count}")
        counts[slug] = count + 1
    return result


def main():
    documents = [*sorted(ROOT.glob("*.md")), ROOT.parent / "README.md"]
    link_count = 0
    for path in documents:
        text = path.read_text()
        require(len(re.findall(r"^```", text, re.M)) % 2 == 0, f"unbalanced fences: {path}")
        for target in re.findall(r"\]\(([^)]+)\)", text):
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            name, _, anchor = unquote(target).partition("#")
            destination = (path.parent / name).resolve() if name else path
            require(destination.exists(), f"missing link: {path.name}: {target}")
            if anchor and destination.suffix == ".md":
                require(anchor in anchors(destination), f"missing anchor: {path.name}: {target}")
            link_count += 1

    tasks = (ROOT / "tasks.md").read_text()
    task_ids = re.findall(r"^### (T\d{2}\.\d+)\s", tasks, re.M)
    expected = [f"T{group:02}.{item}" for group in range(11) for item in range(1, 7)]
    require(task_ids == expected, "task IDs must preserve the ordered 66-entry ledger")
    for path in documents:
        references = set(re.findall(r"\bT\d{2}\.\d+", path.read_text()))
        require(references <= set(expected), f"unknown task reference: {path.name}")

    plan = (ROOT / "plan.md").read_text()
    lessons = re.findall(r"^### (L\d{2})：", plan, re.M)
    require(lessons == [f"L{i:02}" for i in range(1, 7)], "expected six ordered lessons")
    dependency_text = tasks.split('<a id="task-dependencies"></a>', 1)[1].split("## 源码导航", 1)[0]
    dependencies = {}
    for group, needs in re.findall(r"^\| (T\d{2}) \| ([^|]+) \|", dependency_text, re.M):
        dependencies[group] = set(re.findall(r"\bT\d{2}\b", needs))
    require(set(dependencies) == {f"T{i:02}" for i in range(11)}, "missing dependency row")
    visited = set()

    def visit(node, pending):
        require(node in dependencies, f"unknown dependency: {node}")
        require(node not in pending, f"dependency cycle at {node}")
        if node in visited:
            return
        for parent in dependencies[node]:
            visit(parent, pending | {node})
        visited.add(node)

    for group in dependencies:
        visit(group, set())

    getting_started = (ROOT / "getting-started.md").read_text()
    displayed = [body for language, body in code_blocks(getting_started) if language == "cpp"]
    fixture = (ROOT / "examples/l01/attributes.hip").read_text().strip()
    require(displayed and displayed[0].strip() == fixture, "attributes.hip and displayed source differ")
    for language, command in code_blocks(getting_started):
        if language == "bash" and "-target-abi lp64d" in command:
            require("-target-feature +d" in command, "lp64d observation must enable D")
    require("-march=rv64imafd" not in getting_started, "standard baseline must not silently enable A")

    fixtures = {path.name for path in (ROOT / "examples/l01").glob("*.hip")}
    require(fixtures == {"attributes.hip", "illegal-host-call.hip", "illegal-device-call.hip",
                         "launch-ast.hip"}, "unexpected L01 fixture set")
    for path in (ROOT / "examples").glob("*.py"):
        ast.parse(path.read_text(), filename=str(path))
    print(f"PASS: {len(documents)} documents, {link_count} local links/anchors")
    print("PASS: 66 engineering IDs, six lessons, acyclic capability dependencies")
    print("PASS: tutorial source/fixtures, D/ABI observation options, Python syntax")
    print("Scope: static document/input checks; no compiler build or GPU execution.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, IndexError) as error:
        raise SystemExit(f"FAIL: {error}")
