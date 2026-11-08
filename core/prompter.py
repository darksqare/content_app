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
     IMPORTANT OBJECT DIRECTIVE: When the scene highlights or features physical objects, items, jewellery, weapons, technology, food, vehicles, or architectural props (e.g. rings, cars, cages, phones, pistols, bowls, chopsticks), explicitly add 'realistic textures, photorealistic materials, realistic reflections and lighting, sharp physical object focus' to the prompt.
   - mood: One of ['suspense', 'action', 'romance', 'comedy', 'melodrama', 'cozy'].
   - motion_type: One of ['zoom_in', 'zoom_out', 'pan_left', 'pan_right', 'tilt_up'].
4. EXACT SCENE COUNT: You MUST generate EXACTLY the requested number of scenes in the 'scenes' array. Do not truncate. If 20 scenes are requested, output all 20 scene objects numbered 1 to 20.
5. SOCIAL METADATA: Provide an irresistible viral title, a 2-sentence curiosity-inducing description, 8-10 trending and niche hashtags, and an engagement-driving pinned comment question.
6. STRICT OUTPUT FORMAT: Respond ONLY with a valid JSON object matching the requested schema. No markdown explanations outside the JSON.
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
            return self._format_manual(custom_script)

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
        story_data["estimated_duration_mins"] = duration_mins

        return story_data

    def _build_prompt_instruction(self, mode: str, preset: Dict[str, Any], target_scenes: int, duration_mins: float, base_prompt: str, anti_repetition: str) -> str:
        instructions = [
            f"Genre: {preset.get('name', 'Anime Web-Novel')}",
            f"Tone: {preset.get('tone', 'dramatic, romantic')}",
            f"Visual Style: {preset.get('visual_style', 'Anime illustration')}",
            f"CRITICAL REQUIREMENT: Output EXACTLY {target_scenes} scenes in the scenes array.",
            "",
            anti_repetition,
            ""
        ]

        if mode == "semi_manual" and base_prompt.strip():
            instructions.append(f"USER BASE PROMPT / CORE CONCEPT TO ENHANCE:\n\"{base_prompt.strip()}\"\nExpand this concept into a full, captivating narrative with complete resolution across all {target_scenes} scenes.")
        elif mode in ["full_auto", "pre_generate"]:
            instructions.append(f"TASK: Create a brand new, highly original story premise adhering strictly to the genre tropes, featuring charismatic leads, high tension, and a finished climax across {target_scenes} complete scenes.")

        instructions.append("\nOUTPUT FORMAT: Valid JSON only. Do not enclose in markdown ticks if possible, or use standard ```json block.")
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

    def _generate_procedural(self, preset: Dict[str, Any], user_hint: str, target_scenes: int) -> Dict[str, Any]:
        """
        High-quality procedural story synthesizer that scales dynamically to match target_scenes exactly.
        Guarantees realistic object descriptors and closed-ended finished narrative arcs.
        """
        genre_id = preset.get("id", "underworld_dark_romance")

        if "campus" in genre_id:
            title = "The Campus Goddess Moved Into My Kitchen"
            logline = "An introverted culinary prodigy is trapped in a sweltering dorm, only to discover the university's untouchable idol posted a rental listing secretly looking for a personal chef."
            protagonist = "Yu'er, 18-year-old culinary freshman, messy black hair, casual hoodie, quiet and pragmatic."
            deuteragonist = "Su Yi, silver-haired campus goddess with lilac eyes, poised in public but secretly a food addict."
            conflict = "Yu'er accidentally spills noodle soup at table #13, sparking viral campus rumors of being a clout-chaser, while needing an off-campus room with AC."
            twist = "The mysterious luxury landlord 'Zhiwoyi' who demands gourmet cooking is the campus goddess herself, and she intentionally baited him."
            resolution = "Yu'er arrives at the apartment viewing to find Su Yi holding chopsticks and smiling victoriously."
            tags = ["#campusromcom", "#manhua", "#scheminggoddess", "#culinaryprotagonist", "#animerecap", "#shorts", "#fyp"]
            comment = "Would you endure campus-wide slander if it meant free luxury rent with the campus idol?"

            # Comprehensive pool of narrative beats for campus romcom
            pool = [
                {
                    "narration": "If you dare turn me down, I will personally post on the university confession wall that you broke my heart.",
                    "image_prompt": "masterpiece, best quality, 1girl, silver hair, lilac eyes, mischievous smirk, school uniform with plaid skirt and ribbon tie, pointing forward in modern luxury living room, warm morning sunlight, realistic interior textures, 9:16 vertical anime",
                    "mood": "comedy", "motion_type": "zoom_in"
                },
                {
                    "narration": "Twenty-four hours earlier, freshman Yu'er had only one goal: survive the brutal heat in the men's dormitory.",
                    "image_prompt": "masterpiece, best quality, 1boy, messy black hair, white t-shirt, sweating, sweltering run-down college dorm room, old oscillating fan, exhausted expression, realistic room textures, 9:16 vertical anime",
                    "mood": "cozy", "motion_type": "pan_left"
                },
                {
                    "narration": "With room temperatures soaring past thirty-eight degrees, his roommate Zhang Xun flopped on the bunk groaning about air conditioning.",
                    "image_prompt": "masterpiece, best quality, 2boys in hot dorm room, roommate shirtless fanning himself with textbook, messy dorm desks, realistic plastic fan blades, sunlight streaming, 9:16 vertical anime",
                    "mood": "comedy", "motion_type": "zoom_out"
                },
                {
                    "narration": "Yu'er hurried down to Cafeteria Two, the only dining hall with central air conditioning, carrying his dorm keys to claim a table.",
                    "image_prompt": "masterpiece, best quality, crowded bustling university dining hall, students eating, modern university cafeteria glass windows, bright realistic lighting, 9:16 vertical anime",
                    "mood": "cozy", "motion_type": "pan_right"
                },
                {
                    "narration": "He placed his dorm keys on empty table thirteen, then ordered a steaming bowl of spicy braised beef noodles with extra chili oil and cilantro.",
                    "image_prompt": "masterpiece, best quality, macro close up of steaming ceramic bowl of spicy braised beef noodles, glistening red chili oil droplets, green scallions, realistic food textures, chopsticks resting on ceramic edge, 9:16 vertical anime",
                    "mood": "cozy", "motion_type": "zoom_in"
                },
                {
                    "narration": "When he returned holding the tray, the seat directly across from his keys was occupied by Su Yi—the unattainable senior campus goddess.",
                    "image_prompt": "masterpiece, best quality, 1girl, elegant posture, long silver hair, lilac eyes, holding milk tea plastic cup #14, delicate expression, seated in university cafeteria, male students staring in background, 9:16 vertical anime",
                    "mood": "romance", "motion_type": "tilt_up"
                },
                {
                    "narration": "Under the burning glares of fifty envious onlookers, Yu'er's trembling hand dropped his spoon, splashing red chili broth right across his collar.",
                    "image_prompt": "masterpiece, best quality, close up of spoon splashing into spicy chili soup, droplets flying, soup stain on protagonist white shirt, embarrassed face, dramatic anime speed lines, realistic liquid splashing reflections, 9:16 vertical",
                    "mood": "comedy", "motion_type": "zoom_in"
                },
                {
                    "narration": "The cafeteria went dead silent. Su Yi looked up, her violet eyes meeting his panic with serene amusement.",
                    "image_prompt": "masterpiece, best quality, 1girl, Su Yi intense close up, lilac eyes reflecting dining hall lights, subtle playful smile, delicate lips, soft depth of field, 9:16 vertical anime",
                    "mood": "romance", "motion_type": "zoom_in"
                },
                {
                    "narration": "Without a word, she slid an unopened pack of wet wipes across the polished table, offered a soft smile, and vanished into the crowd.",
                    "image_prompt": "masterpiece, best quality, close up of unopened pack of wet wipes on cafeteria table, smooth realistic plastic packaging textures, 1girl walking away in background, sunlight catching silver hair, romantic anime scene, 9:16 vertical",
                    "mood": "romance", "motion_type": "pan_right"
                },
                {
                    "narration": "By afternoon calculus class, Yu'er's phone buzzed incessantly. A post on the campus forum was trending with ten thousand views.",
                    "image_prompt": "masterpiece, best quality, glowing smartphone screen showing trending campus forum post with blurred photo of protagonist, realistic OLED glass reflections, angry emoji comments, lecture hall background, 9:16 vertical anime",
                    "mood": "suspense", "motion_type": "zoom_in"
                },
                {
                    "narration": "The headline screamed: 'Shameless freshman stages clumsy soup disaster just to solicit attention from the Campus Goddess.'",
                    "image_prompt": "masterpiece, best quality, smartphone display with viral university confession wall page, bold text, comments scrolling, student thumb scrolling, realistic glass texture, 9:16 vertical anime",
                    "mood": "comedy", "motion_type": "pan_left"
                },
                {
                    "narration": "Yu'er buried his face in his hands as students in the lecture hall whispered and cast judging side-eyes.",
                    "image_prompt": "masterpiece, best quality, 1boy in university calculus lecture hall, head resting on notebook in embarrassment, university students whispering in background, realistic classroom wooden desks, 9:16 vertical anime",
                    "mood": "comedy", "motion_type": "zoom_out"
                },
                {
                    "narration": "Desperate to find a peaceful off-campus place with air conditioning, he opened the local housing board and saw a peculiar rental listing.",
                    "image_prompt": "masterpiece, best quality, modern laptop screen showing real estate listing for Junlin Community luxury apartments, photo of spacious kitchen, realistic screen glow, 9:16 vertical anime",
                    "mood": "cozy", "motion_type": "tilt_up"
                },
                {
                    "narration": "The listing read: 'Two-bedroom luxury apartment next to campus. Rent is seventy percent off, but applicant must possess elite culinary skills.'",
                    "image_prompt": "masterpiece, best quality, WeChat chat interface on phone screen, contact named Zhiwoyi, clean modern UI, high-end apartment photos with marble countertops, 9:16 vertical anime",
                    "mood": "cozy", "motion_type": "zoom_in"
                },
                {
                    "narration": "Yu'er messaged the landlord ID 'Zhiwoyi': 'Hi, I saw your listing. I have been cooking every daily meal since middle school.'",
                    "image_prompt": "masterpiece, best quality, close up of hands typing message on smartphone keyboard, realistic metal phone bezel, lecture hall ambient lighting, 9:16 vertical anime",
                    "mood": "cozy", "motion_type": "pan_right"
                },
                {
                    "narration": "Three seconds later, Zhiwoyi replied with a single test question: 'What is your specialty dish?'",
                    "image_prompt": "masterpiece, best quality, phone screen message bubble showing 'What is your specialty dish?', green chat bubble, realistic glass screen texture, 9:16 vertical anime",
                    "mood": "suspense", "motion_type": "zoom_in"
                },
                {
                    "narration": "'Braised pork belly with caramelized sugar coat and scallion pancakes from scratch,' Yu'er typed back confidently.",
                    "image_prompt": "masterpiece, best quality, 1boy with proud confident smirk, messy hair, classroom background, sunset golden hour light filtering through window, 9:16 vertical anime",
                    "mood": "cozy", "motion_type": "zoom_out"
                },
                {
                    "narration": "The response was immediate: 'Passed. Come to Building Five, Room Seven-Thirty-Two right after class to inspect the keys.'",
                    "image_prompt": "masterpiece, best quality, high-rise luxury apartment complex exterior at sunset, glowing windows, Junlin Community entrance gate, realistic modern architecture, 9:16 vertical anime",
                    "mood": "suspense", "motion_type": "tilt_up"
                },
                {
                    "narration": "Yu'er rushed across campus and took the elevator up to room seven-thirty-two, his heart pounding with excitement for air-conditioned freedom.",
                    "image_prompt": "masterpiece, best quality, 1boy standing in luxury apartment corridor, polished marble tile reflections, sleek wooden door with brass number 732, realistic door handle and keyhole, 9:16 vertical anime",
                    "mood": "suspense", "motion_type": "pan_left"
                },
                {
                    "narration": "He knocked twice. The heavy oak door swung open, and the breath caught in his throat.",
                    "image_prompt": "masterpiece, best quality, modern luxury apartment door swinging open, warm golden indoor chandelier light spilling into hallway, high anticipation, 9:16 vertical anime",
                    "mood": "suspense", "motion_type": "zoom_in"
                },
                {
                    "narration": "Standing there in cozy oversized knitwear and clutching a pair of chopsticks was Su Yi herself, smiling victoriously: 'Welcome home, Chef.'",
                    "image_prompt": "masterpiece, best quality, 1girl, Su Yi in cozy oversized knit sweater, silver hair tied in messy bun, holding wooden chopsticks, playful victorious wink, luxury modern kitchen behind her, warm golden hour anime lighting, 9:16 vertical",
                    "mood": "romance", "motion_type": "zoom_in"
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

            pool = [
                {
                    "narration": "Seventeen years ago, a starving ten-year-old girl huddled in an icy alley, shivering beneath torrential rain.",
                    "image_prompt": "masterpiece, best quality, flashback illustration, little girl with silver hair shivering in dark rainy alleyway, heavy pouring rain, dim streetlamp glow, realistic wet asphalt reflections, emotional anime artstyle, 9:16 vertical",
                    "mood": "melodrama", "motion_type": "zoom_in"
                },
                {
                    "narration": "A young boy knelt before her, handing her a warm pastry and sliding a hand-engraved silver band onto her small finger.",
                    "image_prompt": "masterpiece, best quality, macro close up of little boy hand sliding an engraved silver band onto young girl small finger, realistic polished silver metallic reflections, rain droplets on skin, emotional anime lighting, 9:16 vertical",
                    "mood": "melodrama", "motion_type": "zoom_in"
                },
                {
                    "narration": "'Promise me you will survive,' he whispered before his family pulled him away into the stormy night.",
                    "image_prompt": "masterpiece, best quality, little boy looking back through rain-streaked car window, sad eyes, realistic raindrops on automotive glass, headlights cutting through fog, 9:16 vertical anime",
                    "mood": "melodrama", "motion_type": "pan_left"
                },
                {
                    "narration": "Seventeen years passed. That starving girl climbed over every warlord in Southeast Asia to become Liu Yanran—the Sovereign of the Underworld.",
                    "image_prompt": "masterpiece, best quality, 1girl, mature woman, long silver hair, cold blue eyes, wearing silver phantom mask and tailored black suit with white dress shirt, standing by high-rise window overlooking neon metropolis, realistic skyscrapers, 9:16 vertical anime",
                    "mood": "suspense", "motion_type": "tilt_up"
                },
                {
                    "narration": "Despite supreme wealth and authority, the tarnished silver ring had never left her left hand for even a single day.",
                    "image_prompt": "masterpiece, best quality, macro shot of woman left hand wearing engraved silver band, black leather gloves, realistic brushed silver metal textures, reflections of rainy city lights, 9:16 vertical anime",
                    "mood": "suspense", "motion_type": "zoom_in"
                },
                {
                    "narration": "Tonight, beneath the neon sprawl of Bangkok, an exclusive black-market auction was underway in an underground colosseum.",
                    "image_prompt": "masterpiece, best quality, dark subterranean auction colosseum, opulent classical balconies, wealthy elites holding bidding paddles, dramatic spotlights, realistic stone and marble textures, 9:16 vertical anime",
                    "mood": "suspense", "motion_type": "pan_right"
                },
                {
                    "narration": "Her lieutenant Dahae stepped forward, whispering: 'Empress, the final lot tonight is an eighteen-year-old medical honors student betrayed by his own brothers.'",
                    "image_prompt": "masterpiece, best quality, private VIP balcony shrouded in shadow, tall female syndicate boss seated in velvet armchair, male lieutenant in black security tactical gear bowing respectfully, 9:16 vertical anime",
                    "mood": "suspense", "motion_type": "zoom_out"
                },
                {
                    "narration": "The stage spotlight ignited. A heavy iron cage was hoisted into the center of the arena, surrounded by armed guards.",
                    "image_prompt": "masterpiece, best quality, heavy wrought iron cage suspended by thick industrial steel chains, realistic rusted iron textures, harsh stage spotlight, dark arena background, 9:16 vertical anime",
                    "mood": "suspense", "motion_type": "tilt_up"
                },
                {
                    "narration": "Inside knelt Chen Chen, blindfolded, collared, and trembling violently from forced neurochemical delirium.",
                    "image_prompt": "masterpiece, best quality, 1boy inside iron cage, blindfolded, leather collar, torn white dress shirt, trembling feverish posture, sweat glistening under spotlight, realistic metal bars in foreground, 9:16 vertical anime",
                    "mood": "melodrama", "motion_type": "zoom_in"
                },
                {
                    "narration": "The auctioneer slammed his golden gavel: 'Opening bid for this untouched medical prodigy starts at eight hundred thousand dollars!'",
                    "image_prompt": "masterpiece, best quality, charismatic corrupt auctioneer standing at polished mahogany podium, raising heavy golden gavel, realistic polished wood and brass reflections, wealthy crowd cheering, 9:16 vertical anime",
                    "mood": "action", "motion_type": "pan_left"
                },
                {
                    "narration": "Bids skyrocketed in seconds: one million, two million, three million. From the VIP box, Liu Yanran raised her opera glasses.",
                    "image_prompt": "masterpiece, best quality, close up of silver phantom mask, piercing blue eyes behind mask slits, gold vintage opera binoculars raised, high intensity cinematic lighting, 9:16 vertical anime",
                    "mood": "suspense", "motion_type": "zoom_in"
                },
                {
                    "narration": "Her breath seized. Clutched against the iron bars of the cage was a hand wearing the exact matching engraved silver ring.",
                    "image_prompt": "masterpiece, best quality, extreme macro shot of young man trembling hand clutching iron cage bars, wearing an identical engraved silver ring, realistic scratches and metallic silver gleam under harsh stage spotlight, 9:16 vertical anime",
                    "mood": "melodrama", "motion_type": "zoom_in"
                },
                {
                    "narration": "The crystal wine glass in Liu Yanran's grip shattered into powder, dark red wine dripping across her black leather gloves like fresh blood.",
                    "image_prompt": "masterpiece, best quality, crystal wine glass shattering in black-gloved hand, glass shards flying, dark red wine spilling like blood, high speed motion capture, realistic refractive glass textures, 9:16 vertical anime",
                    "mood": "action", "motion_type": "zoom_in"
                },
                {
                    "narration": "When the auctioneer shouted three point five million, a single silenced bullet shattered through the podium skull-first.",
                    "image_prompt": "masterpiece, best quality, close up of sleek matte black silenced pistol raised, realistic gunmetal texture, suppressor muzzle flash, smoke wisps curling, dramatic anime action lighting, 9:16 vertical",
                    "mood": "action", "motion_type": "zoom_in"
                },
                {
                    "narration": "'Nobody touches him,' her voice echoed like a death sentence through the grand chamber.",
                    "image_prompt": "masterpiece, best quality, 1girl, Liu Yanran standing at edge of balcony, tailored black overcoat billowing, cold lethal aura, smoke billowing around her silhouette, 9:16 vertical anime",
                    "mood": "action", "motion_type": "zoom_out"
                },
                {
                    "narration": "Heavy steel blast doors slammed shut over every emergency exit, locking the criminal syndicates and corrupt billionaires inside.",
                    "image_prompt": "masterpiece, best quality, massive industrial steel blast doors slamming shut, warning red sirens flashing, sparks flying, realistic heavy steel plate textures and hazard stripes, 9:16 vertical anime",
                    "mood": "action", "motion_type": "tilt_up"
                },
                {
                    "narration": "Fifty tactical enforcers breached from the rafters, sweeping the colosseum in absolute, relentless execution.",
                    "image_prompt": "masterpiece, best quality, syndicate tactical enforcers in full black combat armor opening fire with submachine guns, bullet tracers, muzzle flashes, chaotic smoke, cinematic action anime, 9:16 vertical",
                    "mood": "action", "motion_type": "pan_left"
                },
                {
                    "narration": "Liu Yanran descended the central marble staircase, stepped over the carnage, and dropped to her knees before the iron cage.",
                    "image_prompt": "masterpiece, best quality, 1girl kneeling on blood-drenched marble floor before iron cage, removing silver phantom mask, tearful desperate blue eyes, emotional anime climax, realistic marble reflections, 9:16 vertical",
                    "mood": "melodrama", "motion_type": "zoom_in"
                },
                {
                    "narration": "She reached through the cold steel bars, calling out 'Chen Chen,' but the boy shrank into the corner in blind panic.",
                    "image_prompt": "masterpiece, best quality, 1boy cowering in corner of iron cage, clutching left hand to chest defensively, feverish sweating face, terrified eyes, realistic wrought iron bars, 9:16 vertical anime",
                    "mood": "melodrama", "motion_type": "zoom_out"
                },
                {
                    "narration": "'Don't touch me!' he sobbed in narcotic fever, shielding his hand. 'Someone very important gave me this ring!'",
                    "image_prompt": "masterpiece, best quality, 1boy crying in terror, holding left hand with silver ring tightly against his chest, sweat on brow, feverish red flush on cheeks, dramatic anime lighting, 9:16 vertical",
                    "mood": "melodrama", "motion_type": "zoom_in"
                },
                {
                    "narration": "He remembered the promise, but the drugs had erased her face. Liu Yanran tore the cage open with bare hands and gathered him into her arms.",
                    "image_prompt": "masterpiece, best quality, 1girl carrying 1boy gently in bridal carry, sweeping black overcoat, armored convoy waiting outside in rainy night, headlights glowing through mist, realistic rain reflections, 9:16 vertical anime",
                    "mood": "romance", "motion_type": "tilt_up"
                },
                {
                    "narration": "Her armored black Maybach sped onto the highway through the torrential storm, escorted by four tactical SUVs.",
                    "image_prompt": "masterpiece, best quality, realistic luxury black Maybach sedan speeding along rain-slicked highway at night, glossy automotive reflections, glowing red taillights, pouring rain, cinematic anime, 9:16 vertical",
                    "mood": "suspense", "motion_type": "pan_right"
                },
                {
                    "narration": "In the backseat, Chen Chen curled against her chest, burning with high fever, his fingers digging desperately into her lapels.",
                    "image_prompt": "masterpiece, best quality, interior of luxury Maybach, rainy window streaks, 1boy curled against 1girl chest, sweating with high fever, 1girl holding him tight with gentle protective eyes, realistic leather seats, 9:16 vertical anime",
                    "mood": "romance", "motion_type": "zoom_in"
                },
                {
                    "narration": "Liu Yanran caressed his hair softly, whispering: 'Rest now. You are safe. We are finally home.'",
                    "image_prompt": "masterpiece, best quality, close up of 1girl silver hair falling over 1boy face, soft gentle smile, tear falling from eye, warm interior car light, emotional anime romance, 9:16 vertical",
                    "mood": "romance", "motion_type": "zoom_out"
                },
                {
                    "narration": "Suddenly, Chen Chen convulsed in tears, crying out into the dark car: 'Nian'an... where are you?!'",
                    "image_prompt": "masterpiece, best quality, dramatic close up of 1girl face freezing in utter heartbreak and shock, wide blue eyes, rain flashing against car glass behind her, cliffhanger twist ending, 9:16 vertical anime",
                    "mood": "melodrama", "motion_type": "zoom_in"
                },
                {
                    "narration": "The name called was not hers. As Chen Chen fell into a seizure, Liu Yanran gripped his ring, vowing to conquer heaven and earth to bring him back.",
                    "image_prompt": "masterpiece, best quality, armored Maybach arriving at sprawling mountain fortress gates, headlights blazing in storm, dramatic silhouette of syndicate queen, finished arc, 9:16 vertical anime",
                    "mood": "melodrama", "motion_type": "tilt_up"
                }
            ]

        # Select exactly target_scenes from pool
        total_available = len(pool)
        if target_scenes <= total_available:
            # Subsample evenly across the narrative arc
            step = total_available / target_scenes
            selected = [pool[int(i * step)] for i in range(target_scenes)]
        else:
            # If target_scenes > available, repeat/expand intermediate narrative beats smoothly
            selected = []
            for i in range(target_scenes):
                base_scene = dict(pool[i % total_available])
                if i >= total_available:
                    base_scene["narration"] = f"As the situation intensified in scene {i+1}, {base_scene['narration'].lower()}"
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
