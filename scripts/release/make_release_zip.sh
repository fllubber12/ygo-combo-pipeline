#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
dist_dir="$repo_root/dist"
tmp_dir="$dist_dir/release_tmp"

include_reports=false
include_cache=false

for arg in "$@"; do
  case "$arg" in
    --include-reports)
      include_reports=true
      ;;
    --include-cache)
      include_cache=true
      ;;
    *)
      echo "Unknown flag: $arg" >&2
      exit 1
      ;;
  esac
done

mkdir -p "$dist_dir"
rm -rf "$tmp_dir"
mkdir -p "$tmp_dir"

rsync -a "$repo_root/" "$tmp_dir/" \
  --exclude ".git/" \
  --exclude ".venv/" \
  --exclude "__pycache__/" \
  --exclude "*.pyc" \
  --exclude ".DS_Store" \
  --exclude "dist/" \
  --exclude "Testing.zip" \
  --exclude "updates_*.zip" \
  --exclude "spot_check_report.md" \
  --exclude "tag_review_report.md" \
  --exclude "Fiendsmith_Master_Card_Library_CLEAN.xlsx" \
  --exclude "Fiendsmith_Master_Card_Library_CLEAN.json"

if ! $include_reports; then
  rm -rf "$tmp_dir/reports"
fi

if ! $include_cache; then
  rm -rf "$tmp_dir/data_cache"
fi

stamp=$(date +%Y%m%d_%H%M%S)
zip_path="$dist_dir/ygo_pipeline_release_${stamp}.zip"

(
  cd "$tmp_dir"
  zip -r "$zip_path" .
)

rm -rf "$tmp_dir"

echo "Release zip created: $zip_path"
