#!/usr/bin/env bash
set -euo pipefail
python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -r requirements.txt
python web_app.py
