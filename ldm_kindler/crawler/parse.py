from __future__ import annotations

import re
from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class ParserProfile:
    title_selector: str = TITLE_SELECTOR
    content_selector: str = CONTENT_SELECTOR
    prev_selector: str = PREV_SELECTOR
    next_selector: str = NEXT_SELECTOR
    remove_selectors: tuple[str, ...] = ()


DEFAULT_PROFILE = ParserProfile()
CENTRAL_NOVEL_PROFILE = ParserProfile(
    title_selector="h1.entry-title",
    content_selector=".epcontent.entry-content",
    prev_selector="a[rel=prev]",
    next_selector="a[rel=next]",
    remove_selectors=(
        ".chapter-options",
        ".sharedaddy",
        ".adsbygoogle",
        ".ad",
        ".ads",
        "nav",
    ),
)


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


def parse_chapter(
    expected_id: int,
    url: str,
    html: str,
    *,
    profile: ParserProfile = DEFAULT_PROFILE,
) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    title_el = soup.select_one(profile.title_selector)
    content_el = soup.select_one(profile.content_selector)

    title_text = title_el.get_text(strip=True) if title_el else f"Capítulo {expected_id}"
    prev_el = soup.select_one(profile.prev_selector)
    next_el = soup.select_one(profile.next_selector)
    prev_href = prev_el.get("href") if prev_el else None
    next_href = next_el.get("href") if next_el else None

    chapter_id = extract_chapter_id_from(title_text, url) or expected_id

    if content_el is not None:
        for selector in profile.remove_selectors:
            for unwanted in content_el.select(selector):
                unwanted.decompose()
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


