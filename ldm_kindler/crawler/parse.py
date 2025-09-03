from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict

from bs4 import BeautifulSoup
try:
    from readability import Document  # type: ignore
except Exception:  # pragma: no cover
    Document = None  # type: ignore


TITLE_SELECTOR = "h1.entry-title"
CONTENT_SELECTOR = "div.entry-content"
PREV_SELECTOR = "a.prev, a[rel=prev]"
NEXT_SELECTOR = "a.next, a[rel=next]"


CHAPTER_REGEX_TITLE = re.compile(r"cap[íi]tulo\s*(\d+)", re.IGNORECASE)
CHAPTER_REGEX_URL = re.compile(r"capitulo[-_]?(\d+)")


def extract_chapter_id_from(title: str, url: str) -> int | None:
    m = CHAPTER_REGEX_TITLE.search(title or "")
    if m:
        return int(m.group(1))
    m2 = CHAPTER_REGEX_URL.search(url or "")
    if m2:
        return int(m2.group(1))
    return None


def parse_chapter(expected_id: int, url: str, html: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    title_el = soup.select_one(TITLE_SELECTOR)
    content_el = soup.select_one(CONTENT_SELECTOR)

    title_text = title_el.get_text(strip=True) if title_el else f"Capítulo {expected_id}"
    prev_href = (soup.select_one(PREV_SELECTOR) or {}).get("href") if soup.select_one(PREV_SELECTOR) else None
    next_href = (soup.select_one(NEXT_SELECTOR) or {}).get("href") if soup.select_one(NEXT_SELECTOR) else None

    chapter_id = extract_chapter_id_from(title_text, url) or expected_id

    if content_el is not None:
        content_html = str(content_el)
    else:
        # Fallback com readability
        if Document is not None:
            try:
                doc = Document(html)
                content_html = doc.summary(html_partial=True)
                if not title_el:
                    title_text = doc.short_title()
            except Exception:
                content_html = ""
        else:
            content_html = ""

    return {
        "id": chapter_id,
        "title": title_text,
        "source_url": url,
        "content_html": content_html,
        "prev": prev_href,
        "next": next_href,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


