#!/bin/zsh

set -euo pipefail

PROJECT_ROOT=${0:A:h:h}
export GOCACHE="$PROJECT_ROOT/.cache/go-build"
export GOPATH="$PROJECT_ROOT/.cache/go"
GO_BIN=${GO_BIN:-go}
GIT_BIN=${GIT_BIN:-git}

mkdir -p "$GOCACHE" "$GOPATH"

echo "[1/7] Tool versions"
"$PROJECT_ROOT/.venv/bin/python" --version
command "$GO_BIN" version
command "$GIT_BIN" --version

echo "[2/7] Rebuild source evidence data"
cd "$PROJECT_ROOT"
"$PROJECT_ROOT/.venv/bin/python" scripts/build_social_events.py

echo "[3/7] Rebuild NIULAI event study"
"$PROJECT_ROOT/.venv/bin/python" scripts/build_market_event.py

echo "[4/7] Rebuild on-chain profile and readiness score"
"$PROJECT_ROOT/.venv/bin/python" scripts/build_decision_readiness.py

echo "[5/7] Python tests"
cd "$PROJECT_ROOT"
"$PROJECT_ROOT/.venv/bin/python" -m pytest -q

echo "[6/7] Go tests"
cd "$PROJECT_ROOT/collector"
command "$GO_BIN" test ./...

echo "[7/7] Result"
echo "Python + Go + Git checks passed."
