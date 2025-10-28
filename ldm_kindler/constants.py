from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


BASE_URL = (
    "https://illusia.com.br/story/ldm-lorde-dos-misterios/"
    "ldm-lorde-dos-misterios-capitulo-{id}"
)


BOOKS = [
    {"book": 1, "title": "O Mago", "start": 1, "end": 185},
    {"book": 2, "title": "O Louco", "start": 186, "end": 381},
    {"book": 3, "title": "O Viajante", "start": 382, "end": 732},
    {"book": 4, "title": "O Imperador", "start": 733, "end": 789},
    {"book": 5, "title": "O Louco dos Ventos", "start": 790, "end": 961},
    {"book": 6, "title": "O Eremita", "start": 962, "end": 1145},
    {"book": 7, "title": "O Enforcado", "start": 1146, "end": 1353},
    {"book": 8, "title": "O Sol", "start": 1354, "end": 1436},
]


def chapter_url(chapter_id: int) -> str:
    return BASE_URL.format(id=chapter_id)


def ensure_dirs(base_out: Path) -> None:
    (base_out / "build").mkdir(parents=True, exist_ok=True)
    (base_out / "ldm_kindler" / "cache" / "html").mkdir(parents=True, exist_ok=True)
    (base_out / "ldm_kindler" / "cache" / "json").mkdir(parents=True, exist_ok=True)


def get_book_info_for_chapter(chapter_id: int) -> tuple[int | None, str | None]:
    for b in BOOKS:
        if b["start"] <= chapter_id <= b["end"]:
            return b["book"], b["title"]
    return None, None


def output_filename_for_book(book: dict) -> str:
    book_num = f"{book['book']:02d}"
    safe_title = (
        book["title"].replace(" ", "_")
        .replace("(", "(")
        .replace(")", ")")
        .replace("ã", "a")
        .replace("â", "a")
        .replace("ê", "e")
        .replace("é", "e")
        .replace("ó", "o")
        .replace("ç", "c")
    )
    return (
        f"Lorde_dos_Misterios_Livro_{book_num}_"
        f"{safe_title.replace('/', '_')}_(" 
        f"{book['start']}-{book['end']}).epub"
    )


def output_filename(series_title: str, book: dict) -> str:
    series = sanitize_for_filename(series_title)
    book_num = f"{book['book']:02d}"
    safe_title = sanitize_for_filename(book["title"]) 
    return f"{series}_Livro_{book_num}_{safe_title}_({book['start']}-{book['end']}).epub"


def sanitize_for_filename(text: str) -> str:
    return (
        text.replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "-")
        .replace("*", "-")
        .replace("?", "")
        .replace("\"", "'")
        .replace("<", "(")
        .replace(">", ")")
        .replace("|", "-")
        .replace("ã", "a").replace("â", "a").replace("ê", "e")
        .replace("é", "e").replace("ó", "o").replace("ç", "c")
    )


def output_filename_single(title: str, start: int, end: int) -> str:
    base = sanitize_for_filename(title)
    return f"{base}_({start}-{end}).epub"


# ===== TXT filenames =====
def output_txt_filename_for_book(book: dict) -> str:
    book_num = f"{book['book']:02d}"
    safe_title = sanitize_for_filename(book["title"]) 
    return (
        f"Lorde_dos_Misterios_Livro_{book_num}_"
        f"{safe_title}_(" 
        f"{book['start']}-{book['end']}).txt"
    )


def output_txt_filename(series_title: str, book: dict) -> str:
    series = sanitize_for_filename(series_title)
    book_num = f"{book['book']:02d}"
    safe_title = sanitize_for_filename(book["title"]) 
    return f"{series}_Livro_{book_num}_{safe_title}_({book['start']}-{book['end']}).txt"


def output_txt_filename_single(title: str, start: int, end: int) -> str:
    base = sanitize_for_filename(title)
    return f"{base}_({start}-{end}).txt"


