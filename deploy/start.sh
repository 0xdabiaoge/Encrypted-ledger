#!/usr/bin/env bash
# ==============================================================================
# Encrypted Ledger - VPS One-Click Startup Script
# ==============================================================================
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "🚀 [Encrypted Ledger] Starting up institutional trading workstation..."

# 1. Check Python
if command -v python3.11 &> /dev/null; then
    PY_BIN=python3.11
elif command -v python3 &> /dev/null; then
    PY_BIN=python3
else
    echo "❌ Python 3.10+ required. Please install python3 or python3.11."
    exit 1
fi

# 2. Check or create .env
if [ ! -f .env ]; then
    if [ -f env.example ]; then
        echo "📝 Creating .env from env.example..."
        cp env.example .env
        chmod 600 .env
    else
        echo "⚠️ Warning: env.example not found, please configure .env manually."
    fi
fi

# 3. Create directories
mkdir -p data logs data/policy_archives

# 4. Check Virtualenv
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtualenv in .venv..."
    $PY_BIN -m venv .venv
    . .venv/bin/activate
    pip install --upgrade pip
    pip install -r backend/requirements.txt
else
    . .venv/bin/activate
fi

# 5. Launch FastAPI Control Plane & Scheduler
echo "✨ Launching Encrypted Ledger on http://0.0.0.0:8080 ..."
export PYTHONPATH="$ROOT_DIR/backend:$PYTHONPATH"
exec python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8080
