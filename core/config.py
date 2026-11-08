import os
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent

@dataclass
class AppConfig:
    # Execution & Server
    host: str = "127.0.0.1"
    port: int = 7860
    open_browser: bool = True
    debug: bool = False

    # Hardware & Performance (tuned for RTX 4060 8GB / 16GB RAM)
    device: str = "cuda"  # "cuda", "cpu"
    half_precision: bool = True  # FP16
    vram_budget_gb: float = 8.0
    cpu_threads: int = 4

    # Prompter LLM
    llm_backend: str = "llama_cpp"  # "llama_cpp", "ollama", "mock"
    llm_model_name: str = "Qwen/Qwen2.5-3B-Instruct-GGUF"
    llm_model_file: str = "qwen2.5-3b-instruct-q4_k_m.gguf"
    llm_context_length: int = 4096
    llm_gpu_layers: int = 33  # Offload all layers on 8GB VRAM
    llm_temperature: float = 0.75

    # Story Vault & Anti-Repetition
    vault_db_path: str = str(BASE_DIR / "output" / "story_vault.db")
    memory_lookback_count: int = 30

    # Image Generation (SD 1.5 Anime)
    image_backend: str = "diffusers"  # "diffusers", "mock"
    image_model_id: str = "dreamlike-art/dreamlike-anime-1.0"
    image_width: int = 576
    image_height: int = 1024
    image_steps: int = 25
    image_guidance_scale: float = 7.0

    # TTS Narration (Default Male Narrator)
    tts_backend: str = "kokoro"  # "kokoro", "edge_tts", "mock"
    tts_voice: str = "am_michael"  # Male deep dramatic narrator (Kokoro)
    tts_speed: float = 1.05

    # Video Assembly
    video_fps: int = 30
    video_resolution: str = "576x1024"  # 9:16 vertical
    ken_burns_enabled: bool = True
    subtitle_style: str = "anime_bold_karaoke"
    bgm_volume: float = 0.18
    voice_volume: float = 1.0

    # Upload & Review Toggles
    auto_upload: bool = False  # False = Manual review required
    upload_platforms: Dict[str, bool] = field(default_factory=lambda: {
        "youtube_shorts": False,
        "tiktok": False,
        "instagram_reels": False
    })

    # Paths
    output_dir: str = str(BASE_DIR / "output")
    models_dir: str = str(BASE_DIR / "models")
    presets_dir: str = str(BASE_DIR / "presets")
    bgm_dir: str = str(BASE_DIR / "assets" / "bgm")

    def save(self, config_path: str = None):
        path = Path(config_path or (BASE_DIR / "config.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls, config_path: str = None) -> "AppConfig":
        path = Path(config_path or (BASE_DIR / "config.json"))
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                cfg = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
                # Auto-upgrade previous defaults
                if "counterfeit" in cfg.image_model_id.lower():
                    cfg.image_model_id = "dreamlike-art/dreamlike-anime-1.0"
                if cfg.tts_voice.startswith("af_"):
                    cfg.tts_voice = "am_michael"
                return cfg
            except Exception as e:
                print(f"[Config] Error loading {path}, falling back to defaults: {e}")
        return cls()

# Global config instance
config = AppConfig.load()
