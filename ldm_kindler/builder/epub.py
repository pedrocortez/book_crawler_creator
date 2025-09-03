from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from ebooklib import epub

from ldm_kindler.constants import output_filename_for_book, output_filename
from ldm_kindler.builder.cover import generate_cover_image


CSS_TEXT = """
body { font-family: serif; line-height: 1.5; margin: 0 5%; }
h2 { margin-top: 1.2em; font-size: 1.4em; }
p { text-indent: 1.2em; margin: 0.4em 0; }
img { max-width: 100%; height: auto; }
"""


class EpubBuilder:
    def __init__(self, out_dir: Path, series_title: str | None = None, author: str | None = None):
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.series_title = series_title or "Lorde dos Mistérios"
        self.author = author or "Cuttlefish That Loves Diving (trad. fã)"

    def build_epub(self, chapters: List[Dict[str, Any]], book: Dict[str, Any]) -> Path:
        book_id = str(uuid.uuid4())
        title = f"{self.series_title} – Livro {book['book']}: {book['title']}"

        book_epub = epub.EpubBook()
        book_epub.set_identifier(f"urn:uuid:{book_id}")
        book_epub.set_title(title)
        book_epub.set_language("pt-BR")
        book_epub.add_author(self.author)
        book_epub.add_metadata('DC', 'publisher', 'Compilação pessoal – uso privado')
        book_epub.add_metadata('DC', 'date', datetime.utcnow().strftime('%Y-%m-%d'))

        style = epub.EpubItem(uid="style_nav", file_name="style/style.css", media_type="text/css", content=CSS_TEXT)
        book_epub.add_item(style)

        # Capa
        cover_bytes = generate_cover_image(book, series_title=self.series_title)
        book_epub.set_cover("cover.png", cover_bytes)

        # Conteúdo
        spine_items = ['nav']
        toc_items = []

        for ch in sorted(chapters, key=lambda c: c['id']):
            chap = epub.EpubHtml(title=ch.get('title', f"Capítulo {ch['id']}"), file_name=f"chap_{ch['id']}.xhtml", lang="pt-BR")
            chap.content = ch['content_html']
            book_epub.add_item(chap)
            spine_items.append(chap)
            toc_items.append(chap)

        book_epub.toc = tuple(toc_items)
        book_epub.spine = spine_items
        book_epub.add_item(epub.EpubNcx())
        book_epub.add_item(epub.EpubNav())

        # Se o título da série for personalizado, reflete no nome do arquivo
        if self.series_title != "Lorde dos Mistérios":
            filename = output_filename(self.series_title, book)
        else:
            filename = output_filename_for_book(book)
        out_path = self.out_dir / filename
        epub.write_epub(str(out_path), book_epub)
        return out_path


