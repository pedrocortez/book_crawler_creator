"""Central Novel (centralnovel.com) — tema WordPress "LightNovel" (Themesia).

Diferenças em relação ao layout padrão:
  * capítulo: ``/<obra>-capitulo-<n>/`` direto na raiz (sem pasta da obra);
  * índice: ``/series/<obra>/``, links em ``.eplister`` / ``.ts-chl-collapsible-content``;
  * extras usam URLs como ``-capitulo-10-5`` ou ``-extra-1`` e ficam de fora;
  * conteúdo em ``.epcontent.entry-content``, com blocos de anúncio no meio.
"""
from __future__ import annotations

import re
from typing import Dict, Optional
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from ldm_kindler.crawler.sources.base import NovelSource

# Link de capítulo informado pelo usuário (aceita sufixo após o número).
_CHAPTER_PATH_RE = re.compile(
    r"^/(?P<slug>[^/]+?)-cap[ií]tulo-(?P<id>\d+)(?:-[^/]*)?/?$", re.IGNORECASE
)
# Template gerado por derive_template (``/<obra>-capitulo-{id}/``).
_TEMPLATE_PATH_RE = re.compile(r"^/(?P<slug>[^/]+?)-cap[ií]tulo-\{id\}/?$", re.IGNORECASE)
# Capítulo numerado "puro" no índice: sem sufixo (exclui 10-5, extras etc.).
_INDEX_HREF_RE = re.compile(r"-cap[ií]tulo-(\d+)/?$", re.IGNORECASE)
_URL_ID_RE = re.compile(r"-cap[ií]tulo-(\d+)", re.IGNORECASE)


class CentralNovelSource(NovelSource):
    name = "central_novel"
    label = "Central Novel"
    hosts = ("centralnovel.com",)
    example_url = "https://centralnovel.com/the-beginning-after-the-end-capitulo-1/"

    title_selector = "h1.entry-title"
    content_selector = "div.epcontent"
    prev_selector = ".naveps a[rel=prev], a[rel=prev]"
    next_selector = ".naveps a[rel=next], a[rel=next]"
    content_junk_selectors = (
        ".code-block",
        "ins.adsbygoogle",
        "div[id^=div-gpt-ad]",
        ".naveps",
        ".bixbox",
        ".sharedaddy",
    )

    def derive_template(self, chapter_url: str) -> tuple[str, int, str]:
        if not chapter_url or not isinstance(chapter_url, str):
            raise ValueError("URL vazia ou inválida")
        parsed = urlparse(chapter_url.strip())
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"URL inválida (sem scheme/host): {chapter_url!r}")
        m = _CHAPTER_PATH_RE.match(parsed.path)
        if not m:
            raise ValueError(
                f"Link da Central Novel não reconhecido: {chapter_url!r} "
                "(esperado https://centralnovel.com/<obra>-capitulo-<n>/)."
            )
        slug = m.group("slug")
        template = urlunparse((parsed.scheme, parsed.netloc, f"/{slug}-capitulo-{{id}}/", "", "", ""))
        # Prefixo inclui "-capitulo-": evita confundir "obra" com "obra-2".
        return template, int(m.group("id")), f"/{slug}-capitulo-"

    def normalize_story_prefix(self, prefix: str) -> str:
        # Capítulos ficam na raiz: o prefixo é "/<obra>-capitulo-", não uma pasta.
        return prefix

    def story_index_url(self, url_template: str) -> str:
        if not url_template:
            raise ValueError("url_template ausente")
        parsed = urlparse(url_template)
        m = _TEMPLATE_PATH_RE.match(parsed.path)
        if not m:
            raise ValueError(f"Template fora do padrão da Central Novel: {url_template!r}")
        return urlunparse((parsed.scheme, parsed.netloc, f"/series/{m.group('slug')}/", "", "", ""))

    def parse_index(self, html: str, index_url: str) -> Dict[int, str]:
        soup = BeautifulSoup(html, "lxml")
        links = soup.select(".eplister a[href], .ts-chl-collapsible-content a[href]")
        found: Dict[int, str] = {}
        for a in links:
            full = urljoin(index_url, a["href"])
            m = _INDEX_HREF_RE.search(urlparse(full).path)
            if m:
                found.setdefault(int(m.group(1)), full)
        return found

    def chapter_id_from_url(self, url: str) -> Optional[int]:
        # Sem âncora no fim: "-capitulo-10-5" devolve 10, então um link
        # "próximo" que aponte para um extra é rejeitado como id divergente.
        matches = _URL_ID_RE.findall(urlparse(url or "").path)
        return int(matches[-1]) if matches else None
