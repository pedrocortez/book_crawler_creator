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

    def stats(self) -> Dict[str, Any]:
        """Tamanho e contagem de cada diretório de cache (em bytes)."""

        def _measure(folder: Path) -> tuple[int, int]:
            count = 0
            size = 0
            if folder.exists():
                for f in folder.iterdir():
                    if f.is_file():
                        count += 1
                        try:
                            size += f.stat().st_size
                        except OSError:
                            pass
            return count, size

        html_count, html_size = _measure(self.html_dir)
        json_count, json_size = _measure(self.json_dir)
        return {
            "html": {"count": html_count, "bytes": html_size},
            "json": {"count": json_count, "bytes": json_size},
            "total_files": html_count + json_count,
            "total_bytes": html_size + json_size,
        }

    def clear(self, kinds: Optional[set[str]] = None) -> Dict[str, int]:
        """Remove arquivos do cache. ``kinds`` pode conter 'html' e/ou 'json'.

        Por padrão limpa ambos. Retorna a contagem de arquivos removidos por tipo.
        Não falha se um arquivo individual não puder ser removido — apenas pula.
        """
        kinds = kinds or {"html", "json"}
        removed: Dict[str, int] = {"html": 0, "json": 0}
        targets: Dict[str, Path] = {}
        if "html" in kinds:
            targets["html"] = self.html_dir
        if "json" in kinds:
            targets["json"] = self.json_dir
        for kind, folder in targets.items():
            if not folder.exists():
                continue
            for f in folder.iterdir():
                if not f.is_file():
                    continue
                try:
                    f.unlink()
                    removed[kind] += 1
                except OSError:
                    pass
        return removed


