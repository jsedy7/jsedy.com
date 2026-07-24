#!/usr/bin/env bash
set -euo pipefail

COMPETITORS_DIR="knowledgebase/projects/howlops/competitors-research"
INDEX_DIR="content/en/read"

# Create _index.md for any new competitor directory
for dir in "$COMPETITORS_DIR"/*/; do
  name=$(basename "$dir")
  target="$INDEX_DIR/$name"
  mkdir -p "$target"

  if [ ! -f "$target/_index.md" ]; then
    # Title: hyphen-separated slug -> Title Case
    title=$(echo "$name" | tr '-' ' ' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) substr($i,2)}1')
    cat > "$target/_index.md" <<EOF
---
title: "$title"
description: ""
---
EOF
    echo "Created: $target/_index.md"
  fi
done

# Remove _index.md dirs for competitors that no longer exist in submodule
for index_dir in "$INDEX_DIR"/*/; do
  name=$(basename "$index_dir")
  if [ ! -d "$COMPETITORS_DIR/$name" ]; then
    rm -rf "$index_dir"
    echo "Removed: $index_dir"
  fi
done

# Refresh derived research metadata used by Hugo templates
python3 scripts/build-read-research-data.py
