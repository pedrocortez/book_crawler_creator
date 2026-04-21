from __future__ import annotations

from pathlib import Path

from ldm_kindler.builder.epub import EpubBuilder


def test_epub_builder_with_custom_series_filename(tmp_path: Path):
    builder = EpubBuilder(tmp_path, series_title="Minha Série", author="Autor X")
    chapters = [
        {"id": 1, "title": "Capítulo 1", "content_html": "<h2>Capítulo 1</h2><p>Oi</p>"},
        {"id": 2, "title": "Capítulo 2", "content_html": "<h2>Capítulo 2</h2><p>Tchau</p>"},
    ]
    book = {"book": 1, "title": "Clown (Palhaço)", "start": 1, "end": 2}
    out = builder.build_epub(chapters, book)
    assert out.exists()
    assert out.name.startswith("Minha_Serie_Livro_01_")
    assert out.name.endswith("(1-2).epub")
