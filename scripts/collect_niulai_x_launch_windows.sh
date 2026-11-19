#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="$PROJECT_ROOT/config/niulai_x_launch_queries.json"
COLLECTOR="$PROJECT_ROOT/collector"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
output_dir="$PROJECT_ROOT/data/raw/x/niulai_archive_launch_$stamp"
mkdir -p "$output_dir"

while IFS=$'\t' read -r query_id start_time end_time max_posts query; do
  echo "Collecting $query_id ($start_time to $end_time, cap $max_posts)"
  (
    cd "$COLLECTOR"
    go run . \
      -x-query "$query" \
      -x-query-id "$query_id" \
      -x-start-time "$start_time" \
      -x-end-time "$end_time" \
      -x-limit "$max_posts" \
      -x-page-size 10 \
      -x-endpoint "$(jq -r '.endpoint' "$CONFIG")" \
      -env-file "$PROJECT_ROOT/.env" \
      -out "$output_dir/$query_id.json"
  )
done < <(jq -r '.tracks[] | [.id,.start_time,.end_time,(.max_posts|tostring),.query] | @tsv' "$CONFIG")

echo "Saved to: $output_dir"
