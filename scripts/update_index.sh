#!/usr/bin/env bash
# scripts/update_index.sh – 自动同步 content/index.md 与仓库中文件列表
# 用法: ./scripts/update_index.sh
# 在新增、删除或移动 *.md 文件后执行，即可保持首页列表最新。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECTIONS=("tutorials" "notes" "skills")
INDEX_FILE="${ROOT_DIR}/content/index.md"

python3 - "${ROOT_DIR}" "${INDEX_FILE}" "${SECTIONS[@]}" <<'PY'
import os
import re
import sys

root_dir = sys.argv[1]
index_file = sys.argv[2]
sections = sys.argv[3:]
content_dir = os.path.join(root_dir, "content")

header = """---
title: kaishaoshao的个人空间 🌱
---
欢迎来到我的个人空间！
这里主要记录我在计算机体系结构、编译器、高性能计算、机器学习底层以及LLM大模型方面的学习笔记与探索。

## 🪴 归档文章"""


def parse_note(path: str):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    fm_title = None
    is_draft = False
    body = text

    fm_match = re.match(r"^---\s*\n([\s\S]*?)\n---\s*(?:\n|$)", text)
    if fm_match:
        fm_block = fm_match.group(1)
        body = text[fm_match.end():]
        for line in fm_block.splitlines():
            m_draft = re.match(r"^\s*draft\s*:\s*(.+?)\s*$", line, re.IGNORECASE)
            if m_draft and m_draft.group(1).strip().strip("'\"").lower() == "true":
                is_draft = True
            m_title = re.match(r"^\s*title\s*:\s*(.+?)\s*$", line)
            if m_title:
                val = m_title.group(1).strip()
                if (val.startswith('"') and val.endswith('"')) or (
                    val.startswith("'") and val.endswith("'")
                ):
                    val = val[1:-1].strip()
                if val:
                    fm_title = val

    if is_draft:
        return None

    h1_title = None
    if not fm_title:
        for line in body.splitlines():
            m_h1 = re.match(r"^#\s+(.+?)\s*$", line)
            if m_h1:
                h1_title = m_h1.group(1).strip()
                break

    fallback_title = os.path.splitext(os.path.basename(path))[0]
    return fm_title or h1_title or fallback_title


lines = [header, ""]

for sec in sections:
    sec_dir = os.path.join(content_dir, sec)
    if not os.path.isdir(sec_dir):
        continue

    md_files = []
    for dirpath, _, filenames in os.walk(sec_dir):
        for fn in filenames:
            if fn.endswith(".md") and fn != "index.md":
                md_files.append(os.path.join(dirpath, fn))
    md_files.sort()

    entries = []
    for fpath in md_files:
        title = parse_note(fpath)
        if title is None:
            continue
        rel_path = os.path.relpath(fpath, content_dir).replace(os.sep, "/")
        target = rel_path[:-3] if rel_path.endswith(".md") else rel_path
        safe_title = title.replace("|", "\\|")
        entries.append(f"- [[{target}|{safe_title}]]：{rel_path}")

    if entries:
        lines.append("")
        lines.append(f"### {sec.capitalize()}")
        lines.append("")
        lines.extend(entries)

with open(index_file, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print(f"✅ 已更新 {index_file}")
PY
