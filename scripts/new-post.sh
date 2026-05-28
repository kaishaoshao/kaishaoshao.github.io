#!/usr/bin/env bash
# scripts/new_post.sh – Quickly create a Markdown file with a unified Front‑matter.
# Usage: ./scripts/new_post.sh <category> "<title>" [tag1 tag2 ...]
#   <category> – one of the subfolders under content/ (e.g., tutorials, notes, articles)
#   "<title>"   – the page title (quoted if it contains spaces)
#   [tags...]   – optional list of tags (space‑separated)

set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <category> \"<title>\" [tag1 tag2 ...]"
  exit 1
fi

CATEGORY="$1"
TITLE="$2"
shift 2
TAGS=("$@")

# Ensure the target directory exists
TARGET_DIR="content/${CATEGORY}"
mkdir -p "${TARGET_DIR}"

# Create a filename from the title: keep the original characters (including Unicode),
# just strip characters that are unsafe for file names.
# Forbidden characters on most filesystems: / \\ ? * : \" < > | and control characters.
SAFE_TITLE=$(echo "$TITLE" | tr -d '/\\?*:<>|\"')
FILE="${TARGET_DIR}/${SAFE_TITLE}.md"

# Prepare tags line (comma‑separated) if tags were given
if [[ ${#TAGS[@]} -gt 0 ]]; then
  TAGS_JOIN=$(printf "%s, " "${TAGS[@]}")
  TAGS_JOIN=${TAGS_JOIN%, }   # remove trailing comma and space
  TAG_LINE="tags: [${TAGS_JOIN}]"
else
  TAG_LINE="# tags omitted"
fi

# Write the markdown file (variables are expanded)
cat > "${FILE}" <<EOF
---
title: ${TITLE}
date: $(date +%Y-%m-%d)
${TAG_LINE}
---

# ${TITLE}

<!-- Write your content below -->
EOF

chmod +x "${FILE}"

echo "✅ Created ${FILE} with unified Front‑matter"
