import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger("StoryVault")

class StoryVault:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    genre TEXT NOT NULL,
                    logline TEXT NOT NULL,
                    protagonist TEXT,
                    deuteragonist TEXT,
                    core_conflict TEXT,
                    climax_twist TEXT,
                    resolution TEXT,
                    hashtags TEXT,
                    full_script TEXT,
                    scenes_json TEXT,
                    video_path TEXT,
                    upload_status TEXT DEFAULT 'pending_review',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_stories_genre ON stories(genre);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_stories_created ON stories(created_at DESC);")
            conn.commit()

    def add_story(self, 
                  title: str, 
                  genre: str, 
                  logline: str,
                  protagonist: str = "",
                  deuteragonist: str = "",
                  core_conflict: str = "",
                  climax_twist: str = "",
                  resolution: str = "",
                  hashtags: str = "",
                  full_script: str = "",
                  scenes: List[Dict[str, Any]] = None,
                  video_path: str = "") -> int:
        scenes_json = json.dumps(scenes or [], ensure_ascii=False)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO stories (
                    title, genre, logline, protagonist, deuteragonist,
                    core_conflict, climax_twist, resolution, hashtags,
                    full_script, scenes_json, video_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                title, genre, logline, protagonist, deuteragonist,
                core_conflict, climax_twist, resolution, hashtags,
                full_script, scenes_json, video_path
            ))
            conn.commit()
            story_id = cursor.lastrowid
            logger.info(f"Registered story #{story_id} ('{title}') into Story Vault.")
            return story_id

    def update_video_path(self, story_id: int, video_path: str):
        with self._get_connection() as conn:
            conn.execute("UPDATE stories SET video_path = ? WHERE id = ?", (video_path, story_id))
            conn.commit()

    def update_upload_status(self, story_id: int, status: str):
        with self._get_connection() as conn:
            conn.execute("UPDATE stories SET upload_status = ? WHERE id = ?", (status, story_id))
            conn.commit()

    def get_anti_repetition_context(self, limit: int = 25) -> str:
        """
        Builds a compact summary of previous stories to inject into the LLM system prompt.
        Ensures the AI knows every past premise, twist, and character setup to prevent duplicates.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, title, genre, logline, protagonist, deuteragonist, climax_twist 
                FROM stories 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()

        if not rows:
            return "No previous stories recorded yet. This is the first story."

        lines = [
            f"VAULT RECORD OF PREVIOUSLY GENERATED STORIES ({len(rows)} most recent):",
            "CRITICAL DIRECTIVE: You MUST NEVER recreate or closely mirror any premise, twist, or character dynamic listed below:"
        ]

        for r in rows:
            desc = f"- #{r['id']} [{r['genre']}] \"{r['title']}\": {r['logline']}"
            if r['climax_twist']:
                desc += f" (Twist: {r['climax_twist']})"
            lines.append(desc)

        return "\n".join(lines)

    def list_stories(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM stories ORDER BY created_at DESC LIMIT ? OFFSET ?
            """, (limit, offset))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_story(self, story_id: int) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM stories WHERE id = ?", (story_id,))
            row = cursor.fetchone()
            if row:
                res = dict(row)
                try:
                    res['scenes'] = json.loads(res.get('scenes_json') or '[]')
                except Exception:
                    res['scenes'] = []
                return res
            return None

    def search_stories(self, query: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            term = f"%{query}%"
            cursor.execute("""
                SELECT * FROM stories 
                WHERE title LIKE ? OR logline LIKE ? OR full_script LIKE ? 
                ORDER BY created_at DESC LIMIT 30
            """, (term, term, term))
            return [dict(r) for r in cursor.fetchall()]

    def delete_story(self, story_id: int):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM stories WHERE id = ?", (story_id,))
            conn.commit()

    def clear_all(self):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM stories;")
            conn.commit()
