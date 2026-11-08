import os
import logging
from pathlib import Path
from typing import Optional, List
from PIL import Image, ImageDraw, ImageFont
from core.config import config

logger = logging.getLogger("ImageGenerator")

DEFAULT_POSITIVE_PREFIX = "masterpiece, best quality, ultra-detailed 2D anime illustration, vibrant colors, cinematic lighting, vertical 9:16, "
DEFAULT_NEGATIVE_PROMPT = "(worst quality, low quality:1.4), bad anatomy, deformed, bad hands, missing fingers, extra digits, blurry, cropped, bad proportions, watermark, signature, username, text, photorealistic, 3d render"

class ImageGenerator:
    def __init__(self):
        self.pipe = None
        self.device = config.device
        self._initialized = False

    def _ensure_pipeline(self):
        if self._initialized:
            return
        self._initialized = True

        if config.image_backend == "mock":
            logger.info("ImageGenerator running in mock/procedural mode.")
            return

        try:
            import torch
            from diffusers import StableDiffusionPipeline, DPMSolverMultistepScheduler

            if not torch.cuda.is_available():
                logger.info("CUDA not active for diffusion. Using procedural generator for fast response.")
                return

            logger.info(f"Loading SD 1.5 Anime Checkpoint ({config.image_model_id}) on {self.device}...")
            
            local_ckpt = Path(config.models_dir) / "anime_checkpoint.safetensors"
            if local_ckpt.exists():
                self.pipe = StableDiffusionPipeline.from_single_file(
                    str(local_ckpt),
                    torch_dtype=torch.float16 if config.half_precision else torch.float32,
                    safety_checker=None
                )
            else:
                self.pipe = StableDiffusionPipeline.from_pretrained(
                    config.image_model_id,
                    torch_dtype=torch.float16 if config.half_precision else torch.float32,
                    safety_checker=None
                )

            self.pipe.scheduler = DPMSolverMultistepScheduler.from_config(self.pipe.scheduler.config)
            self.pipe.enable_attention_slicing()
            try:
                self.pipe.enable_xformers_memory_efficient_attention()
            except Exception:
                pass
            
            self.pipe.to(self.device)
            logger.info("SD Anime Pipeline loaded successfully on RTX 4060.")

        except ImportError:
            logger.info("Diffusers/Transformers not installed. Using procedural fallback.")
        except Exception as e:
            logger.warning(f"Notice initializing Diffusers: {e}. Using procedural graphics.")

    def generate_scene_image(self, prompt: str, output_path: str, scene_num: int = 1, mood: str = "suspense") -> str:
        """
        Generates a 9:16 anime vertical illustration.
        Saves image to output_path and returns the path.
        """
        self._ensure_pipeline()
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)

        full_prompt = DEFAULT_POSITIVE_PREFIX + prompt

        if self.pipe is not None:
            try:
                import torch
                logger.info(f"[SD Anime] Generating Scene #{scene_num} (mood: {mood})...")
                with torch.inference_mode():
                    image = self.pipe(
                        prompt=full_prompt,
                        negative_prompt=DEFAULT_NEGATIVE_PROMPT,
                        width=config.image_width,
                        height=config.image_height,
                        num_inference_steps=config.image_steps,
                        guidance_scale=config.image_guidance_scale
                    ).images[0]
                image.save(out_file)
                logger.info(f"Scene #{scene_num} saved to {out_file}")
                return str(out_file)
            except Exception as e:
                logger.error(f"Diffusers generation failed: {e}. Falling back to procedural graphic.")

        # Fallback / procedural graphic generator (for fast testing, CPU environments, or offline setup)
        return self._generate_procedural_slide(prompt, str(out_file), scene_num, mood)

    def _generate_procedural_slide(self, prompt: str, output_path: str, scene_num: int, mood: str) -> str:
        """
        Generates a high-resolution stylized anime slide background with mood-themed gradients.
        Guarantees that video production and FFmpeg motion tweening work seamlessly even before weights are loaded.
        """
        w, h = config.image_width, config.image_height
        mood_palettes = {
            "suspense": [(15, 23, 42), (30, 41, 59), (10, 15, 28)],     # Deep navy / noir
            "action": [(69, 10, 10), (127, 29, 29), (24, 24, 27)],      # Crimson / dark charcoal
            "romance": [(76, 29, 149), (131, 24, 67), (24, 24, 27)],    # Violet / rose / midnight
            "comedy": [(180, 83, 9), (217, 119, 6), (245, 158, 11)],    # Warm amber / gold
            "melodrama": [(24, 24, 27), (55, 65, 81), (17, 24, 39)],   # Rainy monochrome
            "cozy": [(20, 83, 45), (22, 101, 52), (15, 23, 42)]        # Forest green / deep slate
        }

        colors = mood_palettes.get(mood.lower(), mood_palettes["suspense"])
        img = Image.new("RGB", (w, h), color=colors[0])
        draw = ImageDraw.Draw(img)

        # Smooth vertical gradient
        for y in range(h):
            ratio = y / h
            r = int(colors[0][0] * (1 - ratio) + colors[1][0] * ratio)
            g = int(colors[0][1] * (1 - ratio) + colors[1][1] * ratio)
            b = int(colors[0][2] * (1 - ratio) + colors[1][2] * ratio)
            draw.line([(0, y), (w, y)], fill=(r, g, b))

        # Stylized framing overlays (cinematic bars, anime vignette, scene tag)
        draw.rectangle([(20, 20), (w - 20, h - 20)], outline=(255, 255, 255, 40), width=2)
        
        # Scene badge header
        draw.rectangle([(30, 30), (160, 75)], fill=(0, 0, 0, 180))
        draw.text((45, 45), f"SCENE {scene_num:02d}", fill=(255, 255, 255))
        
        # Mood badge
        draw.rectangle([(w - 180, 30), (w - 30, 75)], fill=(0, 0, 0, 180))
        draw.text((w - 165, 45), f"[{mood.upper()}]", fill=(250, 204, 21))

        # Abstract visual atmosphere circles / particles
        for i in range(12):
            cx = (i * 97) % w
            cy = (i * 173) % h
            rad = 40 + (i * 8)
            draw.ellipse([(cx - rad, cy - rad), (cx + rad, cy + rad)], outline=(255, 255, 255, 25), width=2)

        # Prompt hint in lower frame
        summary_text = (prompt[:120] + "...") if len(prompt) > 120 else prompt
        draw.rectangle([(30, h - 180), (w - 30, h - 70)], fill=(0, 0, 0, 210))
        draw.text((45, h - 160), "AI SCENE PROMPT:", fill=(147, 197, 253))
        draw.text((45, h - 130), summary_text, fill=(229, 231, 235))

        img.save(output_path, quality=95)
        return output_path
