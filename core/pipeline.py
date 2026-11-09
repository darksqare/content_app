import os
import time
import json
import logging
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from core.config import config
from core.memory import StoryVault
from core.prompter import StoryPrompter
from core.image_gen import ImageGenerator
from core.tts import TTSEngine
from core.video_engine import VideoEngine
from core.uploader import SocialUploader

logger = logging.getLogger("PipelineManager")

class PipelineManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(PipelineManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self.vault = StoryVault(config.vault_db_path)
        self.prompter = StoryPrompter(self.vault)
        self.image_gen = ImageGenerator()
        self.tts = TTSEngine()
        self.video_engine = VideoEngine()
        self.uploader = SocialUploader(self.vault)
        
        self.current_job = None
        self.job_lock = threading.Lock()
        
        # 24/7 Autopilot Continuous Mode
        self.autopilot_enabled = False
        self.autopilot_cooldown = 10
        self.autopilot_duration_mins = 3.0
        self.autopilot_voice = "am_michael"
        self.autopilot_genre_idx = 0
        self.autopilot_stats = {
            "videos_created": 0,
            "last_title": None,
            "state": "idle"
        }
        self.autopilot_thread = None

        self._initialized = True

    def get_autopilot_status(self) -> Dict[str, Any]:
        return {
            "enabled": self.autopilot_enabled,
            "cooldown": self.autopilot_cooldown,
            "duration_mins": self.autopilot_duration_mins,
            "stats": self.autopilot_stats,
            "current_job": self.current_job
        }

    def set_autopilot(self, enabled: bool, cooldown: int = 10, duration_mins: float = 3.0, voice: str = "am_michael"):
        self.autopilot_enabled = enabled
        self.autopilot_cooldown = max(2, cooldown)
        self.autopilot_duration_mins = max(1.0, duration_mins)
        self.autopilot_voice = voice

        if enabled and (self.autopilot_thread is None or not self.autopilot_thread.is_alive()):
            self.autopilot_stats["state"] = "running"
            self.autopilot_thread = threading.Thread(target=self._autopilot_loop, daemon=True)
            self.autopilot_thread.start()
            logger.info("24/7 Autopilot Mode ACTIVATED.")
        elif not enabled:
            self.autopilot_stats["state"] = "stopped"
            logger.info("24/7 Autopilot Mode DEACTIVATED.")

    def _autopilot_loop(self):
        genres = [
            "underworld_dark_romance",
            "campus_romcom_cohabitation",
            "reincarnation_urban_cultivation",
            "psychological_thriller_mystery"
        ]
        
        while self.autopilot_enabled:
            try:
                genre_id = genres[self.autopilot_genre_idx % len(genres)]
                self.autopilot_genre_idx += 1

                self.autopilot_stats["state"] = "generating_story"
                logger.info(f"[Autopilot] Generating fresh story in genre '{genre_id}'...")

                story_data = self.prompter.generate(
                    mode="full_auto",
                    genre_id=genre_id,
                    duration_mins=self.autopilot_duration_mins
                )
                story_data["voice"] = self.autopilot_voice

                job_id = f"job_auto_{int(time.time())}"
                self.current_job = {
                    "id": job_id,
                    "status": "running",
                    "progress": 5,
                    "stage": f"[Autopilot] Producing '{story_data.get('title')}'...",
                    "story_title": story_data.get("title"),
                    "video_path": None,
                    "error": None
                }

                res = self._execute_full_generation(story_data, job_id)
                self.current_job["status"] = "completed"
                self.current_job["progress"] = 100
                self.current_job["stage"] = "Autopilot video complete!"
                self.current_job["video_path"] = res.get("video_path")
                self.current_job["package"] = res.get("package")

                self.autopilot_stats["videos_created"] += 1
                self.autopilot_stats["last_title"] = story_data.get("title")

                logger.info(f"[Autopilot] Video #{self.autopilot_stats['videos_created']} complete! Cooling down for {self.autopilot_cooldown}s...")
                
                self.autopilot_stats["state"] = "cooldown"
                for _ in range(self.autopilot_cooldown):
                    if not self.autopilot_enabled:
                        break
                    time.sleep(1)

            except Exception as e:
                logger.exception(f"[Autopilot] Error in cycle: {e}")
                time.sleep(5)

        self.autopilot_stats["state"] = "idle"

    def pre_generate_story(self, 
                           mode: str, 
                           genre_id: str, 
                           duration_mins: float, 
                           base_prompt: str = "",
                           custom_script: Dict[str, Any] = None,
                           exact_scenes: Optional[int] = None) -> Dict[str, Any]:
        """
        Executes the prompt generation phase.
        Allows users to read, inspect, and approve/tweak scenes before media creation.
        """
        logger.info(f"Generating story proposal (mode={mode}, genre={genre_id}, duration={duration_mins}m, exact_scenes={exact_scenes})...")
        story_data = self.prompter.generate(
            mode=mode,
            genre_id=genre_id,
            duration_mins=duration_mins,
            base_prompt=base_prompt,
            custom_script=custom_script,
            exact_scenes=exact_scenes
        )
        return story_data

    def start_pipeline_job(self, story_data: Dict[str, Any], callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> str:
        """
        Starts full media generation in a background thread.
        """
        job_id = f"job_{int(time.time())}"
        
        def worker():
            with self.job_lock:
                self.current_job = {
                    "id": job_id,
                    "status": "running",
                    "progress": 5,
                    "stage": "Initializing production...",
                    "story_title": story_data.get("title", "Untitled Story"),
                    "video_path": None,
                    "error": None
                }
                if callback:
                    callback(self.current_job)

                try:
                    res = self._execute_full_generation(story_data, job_id, callback)
                    self.current_job["status"] = "completed"
                    self.current_job["progress"] = 100
                    self.current_job["stage"] = "Video generation complete!"
                    self.current_job["video_path"] = res.get("video_path")
                    self.current_job["package"] = res.get("package")
                    if callback:
                        callback(self.current_job)
                except Exception as e:
                    logger.exception(f"Job {job_id} encountered an error: {e}")
                    self.current_job["status"] = "failed"
                    self.current_job["error"] = str(e)
                    self.current_job["stage"] = f"Failed: {e}"
                    if callback:
                        callback(self.current_job)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return job_id

    def _execute_full_generation(self, story_data: Dict[str, Any], job_id: str, callback: Optional[Callable] = None) -> Dict[str, Any]:
        scenes = story_data.get("scenes", [])
        total_scenes = len(scenes)
        if total_scenes == 0:
            raise ValueError("Story contains zero scenes to produce.")

        job_dir = Path(config.output_dir) / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        # Save complete story data with character visual bibles
        with open(job_dir / "story_data.json", "w", encoding="utf-8") as f:
            json.dump(story_data, f, indent=2, ensure_ascii=False)

        audio_segments = []

        # Initialize / verify diffusion pipeline before starting
        if self.image_gen.pipe is None and config.image_backend != "mock":
            if self.current_job:
                self.current_job["stage"] = "Loading SD Anime Diffusion Model (first time download ~2GB)..."
                if callback:
                    callback(self.current_job)
            self.image_gen._ensure_pipeline()

        chosen_voice = story_data.get("voice") or config.tts_voice

        # 1. Generate Voice Audio & Scene Visuals
        for idx, scene in enumerate(scenes):
            scene_num = scene.get("scene_number", idx + 1)
            percent = 10 + int((idx / total_scenes) * 60)
            
            if self.current_job:
                self.current_job["progress"] = percent
                self.current_job["stage"] = f"Producing Scene {scene_num}/{total_scenes}..."
                if callback:
                    callback(self.current_job)

            # Generate Speech (using selected male/female voice)
            narration = scene.get("narration", "").strip()
            audio_out = job_dir / f"audio_scene_{scene_num:02d}.wav"
            audio_res = self.tts.synthesize(narration, str(audio_out), voice=chosen_voice)
            audio_segments.append(audio_res)

            # Generate Image Slide
            image_prompt = scene.get("image_prompt", "")
            img_out = job_dir / f"slide_scene_{scene_num:02d}.png"
            scene_img_path = self.image_gen.generate_scene_image(
                prompt=image_prompt,
                output_path=str(img_out),
                scene_num=scene_num,
                mood=scene.get("mood", "suspense")
            )
            scene["image_path"] = scene_img_path

        # 2. Assemble Final 9:16 Video
        if self.current_job:
            self.current_job["progress"] = 75
            self.current_job["stage"] = "Rendering Ken Burns motion and burning dynamic subtitles..."
            if callback:
                callback(self.current_job)

        final_video_path = job_dir / f"{job_id}_final_video.mp4"
        self.video_engine.assemble_video(
            scenes=scenes,
            audio_segments=audio_segments,
            output_video_path=str(final_video_path)
        )

        # 3. Register story into the SQLite Vault
        if self.current_job:
            self.current_job["progress"] = 90
            self.current_job["stage"] = "Registering narrative into Story Vault..."
            if callback:
                callback(self.current_job)

        full_script = "\n\n".join([f"[Scene {s.get('scene_number', i+1)}] {s.get('narration')}" for i, s in enumerate(scenes)])
        story_id = self.vault.add_story(
            title=story_data.get("title", "Untitled Story"),
            genre=story_data.get("genre", "Anime Story"),
            logline=story_data.get("logline", ""),
            protagonist=story_data.get("protagonist", ""),
            deuteragonist=story_data.get("deuteragonist", ""),
            core_conflict=story_data.get("core_conflict", ""),
            climax_twist=story_data.get("climax_twist", ""),
            resolution=story_data.get("resolution", ""),
            hashtags=" ".join(story_data.get("hashtags", [])),
            full_script=full_script,
            scenes=scenes,
            video_path=str(final_video_path)
        )

        # 4. Package for Social Upload
        package = self.uploader.prepare_package(
            story_id=story_id,
            title=story_data.get("title", ""),
            description=story_data.get("description", story_data.get("logline", "")),
            hashtags=story_data.get("hashtags", []),
            pinned_comment=story_data.get("pinned_comment", ""),
            video_path=str(final_video_path)
        )

        # 5. Check Auto-Upload toggle
        if config.auto_upload:
            if self.current_job:
                self.current_job["progress"] = 95
                self.current_job["stage"] = "Auto-uploading to enabled social channels..."
                if callback:
                    callback(self.current_job)
            self.uploader.execute_upload(package)

        return {
            "story_id": story_id,
            "video_path": str(final_video_path),
            "package": package
        }
