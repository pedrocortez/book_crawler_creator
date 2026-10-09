"""Testes para o modo prefer_next_link + story_path_prefix do FetchClient.

Cobre o cenário real reportado no Illusia/Fictioneer onde a URL composta pelo
template (``capitulo-737/``) responde 200 servindo conteúdo de outra obra. Com
``prefer_next_link=True`` e ``story_path_prefix`` setados, o cliente deve
priorizar o link "próximo" do capítulo anterior e bloquear qualquer URL fora da
obra.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from ldm_kindler.crawler.fetch import FetchClient


class _FakeCacheStore:
    """Cache em memória mínimo: somente o método load_json é consultado."""

    def __init__(self, items: Dict[int, Dict[str, Any]] | None = None) -> None:
        self._items = items or {}

    def load_json(self, chapter_id: int) -> Optional[Dict[str, Any]]:
        return self._items.get(chapter_id)


def _make_client(**overrides: Any) -> tuple[FetchClient, List[str]]:
    """Cria um FetchClient com _fetch_single instrumentado.

    Devolve (client, calls) onde ``calls`` é a lista (ordenada) de URLs que o
    código tentou buscar, para validar a estratégia escolhida.
    """
    calls: List[str] = []
    client = FetchClient(
        url_template="https://illusia.com.br/story/cdi-circulo-da-inevitabilidade/capitulo-{id}/",
        cache_store=_FakeCacheStore(
            {
                736: {
                    "id": 736,
                    "next": "https://illusia.com.br/story/cdi-circulo-da-inevitabilidade/capitulo-737-opiniao/",
                }
            }
        ),
        **overrides,
    )

    # Não queremos rede nem robots em testes unitários.
    client._allowed = lambda url: True  # type: ignore[assignment]
    client._ensure_index_cache = lambda: None  # type: ignore[assignment]

    def _fake_fetch_single(chapter_id: int, url: str) -> Optional[str]:
        calls.append(url)
        # _belongs_to_story é checado dentro do código real; replicamos aqui
        # para honrar o contrato em testes.
        if not client._belongs_to_story(url):
            return None
        # URL "boa" (com slug) devolve HTML; URL composta pelo template (sem
        # slug) também responderia 200 num cenário real — devolvemos algo para
        # poder detectar se o cliente tentou indevidamente.
        return f"<html><h1>fetched: {url}</h1></html>"

    client._fetch_single = _fake_fetch_single  # type: ignore[assignment]
    return client, calls


def test_prefer_next_link_uses_next_first_skipping_template():
    client, calls = _make_client(
        prefer_next_link=True,
        story_path_prefix="/story/cdi-circulo-da-inevitabilidade/",
    )

    composed = client.compose_url(737)
    html, used = client.fetch(737, composed)

    assert html is not None
    assert used == "https://illusia.com.br/story/cdi-circulo-da-inevitabilidade/capitulo-737-opiniao/"
    # A primeira URL tentada deve ser a do link "próximo", não a do template.
    assert calls[0].endswith("/capitulo-737-opiniao/"), calls
    # O template (sem slug) NÃO deve ter sido chamado quando o next resolveu.
    assert not any(c.endswith("/capitulo-737/") for c in calls), calls


def test_legacy_order_template_first_when_prefer_next_link_false():
    client, calls = _make_client(prefer_next_link=False)

    composed = client.compose_url(737)
    html, used = client.fetch(737, composed)

    assert html is not None
    # Sem prefer_next_link a primeira tentativa deve ser a URL composta.
    assert calls[0] == composed
    assert used == composed


def test_cross_story_url_is_blocked_at_candidate_stage():
    """Se o next do capítulo anterior aponta para outra obra, deve ser rejeitado."""
    bad_cache = _FakeCacheStore(
        {
            736: {
                "id": 736,
                "next": "https://illusia.com.br/story/ea-era-dos-adeptos/capitulo-737/",
            }
        }
    )
    calls: List[str] = []
    client = FetchClient(
        url_template="https://illusia.com.br/story/cdi-circulo-da-inevitabilidade/capitulo-{id}/",
        cache_store=bad_cache,
        prefer_next_link=True,
        story_path_prefix="/story/cdi-circulo-da-inevitabilidade/",
    )
    client._allowed = lambda url: True  # type: ignore[assignment]
    client._ensure_index_cache = lambda: None  # type: ignore[assignment]

    def _fake_fetch_single(chapter_id: int, url: str) -> Optional[str]:
        calls.append(url)
        if not client._belongs_to_story(url):
            return None
        return "<html>ok</html>"

    client._fetch_single = _fake_fetch_single  # type: ignore[assignment]

    composed = client.compose_url(737)
    html, used = client.fetch(737, composed)

    # O next inválido nem deveria chegar a _fetch_single (bloqueado em _try_candidate).
    assert "ea-era-dos-adeptos" not in "|".join(calls), calls
    # Deve ter caído para o template (que neste teste retorna HTML por estar no prefixo).
    assert html is not None
    assert used == composed


def test_post_fetch_redirect_to_other_story_is_blocked():
    """Mesmo com 200 do servidor, se a URL final estiver fora do prefixo, rejeita."""
    client = FetchClient(
        url_template="https://illusia.com.br/story/cdi-circulo-da-inevitabilidade/capitulo-{id}/",
        story_path_prefix="/story/cdi-circulo-da-inevitabilidade/",
    )
    client._allowed = lambda url: True  # type: ignore[assignment]

    fake_resp = MagicMock()
    fake_resp.text = "<html>conteúdo de outra obra</html>"
    fake_resp.url = "https://illusia.com.br/story/ea-era-dos-adeptos/capitulo-737/"
    client._do_fetch = MagicMock(return_value=fake_resp)  # type: ignore[assignment]

    result = client._fetch_single(
        737, "https://illusia.com.br/story/cdi-circulo-da-inevitabilidade/capitulo-737/"
    )
    assert result is None


def test_belongs_to_story_true_when_no_prefix_configured():
    client = FetchClient(url_template="https://x/cap-{id}")
    assert client._belongs_to_story("https://qualquer.coisa/abc/") is True


def test_belongs_to_story_normalizes_trailing_slash():
    client = FetchClient(
        url_template="https://x/story/abc/capitulo-{id}/",
        story_path_prefix="/story/abc",  # sem barra no final propositalmente
    )
    assert client.story_path_prefix == "/story/abc/"
    assert client._belongs_to_story("https://x/story/abc/capitulo-10/") is True
    assert client._belongs_to_story("https://x/story/abc-outro/capitulo-10/") is False


def test_url_not_found_when_all_strategies_fail():
    client = FetchClient(
        url_template="https://x/cap-{id}",
        story_path_prefix="/cap-",  # tudo combina
        prefer_next_link=True,
    )
    client._allowed = lambda url: True  # type: ignore[assignment]
    client._ensure_index_cache = lambda: None  # type: ignore[assignment]
    client._fetch_single = lambda cid, url: None  # type: ignore[assignment]

    html, last = client.fetch(5, "https://x/cap-5")
    assert html is None
    assert last == "https://x/cap-5"
