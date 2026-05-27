#!/usr/bin/env bash
# ------------------------------------------------------------
# Quartz 自动部署脚本（特性分支 -> main，仅推送生成的 public 内容）
# 1️⃣ 环境检查
# 2️⃣ 构建站点
# 3️⃣ 使用临时 worktree 更新 main，仅保留 public/ 输出
# ------------------------------------------------------------

set -euo pipefail

# ---------- 1️⃣ 环境检查 ----------
if [[ ! -d public ]]; then
  echo "❌ 错误：未找到 'public' 目录，请先运行构建命令 (npx quartz build)。"
  exit 1
fi

# ---------- 2️⃣ 构建站点（若尚未构建） ----------
# 注意：若已在外部运行 npx quartz build，可省略此步骤
# npx quartz build

# ---------- 3️⃣ 使用临时 worktree 更新 main ----------
TMP_WT=$(mktemp -d)
# 添加 main 分支的 worktree 到临时目录
git worktree add "$TMP_WT" main

# 在 worktree 中清空所有非 .git 文件（保留 .git 目录）
shopt -s dotglob
rm -rf "$TMP_WT"/*
shopt -u dotglob

# 将生成的 public 内容复制进去
cp -r public/* "$TMP_WT"/

# 提交更改
cd "$TMP_WT"
git add .
if git diff --cached --quiet; then
  echo "✅ 没有新的生成文件需要提交。"
else
  git commit -m "ci: deploy generated site from $(git rev-parse --short HEAD)"
  # 配置机器人身份（CI 环境）
  git config user.name "github-actions[bot]"
  git config user.email "github-actions[bot]@users.noreply.github.com"
  if [[ -n "${GH_TOKEN:-}" ]]; then
    git push --force-with-lease "https://${GH_TOKEN}@$(git remote get-url origin | sed -e 's|^https://||')" main
  else
    git push --force-with-lease origin main
  fi
  echo "🚀 主分支已更新为生成的站点内容。"
fi

# ---------- 4️⃣ 清理临时 worktree ----------
cd ..
git worktree remove "$TMP_WT" --force
rm -rf "$TMP_WT"

echo "🧹 完成部署并清理临时工作区。"
