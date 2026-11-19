#!/bin/zsh

set -euo pipefail

PROJECT_ROOT=${0:A:h:h}
cd "$PROJECT_ROOT"
exec "$PROJECT_ROOT/.venv/bin/streamlit" run app.py
