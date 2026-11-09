#!/usr/bin/env python3
import os
import sys
import urllib.request
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from core.config import config

MODEL_URL = "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf"
TARGET_DIR = Path(config.models_dir)
TARGET_FILE = TARGET_DIR / config.llm_model_file

def download_progress(block_num, block_size, total_size):
    downloaded = block_num * block_size
    if total_size > 0:
        percent = min(100, int((downloaded / total_size) * 100))
        mb_down = downloaded / (1024 * 1024)
        mb_total = total_size / (1024 * 1024)
        sys.stdout.write(f"\r[*] Downloading Qwen 2.5 3B GGUF: {percent}% [{mb_down:.1f} MB / {mb_total:.1f} MB]")
        sys.stdout.flush()

def main():
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    if TARGET_FILE.exists() and TARGET_FILE.stat().st_size > 1_000_000_000:
        print(f"[OK] Model already exists at: {TARGET_FILE}")
        return

    print("========================================================")
    print("  AutoAnime Shorts - 1-Click GGUF Model Downloader")
    print("========================================================")
    print(f"Target: {TARGET_FILE}")
    print(f"URL:    {MODEL_URL}\n")

    try:
        urllib.request.urlretrieve(MODEL_URL, str(TARGET_FILE), reporthook=download_progress)
        print(f"\n\n[SUCCESS] Model downloaded successfully to {TARGET_FILE}!")
        print("When you start the Studio, it will automatically use this local GGUF model.")
    except Exception as e:
        print(f"\n[ERROR] Download failed: {e}")
        if TARGET_FILE.exists():
            TARGET_FILE.unlink()
        sys.exit(1)

if __name__ == "__main__":
    main()
