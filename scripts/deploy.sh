#!/usr/bin/env bash
# ------------------------------------------------------------
# Quartz 自动部署脚本（基于当前分支，直接推送到远程 main）
# 1️⃣ 环境检查
# 2️⃣ 保存构建产物到临时目录
# 3️⃣ 恢复产物到工作区
# 4️⃣ 提交并推送到 remote main
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

# ---------- 3️⃣ 恢复产物 ----------
if [[ -d "$TMP_DIR"/public ]]; then
  echo "🔄 恢复 public 目录到仓库根目录"
  rm -rf public || true
  cp -r "$TMP_DIR"/public .
else
  echo "⚠️ 警告：临时目录中未找到 public，跳过拷贝步骤。"
fi

# ---------- 4️⃣ 提交并推送 ----------
git add .
if git diff --cached --quiet; then
  echo "✅ 没有新的更改需要提交。"
else
  git commit -m "ci: auto‑deploy Quartz build"
  # 配置 GitHub Actions 机器人身份（如在 CI 中运行）
  git config user.name "github-actions[bot]"
  git config user.email "github-actions[bot]@users.noreply.github.com"
  if [[ -n "${GH_TOKEN:-}" ]]; then
    git push "https://${GH_TOKEN}@$(git remote get-url origin | sed -e 's|^https://||')" main
  else
    git push origin main
  fi
  echo "🚀 推送完成。"
fi

# ---------- 5️⃣ 清理 ----------
rm -rf "$TMP_DIR"
echo "🧹 临时目录已删除。"
