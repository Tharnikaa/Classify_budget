#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=========================================================="
echo " ExpenseIt FastAPI Backend (Phase 0 Stateful Stubs)"
echo " Docs: http://localhost:8000/docs"
echo " Bind: 0.0.0.0:8000 (accessible from Expo Go on same Wi-Fi)"
echo "=========================================================="

if [ -x "./.venv/bin/uvicorn" ]; then
  ./.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
else
  python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
fi

