from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
try:
    from readability import Document  # type: ignore
except Exception:  # pragma: no cover
    Document = None  # type: ignore

if TYPE_CHECKING:  # pragma: no cover
    from ldm_kindler.crawler.sources.base import NovelSource


CHAPTER_REGEX_TITLE = re.compile(r"cap[íi]tulo\s*(\d+)", re.IGNORECASE)
CHAPTER_REGEX_URL = re.compile(r"capitulo[-_]?(\d+)")


def extract_chapter_id_from(title: str, url: str) -> int | None:
    m = CHAPTER_REGEX_TITLE.search(title or "")
    if m:
        return int(m.group(1))
    matches = CHAPTER_REGEX_URL.findall(url or "")
    if matches:
        return int(matches[-1])
    return None


def _nav_href(soup: BeautifulSoup, selector: str, base_url: str) -> Optional[str]:
    el = soup.select_one(selector)
    href = (el.get("href") or "").strip() if el else ""
    # Temas costumam deixar o botão sem destino ("#", "#/next/") no último capítulo.
    if not href or href.startswith("#"):
        return None
    return urljoin(base_url, href)


def parse_chapter(
    expected_id: int,
    url: str,
    html: str,
    source: Optional["NovelSource"] = None,
) -> Dict[str, Any]:
    """Extrai título, conteúdo e links anterior/próximo usando os seletores da fonte."""
    if source is None:
        from ldm_kindler.crawler.sources import GenericSource

        source = GenericSource()

    soup = BeautifulSoup(html, "lxml")
    title_el = soup.select_one(source.title_selector)
    content_el = soup.select_one(source.content_selector)

    title_text = title_el.get_text(strip=True) if title_el else f"Capítulo {expected_id}"
    prev_href = _nav_href(soup, source.prev_selector, url)
    next_href = _nav_href(soup, source.next_selector, url)

    chapter_id = source.extract_chapter_id(title_text, url) or expected_id

    if content_el is not None:
        for sel in source.content_junk_selectors:
            for junk in content_el.select(sel):
                junk.decompose()
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


