#!/usr/bin/env python3
import sys
import argparse
import subprocess
import shutil
import logging
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

try:
    from web_ui.server import start_server
except ModuleNotFoundError as e:
    missing_mod = getattr(e, 'name', str(e))
    print("\n" + "=" * 60)
    print(f" [ERROR] Missing dependency: '{missing_mod}'")
    print(" It looks like requirements have not been installed yet.")
    print(" To fix this:")
    print("   1. Double-click 'setup.bat' in the project folder (Windows)")
    print("      or run: pip install -r requirements.txt")
    print("   2. Launch using 'start.bat' so the virtual environment is used.")
    print("=" * 60 + "\n")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("Launcher")

def check_system_prerequisites():
    logger.info("Checking system prerequisites...")
    
    # 1. Check FFmpeg
    if not shutil.which("ffmpeg"):
        logger.warning("WARNING: 'ffmpeg' not found in system PATH! Video rendering requires FFmpeg.")
        logger.warning("On Windows: Run 'winget install Gyan.FFmpeg' or download from https://ffmpeg.org")
    else:
        logger.info("✓ FFmpeg detected.")

    # 2. Check PyTorch & CUDA
    try:
        import torch
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            logger.info(f"✓ NVIDIA GPU Detected: {device_name} ({vram_gb:.1f} GB VRAM)")
        else:
            logger.warning("! Running in CPU mode. (CUDA not detected).")
    except ImportError:
        logger.info("! PyTorch not yet installed in current environment.")

def main():
    parser = argparse.ArgumentParser(description="AutoAnime Shorts - Local AI Content Studio")
    parser.add_argument("--host", default=config.host, help=f"Host address (default: {config.host})")
    parser.add_argument("--port", type=int, default=config.port, help=f"Port number (default: {config.port})")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically launch web browser")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    check_system_prerequisites()

    print("\n" + "=" * 65)
    print("  🎬 AutoAnime Shorts - Local AI Web-Novel & Shorts Studio")
    print(f"  URL: http://{args.host}:{args.port}")
    print(f"  Runs strictly on-demand. Close this window to stop.")
    print("=" * 65 + "\n")

    start_server(
        host=args.host,
        port=args.port,
        open_browser=not args.no_browser
    )

if __name__ == "__main__":
    main()
