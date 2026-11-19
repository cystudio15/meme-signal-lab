#!/bin/zsh

set -euo pipefail

PROJECT_ROOT=${0:A:h:h}
export GOCACHE="$PROJECT_ROOT/.cache/go-build"
export GOPATH="$PROJECT_ROOT/.cache/go"
GO_BIN=${GO_BIN:-go}
OUTPUT="$PROJECT_ROOT/data/raw/geckoterminal_bsc_trending_pools.json"

mkdir -p "$GOCACHE" "$GOPATH" "$PROJECT_ROOT/data/raw"
cd "$PROJECT_ROOT/collector"

"$GO_BIN" run . \
  -url "https://api.geckoterminal.com/api/v2/networks/bsc/trending_pools?page=1" \
  -out "$OUTPUT"

echo "Validated raw JSON record saved to: $OUTPUT"
