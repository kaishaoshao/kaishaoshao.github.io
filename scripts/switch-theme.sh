#!/usr/bin/env bash
# scripts/switch-theme.sh - 方便地一键切换 Quartz 静态构建的默认主题配色
# 用法: ./scripts/switch-theme.sh [blue|green|purple|catppuccin]

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="${ROOT_DIR}/quartz.config.yaml"

THEME="${1:-}"

if [[ -z "${THEME}" ]]; then
  echo "🎨 请指定要切换的主题配色名称："
  echo "  1) blue       - 科技极简蓝 (Tech Slate Blue，高清晰度推荐)"
  echo "  2) green      - 数字花园绿 (Forest Green 🌱，护眼自然风)"
  echo "  3) purple     - 赛博黑曜石紫 (Cyber Violet Pro 🟣，优化版紫色)"
  echo "  4) catppuccin - 猫咪暖色 (Catppuccin Mocha 🐱，经典柔和风)"
  echo ""
  echo "用法示例: $0 blue"
  exit 1
fi

case "${THEME}" in
  blue)
    LIGHT_LIGHT="#f8fafc"
    LIGHT_LIGHTGRAY="#e2e8f0"
    LIGHT_GRAY="#94a3b8"
    LIGHT_DARKGRAY="#334155"
    LIGHT_DARK="#0f172a"
    LIGHT_SECONDARY="#2563eb"
    LIGHT_TERTIARY="#3b82f6"
    LIGHT_HIGHLIGHT="rgba(37, 99, 235, 0.08)"
    LIGHT_TEXT_HIGHLIGHT="#fef08a88"

    DARK_LIGHT="#0f172a"
    DARK_LIGHTGRAY="#1e293b"
    DARK_GRAY="#64748b"
    DARK_DARKGRAY="#cbd5e1"
    DARK_DARK="#f8fafc"
    DARK_SECONDARY="#60a5fa"
    DARK_TERTIARY="#93c5fd"
    DARK_HIGHLIGHT="rgba(96, 165, 250, 0.15)"
    DARK_TEXT_HIGHLIGHT="#eab30844"
    THEME_NAME="科技极简蓝 (Tech Slate Blue)"
    ;;

  green)
    LIGHT_LIGHT="#faf8f5"
    LIGHT_LIGHTGRAY="#e7e5e0"
    LIGHT_GRAY="#a39e93"
    LIGHT_DARKGRAY="#363a37"
    LIGHT_DARK="#1c2420"
    LIGHT_SECONDARY="#2d6a4f"
    LIGHT_TERTIARY="#52b788"
    LIGHT_HIGHLIGHT="rgba(45, 106, 79, 0.1)"
    LIGHT_TEXT_HIGHLIGHT="#ffe06688"

    DARK_LIGHT="#121815"
    DARK_LIGHTGRAY="#222c27"
    DARK_GRAY="#5a6b62"
    DARK_DARKGRAY="#d3ded8"
    DARK_DARK="#f0fdf4"
    DARK_SECONDARY="#52b788"
    DARK_TERTIARY="#74c69d"
    DARK_HIGHLIGHT="rgba(82, 183, 136, 0.15)"
    DARK_TEXT_HIGHLIGHT="#10b98133"
    THEME_NAME="数字花园绿 (Forest Green 🌱)"
    ;;

  purple)
    LIGHT_LIGHT="#faf5ff"
    LIGHT_LIGHTGRAY="#ede9fe"
    LIGHT_GRAY="#a78bfa"
    LIGHT_DARKGRAY="#2e1065"
    LIGHT_DARK="#1e1b4b"
    LIGHT_SECONDARY="#7c3aed"
    LIGHT_TERTIARY="#9333ea"
    LIGHT_HIGHLIGHT="rgba(124, 58, 237, 0.1)"
    LIGHT_TEXT_HIGHLIGHT="#e9d5ff88"

    DARK_LIGHT="#0f0e17"
    DARK_LIGHTGRAY="#232035"
    DARK_GRAY="#6c668a"
    DARK_DARKGRAY="#e4e1f0"
    DARK_DARK="#ffffff"
    DARK_SECONDARY="#a78bfa"
    DARK_TERTIARY="#c4b5fd"
    DARK_HIGHLIGHT="rgba(167, 139, 250, 0.18)"
    DARK_TEXT_HIGHLIGHT="#a855f744"
    THEME_NAME="赛博黑曜石紫 (Cyber Violet Pro 🟣)"
    ;;

  catppuccin)
    LIGHT_LIGHT="#eff1f5"
    LIGHT_LIGHTGRAY="#dce0e8"
    LIGHT_GRAY="#9ca0b0"
    LIGHT_DARKGRAY="#4c4f69"
    LIGHT_DARK="#20202a"
    LIGHT_SECONDARY="#1e66f5"
    LIGHT_TERTIARY="#7287fd"
    LIGHT_HIGHLIGHT="rgba(30, 102, 245, 0.1)"
    LIGHT_TEXT_HIGHLIGHT="#df8e1d44"

    DARK_LIGHT="#1e1e2e"
    DARK_LIGHTGRAY="#313244"
    DARK_GRAY="#6c7086"
    DARK_DARKGRAY="#cdd6f4"
    DARK_DARK="#cdd6f4"
    DARK_SECONDARY="#89b4fa"
    DARK_TERTIARY="#b4befe"
    DARK_HIGHLIGHT="rgba(137, 180, 250, 0.15)"
    DARK_TEXT_HIGHLIGHT="#f9e2af44"
    THEME_NAME="猫咪暖色 (Catppuccin Mocha 🐱)"
    ;;

  *)
    echo "❌ 未知主题: '${THEME}'。支持的值: blue, green, purple, catppuccin"
    exit 1
    ;;
esac

# 替换 quartz.config.yaml 中的颜色配置
python3 - <<EOF
import re

with open("${CONFIG_FILE}", "r", encoding="utf-8") as f:
    content = f.read()

new_colors = """    colors:
      lightMode:
        light: "${LIGHT_LIGHT}"
        lightgray: "${LIGHT_LIGHTGRAY}"
        gray: "${LIGHT_GRAY}"
        darkgray: "${LIGHT_DARKGRAY}"
        dark: "${LIGHT_DARK}"
        secondary: "${LIGHT_SECONDARY}"
        tertiary: "${LIGHT_TERTIARY}"
        highlight: "${LIGHT_HIGHLIGHT}"
        textHighlight: "${LIGHT_TEXT_HIGHLIGHT}"
      darkMode:
        light: "${DARK_LIGHT}"
        lightgray: "${DARK_LIGHTGRAY}"
        gray: "${DARK_GRAY}"
        darkgray: "${DARK_DARKGRAY}"
        dark: "${DARK_DARK}"
        secondary: "${DARK_SECONDARY}"
        tertiary: "${DARK_TERTIARY}"
        highlight: "${DARK_HIGHLIGHT}"
        textHighlight: "${DARK_TEXT_HIGHLIGHT}\""""

content = re.sub(r'    colors:\s+lightMode:[\s\S]+?textHighlight:[^\n]+\n', new_colors + '\n', content)

with open("${CONFIG_FILE}", "w", encoding="utf-8") as f:
    f.write(content)
EOF

echo "✨ 已将默认主题成功切换为: ${THEME_NAME}"
echo "💡 提示: 网页前端也已配备 🎨 实时调色盘切换按钮，支持在浏览器中即时预览全部 4 套配色！"
