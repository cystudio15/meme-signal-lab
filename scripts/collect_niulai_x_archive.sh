#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="$PROJECT_ROOT/config/niulai_x_archive_queries.json"
COLLECTOR="$PROJECT_ROOT/collector"
ENV_FILE="$PROJECT_ROOT/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE" >&2
  exit 1
fi

planned=$(jq '[.tracks[].max_posts] | add' "$CONFIG")
probe=$(jq '.probe_reads_already_spent' "$CONFIG")
track_count=$(jq '.tracks | length' "$CONFIG")
if (( planned + probe + track_count * 9 > 600 )); then
  echo "Archive plan exceeds the 600-read hard cap" >&2
  exit 1
fi

stamp=$(date -u +%Y%m%dT%H%M%SZ)
output_dir="$PROJECT_ROOT/data/raw/x/niulai_archive_$stamp"
mkdir -p "$output_dir"
endpoint=$(jq -r '.endpoint' "$CONFIG")

echo "NIULAI archive collection: $planned planned reads + $probe probe reads"
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
      -x-page-size 100 \
      -x-endpoint "$endpoint" \
      -env-file "$ENV_FILE" \
      -out "$output_dir/$query_id.json"
  )
done < <(jq -r '.tracks[] | [.id, .start_time, .end_time, (.max_posts|tostring), .query] | @tsv' "$CONFIG")

echo "Saved to: $output_dir"
