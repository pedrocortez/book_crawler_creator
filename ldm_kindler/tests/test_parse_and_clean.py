from __future__ import annotations

import re
from pathlib import Path

from ldm_kindler.crawler.parse import (
    CENTRAL_NOVEL_PROFILE,
    extract_chapter_id_from,
    parse_chapter,
)
from ldm_kindler.crawler.clean import clean_html


FIXTURES = Path(__file__).parent / "fixtures" / "central_novel"


def test_regex_chapter_number_title():
    assert extract_chapter_id_from("Capítulo 534 – Algo", "https://x/ldm-lorde-dos-misterios-capitulo-534") == 534
    assert extract_chapter_id_from("capitulo 12", "https://x/ldm-lorde-dos-misterios-capitulo-12") == 12


def test_regex_chapter_number_url():
    assert extract_chapter_id_from("", "https://x/ldm-lorde-dos-misterios-capitulo-999") == 999


def test_regex_chapter_url_uses_last_capitulo_segment():
    u = "https://x/story/capitulo-1/foo/capitulo-477-bar"
    assert extract_chapter_id_from("", u) == 477


def test_clean_basic_html():
    parsed = {
        "id": 1,
        "title": "Capítulo 1",
        "content_html": "<div class='entry-content'><p>Olá</p><script>alert(1)</script><br><br>Mundo</div>",
    }
    cleaned = clean_html(parsed)
    html = cleaned["content_html"]
    assert "script" not in html
    assert "<h2>Capítulo 1</h2>" in html


def test_central_novel_profile_keeps_story_and_removes_page_controls():
    source = "https://centralnovel.com/the-beginning-after-the-end-capitulo-2/"
    html = (FIXTURES / "chapter.html").read_text(encoding="utf-8")

    parsed = parse_chapter(2, source, html, profile=CENTRAL_NOVEL_PROFILE)
    cleaned = clean_html(parsed)
    content = cleaned["content_html"]

    assert parsed["id"] == 2
    assert "Primeiro parágrafo." in content
    assert "Segundo parágrafo." in content
    assert "Opções de leitura" not in content
    assert "Compartilhar" not in content
    assert "Publicidade" not in content


