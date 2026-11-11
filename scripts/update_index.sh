#!/usr/bin/env bash
# scripts/update_index.sh – 自动同步 content/index.md 首页归档目录与内容介绍
# 用法: ./scripts/update_index.sh
# 仅展示各板块下的目录及其内容简介，不直接罗列单个文档。

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

# 各目录内容介绍（若目录下存在 index.md 且配置了 description，则优先使用其 frontmatter description）
DIR_DESCRIPTIONS = {
    "notes/Arch": "计算机体系结构核心脉络整理，涵盖 ISA、流水线、分支预测、乱序执行、Cache 与虚拟内存等常见名词",
    "notes/LLM": "大语言模型底层原理与工程实现笔记，包含 Zero to Hero 从零搭建训练体系记录",
    "notes/LLVM": "LLVM 编译器后端架构与代码生成（Code Generation）方向学习笔记",
    "notes/MLIR": "MLIR 多级中间表示学习记录，涵盖 TableGen 数据定义语言基础与工具链实践",
    "notes/Opt": "程序性能优化方法论与实战分析，包含多级性能瓶颈定位及矩阵乘法调优笔记",
    "notes/RISCV": "RISC-V 体系结构与 RVV 向量指令集扩展（SISD/SIMD）基础概念与编程入门",
    "tutorials": "博客搭建与写作入门教程，涵盖 Quartz v5 站点配置及 Hexo 迁移使用指南",
    "skills": "编译器与底层开发工作工具链导航，收录 LLVM、MLIR、GCC 与 RISC-V/ARM 交叉编译资源",
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
    stripped_body = re.sub(r"[#\s`>*_-]+", "", body)
    is_stub = len(stripped_body) < 40
    return {
        "title": fm_title or h1_title or fallback_title,
        "description": fm_desc,
        "is_draft": is_draft,
        "is_stub": is_stub,
    }


def collect_dir_info(dir_path: str, key: str):
    index_md = os.path.join(dir_path, "index.md")
    custom_desc = None
    if os.path.isfile(index_md):
        custom_desc = parse_markdown_meta(index_md)["description"]

    published_titles = []
    stub_count = 0
    for root, _, filenames in os.walk(dir_path):
        for fn in sorted(filenames):
            if not fn.endswith(".md") or fn == "index.md":
                continue
            meta = parse_markdown_meta(os.path.join(root, fn))
            if meta["is_draft"]:
                continue
            if meta["is_stub"]:
                stub_count += 1
            else:
                published_titles.append(meta["title"])

    total_published = len(published_titles) + stub_count
    if total_published == 0:
        return None

    desc = custom_desc or DIR_DESCRIPTIONS.get(key)
    if not desc:
        if published_titles:
            preview = "、".join(published_titles[:3])
            suffix = " 等内容" if len(published_titles) > 3 else ""
            desc = f"收录 {preview}{suffix}"
        else:
            desc = "专题笔记与资料整理中"

    if len(published_titles) == 0 and stub_count > 0:
        count_note = f"（整理中，{stub_count} 篇占位）"
    else:
        count_note = f"（共 {total_published} 篇）"

    return f"{desc}{count_note}"


lines = [header, ""]

for sec in sections:
    sec_dir = os.path.join(content_dir, sec)
    if not os.path.isdir(sec_dir):
        continue

    subdirs = [
        d
        for d in sorted(os.listdir(sec_dir))
        if not d.startswith(".") and os.path.isdir(os.path.join(sec_dir, d))
    ]

    entries = []
    if subdirs:
        for sub in subdirs:
            sub_path = os.path.join(sec_dir, sub)
            info = collect_dir_info(sub_path, f"{sec}/{sub}")
            if not info:
                continue
            href = f"./{slugify_segment(sec)}/{slugify_segment(sub)}/"
            entries.append(f"- [{sub}/]({href})：{info}")
    else:
        info = collect_dir_info(sec_dir, sec)
        if info:
            href = f"./{slugify_segment(sec)}/"
            entries.append(f"- [{sec.capitalize()}/]({href})：{info}")

    if entries:
        lines.append("")
        lines.append(f"### {sec.capitalize()}")
        lines.append("")
        lines.extend(entries)

with open(index_file, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print(f"✅ 已更新 {index_file}")
PY
