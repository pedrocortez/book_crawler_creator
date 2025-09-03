from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


class CacheStore:
    def __init__(self, base_dir: Path):
        self.base = base_dir
        self.html_dir = self.base / "ldm_kindler" / "cache" / "html"
        self.json_dir = self.base / "ldm_kindler" / "cache" / "json"
        self.html_dir.mkdir(parents=True, exist_ok=True)
        self.json_dir.mkdir(parents=True, exist_ok=True)

    def html_path(self, chapter_id: int) -> Path:
        return self.html_dir / f"{chapter_id}.html"

    def json_path(self, chapter_id: int) -> Path:
        return self.json_dir / f"{chapter_id}.json"

    def save_html(self, chapter_id: int, html: str) -> None:
        self.html_path(chapter_id).write_text(html, encoding="utf-8")

    def save_json(self, chapter_id: int, data: Dict[str, Any]) -> None:
        self.json_path(chapter_id).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_json(self, chapter_id: int) -> Optional[Dict[str, Any]]:
        p = self.json_path(chapter_id)
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))


