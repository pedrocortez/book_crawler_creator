from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from bs4 import BeautifulSoup

from ldm_kindler.constants import (
    output_txt_filename_for_book,
    output_txt_filename,
    output_txt_filename_single,
)


class TxtBuilder:
    def __init__(self, out_dir: Path, series_title: str | None = None, author: str | None = None):
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.series_title = series_title or "Lorde dos Mistérios"
        self.author = author or "Cuttlefish That Loves Diving (trad. fã)"

    def _chapter_to_text(self, chapter: Dict[str, Any]) -> str:
        title = chapter.get("title", f"Capítulo {chapter.get('id')}")
        html = chapter.get("content_html", "")
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text("\n", strip=True)
        header = f"{title}\n{'=' * len(title)}"
        return f"{header}\n\n{text}\n\n"

    def build_txt(
        self,
        chapters: List[Dict[str, Any]],
        book: Dict[str, Any],
        override_filename: str | None = None,
    ) -> Path:
        parts: List[str] = []
        # Cabeçalho opcional
        if "book" in book and "title" in book:
            header_title = f"{self.series_title} – Livro {book['book']}: {book['title']} ({book['start']}-{book['end']})"
        else:
            header_title = f"{self.series_title} ({book.get('start')}-{book.get('end')})"
        parts.append(header_title)
        parts.append("".ljust(len(header_title), "="))
        parts.append("")

        for ch in sorted(chapters, key=lambda c: c["id"]):
            parts.append(self._chapter_to_text(ch))

        content = "\n".join(parts).rstrip() + "\n"

        if override_filename:
            filename = override_filename
        else:
            if self.series_title != "Lorde dos Mistérios":
                filename = output_txt_filename(self.series_title, book)
            else:
                filename = output_txt_filename_for_book(book)
        out_path = self.out_dir / filename
        out_path.write_text(content, encoding="utf-8")
        return out_path

    def build_txt_single(self, chapters: List[Dict[str, Any]], title: str, start: int, end: int) -> Path:
        # Constrói um único arquivo com todos os capítulos
        parts: List[str] = []
        header_title = f"{title} ({start}-{end})"
        parts.append(header_title)
        parts.append("".ljust(len(header_title), "="))
        parts.append("")

        for ch in sorted(chapters, key=lambda c: c["id"]):
            parts.append(self._chapter_to_text(ch))

        content = "\n".join(parts).rstrip() + "\n"
        filename = output_txt_filename_single(title, start, end)
        out_path = self.out_dir / filename
        out_path.write_text(content, encoding="utf-8")
        return out_path


