#!/bin/zsh

set -euo pipefail

PROJECT_ROOT=${0:A:h:h}
export GOCACHE="$PROJECT_ROOT/.cache/go-build"
export GOPATH="$PROJECT_ROOT/.cache/go"
GO_BIN=${GO_BIN:-go}
OUTPUT="$PROJECT_ROOT/data/raw/dexscreener_boosts.json"

mkdir -p "$GOCACHE" "$GOPATH" "$PROJECT_ROOT/data/raw"
cd "$PROJECT_ROOT/collector"

"$GO_BIN" run . \
  -url "https://api.dexscreener.com/token-boosts/latest/v1" \
  -out "$OUTPUT"

echo "Raw record saved to: $OUTPUT"
