#!/usr/bin/env bash
# scripts/update_index.sh – 自动同步 content/index.md 与仓库精选/最近文章列表
# 用法: ./scripts/update_index.sh [每个分类最多展示条数，默认 5；传入 0 表示不限制]
# 在新增、删除或移动 *.md 文件后执行，即可保持首页列表简洁且最新。

set -euo pipefail

# 项目根目录（脚本所在目录的上级）
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECTIONS=("tutorials" "notes" "skills")
INDEX_FILE="${ROOT_DIR}/content/index.md"
MAX_ITEMS="${1:-5}"
MIN_BODY_CHARS="${MIN_BODY_CHARS:-40}"

python3 - "${ROOT_DIR}" "${INDEX_FILE}" "${MAX_ITEMS}" "${MIN_BODY_CHARS}" "${SECTIONS[@]}" <<'PY'
import os
import re
import subprocess
import sys
from datetime import datetime

root_dir = sys.argv[1]
index_file = sys.argv[2]
max_items = int(sys.argv[3])
min_body_chars = int(sys.argv[4])
sections = sys.argv[5:]
content_dir = os.path.join(root_dir, "content")

header = """---
title: kaishaoshao的个人空间 🌱
---
欢迎来到我的个人空间！
这里主要记录我在计算机体系结构、编译器、高性能计算、机器学习底层以及LLM大模型方面的学习笔记与探索。

## 🪴 归档文章"""


def get_git_timestamp(path: str) -> float:
    try:
        out = subprocess.check_output(
            ["git", "-C", root_dir, "log", "-1", "--format=%ct", "--", path],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if out:
            return float(out)
    except Exception:
        pass
    return os.path.getmtime(path)


def parse_date_ts(val: str) -> float | None:
    val = val.strip().strip("'\"")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(val, fmt).timestamp()
        except ValueError:
            pass
    return None


def parse_note(path: str):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    fm_title = None
    fm_date_ts = None
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
            m_date = re.match(r"^\s*date\s*:\s*(.+?)\s*$", line)
            if m_date:
                fm_date_ts = parse_date_ts(m_date.group(1))

    if is_draft:
        return None

    # Skip empty or stub-only placeholder files
    stripped_body = re.sub(r"[#\s`>*_-]+", "", body)
    if len(stripped_body) < min_body_chars:
        return None

    h1_title = None
    if not fm_title:
        for line in body.splitlines():
            m_h1 = re.match(r"^#\s+(.+?)\s*$", line)
            if m_h1:
                h1_title = m_h1.group(1).strip()
                break

    fallback_title = os.path.splitext(os.path.basename(path))[0]
    title = fm_title or h1_title or fallback_title
    ts = fm_date_ts if fm_date_ts is not None else get_git_timestamp(path)
    return title, ts


lines = [header, ""]

for sec in sections:
    sec_dir = os.path.join(content_dir, sec)
    if not os.path.isdir(sec_dir):
        continue

    candidates = []
    for dirpath, _, filenames in os.walk(sec_dir):
        for fn in sorted(filenames):
            if not fn.endswith(".md") or fn == "index.md":
                continue
            fpath = os.path.join(dirpath, fn)
            parsed = parse_note(fpath)
            if parsed is None:
                continue
            title, ts = parsed
            rel_path = os.path.relpath(fpath, content_dir).replace(os.sep, "/")
            subtopic = rel_path.split("/")[1] if rel_path.count("/") >= 2 else ""
            candidates.append((ts, subtopic, rel_path, title))

    # Sort newest first, tie-breaking deterministically by path
    candidates.sort(key=lambda item: (-item[0], item[2]))

    if max_items > 0 and len(candidates) > max_items:
        # First pass: pick one representative (newest) article per subtopic
        picked = []
        seen_topics = set()
        for item in candidates:
            if item[1] not in seen_topics:
                picked.append(item)
                seen_topics.add(item[1])
                if len(picked) == max_items:
                    break
        # Second pass: fill remaining slots with newest overall
        if len(picked) < max_items:
            picked_paths = {item[2] for item in picked}
            for item in candidates:
                if item[2] not in picked_paths:
                    picked.append(item)
                    if len(picked) == max_items:
                        break
        selected = picked
    else:
        selected = candidates

    entries = []
    for _, _, rel_path, title in selected:
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
