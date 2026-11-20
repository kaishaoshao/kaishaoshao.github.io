#!/usr/bin/env python3
"""Check tutorial structure and inputs, without claiming compiler support."""

import ast
from pathlib import Path
import re
import unicodedata
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parent.parent
CHAPTERS = ROOT / "chapters"
FENCED_CODE = re.compile(
    r"^([ ]{0,3})```([^\n]*)\n(.*?)^\1```[ \t]*$", re.M | re.S
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def code_blocks(text):
    return [(language, body) for _, language, body in FENCED_CODE.findall(text)]


def anchors(path):
    text = FENCED_CODE.sub("", path.read_text(encoding="utf-8"))
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


def footer_targets(path):
    footer = path.read_text(encoding="utf-8").strip().splitlines()[-1]
    links = re.findall(r"\]\(([^)]+)\)", footer)
    return [(path.parent / link.split("#", 1)[0]).resolve() for link in links]


def check_book():
    cover = ROOT / "tutorial.md"
    contents = cover.read_text(encoding="utf-8").split("## 全书目录", 1)[1].split("## 序章", 1)[0]
    chapter_links = re.findall(r"^### \[(第 (\d+) 章 [^\]]+)\]\((chapters/[^)]+\.md)\)", contents, re.M)
    require(chapter_links, "no chapter links in the book table of contents")
    chapters = []
    lessons = []
    all_pages = []
    lesson_ids = []
    for position, (title, chapter_no, target) in enumerate(chapter_links, 1):
        require(int(chapter_no) == position, f"chapter number out of order: {title}")
        index = ROOT / target
        index_text = index.read_text(encoding="utf-8")
        require(index_text.startswith(f"# {title}\n"), f"chapter title mismatch: {index}")
        chapter_contents = index_text.split("## 本章目录\n", 1)[1].split("\n## ", 1)[0]
        lesson_links = re.findall(r"^- \[([^\]]+)\]\(([^)]+)\)$", chapter_contents, re.M)
        require(lesson_links, f"no lessons in the chapter table of contents: {index}")
        chapters.append(index)
        all_pages.append(index)
        for label, relative in lesson_links:
            page = (index.parent / relative).resolve()
            require(page.read_text(encoding="utf-8").startswith(f"# {label}\n"),
                    f"lesson title mismatch: {page}")
            lessons.append((page, index))
            all_pages.append(page)
            identifier = re.match(r"(L\d{2}\.\d+) ", label)
            if identifier:
                lesson_ids.append(identifier[1])

    cover_links = [(ROOT / path) for path in re.findall(r"\]\((chapters/[^)]+\.md)\)", contents)]
    require(cover_links == all_pages, "book table of contents out of order")
    require(len(all_pages) == len(set(all_pages)) and set(all_pages) == set(CHAPTERS.rglob("*.md")),
            "all chapter and lesson files must appear once in the book")
    expected_ids = [f"L{stage:02}.{step}"
                    for stage, final_step in enumerate((3, 5, 5, 4, 6, 5), 1)
                    for step in range(0 if stage == 3 else 1, final_step + 1)]
    require(len(lesson_ids) == len(set(lesson_ids)), "duplicate lesson ID")
    require([key for key in lesson_ids if key in expected_ids] == expected_ids,
            "existing lesson IDs must keep their order")

    for position, index in enumerate(chapters):
        following = chapters[position + 1] if position + 1 < len(chapters) else cover
        previous = chapters[position - 1:position] if position else []
        require(footer_targets(index) == [*previous, cover, following],
                f"incorrect chapter navigation: {index}")
    for position, (page, index) in enumerate(lessons):
        previous = lessons[position - 1][0] if position else cover
        following = lessons[position + 1][0] if position + 1 < len(lessons) else cover
        require(footer_targets(page) == [previous, index, following],
                f"incorrect lesson navigation: {page}")
    return chapters, lessons


def main():
    documents = [*sorted(ROOT.glob("*.md")), *sorted(CHAPTERS.rglob("*.md")), ROOT.parent / "README.md"]
    link_count = 0
    for path in documents:
        text = path.read_text(encoding="utf-8")
        require(not re.search(r"^[ ]{0,3}```", FENCED_CODE.sub("", text), re.M),
                f"unbalanced fences: {path}")
        for target in re.findall(r"\]\(([^)]+)\)", FENCED_CODE.sub("", text)):
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            name, _, anchor = unquote(target).partition("#")
            destination = (path.parent / name).resolve() if name else path
            require(destination.exists(), f"missing link: {path.name}: {target}")
            if anchor and destination.suffix == ".md":
                require(anchor in anchors(destination), f"missing anchor: {path.name}: {target}")
            link_count += 1

    tasks = (ROOT / "tasks.md").read_text(encoding="utf-8")
    task_ids = re.findall(r"^### (T\d{2}\.\d+)\s", tasks, re.M)
    expected = [f"T{group:02}.{item}" for group in range(11) for item in range(1, 7)]
    require(task_ids == expected, "task IDs must preserve the ordered 66-entry ledger")
    for path in documents:
        references = set(re.findall(r"\bT\d{2}\.\d+", path.read_text(encoding="utf-8")))
        require(references <= set(expected), f"unknown task reference: {path.name}")

    chapters, lessons = check_book()
    plan = (ROOT / "plan.md").read_text(encoding="utf-8")
    milestones = re.findall(r"^### (L\d{2})：", plan, re.M)
    require(milestones == [f"L{i:02}" for i in range(1, 7)], "expected six ordered milestones in plan")
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

    l01 = chapters[0].parent
    l01_text = "\n".join(path.read_text(encoding="utf-8") for path in sorted(l01.glob("*.md")))
    displayed = [body for language, body in code_blocks(l01_text) if language == "cpp"]
    fixture = (ROOT / "examples/l01/attributes.hip").read_text(encoding="utf-8").strip()
    require(displayed and displayed[0].strip() == fixture, "attributes.hip and displayed source differ")
    for language, command in code_blocks(l01_text):
        if language == "bash" and "-target-abi lp64d" in command:
            require("-target-feature +d" in command, "lp64d observation must enable D")
    require("-march=rv64imafd" not in l01_text, "standard baseline must not silently enable A")

    fixtures = {path.name for path in (ROOT / "examples/l01").glob("*.hip")}
    require(fixtures == {"attributes.hip", "illegal-host-call.hip", "illegal-device-call.hip",
                         "launch-ast.hip"}, "unexpected L01 fixture set")
    for path in (ROOT / "examples").glob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    print(f"PASS: {len(documents)} documents, {link_count} local links/anchors")
    print(f"PASS: {len(chapters)} chapters, {len(lessons)} lessons, ordered reading navigation")
    print("PASS: 66 engineering IDs and acyclic capability dependencies")
    print("PASS: tutorial source/fixtures, D/ABI observation options, Python syntax")
    print("Scope: static document/input checks; no compiler build or GPU execution.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, IndexError) as error:
        raise SystemExit(f"FAIL: {error}")
