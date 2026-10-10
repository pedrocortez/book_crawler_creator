from __future__ import annotations

import pytest
from pydantic import ValidationError

from ldm_kindler.api import JobRequest


def test_central_novel_start_url_is_detected():
    req = JobRequest(
        start_url="https://centralnovel.com/the-beginning-after-the-end-capitulo-5/", end=8
    )
    assert req.source == "central_novel"
    assert req.start == 5
    assert req.url_template == "https://centralnovel.com/the-beginning-after-the-end-capitulo-{id}/"
    assert req.story_path_prefix == "/the-beginning-after-the-end-capitulo-"
    assert req.prefer_next_link is True
    assert req.url_overrides == {5: "https://centralnovel.com/the-beginning-after-the-end-capitulo-5/"}
    assert req.cache_namespace == "central_novel/centralnovel.com-series-the-beginning-after-the-end"


def test_illusia_start_url_keeps_previous_behavior():
    req = JobRequest(
        start_url="https://illusia.com.br/story/cdi-circulo-da-inevitabilidade/capitulo-736-noite/",
        end=740,
    )
    assert req.source == "illusia"
    assert req.start == 736
    assert req.url_template == "https://illusia.com.br/story/cdi-circulo-da-inevitabilidade/capitulo-{id}/"
    assert req.story_path_prefix == "/story/cdi-circulo-da-inevitabilidade/"


def test_template_mode_without_source_falls_back_to_generic():
    req = JobRequest(url_template="https://outro.site/obra/capitulo-{id}/", start=1, end=3)
    assert req.source == "generic"
    assert req.prefer_next_link is False
    assert req.cache_namespace == "generic/outro.site-obra"


def test_unknown_source_is_rejected():
    with pytest.raises(ValidationError):
        JobRequest(url_template="https://x/capitulo-{id}", start=1, end=2, source="nope")


def test_central_novel_rejects_series_page_as_start_url():
    with pytest.raises(ValidationError):
        JobRequest(start_url="https://centralnovel.com/series/the-beginning-after-the-end/", end=3)



def test_validation_error_handler_returns_422_with_message():
    import asyncio
    import json
    from types import SimpleNamespace

    from fastapi.exceptions import RequestValidationError

    from ldm_kindler.api import request_validation_handler

    with pytest.raises(ValidationError) as info:
        JobRequest(url_template="https://x/capitulo-{id}", start=1, end=2, source="nope")
    exc = RequestValidationError(info.value.errors())
    request = SimpleNamespace(url=SimpleNamespace(path="/api/jobs"))

    resp = asyncio.run(request_validation_handler(request, exc))
    body = json.loads(resp.body)
    assert resp.status_code == 422
    assert body["code"] == "KM-API-005"
    assert "Fonte desconhecida" in body["errors"][0]["msg"]


def test_list_sources_endpoint():
    import asyncio

    from ldm_kindler.api import list_sources

    names = [s["name"] for s in asyncio.run(list_sources())]
    assert {"illusia", "central_novel", "generic"} <= set(names)
