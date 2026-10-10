from __future__ import annotations

import asyncio
import concurrent.futures
import queue
import random
import re
import sys
import threading
from collections.abc import Callable
from typing import Any
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from ldm_kindler.crawler.fetch import DEFAULT_HEADERS
from ldm_kindler.crawler.sources.base import ChapterRef


CENTRAL_NOVEL_HOST = "centralnovel.com"
INDEX_SELECTOR = "div.ts-chl-collapsible-content a"
CHAPTER_SELECTOR = ".epcontent.entry-content"
CHAPTER_URL_RE = re.compile(r"-capitulo-(\d+)/?$", re.IGNORECASE)
SERIES_PATH_RE = re.compile(r"^/series/([^/]+)/?$", re.IGNORECASE)

EventCallback = Callable[[str, str], None]


class CentralNovelError(RuntimeError):
    """Falha conhecida ao usar a fonte Central Novel."""


class CentralNovelUrlError(CentralNovelError):
    """URL inválida ou fora do domínio permitido."""


class CentralNovelBrowserError(CentralNovelError):
    """O navegador não pôde ser iniciado ou utilizado."""


class CentralNovelChallengeTimeout(CentralNovelError):
    """A verificação manual não foi concluída dentro do prazo."""


class CentralNovelIndexError(CentralNovelError):
    """O índice da obra está ausente ou não contém capítulos válidos."""


class CentralNovelContentError(CentralNovelError):
    """A página não contém o corpo esperado do capítulo."""


class PlaywrightBrowserSession:
    """Playwright preso a uma thread com loop capaz de abrir subprocessos.

    No Windows, ``uvicorn --reload`` usa ``SelectorEventLoop``, que não
    implementa ``create_subprocess_exec``. A API async do Playwright quebra
    nesse loop. Aqui a sessão vive numa thread própria com política Proactor.
    """

    def __init__(self, *, headless: bool = False) -> None:
        self.headless = headless
        self.timeout_error: type[Exception] = TimeoutError
        self._calls: queue.Queue[tuple[Any, tuple[Any, ...], dict[str, Any], concurrent.futures.Future[Any]] | None] = (
            queue.Queue()
        )
        self._thread: threading.Thread | None = None
        self._playwright: Any = None
        self._browser: Any = None
        self._page: Any = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._thread_main,
            name="kindlemake-playwright",
            daemon=True,
        )
        self._thread.start()
        try:
            self._run(self._start_in_thread)
        except Exception:
            self.close()
            raise

    def _thread_main(self) -> None:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        while True:
            item = self._calls.get()
            if item is None:
                break
            func, args, kwargs, future = item
            try:
                future.set_result(func(*args, **kwargs))
            except BaseException as exc:
                future.set_exception(exc)

    def _run(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if self._thread is None or not self._thread.is_alive():
            raise CentralNovelBrowserError("Navegador ainda não foi iniciado.")
        future: concurrent.futures.Future[Any] = concurrent.futures.Future()
        self._calls.put((func, args, kwargs, future))
        return future.result()

    def _start_in_thread(self) -> None:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright

        self.timeout_error = PlaywrightTimeoutError
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        self._page = self._browser.new_page()

    def is_timeout(self, exc: BaseException) -> bool:
        return isinstance(exc, self.timeout_error)

    def goto(self, url: str) -> None:
        self._run(self._goto_in_thread, url)

    def _goto_in_thread(self, url: str) -> None:
        if self._page is None:
            raise CentralNovelBrowserError("Navegador ainda não foi iniciado.")
        self._page.goto(url, wait_until="domcontentloaded", timeout=60_000)

    def wait_for_selector(self, selector: str, timeout: int) -> None:
        self._run(self._wait_for_selector_in_thread, selector, timeout)

    def _wait_for_selector_in_thread(self, selector: str, timeout: int) -> None:
        if self._page is None:
            raise CentralNovelBrowserError("Navegador ainda não foi iniciado.")
        self._page.wait_for_selector(selector, timeout=timeout)

    def content(self) -> str:
        return self._run(self._content_in_thread)

    def _content_in_thread(self) -> str:
        if self._page is None:
            raise CentralNovelBrowserError("Navegador ainda não foi iniciado.")
        return self._page.content()

    def first_attribute(self, selector: str, name: str) -> str | None:
        return self._run(self._first_attribute_in_thread, selector, name)

    def _first_attribute_in_thread(self, selector: str, name: str) -> str | None:
        if self._page is None:
            raise CentralNovelBrowserError("Navegador ainda não foi iniciado.")
        locator = self._page.locator(selector)
        if locator.count() == 0:
            return None
        return locator.first.get_attribute(name)

    def close(self) -> None:
        thread = self._thread
        if thread is None:
            return
        try:
            if thread.is_alive():
                self._run(self._close_in_thread)
        finally:
            self._calls.put(None)
            thread.join(timeout=15)
            self._thread = None

    def _close_in_thread(self) -> None:
        if self._browser is not None:
            try:
                self._browser.close()
            finally:
                self._browser = None
                self._page = None
        if self._playwright is not None:
            try:
                self._playwright.stop()
            finally:
                self._playwright = None


class CentralNovelSource:
    def __init__(
        self,
        source_url: str,
        *,
        start: int = 1,
        end: int | None = None,
        min_delay: float = 2.99,
        max_delay: float = 3.5,
        challenge_timeout_ms: int = 180_000,
        event_callback: EventCallback | None = None,
    ) -> None:
        self.validate_source_url(source_url)
        self.source_url = source_url.strip()
        self.start = start
        self.end = end
        self.min_delay = min_delay
        self.max_delay = max(max_delay, min_delay)
        self.challenge_timeout_ms = challenge_timeout_ms
        self.event_callback = event_callback
        self.series_url: str | None = None
        self._session: PlaywrightBrowserSession | None = None
        self._robots: robotparser.RobotFileParser | None = None
        self._has_navigated = False

    @staticmethod
    def validate_source_url(url: str) -> None:
        try:
            parsed = urlparse((url or "").strip())
        except (TypeError, ValueError) as exc:
            raise CentralNovelUrlError("URL da Central Novel inválida.") from exc
        if parsed.scheme != "https" or parsed.hostname != CENTRAL_NOVEL_HOST:
            raise CentralNovelUrlError(
                "Use uma URL HTTPS do host exato centralnovel.com."
            )

    @staticmethod
    def extract_chapter_refs(
        html: str,
        *,
        start: int = 1,
        end: int | None = None,
    ) -> list[ChapterRef]:
        soup = BeautifulSoup(html, "lxml")
        by_id: dict[int, ChapterRef] = {}
        for anchor in soup.select(INDEX_SELECTOR):
            href = str(anchor.get("href") or "").strip()
            if not href:
                continue
            parsed = urlparse(href)
            if parsed.scheme != "https" or parsed.hostname != CENTRAL_NOVEL_HOST:
                continue
            match = CHAPTER_URL_RE.search(parsed.path)
            if not match:
                continue
            chapter_id = int(match.group(1))
            if chapter_id < max(1, start):
                continue
            if end is not None and chapter_id > end:
                continue
            by_id.setdefault(chapter_id, ChapterRef(chapter_id, href))
        return [by_id[chapter_id] for chapter_id in sorted(by_id)]

    @staticmethod
    def cache_namespace_for(series_url: str) -> str:
        CentralNovelSource.validate_source_url(series_url)
        match = SERIES_PATH_RE.match(urlparse(series_url).path)
        if not match:
            raise CentralNovelUrlError(
                "Não foi possível identificar a série na URL da Central Novel."
            )
        return f"centralnovel/{match.group(1).lower()}"

    @property
    def cache_namespace(self) -> str:
        if not self.series_url:
            raise CentralNovelIndexError("A série ainda não foi descoberta.")
        return self.cache_namespace_for(self.series_url)

    def _emit(self, status: str, message: str) -> None:
        if self.event_callback is not None:
            self.event_callback(status, message)

    async def _ensure_browser(self) -> None:
        if self._session is not None:
            return
        session = PlaywrightBrowserSession(headless=False)
        try:
            await asyncio.to_thread(session.start)
            self._session = session
            self._emit("browser_opened", "Navegador visível aberto.")
        except Exception as exc:
            await asyncio.to_thread(session.close)
            await self.close()
            raise CentralNovelBrowserError(
                "Não foi possível abrir o Chromium. "
                f"{exc}. Se o navegador não estiver instalado, execute "
                "'.venv\\Scripts\\python.exe -m playwright install chromium'."
            ) from exc

    async def _load_robots(self) -> robotparser.RobotFileParser:
        if self._robots is not None:
            return self._robots

        def _read() -> robotparser.RobotFileParser:
            robots_url = "https://centralnovel.com/robots.txt"
            parser = robotparser.RobotFileParser(robots_url)
            try:
                response = requests.get(
                    robots_url,
                    headers=DEFAULT_HEADERS,
                    timeout=30,
                )
                response.raise_for_status()
            except requests.RequestException as exc:
                raise CentralNovelUrlError(
                    "Não foi possível consultar o robots.txt da Central Novel."
                ) from exc
            parser.parse(response.text.splitlines())
            return parser

        self._robots = await asyncio.to_thread(_read)
        return self._robots

    async def _ensure_allowed(self, url: str) -> None:
        parser = await self._load_robots()
        if not parser.can_fetch("ldm-kindler", url):
            raise CentralNovelUrlError(f"URL bloqueada pelo robots.txt: {url}")

    async def _navigate(self, url: str, ready_selector: str) -> None:
        self.validate_source_url(url)
        await self._ensure_allowed(url)
        await self._ensure_browser()
        if self._has_navigated:
            await asyncio.sleep(random.uniform(self.min_delay, self.max_delay))
        self._has_navigated = True
        session = self._session
        if session is None:
            raise CentralNovelBrowserError("Navegador ainda não foi iniciado.")
        try:
            await asyncio.to_thread(session.goto, url)
            try:
                await asyncio.to_thread(session.wait_for_selector, ready_selector, 10_000)
            except Exception as exc:
                if not session.is_timeout(exc):
                    raise
                self._emit(
                    "waiting_for_verification",
                    "Conclua a verificação na janela do navegador.",
                )
                try:
                    await asyncio.to_thread(
                        session.wait_for_selector,
                        ready_selector,
                        self.challenge_timeout_ms,
                    )
                except Exception as wait_exc:
                    if session.is_timeout(wait_exc):
                        raise CentralNovelChallengeTimeout(
                            "A verificação do site não foi concluída dentro do prazo."
                        ) from wait_exc
                    raise
        except CentralNovelError:
            raise
        except Exception as exc:
            raise CentralNovelBrowserError(f"Falha ao abrir {url}: {exc}") from exc

    async def _resolve_series_url(self) -> str:
        parsed = urlparse(self.source_url)
        if SERIES_PATH_RE.match(parsed.path):
            return self.source_url

        await self._navigate(self.source_url, CHAPTER_SELECTOR)
        if self._session is None:
            raise CentralNovelBrowserError("Navegador ainda não foi iniciado.")
        href = await asyncio.to_thread(
            self._session.first_attribute,
            "a[href*='/series/']",
            "href",
        )
        if not href:
            raise CentralNovelIndexError(
                "A página do capítulo não contém link para o índice da série."
            )
        series_url = urljoin(self.source_url, href)
        self.validate_source_url(series_url)
        if not SERIES_PATH_RE.match(urlparse(series_url).path):
            raise CentralNovelIndexError("O link de índice da série é inválido.")
        return series_url

    async def discover_chapters(self) -> list[ChapterRef]:
        self.series_url = await self._resolve_series_url()
        await self._navigate(self.series_url, INDEX_SELECTOR)
        if self._session is None:
            raise CentralNovelBrowserError("Navegador ainda não foi iniciado.")
        html = await asyncio.to_thread(self._session.content)
        chapters = self.extract_chapter_refs(
            html,
            start=self.start,
            end=self.end,
        )
        if not chapters:
            raise CentralNovelIndexError(
                "Nenhum capítulo numérico foi encontrado no intervalo solicitado."
            )
        self._emit(
            "index_discovered",
            f"Índice descoberto com {len(chapters)} capítulo(s) numérico(s).",
        )
        return chapters

    async def fetch_chapter(self, chapter: ChapterRef) -> str:
        self.validate_source_url(chapter.url)
        await self._navigate(chapter.url, CHAPTER_SELECTOR)
        if self._session is None:
            raise CentralNovelBrowserError("Navegador ainda não foi iniciado.")
        html = await asyncio.to_thread(self._session.content)
        soup = BeautifulSoup(html, "lxml")
        if soup.select_one(CHAPTER_SELECTOR) is None:
            raise CentralNovelContentError(
                f"Conteúdo do capítulo {chapter.id} não encontrado."
            )
        return html

    async def close(self) -> None:
        session = self._session
        self._session = None
        if session is not None:
            await asyncio.to_thread(session.close)
        self._emit("browser_closed", "Navegador fechado.")
