import os
import math
import shutil
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from core.config import config, BASE_DIR

logger = logging.getLogger("VideoEngine")

class VideoEngine:
    def __init__(self):
        self.fps = config.video_fps
        self.width, self.height = [int(x) for x in config.video_resolution.split("x")]
        self.ffmpeg_cmd = self._resolve_ffmpeg()

    def _resolve_ffmpeg(self) -> str:
        # 1. System PATH
        cmd = shutil.which("ffmpeg")
        if cmd:
            return cmd

        # 2. tools/ directory in project
        tools_dir = Path(getattr(config, "base_dir", BASE_DIR)) / "tools"
        tools_bin = tools_dir / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        if tools_bin.exists():
            os.environ["PATH"] = str(tools_dir) + os.pathsep + os.environ.get("PATH", "")
            return str(tools_bin)

        # 3. Try portable imageio_ffmpeg and cache to tools/ffmpeg.exe
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            if exe and Path(exe).exists():
                tools_dir.mkdir(parents=True, exist_ok=True)
                target = tools_dir / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
                if not target.exists():
                    try:
                        shutil.copy2(exe, str(target))
                        os.environ["PATH"] = str(tools_dir) + os.pathsep + os.environ.get("PATH", "")
                        return str(target)
                    except Exception:
                        pass
                os.environ["PATH"] = str(Path(exe).parent) + os.pathsep + os.environ.get("PATH", "")
                return exe
        except Exception:
            pass

        # 4. Check common Windows WinGet / Program Files paths
        local_app = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            Path(local_app) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe",
            Path("C:/Program Files/ffmpeg/bin/ffmpeg.exe"),
            Path("C:/ffmpeg/bin/ffmpeg.exe")
        ]
        for p in candidates:
            if p.exists():
                os.environ["PATH"] = str(p.parent) + os.pathsep + os.environ.get("PATH", "")
                return str(p)

        return "ffmpeg"

    def assemble_video(self, 
                       scenes: List[Dict[str, Any]], 
                       audio_segments: List[Dict[str, Any]], 
                       output_video_path: str,
                       bgm_track_path: Optional[str] = None) -> str:
        """
        Renders complete 9:16 vertical short-form video from scenes, images, and audio.
        Applies Ken Burns motion tweening, compiles .ass karaoke subtitles, and mixes BGM.
        """
        out_video = Path(output_video_path)
        out_video.parent.mkdir(parents=True, exist_ok=True)
        work_dir = out_video.parent / "temp_render"
        work_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Beginning video assembly for {len(scenes)} scenes -> {out_video.name}")

        scene_video_clips = []
        total_time_cursor = 0.0
        all_subtitle_events = []

        # Step 1: Render each scene video clip with Ken Burns motion
        for i, (scene, audio_info) in enumerate(zip(scenes, audio_segments)):
            scene_idx = i + 1
            img_path = scene.get("image_path")
            duration = max(1.5, audio_info.get("duration", 3.0))
            motion_type = scene.get("motion_type", "zoom_in")

            clip_path = work_dir / f"scene_{scene_idx:02d}.mp4"
            self._render_ken_burns_clip(img_path, str(clip_path), duration, motion_type)
            scene_video_clips.append(str(clip_path))

            # Collect subtitle timing events
            words = audio_info.get("word_timings", [])
            all_subtitle_events.append({
                "scene_idx": scene_idx,
                "scene_start": total_time_cursor,
                "scene_end": total_time_cursor + duration,
                "words": words,
                "narration": scene.get("narration", "")
            })
            total_time_cursor += duration

        # Step 2: Concatenate visual clips into merged visual MP4
        concat_list_file = work_dir / "concat_list.txt"
        with open(concat_list_file, "w", encoding="utf-8") as f:
            for clip in scene_video_clips:
                clean_path = clip.replace("\\", "/")
                f.write(f"file '{clean_path}'\n")

        raw_visual_mp4 = work_dir / "raw_visual.mp4"
        cmd_concat = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_list_file),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
            "-pix_fmt", "yuv420p",
            str(raw_visual_mp4)
        ]
        self._run_cmd(cmd_concat, "Concatenating scene clips")

        # Step 3: Concatenate voice audio files
        audio_concat_list = work_dir / "audio_concat_list.txt"
        with open(audio_concat_list, "w", encoding="utf-8") as f:
            for audio_info in audio_segments:
                clean_path = audio_info["audio_path"].replace("\\", "/")
                f.write(f"file '{clean_path}'\n")

        merged_voice_wav = work_dir / "merged_voice.wav"
        cmd_audio_concat = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(audio_concat_list),
            "-c:a", "pcm_s16le",
            str(merged_voice_wav)
        ]
        self._run_cmd(cmd_audio_concat, "Concatenating voice narration")

        # Step 4: Generate .ass animated karaoke subtitles
        ass_sub_path = work_dir / "karaoke_subtitles.ass"
        self._generate_ass_subtitles(all_subtitle_events, str(ass_sub_path))

        # Step 5: Audio mixing with BGM (auto-ducking)
        final_audio_path = self._mix_audio(
            voice_path=str(merged_voice_wav),
            bgm_path=bgm_track_path,
            total_duration=total_time_cursor,
            output_path=str(work_dir / "final_mixed_audio.aac")
        )

        # Step 6: Final Muxing: burn subtitles & attach final audio
        clean_ass = str(ass_sub_path).replace("\\", "/").replace(":", "\\:")
        cmd_final = [
            "ffmpeg", "-y",
            "-i", str(raw_visual_mp4),
            "-i", final_audio_path,
            "-vf", f"subtitles='{clean_ass}'",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-shortest",
            str(out_video)
        ]
        self._run_cmd(cmd_final, "Final video mux and subtitle burning")

        logger.info(f"Video assembly complete: {out_video} ({total_time_cursor:.1f}s)")
        return str(out_video)

    def _render_ken_burns_clip(self, image_path: str, output_clip: str, duration: float, motion_type: str):
        """
        Uses FFmpeg's zoompan / scale filters to produce cinematic camera moves.
        """
        frames = max(30, int(duration * self.fps))
        w, h = self.width, self.height

        # Zoompan filter formulas (Ken Burns)
        if motion_type == "zoom_in":
            # Smooth zoom in toward center from 1.0 to 1.14
            vf = (
                f"zoompan=z='min(zoom+0.0015,1.14)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d={frames}:s={w}x{h}:fps={self.fps}"
            )
        elif motion_type == "zoom_out":
            # Start at 1.14 and pull out to 1.0
            vf = (
                f"zoompan=z='if(lte(zoom,1.0),1.14,max(1.001,zoom-0.0015))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d={frames}:s={w}x{h}:fps={self.fps}"
            )
        elif motion_type == "pan_left":
            # Slight zoom (1.10) and drift from right to left
            vf = (
                f"zoompan=z='1.10':x='if(lte(on,-1),(iw-iw/zoom)/2,x-0.5)':y='(ih-ih/zoom)/2':"
                f"d={frames}:s={w}x{h}:fps={self.fps}"
            )
        elif motion_type == "pan_right":
            # Slight zoom (1.10) and drift from left to right
            vf = (
                f"zoompan=z='1.10':x='if(lte(on,-1),0,x+0.5)':y='(ih-ih/zoom)/2':"
                f"d={frames}:s={w}x{h}:fps={self.fps}"
            )
        elif motion_type == "tilt_up":
            # Slight zoom and pan upwards
            vf = (
                f"zoompan=z='1.12':x='(iw-iw/zoom)/2':y='if(lte(on,-1),ih-ih/zoom,y-0.6)':"
                f"d={frames}:s={w}x{h}:fps={self.fps}"
            )
        else:
            # Default subtle slow zoom
            vf = (
                f"zoompan=z='min(zoom+0.001,1.10)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d={frames}:s={w}x{h}:fps={self.fps}"
            )

        cmd = [
            "ffmpeg", "-y", "-loop", "1",
            "-i", image_path,
            "-vf", vf,
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            output_clip
        ]
        self._run_cmd(cmd, f"Rendering motion clip ({motion_type})")

    def _generate_ass_subtitles(self, events: List[Dict[str, Any]], ass_path: str):
        """
        Creates Advanced SubStation Alpha (.ass) subtitles with viral vertical TikTok anime style:
        - Big bold sans-serif font
        - White text with thick black stroke and soft shadow
        - Centered in lower-third
        - Word-level active karaoke glow
        """
        w, h = self.width, self.height
        font_size = int(h * 0.038)  # Scaled for 9:16 vertical readability
        margin_v = int(h * 0.22)    # Positioned above TikTok/Reels bottom UI

        ass_content = [
            "[Script Info]",
            "Title: Anime Web-Novel Short Subtitles",
            "ScriptType: v4.00+",
            f"PlayResX: {w}",
            f"PlayResY: {h}",
            "WrapStyle: 0",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            # Primary: Yellow karaoke highlight &HE0FFFF / Secondary: Clean White &HFFFFFF / Outline: Solid Black &H000000
            f"Style: Default,Trebuchet MS,{font_size},&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,4,2,2,40,40,{margin_v},1",
            f"Style: Highlight,Impact,{int(font_size * 1.08)},&H0000D7FF,&H00FFFFFF,&H00000000,&H90000000,-1,0,0,0,100,100,1,0,1,4,3,2,40,40,{margin_v},1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
        ]

        def fmt_time(seconds: float) -> str:
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = seconds % 60
            return f"{h:d}:{m:02d}:{s:05.2f}"

        # Group words into short 3-6 word punchy lines
        for ev in events:
            scene_start = ev["scene_start"]
            words = ev["words"]
            if not words:
                continue

            chunk_size = 5
            for idx in range(0, len(words), chunk_size):
                chunk = words[idx:idx + chunk_size]
                chunk_start = scene_start + chunk[0]["start"]
                chunk_end = scene_start + chunk[-1]["end"]

                # Build karaoke timed string with \k tags (in centiseconds)
                k_text_parts = []
                for w in chunk:
                    dur_cs = max(10, int((w["end"] - w["start"]) * 100))
                    k_text_parts.append(f"{{\\k{dur_cs}}}{w['word']}")
                karaoke_line = " ".join(k_text_parts)

                ass_content.append(
                    f"Dialogue: 0,{fmt_time(chunk_start)},{fmt_time(chunk_end)},Default,,0,0,0,,{karaoke_line}"
                )

        with open(ass_path, "w", encoding="utf-8") as f:
            f.write("\n".join(ass_content))
        logger.info(f"Generated animated ASS subtitles with {len(ass_content)} lines.")

    def _mix_audio(self, voice_path: str, bgm_path: Optional[str], total_duration: float, output_path: str) -> str:
        """
        Mixes speech voice track with background music.
        Applies auto-ducking to lower music volume during spoken dialogue.
        """
        # If no BGM provided or file does not exist, use voice track directly
        if not bgm_path or not Path(bgm_path).exists():
            # Check default bgm dir
            default_bgms = list(Path(config.bgm_dir).glob("*.mp3")) + list(Path(config.bgm_dir).glob("*.wav"))
            if default_bgms:
                bgm_path = str(default_bgms[0])
            else:
                # Return plain voice track
                return voice_path

        # FFmpeg filter: loop BGM, reduce volume, mix with voice
        bgm_vol = config.bgm_volume
        voice_vol = config.voice_volume
        filter_complex = (
            f"[1:a]aloop=loop=-1:size=2e+09,volume={bgm_vol}[bgm];"
            f"[0:a]volume={voice_vol}[voice];"
            f"[voice][bgm]amix=inputs=2:duration=first:dropout_transition=2[outa]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", voice_path,
            "-i", bgm_path,
            "-filter_complex", filter_complex,
            "-map", "[outa]",
            "-c:a", "aac", "-b:a", "192k",
            output_path
        ]
        try:
            self._run_cmd(cmd, "Mixing voice with background music")
            return output_path
        except Exception as e:
            logger.error(f"BGM mixing failed: {e}. Using voice track alone.")
            return voice_path

    def _run_cmd(self, cmd: List[str], desc: str):
        # Substitute 'ffmpeg' with resolved binary path
        run_cmd = list(cmd)
        if run_cmd and run_cmd[0] == "ffmpeg":
            run_cmd[0] = self.ffmpeg_cmd

        try:
            subprocess.run(run_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except FileNotFoundError:
            raise RuntimeError(
                f"FFmpeg binary not found at '{self.ffmpeg_cmd}'. "
                "Please run in PowerShell: winget install Gyan.FFmpeg "
                "or run in terminal: pip install imageio-ffmpeg"
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error during '{desc}': {e.stderr.decode('utf-8', errors='ignore')}")
            raise
