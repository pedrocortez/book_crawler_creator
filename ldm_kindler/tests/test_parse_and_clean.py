from __future__ import annotations

import re

from ldm_kindler.crawler.parse import extract_chapter_id_from
from ldm_kindler.crawler.clean import clean_html


def test_regex_chapter_number_title():
    assert extract_chapter_id_from("Capítulo 534 – Algo", "https://x/ldm-lorde-dos-misterios-capitulo-534") == 534
    assert extract_chapter_id_from("capitulo 12", "https://x/ldm-lorde-dos-misterios-capitulo-12") == 12


def test_regex_chapter_number_url():
    assert extract_chapter_id_from("", "https://x/ldm-lorde-dos-misterios-capitulo-999") == 999


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


