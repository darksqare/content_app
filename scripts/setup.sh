#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

echo "========================================================"
echo "  AutoAnime Shorts - 1-Click Setup (Linux/macOS)"
echo "========================================================"
echo

if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 not found. Please install Python 3.10+."
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "[*] Creating virtual environment in ./venv ..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "[*] Upgrading pip..."
pip install --upgrade pip

echo "[*] Installing PyTorch..."
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121 || pip install torch torchvision

echo "[*] Installing dependencies..."
pip install -r requirements.txt

if command -v ffmpeg &> /dev/null; then
    echo "[OK] FFmpeg found: $(which ffmpeg)"
else
    echo "[NOTICE] FFmpeg not found. Please install via: sudo apt install ffmpeg"
fi

echo
echo "========================================================"
echo "  Setup complete! Run ./scripts/start.sh to launch."
echo "========================================================"
