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
    from core.config import config
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

def check_system_prerequisites(debug_mode: bool = False):
    import platform
    logger.info("=" * 65)
    logger.info("🎬 AutoAnime Shorts - Subsystems Diagnostics")
    logger.info("=" * 65)
    
    # 1. System & Paths
    logger.info(f"System: OS={platform.system()} {platform.release()} ({platform.machine()}) | Python={platform.python_version()}")
    logger.info(f"Root Directory: {ROOT_DIR}")
    logger.info(f"Output Directory: {config.output_dir}")
    logger.info(f"Story Vault DB: {config.vault_db_path}")

    # 2. Hardware & CUDA
    try:
        import torch
        if torch.cuda.is_available():
            dev_name = torch.cuda.get_device_name(0)
            vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            logger.info(f"Hardware: NVIDIA GPU={dev_name} | VRAM={vram_gb:.1f} GB | PyTorch={torch.__version__} | CUDA={torch.version.cuda}")
        else:
            logger.warning("Hardware: Running on CPU (CUDA not active)")
    except ImportError:
        logger.warning("Hardware: PyTorch not installed in this environment.")
    except Exception as e:
        logger.warning(f"Hardware notice: {e}")

    # 3. Audio & Voice Engine
    try:
        from core.tts import TTSEngine
        tts = TTSEngine()
        logger.info(f"Audio Engine: Backend={config.tts_backend.upper()} | Default Narrator={config.tts_voice} (Male Cinematic) | Speed={config.tts_speed}x")
    except Exception as e:
        logger.warning(f"Audio engine notice: {e}")

    # 4. Video Engine & FFmpeg
    try:
        from core.video_engine import VideoEngine
        engine = VideoEngine()
        ffmpeg_bin = engine.ffmpeg_cmd
        if ffmpeg_bin and (shutil.which(ffmpeg_bin) or Path(ffmpeg_bin).exists()):
            logger.info(f"Video Engine: FFmpeg={ffmpeg_bin} | Target Resolution={config.video_resolution} (9:16) | FPS={config.video_fps}")
        else:
            logger.warning("Video Engine: 'ffmpeg' not found in system PATH or python environment!")
            logger.warning("On Windows: Run 'winget install Gyan.FFmpeg' or 'pip install imageio-ffmpeg'")
    except Exception as e:
        logger.warning(f"Video engine notice: {e}")

    # 5. Visual Diffusion Pipeline
    logger.info(f"Visual Engine: Model={config.image_model_id} | FP16 Half-Precision={config.half_precision} | Device={config.device}")

    # 6. Narrative Prompter Engine
    try:
        from core.prompter import StoryPrompter
        prompter = StoryPrompter()
        llm_status = "Local GGUF (Active)" if prompter.llm else "Procedural Story Synthesizer (0 MB extra VRAM)"
        logger.info(f"Prompter Engine: {llm_status} | Anti-Repetition Vault Lookback={config.memory_lookback_count} stories")
    except Exception as e:
        logger.warning(f"Prompter engine notice: {e}")

    logger.info("=" * 65)

def main():
    parser = argparse.ArgumentParser(description="AutoAnime Shorts - Local AI Content Studio")
    parser.add_argument("--host", default=config.host, help=f"Host address (default: {config.host})")
    parser.add_argument("--port", type=int, default=config.port, help=f"Port number (default: {config.port})")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically launch web browser")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled.")

    check_system_prerequisites(debug_mode=args.debug)

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
