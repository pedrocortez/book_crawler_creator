from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


BASE_URL = (
    "https://illusia.com.br/story/ldm-lorde-dos-misterios/"
    "ldm-lorde-dos-misterios-capitulo-{id}"
)


BOOKS = [
    {"book": 1, "title": "Clown (Palhaço)", "start": 1, "end": 65},
    {"book": 2, "title": "Magician (Mago)", "start": 66, "end": 141},
    {"book": 3, "title": "Seer (Vidente)", "start": 142, "end": 222},
    {"book": 4, "title": "Hero (Herói)", "start": 223, "end": 322},
    {"book": 5, "title": "Bizarro Sorcerer (Feiticeiro Bizarro)", "start": 323, "end": 390},
    {"book": 6, "title": "Hanged Man (Enforcado)", "start": 391, "end": 533},
    {"book": 7, "title": "Fool (O Louco)", "start": 534, "end": 680},
    {"book": 8, "title": "Resonance (Ressonância)", "start": 681, "end": 849},
    {"book": 9, "title": "Mystery Pryer (Explorador do Mistério)", "start": 850, "end": 1029},
    {"book": 10, "title": "Apocalypse (Apocalipse)", "start": 1030, "end": 1394},
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


