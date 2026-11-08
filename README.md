# AutoAnime Shorts 🎬✨
> **Ultra-Lightweight, 100% Local AI Studio for Viral 9:16 Anime & Web-Novel Shorts (TikTok / YouTube Shorts / Instagram Reels).**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11-brightgreen.svg)](https://www.python.org/)
[![Hardware](https://img.shields.io/badge/GPU-RTX%204060%20(8GB)-purple.svg)](#hardware-specs--optimization)
[![Offline](https://img.shields.io/badge/Status-100%25%20Offline%20Ready-success.svg)](#)

---

## 🌟 Highlights

**AutoAnime Shorts** is an on-demand, self-contained AI video generation and auto-upload studio built specifically for creating serialized **anime and web-novel short-form stories** in 9:16 vertical format (TikTok, Shorts, Reels).

* **Runs ONLY when you tell it to**: Zero always-on background daemons, zero telemetry.
* **Ultra-small storage footprint**: Core application is **<5 MB** (no multi-hundred-megabyte Electron bloat). Runs a sleek modern dark-mode local Web GUI on `http://127.0.0.1:7860`.
* **100% Offline & Fully Local**: Runs story generation, anime diffusion, and voice narration directly on your personal computer without external API bills.
* **Tuned for Mid-Range Hardware**: Runs smoothly on **NVIDIA RTX 4060 (8GB VRAM)**, **16GB RAM**, and quad-core CPUs (e.g. Intel i5-6400).
* **Anti-Repetition Story Vault**: SQLite memory registry tracks past loglines, character dynamics, and twists to ensure the Prompter AI **always delivers finished stories** and **never repeats a plot premise**.
* **Dual Upload Modes**: Toggle between **Auto-Upload** (instant hands-free publishing) and **Manual Approval** (review video, copy, and hashtags before posting).

---

## 📖 4 Generation & Prompting Modes

| Mode | How it Works | Best For |
| :--- | :--- | :--- |
| ⚡ **Full Auto** | 1-click batch mode. Generates a fresh story, breaks down scenes, creates images, voices narration, and renders the final video automatically. | Hands-off bulk content creation. |
| 📝 **Pre-Generate & Review** | Generates the complete story script, character profiles, and scene prompts **first**. You read, tweak narration/prompts in the UI, and click *Approve* to render. | Quality control & editorial polish. |
| 💡 **Semi-Manual** | You supply a raw hook or premise (e.g., *"A banished heir attends his ex-fiancée's wedding"*); the AI enhances it into a full multi-scene script. | Directed storytelling. |
| ✍️ **Manual** | Full creative control: type your own script, dialogue, and image prompts directly. | Custom storyboards & personal scripts. |

---

## 🎨 Visual & Audio Style (Reference Video Match)

Built directly around the viral anime web-novel formula seen on TikTok:
- **Cinematic Ken Burns Motion**: Smooth dynamic pans, slow drifts, zoom punches, and tilts rendered via optimized FFmpeg.
- **Dynamic Anime Karaoke Subtitles**: Advanced SubStation Alpha (`.ass`) captions styled in bold typography with thick stroke, drop shadow, and active word-by-word highlight.
- **Offline Studio Voiceover**: Ultra-compact **Kokoro-82M** speech synthesis engine for natural, emotive character narration.
- **Auto-Ducked Background Music**: Voice dialogue automatically ducks music tracks to keep narration crisp and intelligible.

---

## ⚙️ Hardware Specs & Optimization

Tuned specifically for the following personal PC setup:
- **GPU**: NVIDIA GeForce RTX 4060 (8 GB VRAM)
- **CPU**: Intel Core i5-6400 (4 cores) / Equivalent
- **RAM**: 16 GB DDR4
- **OS**: Windows 11 (also fully compatible with Linux & macOS)

### Memory Allocation Architecture
* **VRAM Budget**: ~3.5 GB for SD 1.5 Anime (FP16 + attention slicing) + ~2.1 GB for Qwen2.5-3B LLM layers offload.
* **System RAM**: <4 GB active usage.
* **Storage Footprint**: Modular design—only downloads models when needed; keeps outputs organized in `output/` with zero hidden temporary caches.

---

## 🚀 Quickstart Guide

### Windows 11 (1-Click Launch)

1. **Clone the repository**:
   ```cmd
   git clone https://github.com/darksqare/content_app.git
   cd content_app
   ```

2. **Run 1-Click Setup**:
   Double-click `setup.bat` (or run in terminal):
   ```cmd
   setup.bat
   ```
   *Installs virtual environment, PyTorch with CUDA 12.1 support, and dependencies.*

3. **Start the Studio**:
   Double-click `start.bat`:
   ```cmd
   start.bat
   ```
   *Automatically launches your default browser to `http://127.0.0.1:7860`.*

---

### Linux / macOS

```bash
git clone https://github.com/darksqare/content_app.git
cd content_app

# Run Setup
bash scripts/setup.sh

# Launch Studio
bash scripts/start.sh
```

---

## 🗂️ Project Structure

```
content_app/
├── core/
│   ├── config.py            # Hardware tuning, paths & config dataclasses
│   ├── memory.py            # SQLite Story Vault & anti-repetition memory
│   ├── prompter.py          # Llama-cpp Qwen2.5 story generator (4 modes)
│   ├── image_gen.py         # SD 1.5 Anime pipeline (FP16, low-VRAM 8GB)
│   ├── tts.py               # Kokoro-82M offline voice synthesis & word timings
│   ├── video_engine.py      # FFmpeg Ken Burns motion tweening & ASS karaoke subs
│   ├── uploader.py          # Low-friction upload automation & metadata packager
│   └── pipeline.py          # Master production coordinator
├── presets/                 # Genre templates (Underworld Romance, Campus Rom-Com, etc.)
│   ├── underworld_dark_romance.json
│   ├── campus_romcom_cohabitation.json
│   ├── reincarnation_urban_cultivation.json
│   └── psychological_thriller_mystery.json
├── web_ui/
│   ├── static/              # Sleek dark-mode dashboard (HTML5 / CSS / Vanilla JS)
│   └── server.py            # Lightweight FastAPI backend
├── scripts/
│   ├── setup.bat / setup.sh # 1-click venv & PyTorch CUDA setup
│   └── start.bat / start.sh # 1-click launcher
├── output/                  # Generated MP4 videos, images, and audio
├── requirements.txt         # Pinned requirements
├── run.py                   # Root Python entrypoint
├── setup.bat / start.bat    # Root Windows shortcuts
├── LICENSE                  # MIT License
└── README.md
```

---

## 📱 Social Media Upload & Review Gates

Every completed video automatically generates:
1. **Viral Title** (tested for high click-through rates).
2. **2-Sentence Hook Description**.
3. **High-Performing Hashtags** (niche tags + trending tags).
4. **Engagement-Driving Pinned Comment Question**.

### Upload Controls:
* **Manual Review Queue**: Preview video in the 9:16 vertical player, inspect hashtags, make edits, and click **"Approve & Publish"**.
* **Auto-Upload Mode**: Toggle on in Settings to immediately push to enabled platforms upon render completion without manual review.
* **Low-Friction Setup**: Utilizes local browser session automation (Playwright Chrome profile) requiring zero complicated developer API credentials.

---

## 🤝 Contributing

Contributions are welcome! If you'd like to contribute new genre presets, additional video animation effects, or local model connectors:
1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingPreset`)
3. Commit your Changes (`git commit -m 'Add AmazingPreset'`)
4. Push to the Branch (`git push origin feature/AmazingPreset`)
5. Open a Pull Request

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for more information.
