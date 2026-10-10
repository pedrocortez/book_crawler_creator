from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ChapterRef:
    id: int
    url: str


class ChapterSource(Protocol):
    async def discover_chapters(self) -> list[ChapterRef]:
        """Descobre os capítulos que devem ser processados."""

    async def fetch_chapter(self, chapter: ChapterRef) -> str:
        """Devolve o HTML renderizado de um capítulo."""

    async def close(self) -> None:
        """Libera recursos mantidos pela fonte."""
