from __future__ import annotations

import re
from typing import Any, Dict

from bs4 import BeautifulSoup, NavigableString, Tag
from ldm_kindler.constants import get_book_info_for_chapter


UNWANTED_SELECTORS = [
    "script",
    "style",
    "iframe",
    "noscript",
    "div.sharedaddy",
    "div.breadcrumb",
    "nav",
    "header",
    "footer",
    "aside",
    "div.ad, div.ads, div.adsbygoogle",
    "ul.post-categories",
]


def normalize_whitespace(text: str) -> str:
    # Espaços e entidades comuns
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    return text.strip()


def convert_breaks_to_paragraphs(soup: BeautifulSoup) -> None:
    for br in soup.find_all("br"):
        next_node = br.next_sibling
        if isinstance(next_node, Tag) and next_node.name == "br":
            p = soup.new_tag("p")
            br.replace_with(p)


def unwrap_spans_and_remove_attrs(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(True):
        # Remove atributos de estilo/classes
        for attr in ["class", "style", "id", "data-*", "width", "height"]:
            if attr in tag.attrs:
                del tag.attrs[attr]
        if tag.name == "span":
            tag.unwrap()


def ensure_paragraphs(soup: BeautifulSoup) -> None:
    # Transforma blocos soltos em <p>
    body_children = list(soup.children)
    new_children = []
    for node in body_children:
        if isinstance(node, NavigableString):
            text = normalize_whitespace(str(node))
            if text:
                p = soup.new_tag("p")
                p.string = text
                new_children.append(p)
        elif isinstance(node, Tag):
            if node.name not in {"p", "h2", "h3", "em", "strong", "ul", "ol", "li"}:
                p = soup.new_tag("p")
                p.append(node)
                new_children.append(p)
            else:
                new_children.append(node)
    soup.clear()
    for c in new_children:
        soup.append(c)


def title_to_h2(title: str) -> Tag:
    soup = BeautifulSoup("", "lxml")
    h2 = soup.new_tag("h2")
    h2.string = title
    return h2


def _word_count(soup: BeautifulSoup) -> int:
    text = soup.get_text(" ", strip=True)
    words = [w for w in text.split(" ") if w]
    return len(words)


def clean_html(parsed: Dict[str, Any]) -> Dict[str, Any]:
    html = parsed.get("content_html", "")
    content_soup = BeautifulSoup(html, "lxml")

    # Remove lixo
    for sel in UNWANTED_SELECTORS:
        for t in content_soup.select(sel):
            t.decompose()

    convert_breaks_to_paragraphs(content_soup)
    unwrap_spans_and_remove_attrs(content_soup)

    # Normaliza
    for tag in content_soup.find_all(text=True):
        if isinstance(tag, NavigableString):
            tag.replace_with(normalize_whitespace(str(tag)))

    ensure_paragraphs(content_soup)

    # Constrói XHTML simples
    body = BeautifulSoup("", "lxml")
    body.append(title_to_h2(parsed.get("title", f"Capítulo {parsed.get('id')}") ))
    # Se não houver body, usa o root
    container = content_soup.body if content_soup.body else content_soup
    for child in list(container.children):
        body.append(child)

    # Metadados de livro
    book_num, volume_title = get_book_info_for_chapter(parsed.get("id", 0))

    cleaned = dict(parsed)
    cleaned["content_html"] = str(body)
    cleaned["word_count"] = _word_count(body)
    if book_num is not None:
        cleaned["book"] = book_num
    if volume_title is not None:
        cleaned["volume_title"] = volume_title
    return cleaned


