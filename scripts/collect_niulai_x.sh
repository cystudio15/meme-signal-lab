#!/bin/zsh
set -euo pipefail

PROJECT_ROOT=${0:A:h:h}
CONFIG="$PROJECT_ROOT/config/niulai_x_queries.json"
GO_BIN=${GO_BIN:-go}
export GOCACHE="$PROJECT_ROOT/.cache/go-build"
export GOPATH="$PROJECT_ROOT/.cache/go"

command -v "$GO_BIN" >/dev/null 2>&1 || { echo "Go executable not found: $GO_BIN" >&2; exit 1; }
[[ -s "$PROJECT_ROOT/.env" ]] || { echo "Missing local .env with X_BEARER_TOKEN" >&2; exit 1; }

configured_cap=$(jq '[.queries[].max_posts] | add' "$CONFIG")
hard_cap=$(jq '.post_read_hard_cap' "$CONFIG")
(( configured_cap <= hard_cap )) || { echo "Configured cap exceeds hard cap" >&2; exit 1; }

stamp=$(date -u +%Y%m%dT%H%M%SZ)
output_dir="$PROJECT_ROOT/data/raw/x/niulai_$stamp"
mkdir -p "$GOCACHE" "$GOPATH" "$output_dir"
echo "NIULAI X collection: cap $configured_cap posts"

cd "$PROJECT_ROOT/collector"
while IFS=$'\t' read -r query_id max_posts query; do
  echo "Collecting $query_id (cap: $max_posts)"
  "$GO_BIN" run . -x-query-id "$query_id" -x-query "$query" \
    -x-limit "$max_posts" -x-page-size 100 -env-file "$PROJECT_ROOT/.env" \
    -out "$output_dir/${query_id}.json"
done < <(jq -r '.queries[] | [.query_id, (.max_posts | tostring), .query] | @tsv' "$CONFIG")
echo "Saved to: $output_dir"
