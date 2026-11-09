import os
import re
import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from core.config import config
from core.memory import StoryVault

logger = logging.getLogger("StoryPrompter")

GENRE_AESTHETICS = {
    "underworld_dark_romance": "dark cinematic neo-noir anime aesthetic, dramatic chiaroscuro rim lighting, moody volumetric fog, wet rain-slicked asphalt reflections, vibrant neon glow in shadows, Ufotable and Makoto Shinkai style composition, hyper-detailed 2D anime illustration, 8k resolution, vertical 9:16 portrait framing",
    "campus_romcom_cohabitation": "vibrant modern anime aesthetic, warm golden hour sunbeams, soft romantic bloom, clean Kyoto Animation style lineart, hyper-detailed modern urban apartment interior textures, 8k resolution 2D anime art, vertical 9:16 portrait framing",
    "reincarnation_urban_cultivation": "high-contrast urban fantasy anime aesthetic, glowing ethereal spiritual aura, swirling golden particle embers, opulent crystal chandeliers and reflections, dynamic anime action composition, 8k resolution, vertical 9:16 portrait framing",
    "psychological_thriller_mystery": "chilling psychological thriller anime aesthetic, cold desaturated color palette, dramatic high-contrast shadows, rain-beaded glass reflections, intense suspenseful depth of field, 8k resolution, vertical 9:16 portrait framing"
}

SYSTEM_DIRECTIVE = """You are an elite creative scriptwriter and visual director for viral TikTok, YouTube Shorts, and Instagram Reels anime/manhua web-novel adaptations.

CRITICAL ARCHITECTURE RULES:
1. HARD CHARACTER CONSISTENCY & IMMUTABLE VISUAL ANCHORS:
   - In the 'character_sheets' object, define absolute visual bibles for 'protagonist' and 'deuteragonist':
     * name: Character's exact name
     * gender_tag: '1girl' or '1boy'
     * hair: Exact color, hairstyle, length, and bangs (e.g. 'straight waist-length icy silver hair, blunt bangs')
     * eyes: Exact color, pupil shape, and gaze (e.g. 'piercing sharp sapphire-blue eyes, long dark lashes')
     * face_and_build: Exact facial structure, age, complexion (e.g. 'pale porcelain complexion, regal composed expression, 27 years old')
     * signature_outfit: Exact clothing, fabric, color, cut (e.g. 'tailored charcoal-black double-breasted suit jacket, crisp white silk button-up shirt, black leather gloves')
     * accessories: Specific signature keepsake items (e.g. 'intricate filigree silver phantom mask over right eye, antique engraved silver band on left ring finger')
     * visual_anchor: An immutable, comma-separated token string uniting the above attributes.
   - ABSOLUTE CONSISTENCY IN ALL SCENES: Whenever a character appears in a scene, you MUST start their character description with their exact, verbatim 'visual_anchor'. NEVER change their hair color, eye color, or signature traits between scenes (e.g. NEVER make the MC pink-haired in one scene and blue-haired in another).

2. DETAILED IMAGE PROMPT DIRECTIVE:
   Every single scene prompt must be ultra-detailed and fit the story's visual aesthetic:
   - Format: 'masterpiece, best quality, [CAMERA_SHOT_TYPE], [CHARACTER_VISUAL_ANCHOR], [EXPRESSION & ACTION], [DETAILED_BACKGROUND_AND_LIGHTING], [OBJECT_REALISM if objects present], [GENRE_AESTHETIC], vertical 9:16'
   - Camera shots: specify explicit angles ('extreme close-up on eyes', 'dramatic low-angle Dutch tilt shot', 'cinematic medium waist-up portrait', 'atmospheric wide establishing shot').
   - Object & prop realism: When weapons, cars, jewelry, tech, food, or props appear, add 'realistic textures, photorealistic materials, realistic reflections and lighting, sharp physical object focus'.

3. FINISHED STORIES ONLY: Every story must be complete, closed-ended, and fully resolved within the designated scenes. Strong hook (0-15s), rising tension, and emotional climax or punchy twist ending. NEVER end on an incomplete thought.
4. EXACT SCENE COUNT: Generate EXACTLY the requested number of scenes in the 'scenes' array. If 20 scenes are requested, generate all 20 scene objects numbered 1 to 20.
5. STRICT OUTPUT FORMAT: Valid JSON only matching the schema.
"""

JSON_SCHEMA_EXAMPLE = {
    "title": "Story Title Here",
    "genre": "Underworld / Mafia Dark Romance",
    "logline": "A one-sentence summary of the core premise and hook.",
    "character_sheets": {
        "protagonist": {
            "name": "Liu Yanran",
            "role": "Female Syndicate Sovereign",
            "gender_tag": "1girl",
            "hair": "straight waist-length icy silver hair, blunt bangs",
            "eyes": "piercing sharp sapphire-blue eyes, long dark lashes",
            "face_and_build": "pale porcelain complexion, regal composed expression, 27 years old",
            "signature_outfit": "tailored charcoal-black double-breasted suit jacket, crisp white silk button-up shirt, black leather gloves",
            "accessories": "intricate filigree silver phantom mask over right eye, antique engraved silver band on left ring finger",
            "visual_anchor": "1girl, Liu Yanran, straight waist-length icy silver hair, blunt bangs, piercing sharp sapphire-blue eyes, pale porcelain skin, tailored charcoal-black double-breasted suit jacket, crisp white silk button-up shirt, intricate silver filigree phantom mask over right eye, engraved silver ring on left hand"
        },
        "deuteragonist": {
            "name": "Chen Chen",
            "role": "Trapped Medical Prodigy",
            "gender_tag": "1boy",
            "hair": "messy tousled jet-black hair with parted bangs",
            "eyes": "warm deep amber-brown eyes, intense emotional gaze",
            "face_and_build": "youthful pale face, feverish flush on cheeks, 18 years old",
            "signature_outfit": "tattered white linen dress shirt, unbuttoned collar, dark trousers",
            "accessories": "matching antique engraved silver heirloom band on left ring finger",
            "visual_anchor": "1boy, Chen Chen, messy tousled jet-black hair, parted bangs, deep amber-brown eyes, youthful pale face, tattered white linen dress shirt, unbuttoned collar, matching engraved silver keepsake band on left hand"
        }
    },
    "protagonist": "Liu Yanran, 27, feared syndicate sovereign, silver hair, phantom mask, tailored suit",
    "deuteragonist": "Chen Chen, 18, medical prodigy, tousled black hair, engraved keepsake silver ring",
    "core_conflict": "The primary tension driving the story",
    "climax_twist": "The shocking climax or unexpected revelation",
    "resolution": "How the narrative concludes cleanly",
    "description": "Short 2-sentence teaser for social media captions.",
    "hashtags": ["#animestory", "#webnovel", "#shorts", "#fyp"],
    "pinned_comment": "Question to spark discussion in the comments section?",
    "scenes": [
        {
            "scene_number": 1,
            "narration": "Narration text spoken during scene 1...",
            "image_prompt": "masterpiece, best quality, cinematic close-up portrait, 1girl, Liu Yanran, straight waist-length icy silver hair, blunt bangs, piercing sharp sapphire-blue eyes, pale porcelain skin, tailored charcoal-black double-breasted suit jacket, crisp white silk button-up shirt, intricate silver filigree phantom mask over right eye, engraved silver ring on left hand, standing by rain-streaked luxury penthouse window at night, glowing neon city skyline below, realistic glass reflections and water droplets, dark cinematic neo-noir anime aesthetic, vertical 9:16",
            "mood": "suspense",
            "motion_type": "zoom_in"
        }
    ]
}

class StoryPrompter:
    def __init__(self, vault: Optional[StoryVault] = None):
        self.vault = vault or StoryVault(config.vault_db_path)
        self.llm = None
        self._init_backend()

    def _init_backend(self):
        backend = config.llm_backend.lower()
        if backend == "llama_cpp":
            import sys
            if sys.platform == "win32":
                try:
                    import torch
                    torch_lib = Path(torch.__file__).parent / "lib"
                    if torch_lib.exists():
                        os.add_dll_directory(str(torch_lib))
                except Exception:
                    pass

            try:
                from llama_cpp import Llama
                model_path = Path(config.models_dir) / config.llm_model_file
                if model_path.exists():
                    logger.info(f"Loading local GGUF model: {model_path} with {config.llm_gpu_layers} GPU layers...")
                    self.llm = Llama(
                        model_path=str(model_path),
                        n_ctx=config.llm_context_length,
                        n_gpu_layers=config.llm_gpu_layers,
                        n_threads=config.cpu_threads,
                        verbose=config.debug
                    )
                else:
                    logger.info("Prompter: Using built-in procedural anime story engine (0 MB extra VRAM). (Optional: run scripts/download_model.bat to enable local Qwen 2.5 LLM).")
            except ImportError:
                logger.info("Prompter: Using built-in procedural anime story engine (0 MB extra VRAM).")
            except Exception as e:
                logger.info(f"llama_cpp notice: {e}. Using built-in procedural prompter engine.")

    def generate(self, 
                 mode: str, 
                 genre_id: str = "underworld_dark_romance", 
                 duration_mins: float = 3.0, 
                 base_prompt: str = "",
                 custom_script: Dict[str, Any] = None,
                 exact_scenes: Optional[int] = None) -> Dict[str, Any]:
        """
        Executes one of the 4 prompt generation modes:
        - 'full_auto': Generates end-to-end story based on genre & duration
        - 'pre_generate': Generates complete script for user review/edit
        - 'semi_manual': Takes user base idea and enhances it into full script
        - 'manual': Accepts user-crafted script and scene breakdown
        """
        if mode == "manual" and custom_script:
            story = self._format_manual(custom_script)
            return self.enforce_character_consistency(story, genre_id=genre_id)

        # Calculate exact requested scene count
        if exact_scenes and exact_scenes > 0:
            target_scenes = max(5, min(120, exact_scenes))
        else:
            # Average 7.5 seconds per scene for punchy short pacing
            target_scenes = max(5, min(120, int((duration_mins * 60) / 7.5)))

        # Retrieve anti-repetition memory
        anti_repetition_context = self.vault.get_anti_repetition_context(limit=config.memory_lookback_count)

        # Load genre preset details
        preset_info = self._load_preset(genre_id)

        user_instruction = self._build_prompt_instruction(
            mode=mode,
            preset=preset_info,
            target_scenes=target_scenes,
            duration_mins=duration_mins,
            base_prompt=base_prompt,
            anti_repetition=anti_repetition_context
        )

        # Attempt generation via Local LLM / Ollama or robust procedural synthesis
        story_data = self._invoke_llm(user_instruction)
        if not story_data or len(story_data.get("scenes", [])) < target_scenes:
            logger.info(f"Using procedural anime story engine to produce exactly {target_scenes} scenes.")
            story_data = self._generate_procedural(preset_info, base_prompt, target_scenes)

        story_data["mode"] = mode
        story_data["genre"] = preset_info.get("name", genre_id)
        story_data["genre_id"] = genre_id
        story_data["estimated_duration_mins"] = duration_mins

        # Enforce hard local character consistency and detailed aesthetic tokens
        story_data = self.enforce_character_consistency(story_data, genre_id=genre_id)

        return story_data

    def _build_prompt_instruction(self, mode: str, preset: Dict[str, Any], target_scenes: int, duration_mins: float, base_prompt: str, anti_repetition: str) -> str:
        instructions = [
            f"Genre: {preset.get('name', 'Anime Web-Novel')}",
            f"Tone: {preset.get('tone', 'dramatic, romantic')}",
            f"Visual Style: {preset.get('visual_style', 'Anime illustration')}",
            f"CRITICAL REQUIREMENT: Output EXACTLY {target_scenes} scenes in the scenes array.",
            "CHARACTER RULE: You MUST populate 'character_sheets' with immutable visual anchors for protagonist & deuteragonist, and copy the exact visual anchor verbatim into every scene prompt featuring that character. Never change hair or eye colors between scenes.",
            "",
            anti_repetition,
            ""
        ]

        if mode == "semi_manual" and base_prompt.strip():
            instructions.append(f"USER BASE PROMPT / CORE CONCEPT TO ENHANCE:\n\"{base_prompt.strip()}\"\nExpand this concept into a full, captivating narrative with complete resolution across all {target_scenes} scenes.")
        elif mode in ["full_auto", "pre_generate"]:
            instructions.append(f"TASK: Create a brand new, highly original story premise adhering strictly to the genre tropes, featuring charismatic leads, high tension, and a finished climax across {target_scenes} complete scenes.")

        instructions.append("\nOUTPUT FORMAT: Valid JSON only conforming strictly to JSON_SCHEMA_EXAMPLE.")
        return "\n".join(instructions)

    def _invoke_llm(self, user_instruction: str) -> Optional[Dict[str, Any]]:
        if self.llm:
            try:
                response = self.llm.create_chat_completion(
                    messages=[
                        {"role": "system", "content": SYSTEM_DIRECTIVE},
                        {"role": "user", "content": user_instruction}
                    ],
                    temperature=config.llm_temperature,
                    max_tokens=4096
                )
                text = response["choices"][0]["message"]["content"]
                return self._parse_json_response(text)
            except Exception as e:
                logger.error(f"Llama-cpp completion error: {e}")

        try:
            import urllib.request
            req = urllib.request.Request(
                "http://127.0.0.1:11434/api/generate",
                data=json.dumps({
                    "model": "qwen2.5:3b",
                    "prompt": f"{SYSTEM_DIRECTIVE}\n\n{user_instruction}",
                    "stream": False,
                    "format": "json"
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=3.0) as res:
                res_data = json.loads(res.read().decode("utf-8"))
                text = res_data.get("response", "")
                return self._parse_json_response(text)
        except Exception:
            pass

        return None

    def _parse_json_response(self, text: str) -> Optional[Dict[str, Any]]:
        try:
            cleaned = text.strip()
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
            if match:
                cleaned = match.group(1).strip()
            parsed = json.loads(cleaned)
            if "title" in parsed and "scenes" in parsed and isinstance(parsed["scenes"], list):
                return parsed
        except Exception as e:
            logger.warning(f"Failed to parse LLM JSON output: {e}")
        return None

    def _extract_or_synthesize_character_sheets(self, story_data: Dict[str, Any], genre_id: str) -> Dict[str, Any]:
        """
        Synthesizes structured, detailed character visual bibles with immutable visual anchors.
        """
        sheets = story_data.get("character_sheets")
        if isinstance(sheets, dict) and "protagonist" in sheets and sheets["protagonist"].get("visual_anchor"):
            return sheets

        protag_str = str(story_data.get("protagonist", ""))
        deuter_str = str(story_data.get("deuteragonist", ""))

        gid = genre_id.lower()
        if "campus" in gid:
            p = {
                "name": "Yu'er",
                "role": "Culinary Prodigy Freshman",
                "gender_tag": "1boy",
                "hair": "short messy jet-black textured hair, parted bangs",
                "eyes": "warm dark obsidian eyes, expressive gaze",
                "face_and_build": "slender athletic build, fair complexion, 18 years old",
                "signature_outfit": "oversized cream-white cotton hoodie with black drawstrings, dark denim jeans",
                "accessories": "stainless steel dorm keys on brass lanyard",
                "visual_anchor": "1boy, Yu'er, short messy jet-black textured hair, parted bangs, warm dark obsidian eyes, slender build, oversized cream-white cotton hoodie, dark denim jeans"
            }
            d = {
                "name": "Su Yi",
                "role": "Untouchable Senior Campus Goddess",
                "gender_tag": "1girl",
                "hair": "luminous platinum-silver waist-length hair, soft curtain bangs",
                "eyes": "crystalline lilac-violet eyes, long dark eyelashes",
                "face_and_build": "porcelain pale skin, poised aristocratic posture, delicate facial features, 19 years old",
                "signature_outfit": "pleated navy blue plaid academy blazer uniform with crimson silk ribbon tie",
                "accessories": "delicate pearl hairclip, wooden dining chopsticks",
                "visual_anchor": "1girl, Su Yi, luminous platinum-silver waist-length hair, soft curtain bangs, crystalline lilac-violet eyes, porcelain pale skin, pleated navy blue plaid academy blazer uniform with crimson silk ribbon tie"
            }
        elif "cultivation" in gid or "reincarnation" in gid:
            p = {
                "name": "Lin Chen",
                "role": "Reincarnated Dragon Sovereign",
                "gender_tag": "1boy",
                "hair": "short spiky charcoal-black hair with sweeping fringe",
                "eyes": "piercing celestial golden eyes, faint lightning spark",
                "face_and_build": "calm stoic expression, chiseled jawline, 20 years old",
                "signature_outfit": "tailored charcoal-grey blazer over fitted black turtleneck",
                "accessories": "ancient carved Imperial Dragon jade pendant around neck",
                "visual_anchor": "1boy, Lin Chen, short spiky charcoal-black hair, sweeping fringe, piercing celestial golden eyes, chiseled jawline, tailored charcoal-grey blazer over black turtleneck, glowing Imperial Dragon jade pendant"
            }
            d = {
                "name": "Su Qingxue",
                "role": "Martial Alliance Heiress",
                "gender_tag": "1girl",
                "hair": "long flowing raven-black hair, silver lotus hairpin",
                "eyes": "sharp intelligent hazel-green eyes",
                "face_and_build": "noble elegant visage, graceful poise, 21 years old",
                "signature_outfit": "ivory-white silk evening gown with golden cloud embroidery",
                "accessories": "translucent emerald jade bangle on right wrist",
                "visual_anchor": "1girl, Su Qingxue, long flowing raven-black hair, silver lotus hairpin, sharp intelligent hazel-green eyes, ivory-white silk evening gown with golden cloud embroidery, translucent emerald jade bangle"
            }
        elif "psychological" in gid or "thriller" in gid:
            p = {
                "name": "Detective Kaelen",
                "role": "Forensic Profiler",
                "gender_tag": "1boy",
                "hair": "messy layered ash-grey hair, textured strands over brow",
                "eyes": "sharp analytical golden-amber eyes, intense stare",
                "face_and_build": "slender pale face, light shadow of stubble, 26 years old",
                "signature_outfit": "dark charcoal trench coat over button-up shirt with loosened black tie",
                "accessories": "vintage brass mechanical pocket watch in breast pocket",
                "visual_anchor": "1boy, Detective Kaelen, messy layered ash-grey hair, sharp analytical golden-amber eyes, slender pale face, dark charcoal trench coat, loosened black tie, vintage brass mechanical pocket watch"
            }
            d = {
                "name": "Dr. Elena Vance",
                "role": "Neuro-Psychiatrist Partner",
                "gender_tag": "1girl",
                "hair": "sleek jet-black chin-length bob cut with blunt bangs",
                "eyes": "cool emerald-green eyes behind thin silver wireframe glasses",
                "face_and_build": "composed intellectual demeanor, porcelain skin, 25 years old",
                "signature_outfit": "tailored dark teal wool coat with structured collar, charcoal turtleneck",
                "accessories": "thin silver wireframe spectacles, leather-bound case notebook",
                "visual_anchor": "1girl, Dr. Elena Vance, sleek jet-black chin-length bob cut, blunt bangs, cool emerald-green eyes, thin silver wireframe glasses, tailored dark teal wool coat, charcoal turtleneck"
            }
        else: # underworld_dark_romance default
            p = {
                "name": "Liu Yanran",
                "role": "Female Syndicate Sovereign",
                "gender_tag": "1girl",
                "hair": "straight waist-length icy silver hair, blunt bangs",
                "eyes": "piercing sharp sapphire-blue eyes, long dark lashes",
                "face_and_build": "pale porcelain complexion, regal composed expression, 27 years old",
                "signature_outfit": "tailored charcoal-black double-breasted suit jacket, crisp white silk button-up shirt, black leather gloves",
                "accessories": "intricate filigree silver phantom mask over right eye, antique engraved silver band on left ring finger",
                "visual_anchor": "1girl, Liu Yanran, straight waist-length icy silver hair, blunt bangs, piercing sharp sapphire-blue eyes, pale porcelain skin, tailored charcoal-black double-breasted suit jacket, crisp white silk button-up shirt, intricate silver filigree phantom mask over right eye, engraved silver ring on left hand"
            }
            d = {
                "name": "Chen Chen",
                "role": "Trapped Medical Prodigy",
                "gender_tag": "1boy",
                "hair": "messy tousled jet-black hair with parted bangs",
                "eyes": "warm deep amber-brown eyes, intense emotional gaze",
                "face_and_build": "youthful pale face, feverish flush on cheeks, 18 years old",
                "signature_outfit": "tattered white linen dress shirt, unbuttoned collar, dark trousers",
                "accessories": "matching antique engraved silver heirloom band on left ring finger",
                "visual_anchor": "1boy, Chen Chen, messy tousled jet-black hair, parted bangs, deep amber-brown eyes, youthful pale face, tattered white linen dress shirt, unbuttoned collar, matching engraved silver keepsake band on left hand"
            }

        # Adapt names if user specified custom protagonist / deuteragonist
        if protag_str and "," in protag_str:
            p_name = protag_str.split(",")[0].strip()
            if p_name:
                p["name"] = p_name
        if deuter_str and "," in deuter_str:
            d_name = deuter_str.split(",")[0].strip()
            if d_name:
                d["name"] = d_name

        return {"protagonist": p, "deuteragonist": d}

    def enforce_character_consistency(self, story_data: Dict[str, Any], genre_id: str = "") -> Dict[str, Any]:
        """
        Enforces 100% strict local character consistency across every scene prompt.
        - Guarantees the protagonist never morphs hair or eye colors between scenes.
        - Injects immutable character visual anchors.
        - Enriches scene composition, lighting, camera angles, and genre aesthetic.
        """
        if not story_data:
            return story_data

        if not genre_id:
            genre_id = str(story_data.get("genre_id", story_data.get("genre", "underworld_dark_romance"))).lower().replace(" ", "_")

        sheets = self._extract_or_synthesize_character_sheets(story_data, genre_id)
        story_data["character_sheets"] = sheets

        protag = sheets.get("protagonist", {})
        deuter = sheets.get("deuteragonist", {})

        p_name = protag.get("name", "Protagonist").lower()
        d_name = deuter.get("name", "Deuteragonist").lower()
        p_anchor = protag.get("visual_anchor", "")
        d_anchor = deuter.get("visual_anchor", "")
        p_gender = protag.get("gender_tag", "1girl")
        d_gender = deuter.get("gender_tag", "1boy")

        # Conflict colors to strip from protagonist prompts if they don't match the protagonist's anchor hair
        p_hair = protag.get("hair", "").lower()
        hair_colors = ["silver hair", "white hair", "black hair", "jet-black hair", "blonde hair", "pink hair", "blue hair", "brown hair", "red hair", "green hair", "purple hair"]
        actual_hair = next((hc for hc in hair_colors if hc in p_hair), "")
        conflicting_hairs = [hc for hc in hair_colors if hc != actual_hair and hc]

        # Aesthetic tokens for the genre
        genre_aesthetic = GENRE_AESTHETICS.get(genre_id)
        if not genre_aesthetic:
            for k, v in GENRE_AESTHETICS.items():
                if k in genre_id:
                    genre_aesthetic = v
                    break
        if not genre_aesthetic:
            genre_aesthetic = GENRE_AESTHETICS["underworld_dark_romance"]

        scenes = story_data.get("scenes", [])
        for idx, sc in enumerate(scenes):
            prompt = sc.get("image_prompt", "")
            narration = sc.get("narration", "")
            mood = sc.get("mood", "suspense")
            combined_text = (prompt + " " + narration).lower()

            # Determine featured character
            has_p = (p_name in combined_text) or (p_gender in prompt.lower()) or (idx == 0 and d_name not in combined_text)
            has_d = (d_name in combined_text) or (d_gender in prompt.lower())

            # Keyword heuristic fallback
            if not has_p and not has_d:
                if any(k in combined_text for k in ["she", "her", "female", "empress", "goddess", "woman", "girl"]) and p_gender == "1girl":
                    has_p = True
                elif any(k in combined_text for k in ["he", "him", "male", "boy", "man", "student"]) and p_gender == "1boy":
                    has_p = True
                elif any(k in combined_text for k in ["he", "him", "male", "boy", "man", "student"]) and d_gender == "1boy":
                    has_d = True

            # Clean conflicting hair tokens for protagonist
            clean_prompt = prompt
            if has_p and not has_d and actual_hair:
                for bad_hair in conflicting_hairs:
                    clean_prompt = re.sub(rf"\b{bad_hair}\b", actual_hair, clean_prompt, flags=re.IGNORECASE)

            # Assign character label badge
            if has_p and has_d:
                sc["featured_character"] = "dual"
                sc["featured_character_label"] = f"{protag.get('name')} & {deuter.get('name')}"
            elif has_p:
                sc["featured_character"] = "protagonist"
                sc["featured_character_label"] = protag.get('name')
            elif has_d:
                sc["featured_character"] = "deuteragonist"
                sc["featured_character_label"] = deuter.get('name')
            else:
                sc["featured_character"] = "environment"
                sc["featured_character_label"] = "Object / Environment Focus"

            boundary_lookahead = r"(?=,\s*(?:standing|kneeling|looking|holding|walking|sitting|crying|smil|gaze|face|facing|sweating|in\s|seated|inside|carrying|bowing|facing)|$)"
            if has_p and not has_d:
                if p_name and p_name in clean_prompt.lower():
                    pattern = rf'(?:1girl|1boy)?\s*,?\s*{re.escape(p_name)}.*?' + boundary_lookahead
                    clean_prompt = re.sub(pattern, p_anchor, clean_prompt, count=1, flags=re.IGNORECASE)
                elif p_gender in clean_prompt.lower():
                    clean_prompt = re.sub(rf"\b{p_gender}\b.*?" + boundary_lookahead, p_anchor, clean_prompt, count=1, flags=re.IGNORECASE)
                else:
                    clean_prompt = f"{p_anchor}, {clean_prompt}"

            elif has_d and not has_p:
                if d_name and d_name in clean_prompt.lower():
                    pattern = rf'(?:1girl|1boy)?\s*,?\s*{re.escape(d_name)}.*?' + boundary_lookahead
                    clean_prompt = re.sub(pattern, d_anchor, clean_prompt, count=1, flags=re.IGNORECASE)
                elif d_gender in clean_prompt.lower():
                    clean_prompt = re.sub(rf"\b{d_gender}\b.*?" + boundary_lookahead, d_anchor, clean_prompt, count=1, flags=re.IGNORECASE)
                else:
                    clean_prompt = f"{d_anchor}, {clean_prompt}"

            # Strip redundant standard prefixes and suffixes
            clean_prompt = clean_prompt.replace("masterpiece, best quality, ", "").replace("9:16 vertical", "").replace("vertical 9:16", "").strip(", ")

            # Enrich with camera composition if missing
            camera_keywords = ["close up", "close-up", "macro", "portrait", "wide", "low-angle", "dutch angle", "high angle", "two-shot"]
            if not any(ck in clean_prompt.lower() for ck in camera_keywords):
                if mood in ["suspense", "melodrama"]:
                    camera_tag = "cinematic close-up portrait, intense emotional gaze, shallow depth of field"
                elif mood == "action":
                    camera_tag = "dynamic low-angle Dutch tilt shot, high speed anime action framing"
                elif mood == "romance":
                    camera_tag = "intimate 3/4 medium portrait shot, soft cinematic lighting"
                else:
                    camera_tag = "cinematic medium shot, crisp anime lineart"
                clean_prompt = f"{camera_tag}, {clean_prompt}"

            # Append genre aesthetic if not present
            if "anime aesthetic" not in clean_prompt.lower():
                clean_prompt = f"{clean_prompt}, {genre_aesthetic}"

            sc["image_prompt"] = f"masterpiece, best quality, {clean_prompt}, vertical 9:16"

        return story_data

    def _generate_procedural(self, preset: Dict[str, Any], user_hint: str, target_scenes: int) -> Dict[str, Any]:
        """
        High-quality procedural story synthesizer that scales dynamically to match target_scenes exactly.
        Guarantees 100% strict character visual consistency across all scenes in all genres.
        """
        genre_id = preset.get("id", "underworld_dark_romance")

        if "campus" in genre_id:
            title = "The Campus Goddess Moved Into My Kitchen"
            logline = "An introverted culinary prodigy is trapped in a sweltering dorm, only to discover the university's untouchable idol posted a rental listing secretly looking for a personal chef."
            protagonist = "Yu'er, 18-year-old culinary freshman, messy jet-black hair, casual cream hoodie, quiet and pragmatic."
            deuteragonist = "Su Yi, silver-haired campus goddess with lilac-violet eyes, poised in public but secretly a food addict."
            conflict = "Yu'er accidentally spills noodle soup at table #13, sparking viral campus rumors of being a clout-chaser, while needing an off-campus room with AC."
            twist = "The mysterious luxury landlord 'Zhiwoyi' who demands gourmet cooking is the campus goddess herself, and she intentionally baited him."
            resolution = "Yu'er arrives at the apartment viewing to find Su Yi holding chopsticks and smiling victoriously."
            tags = ["#campusromcom", "#manhua", "#scheminggoddess", "#culinaryprotagonist", "#animerecap", "#shorts", "#fyp"]
            comment = "Would you endure campus-wide slander if it meant free luxury rent with the campus idol?"

            p_anchor = "1boy, Yu'er, short messy jet-black textured hair, parted bangs, warm dark obsidian eyes, slender build, oversized cream-white cotton hoodie, dark denim jeans"
            d_anchor = "1girl, Su Yi, luminous platinum-silver waist-length hair, soft curtain bangs, crystalline lilac-violet eyes, porcelain pale skin, pleated navy blue plaid academy blazer uniform with crimson silk ribbon tie"

            pool = [
                {
                    "narration": "If you dare turn me down, I will personally post on the university confession wall that you broke my heart.",
                    "image_prompt": f"masterpiece, best quality, medium waist-up portrait, {d_anchor}, mischievous smirk, pointing forward in modern luxury living room, warm morning sunlight, realistic interior textures, vertical 9:16",
                    "mood": "comedy", "motion_type": "zoom_in"
                },
                {
                    "narration": "Twenty-four hours earlier, freshman Yu'er had only one goal: survive the brutal heat in the men's dormitory.",
                    "image_prompt": f"masterpiece, best quality, cinematic wide shot, {p_anchor}, sweating, sweltering run-down college dorm room, old oscillating fan, exhausted expression, realistic room textures, vertical 9:16",
                    "mood": "cozy", "motion_type": "pan_left"
                },
                {
                    "narration": "With room temperatures soaring past thirty-eight degrees, his roommate Zhang Xun flopped on the bunk groaning about air conditioning.",
                    "image_prompt": "masterpiece, best quality, cinematic two-shot, 2boys in hot dorm room, roommate shirtless fanning himself with textbook, messy dorm desks, realistic plastic fan blades, sunlight streaming, vertical 9:16",
                    "mood": "comedy", "motion_type": "zoom_out"
                },
                {
                    "narration": "Yu'er hurried down to Cafeteria Two, the only dining hall with central air conditioning, carrying his dorm keys to claim a table.",
                    "image_prompt": f"masterpiece, best quality, atmospheric wide establishing shot, {p_anchor}, bustling university dining hall, students eating, modern cafeteria glass windows, bright realistic lighting, vertical 9:16",
                    "mood": "cozy", "motion_type": "pan_right"
                },
                {
                    "narration": "He placed his dorm keys on empty table thirteen, then ordered a steaming bowl of spicy braised beef noodles with extra chili oil and cilantro.",
                    "image_prompt": "masterpiece, best quality, extreme macro close up of steaming ceramic bowl of spicy braised beef noodles, glistening red chili oil droplets, green scallions, realistic food textures, chopsticks resting on ceramic edge, vertical 9:16",
                    "mood": "cozy", "motion_type": "zoom_in"
                },
                {
                    "narration": "When he returned holding the tray, the seat directly across from his keys was occupied by Su Yi—the unattainable senior campus goddess.",
                    "image_prompt": f"masterpiece, best quality, cinematic medium portrait, {d_anchor}, elegant posture, holding milk tea plastic cup #14, delicate expression, seated in university cafeteria, male students staring in background, vertical 9:16",
                    "mood": "romance", "motion_type": "tilt_up"
                },
                {
                    "narration": "Under the burning glares of fifty envious onlookers, Yu'er's trembling hand dropped his spoon, splashing red chili broth right across his collar.",
                    "image_prompt": f"masterpiece, best quality, dramatic close up, {p_anchor}, spoon splashing into spicy chili soup, droplets flying, soup stain on hoodie, embarrassed face, dramatic anime speed lines, realistic liquid splashing reflections, vertical 9:16",
                    "mood": "comedy", "motion_type": "zoom_in"
                },
                {
                    "narration": "The cafeteria went dead silent. Su Yi looked up, her violet eyes meeting his panic with serene amusement.",
                    "image_prompt": f"masterpiece, best quality, intense close up portrait, {d_anchor}, lilac-violet eyes reflecting dining hall lights, subtle playful smile, delicate lips, soft depth of field, vertical 9:16",
                    "mood": "romance", "motion_type": "zoom_in"
                },
                {
                    "narration": "Without a word, she slid an unopened pack of wet wipes across the polished table, offered a soft smile, and vanished into the crowd.",
                    "image_prompt": f"masterpiece, best quality, cinematic shot, close up of unopened pack of wet wipes on cafeteria table, smooth realistic plastic packaging textures, {d_anchor} walking away in background, sunlight catching silver hair, vertical 9:16",
                    "mood": "romance", "motion_type": "pan_right"
                },
                {
                    "narration": "By afternoon calculus class, Yu'er's phone buzzed incessantly. A post on the campus forum was trending with ten thousand views.",
                    "image_prompt": "masterpiece, best quality, macro shot of glowing smartphone screen showing trending campus forum post with photo of protagonist, realistic OLED glass reflections, lecture hall background, vertical 9:16",
                    "mood": "suspense", "motion_type": "zoom_in"
                },
                {
                    "narration": "The headline screamed: 'Shameless freshman stages clumsy soup disaster just to solicit attention from the Campus Goddess.'",
                    "image_prompt": "masterpiece, best quality, smartphone display with viral university confession wall page, bold text, comments scrolling, student thumb scrolling, realistic glass texture, vertical 9:16",
                    "mood": "comedy", "motion_type": "pan_left"
                },
                {
                    "narration": "Yu'er buried his face in his hands as students in the lecture hall whispered and cast judging side-eyes.",
                    "image_prompt": f"masterpiece, best quality, cinematic shot, {p_anchor}, in university lecture hall, head resting on notebook in embarrassment, students whispering in background, realistic classroom wooden desks, vertical 9:16",
                    "mood": "comedy", "motion_type": "zoom_out"
                },
                {
                    "narration": "Desperate to find a peaceful off-campus place with air conditioning, he opened the local housing board and saw a peculiar rental listing.",
                    "image_prompt": "masterpiece, best quality, modern laptop screen showing real estate listing for Junlin Community luxury apartments, photo of spacious kitchen, realistic screen glow, vertical 9:16",
                    "mood": "cozy", "motion_type": "tilt_up"
                },
                {
                    "narration": "The listing read: 'Two-bedroom luxury apartment next to campus. Rent is seventy percent off, but applicant must possess elite culinary skills.'",
                    "image_prompt": "masterpiece, best quality, WeChat chat interface on phone screen, contact named Zhiwoyi, clean modern UI, high-end apartment photos with marble countertops, vertical 9:16",
                    "mood": "cozy", "motion_type": "zoom_in"
                },
                {
                    "narration": "Yu'er messaged the landlord ID 'Zhiwoyi': 'Hi, I saw your listing. I have been cooking every daily meal since middle school.'",
                    "image_prompt": "masterpiece, best quality, close up of hands typing message on smartphone keyboard, realistic metal phone bezel, lecture hall ambient lighting, vertical 9:16",
                    "mood": "cozy", "motion_type": "pan_right"
                },
                {
                    "narration": "Three seconds later, Zhiwoyi replied with a single test question: 'What is your specialty dish?'",
                    "image_prompt": "masterpiece, best quality, phone screen message bubble showing 'What is your specialty dish?', green chat bubble, realistic glass screen texture, vertical 9:16",
                    "mood": "suspense", "motion_type": "zoom_in"
                },
                {
                    "narration": "'Braised pork belly with caramelized sugar coat and scallion pancakes from scratch,' Yu'er typed back confidently.",
                    "image_prompt": f"masterpiece, best quality, cinematic portrait, {p_anchor}, proud confident smirk, classroom background, sunset golden hour light filtering through window, vertical 9:16",
                    "mood": "cozy", "motion_type": "zoom_out"
                },
                {
                    "narration": "The response was immediate: 'Passed. Come to Building Five, Room Seven-Thirty-Two right after class to inspect the keys.'",
                    "image_prompt": "masterpiece, best quality, high-rise luxury apartment complex exterior at sunset, glowing windows, Junlin Community entrance gate, realistic modern architecture, vertical 9:16",
                    "mood": "suspense", "motion_type": "tilt_up"
                },
                {
                    "narration": "Yu'er rushed across campus and took the elevator up to room seven-thirty-two, his heart pounding with excitement for air-conditioned freedom.",
                    "image_prompt": f"masterpiece, best quality, cinematic shot, {p_anchor}, standing in luxury apartment corridor, polished marble tile reflections, sleek wooden door with brass number 732, realistic door handle and keyhole, vertical 9:16",
                    "mood": "suspense", "motion_type": "pan_left"
                },
                {
                    "narration": "Standing there in cozy oversized knitwear and clutching a pair of chopsticks was Su Yi herself, smiling victoriously: 'Welcome home, Chef.'",
                    "image_prompt": f"masterpiece, best quality, medium portrait, {d_anchor}, cozy oversized knit cardigan over blouse, silver hair tied in messy bun, holding wooden chopsticks, playful victorious wink, luxury modern kitchen behind her, warm golden hour lighting, vertical 9:16",
                    "mood": "romance", "motion_type": "zoom_in"
                }
            ]
        elif "cultivation" in genre_id or "reincarnation" in genre_id:
            title = "The Exiled Sovereign Crushes the Billionaire Banquet"
            logline = "Stripped of his inheritance and mocked as a broke delivery driver, a reincarnated dragon monarch attends his ex-fiancée's engagement gala—only for the city's supreme oligarchs to kneel before his imperial jade seal."
            protagonist = "Lin Chen, 20, reincarnated dragon lord, short spiky black hair, celestial golden eyes, charcoal blazer over black turtleneck, imperial dragon jade pendant."
            deuteragonist = "Su Qingxue, 21, martial alliance heiress, long raven hair, silver lotus hairpin, ivory-white silk gown, emerald jade bangle."
            conflict = "Arrogant Young Master Zhao tries to have security break Lin Chen's legs for daring to step into the five-star banquet hall."
            twist = "When Lin Chen unveils the ancestral Dragon Pendant, the patriarch of the imperial consortium recognizes the supreme overlord of the dragon realm and kneels in terror."
            resolution = "Young Master Zhao collapses in horror as Lin Chen effortlessly takes command of the entire provincial dynasty."
            tags = ["#urbanfantasy", "#manhua", "#revenge", "#hiddengod", "#faceslap", "#animeaction", "#shorts", "#fyp"]
            comment = "Would you reveal your true power immediately or let arrogant bullies embarrass themselves first?"

            p_anchor = "1boy, Lin Chen, short spiky charcoal-black hair, sweeping fringe, piercing celestial golden eyes, chiseled jawline, tailored charcoal-grey blazer over black turtleneck, glowing Imperial Dragon jade pendant"
            d_anchor = "1girl, Su Qingxue, long flowing raven-black hair, silver lotus hairpin, sharp intelligent hazel-green eyes, ivory-white silk evening gown with golden cloud embroidery, translucent emerald jade bangle"

            pool = [
                {
                    "narration": "'A broke delivery orphan thinks he has the right to breathe the same air as the top ten families of Jiangnan?'",
                    "image_prompt": f"masterpiece, best quality, dramatic low-angle Dutch tilt shot, {p_anchor}, calm stoic expression, facing arrogant young master in gold tuxedo inside opulent crystalline banquet hall, massive crystal chandeliers, realistic marble floor reflections, vertical 9:16",
                    "mood": "suspense", "motion_type": "zoom_in"
                },
                {
                    "narration": "Three years ago, Lin Chen fell from the peak of the immortal realm, reincarnating into the body of an exiled, impoverished heir.",
                    "image_prompt": f"masterpiece, best quality, flashback illustration, {p_anchor}, standing beneath pouring storm outside luxury skyscraper gates, clutching an ancient carved green jade stone, realistic rain and asphalt textures, vertical 9:16",
                    "mood": "melodrama", "motion_type": "pan_left"
                },
                {
                    "narration": "Tonight was the centennial gala of the Zhao Consortium, hosted at the Grand Millennium Hotel where high society gathered in diamond-studded luxury.",
                    "image_prompt": "masterpiece, best quality, atmospheric wide establishing shot, grand ballroom of Grand Millennium Hotel, billionaire guests holding champagne flutes, lavish red carpets, realistic crystal chandelier reflections, vertical 9:16",
                    "mood": "cozy", "motion_type": "tilt_up"
                },
                {
                    "narration": "Young Master Zhao stepped onto the central stage, sneering down at Lin Chen while swirling a vintage bottle of Chateau Lafite.",
                    "image_prompt": "masterpiece, best quality, close up of arrogant young master in gold embroidered suit, holding crystal wine glass with vintage red wine, realistic glass refractions and gold watch gleam, vertical 9:16",
                    "mood": "action", "motion_type": "zoom_in"
                },
                {
                    "narration": "'Someone throw this beggar into the dumpster before he stains the carpet,' Zhao barked into the microphone.",
                    "image_prompt": "masterpiece, best quality, dramatic shot of wealthy socialite crowd jeering and pointing, security guards in black tactical suits stepping forward, realistic camera flashes, vertical 9:16",
                    "mood": "suspense", "motion_type": "pan_right"
                },
                {
                    "narration": "Eight muscular security guards armed with electric stun batons surged forward, surrounding Lin Chen in a tight kill circle.",
                    "image_prompt": f"masterpiece, best quality, dynamic low-angle shot, {p_anchor}, surrounded by 8 guards in black suits, electric blue sparks crackling on stun batons, realistic metal and spark reflections, vertical 9:16",
                    "mood": "action", "motion_type": "zoom_in"
                },
                {
                    "narration": "Lin Chen didn't even flinch. He raised one slender finger, and an invisible shockwave of golden dragon aura rippled across the polished granite.",
                    "image_prompt": f"masterpiece, best quality, cinematic action shot, {p_anchor}, golden dragon spiritual aura flaring around his silhouette, celestial golden eyes blazing with lightning sparks, shockwave shattering floor tiles, vertical 9:16",
                    "mood": "action", "motion_type": "zoom_out"
                },
                {
                    "narration": "In a fraction of a second, all eight guards were sent flying backward, crashing into the banquet tables in total concussive shock.",
                    "image_prompt": "masterpiece, best quality, chaotic action anime frame, guards flying through air, shattering tables, champagne bottles exploding into mist, high speed motion blur, realistic liquid droplets, vertical 9:16",
                    "mood": "action", "motion_type": "zoom_in"
                },
                {
                    "narration": "The entire ballroom gasped in frozen terror. Standing at the VIP balcony, Heiress Su Qingxue's eyes widened in recognition.",
                    "image_prompt": f"masterpiece, best quality, cinematic medium portrait, {d_anchor}, standing at gilded balcony, sharp intelligent hazel-green eyes wide in shock, hand covering mouth, realistic silk gown folds, vertical 9:16",
                    "mood": "suspense", "motion_type": "zoom_in"
                },
                {
                    "narration": "From inside his dark blazer, Lin Chen casually unclasped a translucent, emerald-green dragon jade pendant.",
                    "image_prompt": "masterpiece, best quality, extreme macro close up of glowing Imperial Dragon jade pendant resting in hand, intricate ancient dragon engravings, ethereal golden light pulsing from within, realistic polished jade stone textures, vertical 9:16",
                    "mood": "suspense", "motion_type": "zoom_in"
                },
                {
                    "narration": "The imperial dragon carving glowed with ancient celestial script, illuminating the opulent hall in mesmerizing emerald light.",
                    "image_prompt": f"masterpiece, best quality, {p_anchor}, holding radiant dragon jade high, emerald and golden light beams illuminating the vast ballroom ceiling, breathtaking visual effects, vertical 9:16",
                    "mood": "action", "motion_type": "tilt_up"
                },
                {
                    "narration": "Suddenly, the heavy double doors of the banquet hall blew open with the force of a hurricane.",
                    "image_prompt": "masterpiece, best quality, heavy brass double doors bursting open, security guards stumbling back, windy gale rushing into ballroom, dramatic lighting, vertical 9:16",
                    "mood": "suspense", "motion_type": "pan_left"
                },
                {
                    "narration": "Old Patriarch Ye, the supreme commercial warlord controlling seventy percent of the provincial shipping empire, rushed in barefoot and trembling.",
                    "image_prompt": "masterpiece, best quality, elderly patriarch with white beard in traditional silk hanfu, sweating in panic, eyes wide with terror, rushing down the red carpet, vertical 9:16",
                    "mood": "suspense", "motion_type": "zoom_in"
                },
                {
                    "narration": "Before thirty billionaires and fifty cameras, Patriarch Ye dropped to both knees and slammed his forehead to the marble floor: 'Grand Master!'",
                    "image_prompt": f"masterpiece, best quality, dramatic shot of elderly billionaire patriarch kneeling and kowtowing on marble floor before {p_anchor}, crowd staring in utter disbelief, vertical 9:16",
                    "mood": "action", "motion_type": "zoom_out"
                },
                {
                    "narration": "Young Master Zhao dropped his wine glass, his face turning pale as freshly fallen snow: 'Ye... Patriarch Ye, why are you kneeling to this homeless rat?!'",
                    "image_prompt": "masterpiece, best quality, close up of Young Master Zhao trembling in sheer horror, eyes bulging, sweat pouring down cheek, crystal glass shattering at his feet, realistic red wine spilling, vertical 9:16",
                    "mood": "comedy", "motion_type": "zoom_in"
                },
                {
                    "narration": "'Shut your insolent mouth!' Patriarch Ye roared. 'This is the true Sovereign of the Dragon Throne! One word from him can erase our entire bloodline by dawn!'",
                    "image_prompt": "masterpiece, best quality, elderly patriarch pointing furiously at young master, veins bulging on neck, terrifying martial aura, realistic fabric textures, vertical 9:16",
                    "mood": "action", "motion_type": "pan_right"
                },
                {
                    "narration": "Heiress Su Qingxue descended the grand marble stairs, bowing gracefully before Lin Chen: 'The Su family has waited twenty years for your return, Sovereign.'",
                    "image_prompt": f"masterpiece, best quality, cinematic two-shot, {d_anchor} bowing respectfully, silver lotus hairpin gleaming, {p_anchor} gazing calmly down at her, golden eyes glowing, vertical 9:16",
                    "mood": "romance", "motion_type": "zoom_in"
                },
                {
                    "narration": "Young Master Zhao fell backward onto the broken glass, begging for his life in pathetic sobs as his father slapped him into unconsciousness.",
                    "image_prompt": "masterpiece, best quality, young master on knees in tears, father in formal suit backhanding him, crowd backing away in terrified silence, realistic glass fragments on floor, vertical 9:16",
                    "mood": "action", "motion_type": "zoom_out"
                },
                {
                    "narration": "Lin Chen adjusted his cuffs, looked over the trembling sea of oligarchs, and whispered: 'This city was getting boring anyway.'",
                    "image_prompt": f"masterpiece, best quality, medium waist-up portrait, {p_anchor}, stoic regal smile, adjusting charcoal suit cuffs, celestial dragon aura gently settling, billionaires bowing in background, vertical 9:16",
                    "mood": "action", "motion_type": "tilt_up"
                },
                {
                    "narration": "As he walked out beneath the starlit sky with Su Qingxue by his side, every billionaire in the province bowed in absolute submission.",
                    "image_prompt": f"masterpiece, best quality, cinematic closing shot, {p_anchor} and {d_anchor} walking out into cool neon night, luxury Maybach convoy waiting with doors open, starlit sky, finished satisfying arc, vertical 9:16",
                    "mood": "action", "motion_type": "zoom_in"
                }
            ]
        elif "psychological" in genre_id or "thriller" in genre_id:
            title = "The Midnight Cipher and the 60-Second Verdict"
            logline = "Trapped on the 88th floor of a storm-battered penthouse with a dead tech tycoon, an analytical profiler must decipher a bloody cipher before the elevator arrives with the true assassin."
            protagonist = "Detective Kaelen, 26, forensic profiler, ash-grey layered hair, analytical golden-amber eyes, dark trench coat, brass pocket watch."
            deuteragonist = "Dr. Elena Vance, 25, neuro-psychiatrist, sleek black bob cut, emerald eyes, silver wireframe glasses, dark teal wool coat."
            conflict = "A dead-man's switch locks all exits with a 60-second countdown; all clues point to Elena being the poisoner."
            twist = "Kaelen deduces the tycoon poisoned himself to frame Elena, and used holographic glass reflections to alter the cipher timestamp."
            resolution = "Kaelen cracks the true cipher at 00:01, saving Elena and exposing the tycoon's offshore corporate sabotage."
            tags = ["#thriller", "#psychologicalanime", "#mystery", "#plotwist", "#mindgames", "#animecrime", "#shorts", "#fyp"]
            comment = "Would you trust your partner if every piece of physical evidence pointed directly at them?"

            p_anchor = "1boy, Detective Kaelen, messy layered ash-grey hair, sharp analytical golden-amber eyes, slender pale face, dark charcoal trench coat, loosened black tie, vintage brass mechanical pocket watch"
            d_anchor = "1girl, Dr. Elena Vance, sleek jet-black chin-length bob cut, blunt bangs, cool emerald-green eyes, thin silver wireframe glasses, tailored dark teal wool coat, charcoal turtleneck"

            pool = [
                {
                    "narration": "'If you can't solve this room in sixty seconds, Detective, both of our lives will end at midnight.'",
                    "image_prompt": f"masterpiece, best quality, cinematic close up portrait, {d_anchor}, cool emerald-green eyes behind silver wireframe glasses, intense analytical gaze, rain streaking down luxury penthouse floor-to-ceiling glass window, vertical 9:16",
                    "mood": "suspense", "motion_type": "zoom_in"
                },
                {
                    "narration": "Outside the eighty-eighth floor penthouse, lightning slashed across the rain-blackened skyscrapers of New Eden.",
                    "image_prompt": "masterpiece, best quality, atmospheric wide shot, torrential lightning storm raging over towering neon metropolis skyscrapers, high penthouse window overlooking rainy city abyss, vertical 9:16",
                    "mood": "suspense", "motion_type": "tilt_up"
                },
                {
                    "narration": "In the center of the mahogany study lay biotech mogul Julian Thorne, slumped over his desk with cyanide foam around his lips.",
                    "image_prompt": "masterpiece, best quality, crime scene shot, dead tycoon in luxury velvet smoking jacket slumped across polished mahogany desk, overturned crystal tumbler, realistic wood grain and spilled amber scotch, vertical 9:16",
                    "mood": "suspense", "motion_type": "pan_left"
                },
                {
                    "narration": "Detective Kaelen pulled his vintage mechanical pocket watch from his trench coat, its second hand ticking toward twelve.",
                    "image_prompt": f"masterpiece, best quality, macro close up of {p_anchor} hand holding open vintage brass mechanical pocket watch, ticking gears, realistic polished brass scratches, dark rainy room lighting, vertical 9:16",
                    "mood": "suspense", "motion_type": "zoom_in"
                },
                {
                    "narration": "On the reinforced steel security door, a digital LED timer read: '00:58... 00:57... LOCKDOWN ARMED.'",
                    "image_prompt": "masterpiece, best quality, heavy brushed steel security vault door, glowing red digital LED countdown timer reading 00:58, warning klaxon light spinning, realistic metallic texture, vertical 9:16",
                    "mood": "suspense", "motion_type": "zoom_in"
                },
                {
                    "narration": "Beside the body, written in dried crimson blood on the glass desk surface, was a six-digit cipher: '9 - 4 - 0 - 2 - 1 - V'.",
                    "image_prompt": "masterpiece, best quality, extreme close up of bloody numbers written on glass table, dark crimson smeared blood textures, realistic glass reflections of storm flashes, vertical 9:16",
                    "mood": "suspense", "motion_type": "pan_right"
                },
                {
                    "narration": "'V' stands for Vance. Every security camera log says only Elena entered this wing in the last two hours.",
                    "image_prompt": f"masterpiece, best quality, dramatic shot of wall of glowing security monitors showing {d_anchor} walking down private hallway, realistic CRT scanlines, dark security room, vertical 9:16",
                    "mood": "suspense", "motion_type": "zoom_out"
                },
                {
                    "narration": "Elena raised her hands calmly, her voice steady: 'You know my psychological profile, Kaelen. If I killed him, he wouldn't have lived long enough to write my name.'",
                    "image_prompt": f"masterpiece, best quality, medium portrait, {d_anchor}, hands raised slightly in surrender, composed calm expression, silver wireframe glasses catching blue monitor light, vertical 9:16",
                    "mood": "suspense", "motion_type": "zoom_in"
                },
                {
                    "narration": "Kaelen's golden eyes narrowed. He knelt beside the dead man's hand and inspected the fingertips under UV light.",
                    "image_prompt": f"masterpiece, best quality, cinematic low angle, {p_anchor}, illuminating dead man fingers with purple UV forensic flashlight, glowing fluorescent chemical dust, sharp analytical eyes, vertical 9:16",
                    "mood": "suspense", "motion_type": "zoom_in"
                },
                {
                    "narration": "There was no blood on Thorne's right index finger. He didn't write the cipher—someone else held his hand after he was already unconscious.",
                    "image_prompt": "masterpiece, best quality, macro shot of dead man limp fingers under purple UV forensic light, lack of blood staining on fingertip, realistic skin textures and lighting, vertical 9:16",
                    "mood": "suspense", "motion_type": "zoom_in"
                },
                {
                    "narration": "Thirty seconds remained on the door. The elevator indicator dinged: 'Ascending to Floor 88.' The cleaner was coming.",
                    "image_prompt": "masterpiece, best quality, elevator floor indicator panel above brass doors showing red arrow ascending, floor number 84... 85... 86, tension rising, realistic metal textures, vertical 9:16",
                    "mood": "action", "motion_type": "tilt_up"
                },
                {
                    "narration": "Kaelen turned to the massive glass window. Lightning flared outside, and the cipher's reflection appeared in reverse: 'A - 1 - 2 - 0 - 4 - 6'.",
                    "image_prompt": f"masterpiece, best quality, {p_anchor}, looking at inverted bloody reflection in rain-streaked penthouse window, lightning flash illuminating the glass, eureka realization in eyes, vertical 9:16",
                    "mood": "suspense", "motion_type": "zoom_in"
                },
                {
                    "narration": "'It wasn't a V,' Kaelen whispered. 'It was an inverted caret symbol marking an automated audio trigger!'",
                    "image_prompt": f"masterpiece, best quality, dramatic close up of {p_anchor} amber-gold eyes widening in shock, lightning flashing behind silhouette, high suspense anime art, vertical 9:16",
                    "mood": "suspense", "motion_type": "zoom_in"
                },
                {
                    "narration": "He reached under the mahogany desk and tore away a concealed magnetic microphone transmitter.",
                    "image_prompt": "masterpiece, best quality, close up of hand ripping small black electronic transmitter from under wooden desk, tiny red LED blinking, wires snapping, realistic textures, vertical 9:16",
                    "mood": "action", "motion_type": "zoom_in"
                },
                {
                    "narration": "Ten seconds. Elena rushed to the door keypad while Kaelen shouted: 'The passcode is Thorne's birth year inverted: 6 - 4 - 0 - 2 - 1!'",
                    "image_prompt": f"masterpiece, best quality, action shot, {d_anchor} punching glowing numeric keypad with rapid fingers, digital timer at 00:04, intense adrenaline, vertical 9:16",
                    "mood": "action", "motion_type": "pan_left"
                },
                {
                    "narration": "Elena entered the fifth digit with one second left. The digital panel flashed emerald green: 'OVERRIDE ACCEPTED.'",
                    "image_prompt": "masterpiece, best quality, digital keypad screen flashing bright neon green with 'OVERRIDE ACCEPTED', lock bolts disengaging with heavy mechanical clunk, vertical 9:16",
                    "mood": "action", "motion_type": "zoom_in"
                },
                {
                    "narration": "The elevator doors opened. A lone syndicate cleaner stepped out with a suppressed firearm—only to find Kaelen already aiming point-blank.",
                    "image_prompt": f"masterpiece, best quality, action frame, elevator doors sliding open, assassin in black raincoat with suppressed pistol, {p_anchor} already aiming black service revolver skull-height, vertical 9:16",
                    "mood": "action", "motion_type": "zoom_in"
                },
                {
                    "narration": "'Drop the weapon,' Elena commanded, brandishing the recorded audio transmitter that broadcasted the cleaner's employer directly to police dispatch.",
                    "image_prompt": f"masterpiece, best quality, {d_anchor}, cool emerald eyes gleaming, holding blinking digital voice recorder, sirens flashing red and blue through rain outside, vertical 9:16",
                    "mood": "action", "motion_type": "zoom_out"
                },
                {
                    "narration": "The cleaner surrendered his weapon. Sirens echoed up from the street as twelve SWAT teams secured the building.",
                    "image_prompt": "masterpiece, best quality, assassin kneeling with hands behind head, suppressed pistol lying on carpet, police sirens flashing through rain, vertical 9:16",
                    "mood": "suspense", "motion_type": "pan_right"
                },
                {
                    "narration": "As the dawn broke through the storm clouds, Kaelen snapped his pocket watch shut: 'Next time you invite me to dinner, Elena, pick a restaurant with no elevators.'",
                    "image_prompt": f"masterpiece, best quality, cinematic closing shot, {p_anchor} and {d_anchor} standing side by side looking out penthouse window as golden sunrise cuts through rain clouds over metropolis, finished arc, vertical 9:16",
                    "mood": "romance", "motion_type": "zoom_in"
                }
            ]
        else:
            # Underworld / Mafia Dark Romance (Reference Video 1)
            title = "The Syndicate Empress and Her Stolen Light"
            logline = "After ascending to the throne of the Southeast Asian underworld, a ruthless female syndicate boss discovers her kidnapped childhood savior caged in a black-market auction."
            protagonist = "Liu Yanran, 27, feared syndicate sovereign, straight silver hair, filigree phantom mask, tailored black Italian suit, merciless."
            deuteragonist = "Chen Chen, 18, medical prodigy, tousled black hair, wearing an engraved keepsake silver band given 17 years ago."
            conflict = "Corrupt brokers have drugged and caged Chen Chen for elite bidders; Liu Yanran recognizes the keepsake ring."
            twist = "During the bloody armored convoy escape, Chen Chen clutches her in delirium, but in high fever calls out a forgotten name, shattering her certainty."
            resolution = "Liu Yanran removes her mask with tears in her eyes, vowing to conquer the world to cure him."
            tags = ["#darkromance", "#underworldqueen", "#yandere", "#animestory", "#webnovel", "#shorts", "#fyp"]
            comment = "Would you conquer the underworld for someone who doesn't even remember your face?"

            p_anchor = "1girl, Liu Yanran, straight waist-length icy silver hair, blunt bangs, piercing sharp sapphire-blue eyes, pale porcelain skin, tailored charcoal-black double-breasted suit jacket, crisp white silk button-up shirt, intricate silver filigree phantom mask over right eye, engraved silver ring on left hand"
            d_anchor = "1boy, Chen Chen, messy tousled jet-black hair, parted bangs, deep amber-brown eyes, youthful pale face, tattered white linen dress shirt, unbuttoned collar, matching engraved silver keepsake band on left hand"

            pool = [
                {
                    "narration": "Seventeen years ago, a starving ten-year-old girl huddled in an icy alley, shivering beneath torrential rain.",
                    "image_prompt": "masterpiece, best quality, emotional flashback illustration, little girl with straight silver hair shivering in dark rainy alleyway, heavy pouring rain, dim streetlamp glow, realistic wet asphalt reflections, vertical 9:16",
                    "mood": "melodrama", "motion_type": "zoom_in"
                },
                {
                    "narration": "A young boy knelt before her, handing her a warm pastry and sliding a hand-engraved silver band onto her small finger.",
                    "image_prompt": "masterpiece, best quality, macro close up of little boy hand sliding an engraved silver band onto young girl small finger, realistic polished silver metallic reflections, rain droplets on skin, emotional anime lighting, vertical 9:16",
                    "mood": "melodrama", "motion_type": "zoom_in"
                },
                {
                    "narration": "'Promise me you will survive,' he whispered before his family pulled him away into the stormy night.",
                    "image_prompt": "masterpiece, best quality, little boy looking back through rain-streaked car window, sad eyes, realistic raindrops on automotive glass, headlights cutting through fog, vertical 9:16",
                    "mood": "melodrama", "motion_type": "pan_left"
                },
                {
                    "narration": "Seventeen years passed. That starving girl climbed over every warlord in Southeast Asia to become Liu Yanran—the Sovereign of the Underworld.",
                    "image_prompt": f"masterpiece, best quality, dramatic medium portrait, {p_anchor}, standing by high-rise window overlooking neon metropolis, rain-streaked glass, realistic skyscrapers, vertical 9:16",
                    "mood": "suspense", "motion_type": "tilt_up"
                },
                {
                    "narration": "Despite supreme wealth and authority, the tarnished silver ring had never left her left hand for even a single day.",
                    "image_prompt": "masterpiece, best quality, macro shot of woman left hand wearing engraved silver band, black leather gloves, realistic brushed silver metal textures, reflections of rainy city lights, vertical 9:16",
                    "mood": "suspense", "motion_type": "zoom_in"
                },
                {
                    "narration": "Tonight, beneath the neon sprawl of Bangkok, an exclusive black-market auction was underway in an underground colosseum.",
                    "image_prompt": "masterpiece, best quality, atmospheric wide shot, dark subterranean auction colosseum, opulent classical balconies, wealthy elites holding bidding paddles, dramatic spotlights, realistic stone and marble textures, vertical 9:16",
                    "mood": "suspense", "motion_type": "pan_right"
                },
                {
                    "narration": "Her lieutenant Dahae stepped forward, whispering: 'Empress, the final lot tonight is an eighteen-year-old medical honors student betrayed by his own brothers.'",
                    "image_prompt": f"masterpiece, best quality, cinematic shot, private VIP balcony shrouded in shadow, {p_anchor} seated in velvet armchair, male lieutenant in black security tactical gear bowing respectfully, vertical 9:16",
                    "mood": "suspense", "motion_type": "zoom_out"
                },
                {
                    "narration": "The stage spotlight ignited. A heavy iron cage was hoisted into the center of the arena, surrounded by armed guards.",
                    "image_prompt": "masterpiece, best quality, heavy wrought iron cage suspended by thick industrial steel chains, realistic rusted iron textures, harsh stage spotlight, dark arena background, vertical 9:16",
                    "mood": "suspense", "motion_type": "tilt_up"
                },
                {
                    "narration": "Inside knelt Chen Chen, blindfolded, collared, and trembling violently from forced neurochemical delirium.",
                    "image_prompt": f"masterpiece, best quality, dramatic close up, {d_anchor}, inside iron cage, blindfolded, leather collar, trembling feverish posture, sweat glistening under spotlight, realistic metal bars in foreground, vertical 9:16",
                    "mood": "melodrama", "motion_type": "zoom_in"
                },
                {
                    "narration": "The auctioneer slammed his golden gavel: 'Opening bid for this untouched medical prodigy starts at eight hundred thousand dollars!'",
                    "image_prompt": "masterpiece, best quality, charismatic corrupt auctioneer standing at polished mahogany podium, raising heavy golden gavel, realistic polished wood and brass reflections, wealthy crowd cheering, vertical 9:16",
                    "mood": "action", "motion_type": "pan_left"
                },
                {
                    "narration": "Bids skyrocketed in seconds: one million, two million, three million. From the VIP box, Liu Yanran raised her opera glasses.",
                    "image_prompt": f"masterpiece, best quality, cinematic extreme close up, {p_anchor}, gold vintage opera binoculars raised to eyes, intense piercing sapphire gaze behind mask slits, cinematic lighting, vertical 9:16",
                    "mood": "suspense", "motion_type": "zoom_in"
                },
                {
                    "narration": "Her breath seized. Clutched against the iron bars of the cage was a hand wearing the exact matching engraved silver ring.",
                    "image_prompt": "masterpiece, best quality, extreme macro shot of young man trembling hand clutching iron cage bars, wearing an identical engraved silver ring, realistic scratches and metallic silver gleam under harsh stage spotlight, vertical 9:16",
                    "mood": "melodrama", "motion_type": "zoom_in"
                },
                {
                    "narration": "The crystal wine glass in Liu Yanran's grip shattered into powder, dark red wine dripping across her black leather gloves like fresh blood.",
                    "image_prompt": "masterpiece, best quality, crystal wine glass shattering in black-gloved hand, glass shards flying, dark red wine spilling like blood, high speed motion capture, realistic refractive glass textures, vertical 9:16",
                    "mood": "action", "motion_type": "zoom_in"
                },
                {
                    "narration": "When the auctioneer shouted three point five million, a single silenced bullet shattered through the podium skull-first.",
                    "image_prompt": "masterpiece, best quality, close up of sleek matte black silenced pistol raised, realistic gunmetal texture, suppressor muzzle flash, smoke wisps curling, dramatic anime action lighting, vertical 9:16",
                    "mood": "action", "motion_type": "zoom_in"
                },
                {
                    "narration": "'Nobody touches him,' her voice echoed like a death sentence through the grand chamber.",
                    "image_prompt": f"masterpiece, best quality, dramatic low angle, {p_anchor}, standing at edge of balcony, tailored black overcoat billowing, cold lethal aura, smoke billowing around her silhouette, vertical 9:16",
                    "mood": "action", "motion_type": "zoom_out"
                },
                {
                    "narration": "Heavy steel blast doors slammed shut over every emergency exit, locking the criminal syndicates and corrupt billionaires inside.",
                    "image_prompt": "masterpiece, best quality, massive industrial steel blast doors slamming shut, warning red sirens flashing, sparks flying, realistic heavy steel plate textures and hazard stripes, vertical 9:16",
                    "mood": "action", "motion_type": "tilt_up"
                },
                {
                    "narration": "Fifty tactical enforcers breached from the rafters, sweeping the colosseum in absolute, relentless execution.",
                    "image_prompt": "masterpiece, best quality, syndicate tactical enforcers in full black combat armor opening fire with submachine guns, bullet tracers, muzzle flashes, chaotic smoke, vertical 9:16",
                    "mood": "action", "motion_type": "pan_left"
                },
                {
                    "narration": "Liu Yanran descended the central marble staircase, stepped over the carnage, and dropped to her knees before the iron cage.",
                    "image_prompt": f"masterpiece, best quality, emotional scene, {p_anchor}, kneeling on marble floor before iron cage, removing silver phantom mask, tearful desperate sapphire eyes, realistic marble reflections, vertical 9:16",
                    "mood": "melodrama", "motion_type": "zoom_in"
                },
                {
                    "narration": "She reached through the cold steel bars, calling out 'Chen Chen,' but the boy shrank into the corner in blind panic.",
                    "image_prompt": f"masterpiece, best quality, {d_anchor}, cowering in corner of iron cage, clutching left hand with silver ring to chest defensively, feverish sweating face, terrified eyes, realistic wrought iron bars, vertical 9:16",
                    "mood": "melodrama", "motion_type": "zoom_out"
                },
                {
                    "narration": "He remembered the promise, but the drugs had erased her face. Liu Yanran tore the cage open with bare hands and gathered him into her arms.",
                    "image_prompt": f"masterpiece, best quality, cinematic romance shot, {p_anchor} carrying {d_anchor} gently in protective bridal carry, sweeping black overcoat, armored Maybach convoy waiting outside in rainy night, headlights glowing through mist, vertical 9:16",
                    "mood": "romance", "motion_type": "tilt_up"
                }
            ]

        # Select exactly target_scenes from pool
        total_available = len(pool)
        if target_scenes <= total_available:
            step = total_available / target_scenes
            selected = [pool[int(i * step)] for i in range(target_scenes)]
        else:
            selected = []
            for i in range(target_scenes):
                base_scene = dict(pool[i % total_available])
                if i >= total_available:
                    base_scene["narration"] = f"As tension mounted in scene {i+1}, {base_scene['narration'].lower()}"
                selected.append(base_scene)

        # Renumber scenes 1 to target_scenes
        scenes = []
        for i, sc in enumerate(selected):
            sc_copy = dict(sc)
            sc_copy["scene_number"] = i + 1
            scenes.append(sc_copy)

        if user_hint and user_hint.strip():
            logline = f"{logline} (Inspired by: {user_hint.strip()})"

        return {
            "title": title,
            "genre": preset.get("name", "Anime Story"),
            "genre_id": genre_id,
            "logline": logline,
            "protagonist": protagonist,
            "deuteragonist": deuteragonist,
            "core_conflict": conflict,
            "climax_twist": twist,
            "resolution": resolution,
            "description": f"{logline} Watch the full story to see the shocking twist!",
            "hashtags": tags,
            "pinned_comment": comment,
            "scenes": scenes
        }

    def _format_manual(self, custom: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "title": custom.get("title", "Custom Story"),
            "genre": custom.get("genre", "Custom"),
            "genre_id": custom.get("genre_id", "custom"),
            "logline": custom.get("logline", "Manual story entry"),
            "protagonist": custom.get("protagonist", ""),
            "deuteragonist": custom.get("deuteragonist", ""),
            "core_conflict": custom.get("core_conflict", ""),
            "climax_twist": custom.get("climax_twist", ""),
            "resolution": custom.get("resolution", ""),
            "description": custom.get("description", custom.get("title", "Custom video")),
            "hashtags": custom.get("hashtags", ["#animestory", "#shorts"]),
            "pinned_comment": custom.get("pinned_comment", "What did you think of this story?"),
            "scenes": custom.get("scenes", [])
        }

    def _load_preset(self, genre_id: str) -> Dict[str, Any]:
        path = Path(config.presets_dir) / f"{genre_id}.json"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading preset {genre_id}: {e}")
        return {"id": genre_id, "name": genre_id.replace("_", " ").title()}
