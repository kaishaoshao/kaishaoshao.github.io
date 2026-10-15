#!/usr/bin/env bash
# scripts/update_index.sh – 自动同步 content/index.md 与仓库中文件列表
# 用法: ./scripts/update_index.sh
# 在新增、删除或移动 *.md 文件后执行，即可保持首页列表最新。

set -euo pipefail

# 项目根目录（脚本所在目录的上级）
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECTIONS=("tutorials" "notes" "skills")

# 固定头部（可自行编辑）
HEADER='---
title: kaishaoshao的个人空间 🌱
---
欢迎来到我的个人空间！
这里主要记录我在计算机体系结构、编译器、高性能计算、机器学习底层以及LLM大模型方面的学习笔记与探索。

## 🪴 归档文章'

# 固定尾部（如有需要可补充）
FOOTER=''

# 生成每个子目录的列表
generate_section() {
  local section=$1
  local dir="${ROOT_DIR}/content/${section}"
  if [[ ! -d "${dir}" ]]; then
    return
  fi
  echo ""
  echo "### ${section^}"
  echo ""
  find "${dir}" -type f -name "*.md" ! -name "index.md" | sort | while read -r file; do
    # 读取 front‑matter 中的 title
    local title
    title=$(grep -m1 '^title:' "${file}" | sed -E 's/^title:[[:space:]]*//')
    [[ -z "${title}" ]] && title=$(basename "${file}" .md)
    # 计算相对路径（相对于 content/）
    local rel_path="${file#${ROOT_DIR}/content/}"
    echo "- [[${title}|${title}]]：${rel_path}"
  done
}

INDEX_FILE="${ROOT_DIR}/content/index.md"

{
  printf "%s\n\n" "${HEADER}"
  for sec in "${SECTIONS[@]}"; do
    generate_section "${sec}"
  done
  if [[ -n "${FOOTER}" ]]; then
    printf "\n%s\n" "${FOOTER}"
  fi
} > "${INDEX_FILE}"

echo "✅ 已更新 ${INDEX_FILE}"
