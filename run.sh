#!/usr/bin/env bash
# CounselGrid launcher for macOS and Linux. Creates a private virtual
# environment on first run, then starts the app on http://localhost:8501
# The app binds to this computer only and is not reachable from the network.
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Python 3.10 or newer is required: https://www.python.org/downloads/" >&2
  exit 1
fi

if [ ! -f .venv/.counselgrid-installed ]; then
  echo "Setting up local environment (one time, about a minute)..."
  "$PYTHON" -m venv .venv
  .venv/bin/python -m pip install --quiet --upgrade pip
  .venv/bin/python -m pip install --quiet -r requirements.txt
  touch .venv/.counselgrid-installed
fi

exec .venv/bin/python -m streamlit run app.py \
  --server.address localhost --browser.serverAddress localhost
