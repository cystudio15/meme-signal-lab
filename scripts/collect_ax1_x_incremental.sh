#!/bin/zsh

set -euo pipefail

PROJECT_ROOT=${0:A:h:h}
CONFIG="$PROJECT_ROOT/config/ax1_x_incremental_queries.json"
GO_BIN=${GO_BIN:-go}
POSTS="$PROJECT_ROOT/data/processed/ax1_x_posts.csv"
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
if [[ ! -s "$POSTS" ]]; then
  echo "Missing processed AX1 posts: $POSTS" >&2
  exit 1
fi

configured_cap=$(jq '[.queries[].max_posts] | add' "$CONFIG")
hard_cap=$(jq '.post_read_hard_cap' "$CONFIG")
if (( configured_cap > hard_cap )); then
  echo "Configured post cap $configured_cap exceeds hard cap $hard_cap" >&2
  exit 1
fi

start_time=$(
  "$PROJECT_ROOT/.venv/bin/python" -c \
    "import pandas as pd; d=pd.read_csv('$POSTS'); t=pd.to_datetime(d['created_at_utc'],utc=True,format='mixed').max()-pd.Timedelta(minutes=5); print(t.strftime('%Y-%m-%dT%H:%M:%SZ'))"
)
stamp=$(date -u +%Y%m%dT%H%M%SZ)
output_dir="$PROJECT_ROOT/data/raw/x/ax1_$stamp"
mkdir -p "$GOCACHE" "$GOPATH" "$output_dir"

echo "AX1 incremental X collection"
echo "Start time: $start_time"
echo "Hard cap: $configured_cap post reads"
echo "Maximum incremental post reads: $hard_cap"

cd "$PROJECT_ROOT/collector"
while IFS=$'\t' read -r query_id max_posts query; do
  output="$output_dir/${query_id}.json"
  echo "Collecting $query_id (cap: $max_posts)"
  "$GO_BIN" run . \
    -x-query-id "$query_id" \
    -x-query "$query" \
    -x-start-time "$start_time" \
    -x-limit "$max_posts" \
    -x-page-size 100 \
    -env-file "$PROJECT_ROOT/.env" \
    -out "$output"
done < <(jq -r '.queries[] | [.query_id, (.max_posts | tostring), .query] | @tsv' "$CONFIG")

echo "AX1 incremental raw X collection saved to: $output_dir"
