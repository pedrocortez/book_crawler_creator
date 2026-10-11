"""Testes do contrato de fontes (registro, Illusia e Central Novel)."""
from __future__ import annotations

from typing import Optional

import pytest

from ldm_kindler.crawler.fetch import FetchClient
from ldm_kindler.crawler.parse import parse_chapter
from ldm_kindler.crawler.sources import (
    CentralNovelSource,
    GenericSource,
    IllusiaSource,
    detect_source,
    get_source,
    resolve_source,
)

CN_CHAPTER = "https://centralnovel.com/the-beginning-after-the-end-capitulo-12/"

CN_INDEX_HTML = """
<html><body>
  <div class="eplister"><ul>
    <li><a href="https://centralnovel.com/the-beginning-after-the-end-capitulo-2/">
      <div class="epl-num">Cap. 2</div></a></li>
    <li><a href="https://centralnovel.com/the-beginning-after-the-end-capitulo-1-5/">
      <div class="epl-num">Cap. 1.5</div></a></li>
    <li><a href="/the-beginning-after-the-end-capitulo-1/"><div class="epl-num">Cap. 1</div></a></li>
    <li><a href="https://centralnovel.com/the-beginning-after-the-end-extra-1/">Extra</a></li>
  </ul></div>
  <div class="ts-chl-collapsible-content">
    <a href="https://centralnovel.com/the-beginning-after-the-end-capitulo-3/">Capítulo 3</a>
  </div>
  <aside><a href="https://centralnovel.com/outra-obra-capitulo-99/">Capítulo 99</a></aside>
</body></html>
"""

CN_CHAPTER_HTML = """
<html><body>
  <h1 class="entry-title">The Beginning After The End Capítulo 12</h1>
  <div class="epcontent entry-content" itemprop="text">
    <p>Primeiro parágrafo.</p>
    <div class="code-block code-block-1"><ins class="adsbygoogle"></ins></div>
    <p>Segundo parágrafo.</p>
  </div>
  <div class="naveps bignav">
    <div class="nvs"><a href="https://centralnovel.com/the-beginning-after-the-end-capitulo-11/" rel="prev">Anterior</a></div>
    <div class="nvs"><a href="#/next/" rel="next">Próximo</a></div>
  </div>
</body></html>
"""


# ── Registro ────────────────────────────────────────────────────────────────
def test_detect_source_by_host():
    assert isinstance(detect_source(CN_CHAPTER), CentralNovelSource)
    assert isinstance(detect_source("https://www.centralnovel.com/x-capitulo-1/"), CentralNovelSource)
    assert isinstance(detect_source("https://illusia.com.br/story/x/capitulo-1/"), IllusiaSource)
    assert isinstance(detect_source("https://outro.site/capitulo-1/"), GenericSource)
    assert isinstance(detect_source(None), GenericSource)
    # Domínio que só termina igual não casa
    assert isinstance(detect_source("https://fakecentralnovel.com/x-capitulo-1/"), GenericSource)


def test_resolve_source_explicit_name_wins_over_host():
    assert resolve_source("generic", CN_CHAPTER).name == "generic"
    assert resolve_source("auto", CN_CHAPTER).name == "central_novel"
    with pytest.raises(ValueError):
        get_source("nao-existe")


# ── Central Novel: URLs e índice ───────────────────────────────────────────
def test_central_novel_derive_template():
    template, cid, prefix = CentralNovelSource().derive_template(CN_CHAPTER)
    assert template == "https://centralnovel.com/the-beginning-after-the-end-capitulo-{id}/"
    assert cid == 12
    assert prefix == "/the-beginning-after-the-end-capitulo-"


def test_central_novel_derive_rejects_non_chapter_url():
    with pytest.raises(ValueError):
        CentralNovelSource().derive_template("https://centralnovel.com/series/the-beginning-after-the-end/")


def test_central_novel_story_index_url():
    src = CentralNovelSource()
    template, _, _ = src.derive_template(CN_CHAPTER)
    assert src.story_index_url(template) == "https://centralnovel.com/series/the-beginning-after-the-end/"


def test_central_novel_parse_index_keeps_only_numbered_chapters():
    found = CentralNovelSource().parse_index(
        CN_INDEX_HTML, "https://centralnovel.com/series/the-beginning-after-the-end/"
    )
    assert found == {
        1: "https://centralnovel.com/the-beginning-after-the-end-capitulo-1/",
        2: "https://centralnovel.com/the-beginning-after-the-end-capitulo-2/",
        3: "https://centralnovel.com/the-beginning-after-the-end-capitulo-3/",
    }


def test_central_novel_chapter_id_from_url_flags_extras_as_mismatch():
    src = CentralNovelSource()
    assert src.chapter_id_from_url(CN_CHAPTER) == 12
    # Um "próximo" apontando para o extra 10.5 não pode ser aceito como cap. 11
    assert src.chapter_id_from_url("https://centralnovel.com/obra-capitulo-10-5/") == 10


# ── Central Novel: parse ────────────────────────────────────────────────────
def test_central_novel_parse_chapter_uses_source_selectors():
    parsed = parse_chapter(12, CN_CHAPTER, CN_CHAPTER_HTML, source=CentralNovelSource())
    assert parsed["id"] == 12
    assert parsed["title"] == "The Beginning After The End Capítulo 12"
    assert "Primeiro parágrafo." in parsed["content_html"]
    assert "Segundo parágrafo." in parsed["content_html"]
    assert "adsbygoogle" not in parsed["content_html"]
    assert "code-block" not in parsed["content_html"]
    assert parsed["prev"] == "https://centralnovel.com/the-beginning-after-the-end-capitulo-11/"
    # Botão "próximo" sem destino no último capítulo
    assert parsed["next"] is None


def test_parse_chapter_resolves_relative_nav_links():
    html = '<h1 class="entry-title">Capítulo 5</h1><div class="entry-content"><p>x</p></div>' \
           '<a rel="next" href="../capitulo-6-y/">próx</a>'
    parsed = parse_chapter(5, "https://site/story/obra/capitulo-5-x/", html)
    assert parsed["next"] == "https://site/story/obra/capitulo-6-y/"


# ── FetchClient com a fonte ─────────────────────────────────────────────────
class _FakeCache:
    def __init__(self, items):
        self._items = items

    def load_json(self, chapter_id: int) -> Optional[dict]:
        return self._items.get(chapter_id)


def _cn_client(**kw) -> tuple[FetchClient, list]:
    src = CentralNovelSource()
    template, _, prefix = src.derive_template(CN_CHAPTER)
    calls: list = []
    client = FetchClient(
        url_template=template,
        story_path_prefix=prefix,
        source=src,
        min_delay=0,
        max_delay=0,
        **kw,
    )
    client._allowed = lambda url: True  # type: ignore[assignment]

    def _fake_fetch_single(cid, url):
        calls.append(url)
        return f"<html>{url}</html>"

    client._fetch_single = _fake_fetch_single  # type: ignore[assignment]
    return client, calls


def test_fetch_client_uses_source_index():
    client, _ = _cn_client()
    assert client._story_index_url() == "https://centralnovel.com/series/the-beginning-after-the-end/"
    client._parse_index_into_cache(CN_INDEX_HTML, client._story_index_url())
    client._index_loaded = True
    assert client._discovered_url_from_index(3) == (
        "https://centralnovel.com/the-beginning-after-the-end-capitulo-3/"
    )


def test_fetch_client_follows_next_link_and_rejects_extra():
    # "próximo" do cap. 10 aponta para o extra 10.5 → rejeitado; cai no template.
    client, calls = _cn_client(
        prefer_next_link=True,
        cache_store=_FakeCache({10: {"next": "https://centralnovel.com/the-beginning-after-the-end-capitulo-10-5/"}}),
    )
    client._ensure_index_cache = lambda: None  # type: ignore[assignment]
    html, used = client.fetch(11, client.compose_url(11))
    assert html is not None
    assert used == "https://centralnovel.com/the-beginning-after-the-end-capitulo-11/"
    assert calls == [used]


def test_fetch_client_blocks_other_series():
    client, calls = _cn_client(
        prefer_next_link=True,
        cache_store=_FakeCache({10: {"next": "https://centralnovel.com/outra-obra-capitulo-11/"}}),
    )
    client._ensure_index_cache = lambda: None  # type: ignore[assignment]
    _, used = client.fetch(11, client.compose_url(11))
    assert "outra-obra" not in "|".join(calls)
    assert used == "https://centralnovel.com/the-beginning-after-the-end-capitulo-11/"


# ── Namespace de cache ──────────────────────────────────────────────────────
def test_cache_namespace_is_per_source_and_story():
    cn = CentralNovelSource()
    template, _, _ = cn.derive_template(CN_CHAPTER)
    assert cn.cache_namespace(template) == "central_novel/centralnovel.com-series-the-beginning-after-the-end"

    il = IllusiaSource()
    t1, _, _ = il.derive_template("https://illusia.com.br/story/cdi-circulo-da-inevitabilidade/capitulo-736-noite/")
    t2 = "https://illusia.com.br/story/cdi-circulo-da-inevitabilidade/capitulo-{id}/"
    # start_url e template manual da mesma obra compartilham o cache
    assert il.cache_namespace(t1) == il.cache_namespace(t2) == (
        "illusia/illusia.com.br-story-cdi-circulo-da-inevitabilidade"
    )
    assert il.cache_namespace(None) is None
