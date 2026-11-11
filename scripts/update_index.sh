#!/usr/bin/env bash
# scripts/update_index.sh – 自动同步 content/index.md 首页顶层目录与介绍
# 用法: ./scripts/update_index.sh
# 仅展示顶层板块目录（Notes / Tutorials / Skills）及其内容简介，子目录与文章在进入各目录后展示。

set -euo pipefail

# 项目根目录（脚本所在目录的上级）
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECTIONS=("notes" "tutorials" "skills")
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

# 顶层目录内容介绍（若目录下存在 index.md 且配置了 description，则优先使用其 frontmatter description）
SECTION_DESCRIPTIONS = {
    "notes": "底层技术与系统学习笔记合集，涵盖计算机体系结构（Arch）、LLVM / MLIR 编译器、程序性能优化（Opt）、RISC-V RVV 与 LLM 大模型方向",
    "tutorials": "博客搭建与写作入门教程，涵盖 Quartz v5 站点配置、本地预览及从 Hexo 迁移的完整使用指南",
    "skills": "编译器与底层开发工作工具链导航，收录 LLVM、MLIR、GCC 与 RISC-V / ARM 交叉编译实用资源",
}


def slugify_segment(seg: str) -> str:
    return seg.strip().lower().replace(" ", "-")


def parse_markdown_meta(path: str):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    fm_title = None
    fm_desc = None
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
            m_desc = re.match(r"^\s*description\s*:\s*(.+?)\s*$", line)
            if m_desc:
                val = m_desc.group(1).strip()
                if (val.startswith('"') and val.endswith('"')) or (
                    val.startswith("'") and val.endswith("'")
                ):
                    val = val[1:-1].strip()
                if val:
                    fm_desc = val

    h1_title = None
    if not fm_title:
        for line in body.splitlines():
            m_h1 = re.match(r"^#\s+(.+?)\s*$", line)
            if m_h1:
                h1_title = m_h1.group(1).strip()
                break

    fallback_title = os.path.splitext(os.path.basename(path))[0]
    return {
        "title": fm_title or h1_title or fallback_title,
        "description": fm_desc,
        "is_draft": is_draft,
    }


def collect_section_info(sec_path: str, sec_name: str):
    index_md = os.path.join(sec_path, "index.md")
    custom_desc = None
    if os.path.isfile(index_md):
        custom_desc = parse_markdown_meta(index_md)["description"]

    subdirs = [
        d
        for d in sorted(os.listdir(sec_path))
        if not d.startswith(".") and os.path.isdir(os.path.join(sec_path, d))
    ]

    published_titles = []
    for root, _, filenames in os.walk(sec_path):
        for fn in sorted(filenames):
            if not fn.endswith(".md") or fn == "index.md":
                continue
            meta = parse_markdown_meta(os.path.join(root, fn))
            if not meta["is_draft"]:
                published_titles.append(meta["title"])

    total_files = len(published_titles)
    if total_files == 0 and not subdirs:
        return None

    desc = custom_desc or SECTION_DESCRIPTIONS.get(sec_name)
    if not desc:
        if subdirs:
            desc = f"包含 {'、'.join(subdirs)} 等子目录专题内容"
        else:
            desc = f"收录 {'、'.join(published_titles[:3])} 等内容"

    if subdirs:
        count_note = f"（{len(subdirs)} 个子目录 · 共 {total_files} 篇）"
    else:
        count_note = f"（共 {total_files} 篇）"

    return f"{desc}{count_note}"


entries = []
for sec in sections:
    sec_dir = os.path.join(content_dir, sec)
    if not os.path.isdir(sec_dir):
        continue
    info = collect_section_info(sec_dir, sec)
    if not info:
        continue
    href = f"./{slugify_segment(sec)}/"
    entries.append(f"- [{sec.capitalize()}/]({href})：{info}")

lines = [header, ""]
lines.extend(entries)

with open(index_file, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print(f"✅ 已更新 {index_file}")
PY
