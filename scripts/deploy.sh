#!/usr/bin/env bash
# ------------------------------------------------------------
# Quartz 自动部署脚本
# 1️⃣ 使用当前分支（需要已完成 `npx quartz build`，生成 public/）
# 2️⃣ 将构建产物临时保存，切换到 main 分支
# 3️⃣ 将产物拷贝回仓库根目录并提交
#
# 适用于：
#   - 本地调试（手动执行）
#   - GitHub Actions（作为单独步骤运行）
#
# 前置条件：
#   - 已在 CI/本地执行 `npm ci && npx quartz build`
#   - 已配置 GitHub 的写权限 token（环境变量 GH_TOKEN）
# ------------------------------------------------------------

set -euo pipefail

# ---------- 1️⃣ 环境检查 ----------
if [[ ! -d public ]]; then
  echo "❌ 错误：未找到 'public' 目录，请先运行构建命令 (npx quartz build)。"
  exit 1
fi

# ---------- 2️⃣ 保存构建产物 ----------
TMP_DIR=$(mktemp -d)
echo "🔹 将构建产物复制到临时目录 $TMP_DIR"
cp -r public "$TMP_DIR"/

# ---------- 3️⃣ 切换到 main ----------
echo "🔄 检出 main 分支"
# 配置 GitHub Actions 机器人身份
git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

git checkout main

# ---------- 4️⃣ 恢复产物 ----------
if [[ -d "$TMP_DIR"/public ]]; then
  echo "🔄 恢复 public 目录到仓库根目录"
  rm -rf public || true
  cp -r "$TMP_DIR"/public .
else
  echo "⚠️ 警告：临时目录中未找到 public，跳过拷贝步骤。"
fi

# ---------- 5️⃣ 提交并推送 ----------
git add .
if git diff --cached --quiet; then
  echo "✅ 没有新的更改需要提交。"
else
  git commit -m "ci: auto‑deploy Quartz build [skip ci]"
  # 使用 token 推送；在 CI 中需要把 token 暴露为环境变量 GH_TOKEN
  if [[ -n "${GH_TOKEN:-}" ]]; then
    git push "https://${GH_TOKEN}@$(git remote get-url origin | sed -e 's|^https://||')" main
  else
    git push origin main
  fi
  echo "🚀 推送完成。"
fi

# ---------- 6️⃣ 清理 ----------
rm -rf "$TMP_DIR"
echo "🧹 临时目录已删除。"
