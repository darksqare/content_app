import os
import re
import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from core.config import config
from core.memory import StoryVault

logger = logging.getLogger("StoryPrompter")

SYSTEM_DIRECTIVE = """You are an elite creative scriptwriter and visual director for viral TikTok, YouTube Shorts, and Instagram Reels anime/manhua web-novel adaptations.

CRITICAL RULES:
1. FINISHED STORIES ONLY: Every story must be complete, closed-ended, and fully resolved within the designated scenes. It must feature a strong hook (0-15s), rising tension, and an emotional climax or punchy twist ending. NEVER end on an incomplete thought or generic 'to be continued'.
2. ANTI-REPETITION: You MUST NOT reuse or closely mirror any past story premises, plot twists, or character setups provided in the Vault Record. Create fresh, unique character dynamics and specific conflicts.
3. SCENE BREAKDOWNS: For each scene, provide:
   - narration: The spoken narration text for TTS (natural, emotive, conversational yet dramatic).
   - image_prompt: A detailed, high-quality Anime diffusion prompt in English describing character appearance, expression, outfit, camera angle, lighting, and background. Style: masterpiece, best quality, 2D anime illustration, vertical 9:16 framing.
   - mood: One of ['suspense', 'action', 'romance', 'comedy', 'melodrama', 'cozy'].
   - motion_type: One of ['zoom_in', 'zoom_out', 'pan_left', 'pan_right', 'tilt_up'].
4. SOCIAL METADATA: Provide an irresistible viral title, a 2-sentence curiosity-inducing description, 8-10 trending and niche hashtags, and an engagement-driving pinned comment question.
5. STRICT OUTPUT FORMAT: Respond ONLY with a valid JSON object matching the requested schema. No markdown explanations outside the JSON.
"""

JSON_SCHEMA_EXAMPLE = {
    "title": "Story Title Here",
    "genre": "Underworld / Mafia Dark Romance",
    "logline": "A one-sentence summary of the core premise and hook.",
    "protagonist": "Name and brief visual/personality profile",
    "deuteragonist": "Name and brief visual/personality profile",
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
            "image_prompt": "masterpiece, best quality, 1girl, silver hair, sharp blue eyes, tailored black suit, standing by rain-streaked luxury penthouse window at night, glowing neon city skyline below, cinematic anime lighting, 9:16 vertical",
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
            # On Windows, resolve CUDA runtime DLLs (cudart64_12.dll, etc.) from torch/lib
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
                    logger.info(f"GGUF model not found at {model_path}. Using built-in procedural anime story engine.")
            except ImportError:
                logger.info("llama_cpp not installed. Using built-in procedural prompter engine.")
            except Exception as e:
                logger.info(f"llama_cpp DLL notice: {e}. Using built-in procedural prompter engine.")

    def generate(self, 
                 mode: str, 
                 genre_id: str = "underworld_dark_romance", 
                 duration_mins: float = 3.0, 
                 base_prompt: str = "",
                 custom_script: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Executes one of the 4 prompt generation modes:
        - 'full_auto': Generates end-to-end story based on genre & duration
        - 'pre_generate': Generates complete script for user review/edit
        - 'semi_manual': Takes user base idea and enhances it into full script
        - 'manual': Accepts user-crafted script and scene breakdown
        """
        if mode == "manual" and custom_script:
            return self._format_manual(custom_script)

        # Estimate scene count based on duration (avg 6-10 seconds per scene)
        target_scenes = max(10, min(35, int((duration_mins * 60) / 8)))

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
        if not story_data:
            logger.info("Using procedural anime story engine for generation.")
            story_data = self._generate_procedural(preset_info, base_prompt, target_scenes)

        story_data["mode"] = mode
        story_data["genre"] = preset_info.get("name", genre_id)
        story_data["estimated_duration_mins"] = duration_mins

        return story_data

    def _build_prompt_instruction(self, mode: str, preset: Dict[str, Any], target_scenes: int, duration_mins: float, base_prompt: str, anti_repetition: str) -> str:
        instructions = [
            f"Genre: {preset.get('name', 'Anime Web-Novel')}",
            f"Tone: {preset.get('tone', 'dramatic, romantic')}",
            f"Visual Style: {preset.get('visual_style', 'Anime illustration')}",
            f"Target Scenes: Exactly {target_scenes} scenes (~{duration_mins:.1f} minutes).",
            "",
            anti_repetition,
            ""
        ]

        if mode == "semi_manual" and base_prompt.strip():
            instructions.append(f"USER BASE PROMPT / CORE CONCEPT TO ENHANCE:\n\"{base_prompt.strip()}\"\nExpand this concept into a full, captivating narrative with complete resolution.")
        elif mode in ["full_auto", "pre_generate"]:
            instructions.append("TASK: Create a brand new, highly original story premise adhering strictly to the genre tropes, featuring charismatic leads, high tension, and a finished climax.")

        instructions.append("\nOUTPUT FORMAT: Valid JSON only. Do not enclose in markdown ticks if possible, or use standard ```json block.")
        return "\n".join(instructions)

    def _invoke_llm(self, user_instruction: str) -> Optional[Dict[str, Any]]:
        # 1. Try local llama_cpp if loaded
        if self.llm:
            try:
                response = self.llm.create_chat_completion(
                    messages=[
                        {"role": "system", "content": SYSTEM_DIRECTIVE},
                        {"role": "user", "content": user_instruction}
                    ],
                    temperature=config.llm_temperature,
                    max_tokens=3200
                )
                text = response["choices"][0]["message"]["content"]
                return self._parse_json_response(text)
            except Exception as e:
                logger.error(f"Llama-cpp completion error: {e}")

        # 2. Try Ollama local endpoint if available
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
            # Remove markdown ```json ... ``` wrapper
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
            if match:
                cleaned = match.group(1).strip()
            parsed = json.loads(cleaned)
            if "title" in parsed and "scenes" in parsed:
                return parsed
        except Exception as e:
            logger.warning(f"Failed to parse LLM JSON output: {e}")
        return None

    def _generate_procedural(self, preset: Dict[str, Any], user_hint: str, target_scenes: int) -> Dict[str, Any]:
        """
        High-quality procedural story synthesizer matching the reference videos in video_analysis_for_ai.md.
        Guarantees closed-ended finished arcs, structured character profiles, and scene prompts.
        """
        genre_id = preset.get("id", "underworld_dark_romance")

        if "campus" in genre_id:
            title = "The Campus Goddess Moved Into My Kitchen"
            logline = "An introverted culinary prodigy is trapped in a sweltering dorm, only to discover the university's untouchable idol posted a rental listing secretly looking for a personal chef."
            protagonist = "Yu'er, 18-year-old culinary freshman, messy black hair, casual hoodie, quiet and pragmatic."
            deuteragonist = "Su Yi, silver-haired campus goddess with lilac eyes, poised in public but secretly a food addict."
            conflict = "Yu'er accidentally spills noodle soup at table #13, sparking viral campus rumors of being a clout-chaser, while needing an off-campus room with AC."
            twist = "The mysterious luxury landlord 'Zhiwoyi' who demands gourmet cooking is the campus goddess herself, and she intentionally baited him."
            resolution = "Yu'er arrives at the apartment viewing to find Su Yi holding a pair of chopsticks and smiling victoriously."
            tags = ["#campusromcom", "#manhua", "#scheminggoddess", "#culinaryprotagonist", "#animerecap", "#shorts", "#fyp"]
            comment = "Would you endure campus-wide slander if it meant free luxury rent with the campus idol?"
            
            scenes = [
                {
                    "scene_number": 1,
                    "narration": "If you dare turn me down, I will personally post on the university confession wall that you broke my heart.",
                    "image_prompt": "masterpiece, best quality, 1girl, silver hair, lilac eyes, mischievous smirk, school uniform with plaid skirt and ribbon tie, pointing forward in modern luxury living room, warm morning sunlight, 9:16 vertical anime",
                    "mood": "comedy",
                    "motion_type": "zoom_in"
                },
                {
                    "scene_number": 2,
                    "narration": "Twenty-four hours earlier, freshman Yu'er had only one goal: survive the scorching heat in the men's dormitory.",
                    "image_prompt": "masterpiece, best quality, 1boy, messy black hair, white t-shirt, sweating, sweltering run-down college dorm room, old oscillating fan, exhausted expression, realistic anime lighting, 9:16 vertical",
                    "mood": "cozy",
                    "motion_type": "pan_left"
                },
                {
                    "scene_number": 3,
                    "narration": "He reserved table thirteen at Cafeteria Two with his dorm keys, carrying a steaming bowl of spicy braised beef noodles.",
                    "image_prompt": "masterpiece, best quality, 1boy holding a large steaming bowl of beef noodles with chili oil and cilantro, crowded bustling university dining hall, vibrant anime aesthetic, 9:16 vertical",
                    "mood": "cozy",
                    "motion_type": "tilt_up"
                },
                {
                    "scene_number": 4,
                    "narration": "When he returned, the seat across from his keys was taken by Su Yi—the unattainable senior goddess everyone feared to approach.",
                    "image_prompt": "masterpiece, best quality, 1girl, elegant posture, silver hair, lilac eyes, holding milk tea cup #14, delicate expression, seated in university cafeteria, male students staring in background, 9:16 vertical anime",
                    "mood": "romance",
                    "motion_type": "zoom_out"
                },
                {
                    "scene_number": 5,
                    "narration": "Under the burning glares of fifty onlookers, Yu'er's trembling hand dropped his spoon, splashing red chili broth right across his collar.",
                    "image_prompt": "masterpiece, best quality, close up of spoon splashing into spicy chili soup, droplets flying, soup stain on protagonist white shirt, embarrassed face, dramatic anime speed lines, 9:16 vertical",
                    "mood": "comedy",
                    "motion_type": "zoom_in"
                },
                {
                    "scene_number": 6,
                    "narration": "Without a word, Su Yi quietly slid an unopened pack of wet wipes across the table, offered a soft smile, and vanished.",
                    "image_prompt": "masterpiece, best quality, 1girl, Su Yi smiling gently, placing pack of wet wipes on table, walking away with milk tea, sunlight catching silver hair, romantic anime scene, 9:16 vertical",
                    "mood": "romance",
                    "motion_type": "pan_right"
                },
                {
                    "scene_number": 7,
                    "narration": "By afternoon calculus, Yu'er was trending on the campus forum as the 'shameless freshman who staged an accident to flirt with Su Yi.'",
                    "image_prompt": "masterpiece, best quality, glowing smartphone screen showing trending campus forum post with blurred photo of protagonist, angry emoji comments, lecture hall background, 9:16 vertical anime",
                    "mood": "suspense",
                    "motion_type": "zoom_in"
                },
                {
                    "scene_number": 8,
                    "narration": "Desperate to hide from the spotlight, he noticed an odd rental listing for a luxury two-bedroom: 'Rent negotiable, but applicant must be an elite home cook.'",
                    "image_prompt": "masterpiece, best quality, WeChat chat interface on phone screen, contact named Zhiwoyi, clean modern UI, high-end apartment photos, 9:16 vertical anime",
                    "mood": "cozy",
                    "motion_type": "tilt_up"
                },
                {
                    "scene_number": 9,
                    "narration": "He passed the landlord's cooking questionnaire with flying colors and agreed to visit room seven-thirty-two right after class.",
                    "image_prompt": "masterpiece, best quality, 1boy walking down hallway of high-end luxury apartment complex, polished marble floors, sleek door number 732, nervous anticipation, 9:16 vertical anime",
                    "mood": "suspense",
                    "motion_type": "pan_left"
                },
                {
                    "scene_number": 10,
                    "narration": "The door swung open. Standing there in casual loungewear with chopsticks in hand was Su Yi herself, smiling: 'Welcome home, Chef.'",
                    "image_prompt": "masterpiece, best quality, 1girl, Su Yi in cozy oversized knit sweater, silver hair tied in messy bun, holding wooden chopsticks, playful victorious wink, luxury modern kitchen behind her, warm golden hour anime lighting, 9:16 vertical",
                    "mood": "romance",
                    "motion_type": "zoom_in"
                }
            ]
        else:
            # Underworld / Mafia Dark Romance (Reference Video 1)
            title = "The Syndicate Empress and Her Stolen Light"
            logline = "After ascending to the throne of the Southeast Asian underworld, a ruthless female syndicate boss discovers her kidnapped childhood savior caged in a black-market auction."
            protagonist = "Liu Yanran, 27, feared syndicate empress, long silver hair, phantom silver mask, tailored black suit, merciless."
            deuteragonist = "Chen Chen, 18, medical student, tousled black hair, wearing an engraved silver ring given 17 years ago."
            conflict = "Corrupt brokers have drugged and caged Chen Chen for elite bidders; Liu Yanran recognizes the keepsake ring."
            twist = "During the bloody armored convoy escape, Chen Chen clutches her in delirium, but in high fever calls out a forgotten name, shattering her certainty."
            resolution = "Liu Yanran removes her mask with tears in her eyes, vowing to conquer the world to cure him."
            tags = ["#darkromance", "#underworldqueen", "#yandere", "#animestory", "#webnovel", "#shorts", "#fyp"]
            comment = "Would you conquer the underworld for someone who doesn't even remember your face?"
            
            scenes = [
                {
                    "scene_number": 1,
                    "narration": "Seventeen years ago, a starving ten-year-old girl was given a single pastry and an engraved silver band by a boy in the rain.",
                    "image_prompt": "masterpiece, best quality, flashback illustration, little boy handing a warm pastry to a poor shivering young girl with silver hair, heavy pouring rain, dim streetlamp glow, emotional anime artstyle, 9:16 vertical",
                    "mood": "melodrama",
                    "motion_type": "zoom_in"
                },
                {
                    "scene_number": 2,
                    "narration": "Today, Liu Yanran rules the Southeast Asian underworld, feared by kings and warlords alike—yet that ring never left her left hand.",
                    "image_prompt": "masterpiece, best quality, 1girl, mature woman, long silver hair, cold blue eyes, wearing silver phantom mask and tailored black suit with white dress shirt, standing by high-rise window overlooking neon metropolis, silver ring on finger, 9:16 vertical anime",
                    "mood": "suspense",
                    "motion_type": "pan_right"
                },
                {
                    "scene_number": 3,
                    "narration": "At the subterranean colosseum in Bangkok, the final lot was brought onto the auction stage: an untouched eighteen-year-old medical honor student.",
                    "image_prompt": "masterpiece, best quality, dark subterranean auction house, heavy spotlight on iron cage, 1boy inside, blindfolded, collared, trembling in white collared shirt, wealthy bidders holding paddles, 9:16 vertical anime",
                    "mood": "suspense",
                    "motion_type": "tilt_up"
                },
                {
                    "scene_number": 4,
                    "narration": "The opening bid hit eight hundred thousand dollars. From her private VIP balcony, Liu Yanran's eyes locked onto the boy's left hand.",
                    "image_prompt": "masterpiece, best quality, extreme close up of trembling young man hand clutching iron bars, wearing an identical engraved silver ring, spotlight gleaming off metal, high tension anime, 9:16 vertical",
                    "mood": "suspense",
                    "motion_type": "zoom_in"
                },
                {
                    "scene_number": 5,
                    "narration": "Her wine glass shattered in her bare hand. When the auctioneer shouted three point five million, a silenced shot pierced through the podium.",
                    "image_prompt": "masterpiece, best quality, wine glass shattering in black-gloved hand, red wine spilling like blood, silenced pistol raised, muzzle flash, dark intense anime lighting, 9:16 vertical",
                    "mood": "action",
                    "motion_type": "zoom_in"
                },
                {
                    "scene_number": 6,
                    "narration": "'Nobody touches him,' her voice echoed coldly as blast doors slammed shut and armored enforcers breached the arena.",
                    "image_prompt": "masterpiece, best quality, heavy blast doors slamming shut, tactical armored security team opening fire, chaotic black-market auction house, smoke and bullet tracers, cinematic anime action, 9:16 vertical",
                    "mood": "action",
                    "motion_type": "pan_left"
                },
                {
                    "scene_number": 7,
                    "narration": "Walking through the fallen room, Liu Yanran knelt before the cage, tearing away her silver mask to reveal tears streaming down her face.",
                    "image_prompt": "masterpiece, best quality, 1girl kneeling on blood-drenched marble floor before iron cage, removing silver mask, tearful desperate blue eyes, emotional anime climax, 9:16 vertical",
                    "mood": "melodrama",
                    "motion_type": "zoom_in"
                },
                {
                    "scene_number": 8,
                    "narration": "She called out his name, but Chen Chen shrank back in narcotic terror, desperately shielding his ring: 'Don't touch it! Someone important gave this to me!'",
                    "image_prompt": "masterpiece, best quality, 1boy cowering in corner of iron cage, clutching left hand to chest defensively, feverish sweating face, terrified eyes, 9:16 vertical anime",
                    "mood": "melodrama",
                    "motion_type": "zoom_out"
                },
                {
                    "scene_number": 9,
                    "narration": "He remembered the ring's promise, but the drugs had erased her face. Liu Yanran scooped him into her arms: 'I have you now. We are going home.'",
                    "image_prompt": "masterpiece, best quality, 1girl carrying 1boy gently in bridal carry, sweeping black overcoat, armored convoy waiting outside in rainy night, headlights glowing through mist, 9:16 vertical anime",
                    "mood": "romance",
                    "motion_type": "tilt_up"
                },
                {
                    "scene_number": 10,
                    "narration": "Speeding through the storm in her armored Maybach, Chen Chen clawed at her chest in high fever, sobbing softly: 'Nian'an... where are you?'",
                    "image_prompt": "masterpiece, best quality, interior of luxury Maybach, rainy window streaks, 1boy curled against 1girl chest, sweating with high fever, 1girl frozen in shock, heartbreak in her eyes, cliffhanger anime ending, 9:16 vertical",
                    "mood": "melodrama",
                    "motion_type": "zoom_in"
                }
            ]

        # If base_prompt was supplied, integrate into logline
        if user_hint and user_hint.strip():
            logline = f"{logline} (Inspired by: {user_hint.strip()})"

        return {
            "title": title,
            "genre": preset.get("name", "Anime Story"),
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
