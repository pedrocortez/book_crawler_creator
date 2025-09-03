from __future__ import annotations

from pathlib import Path

from ldm_kindler.builder.epub import EpubBuilder


def test_epub_build_structure(tmp_path: Path):
    builder = EpubBuilder(tmp_path)
    chs = [
        {"id": 1, "title": "Capítulo 1", "content_html": "<h2>Capítulo 1</h2><p>Oi</p>"},
        {"id": 2, "title": "Capítulo 2", "content_html": "<h2>Capítulo 2</h2><p>Tchau</p>"},
    ]
    book = {"book": 99, "title": "Teste", "start": 1, "end": 2}
    out = builder.build_epub(chs, book)
    assert out.exists()
    assert out.suffix == ".epub"


