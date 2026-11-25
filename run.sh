#!/usr/bin/env bash
# CounselGrid launcher for macOS and Linux. Creates a private virtual
# environment on first run, then starts the app on http://localhost:8501
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Python 3.10 or newer is required: https://www.python.org/downloads/" >&2
  exit 1
fi

if [ ! -d .venv ]; then
  echo "First run: creating local environment (one time, about a minute)..."
  "$PYTHON" -m venv .venv
  .venv/bin/python -m pip install --quiet --upgrade pip
  .venv/bin/python -m pip install --quiet -r requirements.txt
fi

exec .venv/bin/python -m streamlit run app.py
