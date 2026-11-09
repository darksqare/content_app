import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.config import config, BASE_DIR
from core.pipeline import PipelineManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("WebServer")

app = FastAPI(title="AI Short-Form Anime Creator", version="1.0.0")

# Enable CORS for local cross-origin development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline = PipelineManager()

# Mount Static Directories
static_dir = BASE_DIR / "web_ui" / "static"
output_dir = Path(config.output_dir)
output_dir.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
app.mount("/output", StaticFiles(directory=str(output_dir)), name="output")

# Pydantic Request Models
class StoryGenRequest(BaseModel):
    mode: str = "pre_generate"  # 'full_auto', 'pre_generate', 'semi_manual', 'manual'
    genre_id: str = "underworld_dark_romance"
    duration_mins: float = 3.0
    base_prompt: str = ""
    custom_script: Optional[Dict[str, Any]] = None
    exact_scenes: Optional[int] = None

class JobStartRequest(BaseModel):
    story_data: Dict[str, Any]

class VoicePreviewRequest(BaseModel):
    voice: str = "am_michael"

class AutopilotRequest(BaseModel):
    enabled: bool
    cooldown: Optional[int] = 10
    duration_mins: Optional[float] = 3.0
    voice: Optional[str] = "am_michael"

class UploadRequest(BaseModel):
    story_id: Optional[int] = None
    video_path: str
    title: str
    description: str
    hashtags: List[str]
    pinned_comment: str = ""
    platforms: Optional[List[str]] = None

class ConfigUpdateRequest(BaseModel):
    auto_upload: Optional[bool] = None
    upload_platforms: Optional[Dict[str, bool]] = None
    video_resolution: Optional[str] = None
    bgm_volume: Optional[float] = None
    tts_voice: Optional[str] = None
    tts_speed: Optional[float] = None
    llm_backend: Optional[str] = None
    image_backend: Optional[str] = None

@app.get("/")
def get_index():
    index_file = static_dir / "index.html"
    return FileResponse(str(index_file))

@app.get("/api/config")
def get_config():
    return {
        "auto_upload": config.auto_upload,
        "upload_platforms": config.upload_platforms,
        "video_resolution": config.video_resolution,
        "bgm_volume": config.bgm_volume,
        "tts_voice": config.tts_voice,
        "tts_speed": config.tts_speed,
        "llm_backend": config.llm_backend,
        "image_backend": config.image_backend,
        "device": config.device,
        "vram_budget_gb": config.vram_budget_gb
    }

@app.post("/api/config")
def update_config(req: ConfigUpdateRequest):
    if req.auto_upload is not None:
        config.auto_upload = req.auto_upload
    if req.upload_platforms is not None:
        config.upload_platforms = req.upload_platforms
    if req.video_resolution is not None:
        config.video_resolution = req.video_resolution
    if req.bgm_volume is not None:
        config.bgm_volume = req.bgm_volume
    if req.tts_voice is not None:
        config.tts_voice = req.tts_voice
    if req.tts_speed is not None:
        config.tts_speed = req.tts_speed
    if req.llm_backend is not None:
        config.llm_backend = req.llm_backend
    if req.image_backend is not None:
        config.image_backend = req.image_backend
    
    config.save()
    return {"status": "success", "config": get_config()}

@app.get("/api/presets")
def get_presets():
    presets_dir = Path(config.presets_dir)
    presets = []
    for file in presets_dir.glob("*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                presets.append(json.load(f))
        except Exception as e:
            logger.error(f"Error reading preset {file}: {e}")
    return presets

@app.post("/api/presets")
def create_preset(data: Dict[str, Any] = Body(...)):
    preset_id = data.get("id", "").strip().lower().replace(" ", "_")
    if not preset_id:
        raise HTTPException(status_code=400, detail="Preset ID is required.")
    
    preset_file = Path(config.presets_dir) / f"{preset_id}.json"
    with open(preset_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    return {"status": "success", "preset": data}

@app.post("/api/prompts/generate")
def generate_prompts(req: StoryGenRequest):
    try:
        story_data = pipeline.pre_generate_story(
            mode=req.mode,
            genre_id=req.genre_id,
            duration_mins=req.duration_mins,
            base_prompt=req.base_prompt,
            custom_script=req.custom_script,
            exact_scenes=req.exact_scenes
        )
        return {"status": "success", "story": story_data}
    except Exception as e:
        logger.exception("Error generating prompt/script")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/story/sync-characters")
def sync_character_consistency(req: Dict[str, Any] = Body(...)):
    try:
        story_data = req.get("story_data", {})
        genre_id = req.get("genre_id", story_data.get("genre_id", ""))
        synced_story = pipeline.prompter.enforce_character_consistency(story_data, genre_id=genre_id)
        return {"status": "success", "story": synced_story}
    except Exception as e:
        logger.exception("Error syncing character consistency")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tts/preview")
def preview_voice(req: VoicePreviewRequest):
    try:
        preview_file = pipeline.tts.generate_preview(req.voice)
        rel_path = Path(preview_file).relative_to(config.output_dir)
        return {"status": "success", "audio_url": f"/output/{rel_path.as_posix()}"}
    except Exception as e:
        logger.exception("Voice preview generation failed")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/autopilot")
def get_autopilot():
    return pipeline.get_autopilot_status()

@app.post("/api/autopilot")
def set_autopilot(req: AutopilotRequest):
    pipeline.set_autopilot(
        enabled=req.enabled,
        cooldown=req.cooldown or 10,
        duration_mins=req.duration_mins or 3.0,
        voice=req.voice or "am_michael"
    )
    return {"status": "success", "autopilot": pipeline.get_autopilot_status()}

@app.post("/api/pipeline/start")
def start_pipeline(req: JobStartRequest):
    try:
        job_id = pipeline.start_pipeline_job(req.story_data)
        return {"status": "success", "job_id": job_id}
    except Exception as e:
        logger.exception("Error initiating pipeline generation job")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/pipeline/status")
def get_pipeline_status():
    job = pipeline.current_job
    if not job:
        return {"status": "idle", "progress": 0, "stage": "Ready"}
    
    # If video path exists, convert to web url
    resp = dict(job)
    if job.get("video_path"):
        try:
            rel_path = Path(job["video_path"]).relative_to(config.output_dir)
            resp["video_url"] = f"/output/{rel_path.as_posix()}"
        except Exception:
            resp["video_url"] = f"/output/{Path(job['video_path']).name}"
            
    return resp

@app.get("/api/stories")
def list_stories(limit: int = 50, offset: int = 0):
    stories = pipeline.vault.list_stories(limit=limit, offset=offset)
    # Add web urls for videos
    for s in stories:
        if s.get("video_path") and Path(s["video_path"]).exists():
            try:
                rel = Path(s["video_path"]).relative_to(config.output_dir)
                s["video_url"] = f"/output/{rel.as_posix()}"
            except Exception:
                s["video_url"] = f"/output/{Path(s['video_path']).name}"
        else:
            s["video_url"] = None
    return stories

@app.delete("/api/stories/{story_id}")
def delete_story(story_id: int):
    pipeline.vault.delete_story(story_id)
    return {"status": "success", "deleted_id": story_id}

@app.post("/api/upload")
def upload_video(req: UploadRequest):
    try:
        package = pipeline.uploader.prepare_package(
            story_id=req.story_id or 0,
            title=req.title,
            description=req.description,
            hashtags=req.hashtags,
            pinned_comment=req.pinned_comment,
            video_path=req.video_path
        )
        res = pipeline.uploader.execute_upload(package, platforms=req.platforms)
        return {"status": "success", "result": res}
    except Exception as e:
        logger.exception("Manual upload failed")
        raise HTTPException(status_code=500, detail=str(e))

def start_server(host: str = None, port: int = None, open_browser: bool = True):
    import uvicorn
    h = host or config.host
    p = port or config.port

    print("\n" + "=" * 60)
    print("  🎬 AutoAnime Shorts Studio is RUNNING!")
    print(f"  👉 Web Dashboard: http://{h}:{p}")
    print("  Keep this window open while using the Studio.")
    print("=" * 60 + "\n")
    
    if open_browser:
        import threading
        import webbrowser
        def open_url():
            import time
            time.sleep(1.2)
            try:
                webbrowser.open(f"http://{h}:{p}")
            except Exception:
                pass
        threading.Thread(target=open_url, daemon=True).start()

    logger.info(f"Starting Web GUI at http://{h}:{p}")
    uvicorn.run(app, host=h, port=p, log_level="info")
