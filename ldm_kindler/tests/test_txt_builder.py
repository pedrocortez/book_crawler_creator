from pathlib import Path

from ldm_kindler.builder.txt import TxtBuilder


def test_txt_builder_creates_file(tmp_path: Path) -> None:
    chapters = [
        {
            "id": 1,
            "title": "Capítulo 1",
            "content_html": "<h2>Capítulo 1</h2><p>Parágrafo A.</p><p>Parágrafo B.</p>",
        },
        {
            "id": 2,
            "title": "Capítulo 2",
            "content_html": "<h2>Capítulo 2</h2><p>Texto X.</p>",
        },
    ]
    book_meta = {"book": 1, "title": "Clown (Palhaço)", "start": 1, "end": 2}

    builder = TxtBuilder(tmp_path)
    out_path = builder.build_txt(chapters, book_meta)

    assert out_path.exists()
    assert out_path.suffix == ".txt"

    content = out_path.read_text(encoding="utf-8")
    assert "Capítulo 1" in content
    assert "Parágrafo A." in content
    assert "Capítulo 2" in content

