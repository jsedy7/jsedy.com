#!/usr/bin/env bash
set -euo pipefail

COMPETITORS_DIR="knowledgebase/projects/howlops/competitors-research"
READ_INDEX_DIR="content/en/read"
SUMMARY_INDEX_DIR="content/en/summary"

sync_section_dirs() {
  local index_dir="$1"
  local default_description="$2"
  local robots_noindex="$3"

  for dir in "$COMPETITORS_DIR"/*/; do
    local name target title
    name=$(basename "$dir")
    target="$index_dir/$name"
    mkdir -p "$target"

    if [ ! -f "$target/_index.md" ]; then
      title=$(echo "$name" | tr '-' ' ' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) substr($i,2)}1')
      cat > "$target/_index.md" <<EOF
---
title: "$title"
description: "$default_description"
robotsNoIndex: $robots_noindex
---
EOF
      echo "Created: $target/_index.md"
    fi
  done

  for index_subdir in "$index_dir"/*/; do
    local name
    name=$(basename "$index_subdir")
    if [ ! -d "$COMPETITORS_DIR/$name" ]; then
      rm -rf "$index_subdir"
      echo "Removed: $index_subdir"
    fi
  done
}

sync_section_dirs "$READ_INDEX_DIR" "" false
sync_section_dirs "$SUMMARY_INDEX_DIR" "Private HowlOps synthesis page" true

python3 scripts/build-read-research-data.py
python3 scripts/build-summary-research-data.py
python3 scripts/sync-summary-indexes.py
