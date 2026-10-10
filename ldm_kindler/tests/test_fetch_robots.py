"""Testes da leitura do robots.txt pelo FetchClient.

Regressão: ``RobotFileParser.read()`` usa o urllib com User-Agent
``Python-urllib``, que sites atrás de WAF (ex.: illusia.com.br) respondem com
403. O parser trata 403 como "tudo proibido" e o crawler não baixava nenhum
capítulo — quebrando o modo start_url (sem capítulo salvo, não há link
"próximo" para seguir). O robots.txt deve ser lido pela sessão do próprio
cliente, com o nosso User-Agent.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import requests

from ldm_kindler.crawler.fetch import FetchClient

CHAPTER = "https://site.test/story/obra/capitulo-736-noite/"


def _client_with_robots_response(status: int, text: str = "") -> FetchClient:
    client = FetchClient(min_delay=0, max_delay=0)
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    client.session.get = MagicMock(return_value=resp)  # type: ignore[assignment]
    return client


def test_robots_is_fetched_with_client_session():
    client = _client_with_robots_response(200, "")

    assert client._allowed(CHAPTER) is True
    client.session.get.assert_called_once_with("https://site.test/robots.txt")


def test_robots_rules_are_respected():
    client = _client_with_robots_response(200, "User-agent: *\nDisallow: /story/\n")

    assert client._allowed(CHAPTER) is False
    assert client._allowed("https://site.test/outra/") is True


def test_robots_4xx_allows_everything():
    # RFC 9309: robots.txt indisponível (4xx) → crawler pode acessar tudo.
    for status in (401, 403, 404):
        client = _client_with_robots_response(status)
        assert client._allowed(CHAPTER) is True, status


def test_robots_5xx_disallows_everything():
    # RFC 9309: robots.txt inalcançável (5xx) → assume proibição total.
    client = _client_with_robots_response(503)
    assert client._allowed(CHAPTER) is False


def test_robots_network_error_disallows_everything():
    client = FetchClient(min_delay=0, max_delay=0)
    client.session.get = MagicMock(side_effect=requests.ConnectionError("boom"))  # type: ignore[assignment]
    assert client._allowed(CHAPTER) is False


def test_fetch_records_failure_reasons_for_job_log():
    client = _client_with_robots_response(503)
    client._ensure_index_cache = lambda: None  # type: ignore[assignment]

    html, _ = client.fetch(736, CHAPTER)

    assert html is None
    assert client.last_failure_reasons == [f"disallowed_by_robots: {CHAPTER}"]

    # Um novo fetch() começa com a lista limpa.
    client._fetch_single = lambda cid, url: "<html/>"  # type: ignore[assignment]
    client.fetch(737, "https://site.test/story/obra/capitulo-737/")
    assert client.last_failure_reasons == []


def test_robots_is_fetched_only_once():
    client = _client_with_robots_response(200, "")
    client._allowed(CHAPTER)
    client._allowed("https://site.test/story/obra/capitulo-737/")
    assert client.session.get.call_count == 1
