#!/bin/zsh

set -euo pipefail

PROJECT_ROOT=${0:A:h:h}
CONFIG="$PROJECT_ROOT/config/ax1_x_queries.json"
GO_BIN=${GO_BIN:-go}
export GOCACHE="$PROJECT_ROOT/.cache/go-build"
export GOPATH="$PROJECT_ROOT/.cache/go"

if ! command -v "$GO_BIN" >/dev/null 2>&1; then
  echo "Go executable not found: $GO_BIN" >&2
  exit 1
fi
if [[ ! -s "$PROJECT_ROOT/.env" ]]; then
  echo "Missing local .env with X_BEARER_TOKEN" >&2
  exit 1
fi

configured_cap=$(jq '[.queries[].max_posts] | add' "$CONFIG")
hard_cap=$(jq '.post_read_hard_cap' "$CONFIG")
if (( configured_cap > hard_cap )); then
  echo "Configured post cap $configured_cap exceeds hard cap $hard_cap" >&2
  exit 1
fi

stamp=$(date -u +%Y%m%dT%H%M%SZ)
output_dir="$PROJECT_ROOT/data/raw/x/ax1_$stamp"
mkdir -p "$GOCACHE" "$GOPATH" "$output_dir"

echo "AX1 X collection"
echo "Configured hard cap: $configured_cap posts"
echo "Maximum post reads: $hard_cap"

cd "$PROJECT_ROOT/collector"
while IFS=$'\t' read -r query_id max_posts query; do
  output="$output_dir/${query_id}.json"
  echo "Collecting $query_id (cap: $max_posts)"
  "$GO_BIN" run . \
    -x-query-id "$query_id" \
    -x-query "$query" \
    -x-limit "$max_posts" \
    -x-page-size 100 \
    -env-file "$PROJECT_ROOT/.env" \
    -out "$output"
done < <(jq -r '.queries[] | [.query_id, (.max_posts | tostring), .query] | @tsv' "$CONFIG")

echo "AX1 raw X collection saved to: $output_dir"
