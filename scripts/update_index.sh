#!/usr/bin/env bash
# scripts/update_index.sh – 自动同步 content/index.md 与仓库中文件列表
# 用法: ./scripts/update_index.sh
# 在新增、删除或移动 *.md 文件后执行，即可保持首页列表最新。

set -euo pipefail

# 项目根目录（脚本所在目录的上级）
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECTIONS=("tutorials" "notes" "articles")

# 固定头部（可自行编辑）
HEADER='---
title: kaishaoshao 的数字花园 🌱
---
欢迎来到我的个人数字花园！这里主要记录我在计算机体系结构、编译器、高性能计算（HPC）以及机器学习底层的学习笔记与探索。

## 🪴 归档文章'

# 固定尾部
FOOTER='## 📚 文档目录

- [Quartz 教学文档](/docs/)'

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
  find "${dir}" -maxdepth 1 -type f -name "*.md" ! -name "index.md" | sort | while read -r file; do
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
  printf "\n%s\n" "${FOOTER}"
} > "${INDEX_FILE}"

echo "✅ 已更新 ${INDEX_FILE}"
