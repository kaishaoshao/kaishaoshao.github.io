#!/usr/bin/env bash
# new-post.sh - Quickly create a Quartz markdown post with front‑matter
# Usage: ./new-post.sh "Post Title" [optional-date]

set -euo pipefail

# Helper: print usage
usage() {
  echo "Usage: $0 \"Post Title\" [date]"
  echo "  Post Title   - Title for the new article (required)"
  echo "  date         - Publication date (default: today, format YYYY-MM-DD)"
  exit 1
}

# Check arguments
if [[ $# -lt 1 ]]; then
  usage
fi

TITLE="$1"
DATE="${2:-$(date +%Y-%m-%d)}"

# Transform title to a file‑friendly slug (lowercase, spaces→-)
SLUG=$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | sed -E 's/[[:space:]]+/-/g' | sed -E 's/[^a-z0-9\-]//g')

FILE="content/${SLUG}.md"

# Abort if file already exists
if [[ -e "$FILE" ]]; then
  echo "Error: $FILE already exists. Choose a different title or delete the existing file."
  exit 1
fi

# Create the file with front‑matter
cat > "$FILE" <<EOF
---
title: $TITLE
date: $DATE
tags: []
draft: false
---

# $TITLE

Write your article here.
EOF

chmod +x "$FILE"

echo "Created $FILE"

# Optional Git helper – uncomment the following lines if you want the script to commit automatically
# git add "$FILE"
# git commit -m "Add new post: $TITLE"
# echo "Committed $FILE"
