from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
import requests

from ldm_kindler.crawler.sources.central_novel import (
    CHAPTER_SELECTOR,
    CentralNovelBrowserError,
    CentralNovelChallengeTimeout,
    CentralNovelSource,
    CentralNovelUrlError,
    PlaywrightBrowserSession,
)


FIXTURES = Path(__file__).parent / "fixtures" / "central_novel"


def test_accepts_only_https_central_novel_urls() -> None:
    CentralNovelSource.validate_source_url(
        "https://centralnovel.com/the-beginning-after-the-end-capitulo-1/"
    )

    for invalid in (
        "http://centralnovel.com/series/x/",
        "https://www.centralnovel.com/series/x/",
        "https://centralnovel.com.evil.example/series/x/",
        "not-a-url",
    ):
        with pytest.raises(CentralNovelUrlError):
            CentralNovelSource.validate_source_url(invalid)


def test_extracts_sorted_numbered_chapters_and_ignores_special_entries() -> None:
    html = (FIXTURES / "index.html").read_text(encoding="utf-8")

    refs = CentralNovelSource.extract_chapter_refs(html)

    assert [ref.id for ref in refs] == [1, 2, 3]
    assert refs[1].url.endswith("-capitulo-2/")


def test_filters_discovered_chapters_by_requested_range() -> None:
    html = (FIXTURES / "index.html").read_text(encoding="utf-8")

    refs = CentralNovelSource.extract_chapter_refs(html, start=2, end=2)

    assert [(ref.id, ref.url) for ref in refs] == [
        (2, "https://centralnovel.com/the-beginning-after-the-end-capitulo-2/")
    ]


def test_derives_stable_cache_namespace_from_series_url() -> None:
    namespace = CentralNovelSource.cache_namespace_for(
        "https://centralnovel.com/series/the-beginning-after-the-end/"
    )

    assert namespace == "centralnovel/the-beginning-after-the-end"


def test_close_releases_browser_session() -> None:
    calls: list[str] = []

    class FakeSession:
        def close(self) -> None:
            calls.append("session")

    source = CentralNovelSource(
        "https://centralnovel.com/series/the-beginning-after-the-end/"
    )
    source._session = FakeSession()

    asyncio.run(source.close())

    assert calls == ["session"]


def test_challenge_timeout_is_reported_without_bypass_attempt() -> None:
    events: list[str] = []

    class FakeTimeout(Exception):
        pass

    class FakeSession:
        timeout_error = FakeTimeout

        def goto(self, *args, **kwargs) -> None:
            return None

        def wait_for_selector(self, *args, **kwargs) -> None:
            raise FakeTimeout()

        def is_timeout(self, exc: BaseException) -> bool:
            return isinstance(exc, FakeTimeout)

    class AllowedRobots:
        def can_fetch(self, user_agent: str, url: str) -> bool:
            return True

    source = CentralNovelSource(
        "https://centralnovel.com/the-beginning-after-the-end-capitulo-1/",
        challenge_timeout_ms=1,
        event_callback=lambda status, message: events.append(status),
    )
    source._session = FakeSession()
    source._robots = AllowedRobots()

    with pytest.raises(CentralNovelChallengeTimeout):
        asyncio.run(source._navigate(source.source_url, CHAPTER_SELECTOR))

    assert events == ["waiting_for_verification"]


def test_ensure_browser_works_under_windows_selector_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started: list[str] = []

    class FakeSession:
        def start(self) -> None:
            started.append("ok")

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "ldm_kindler.crawler.sources.central_novel.PlaywrightBrowserSession",
        lambda **kwargs: FakeSession(),
    )
    source = CentralNovelSource(
        "https://centralnovel.com/series/the-beginning-after-the-end/"
    )

    async def _run() -> None:
        await source._ensure_browser()
        await source.close()

    if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_run())

    assert started == ["ok"]


def test_browser_error_includes_underlying_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BoomSession:
        def start(self) -> None:
            raise NotImplementedError("create_subprocess_exec")

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "ldm_kindler.crawler.sources.central_novel.PlaywrightBrowserSession",
        lambda **kwargs: BoomSession(),
    )
    source = CentralNovelSource(
        "https://centralnovel.com/series/the-beginning-after-the-end/"
    )

    with pytest.raises(CentralNovelBrowserError, match="create_subprocess_exec"):
        asyncio.run(source._ensure_browser())


@pytest.mark.skipif(sys.platform != "win32", reason="Reproduz o loop do uvicorn --reload no Windows")
def test_real_session_starts_under_selector_policy() -> None:
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    session = PlaywrightBrowserSession(headless=True)
    try:
        session.start()
    finally:
        session.close()


def test_robots_uses_identified_http_client_instead_of_urllib(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    class FakeResponse:
        text = "User-agent: *\nDisallow: /?s=\nAllow: /\n"

        def raise_for_status(self) -> None:
            return None

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        calls.append({"url": url, **kwargs})
        return FakeResponse()

    monkeypatch.setattr(requests, "get", fake_get)
    source = CentralNovelSource(
        "https://centralnovel.com/circle-of-inevitability-capitulo-1075/"
    )

    parser = asyncio.run(source._load_robots())

    assert parser.can_fetch("ldm-kindler", source.source_url) is True
    assert calls[0]["url"] == "https://centralnovel.com/robots.txt"
    assert "ldm-kindler" in calls[0]["headers"]["User-Agent"]
