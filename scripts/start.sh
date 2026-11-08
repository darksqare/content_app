#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

if [ ! -f "venv/bin/activate" ]; then
    echo "[!] Virtual environment not found. Running ./scripts/setup.sh first..."
    bash "${SCRIPT_DIR}/setup.sh"
fi

source venv/bin/activate

echo "[*] Launching AutoAnime Shorts Studio..."
python3 run.py "$@"
