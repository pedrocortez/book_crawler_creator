from __future__ import annotations

import json
import random
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from urllib import robotparser
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ldm_kindler.constants import chapter_url
from ldm_kindler.errors import ErrorCode

DEFAULT_HEADERS = {
    "User-Agent": "ldm-kindler/1.0 (+https://example.invalid; uso pessoal)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

CHAPTER_LINK_TEXT = re.compile(r"Capítulo\s+(\d+)", re.IGNORECASE)


class RetryableHTTPError(Exception):
    """429 ou 5xx: o GET pode ser repetido após espera (não confundir com 404)."""

    __slots__ = ("response",)

    def __init__(self, response: requests.Response) -> None:
        self.response = response
        super().__init__(response.status_code)


class ThrottleSession:
    def __init__(self, min_delay: float, max_delay: float):
        self.session = requests.Session()
        self.min_delay = min_delay
        self.max_delay = max_delay

    def get(self, url: str, **kwargs):
        delay = random.uniform(self.min_delay, self.max_delay)
        time.sleep(delay)
        return self.session.get(url, headers=DEFAULT_HEADERS, timeout=30, **kwargs)


@dataclass
class FetchClient:
    min_delay: float = 2.0
    max_delay: float = 5.0
    max_retries: int = 4
    url_template: str | None = None
    url_overrides: Dict[int, str] = field(default_factory=dict)
    cache_store: Any = None  # CacheStore | None (evita import circular em runtime mínimo)

    _index_cache: Dict[int, str] = field(default_factory=dict, init=False, repr=False)
    _index_loaded: bool = field(default=False, init=False, repr=False)

    def __post_init__(self):
        self.session = ThrottleSession(self.min_delay, self.max_delay)
        self._robots = None

    def compose_url(self, chapter_id: int) -> str:
        if chapter_id in self.url_overrides:
            return self.url_overrides[chapter_id]
        if self.url_template:
            return self.url_template.format(id=chapter_id)
        return chapter_url(chapter_id)

    def _get_robots(self, url: str) -> robotparser.RobotFileParser:
        if self._robots is not None:
            return self._robots
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = robotparser.RobotFileParser()
        try:
            rp.set_url(robots_url)
            rp.read()
        except Exception:
            # Conservador: se não conseguir ler, considera permitido apenas leitura esporádica
            pass
        self._robots = rp
        return rp

    def _allowed(self, url: str) -> bool:
        rp = self._get_robots(url)
        agent = DEFAULT_HEADERS["User-Agent"].split("/")[0]
        try:
            return rp.can_fetch(agent, url)
        except Exception:
            return True

    def _do_fetch(self, url: str) -> requests.Response:
        """GET com retentativas só para rede, Timeout e 429/5xx. 404 não retenta."""
        max_att = max(1, int(self.max_retries))

        @retry(
            stop=stop_after_attempt(max_att),
            wait=wait_exponential(multiplier=1, min=1, max=20),
            retry=retry_if_exception_type(
                (requests.ConnectionError, requests.Timeout, RetryableHTTPError)
            ),
            reraise=True,
        )
        def _get() -> requests.Response:
            resp = self.session.get(url, allow_redirects=True)
            if resp.status_code in (429, 500, 502, 503, 504):
                print(
                    json.dumps(
                        {
                            "level": "WARN",
                            "status": "retryable_status",
                            "code": resp.status_code,
                            "url": url,
                        }
                    )
                )
                raise RetryableHTTPError(resp)
            resp.raise_for_status()
            return resp

        try:
            return _get()
        except RetryableHTTPError as e:
            e.response.raise_for_status()

    def _story_index_url(self) -> str:
        if not self.url_template:
            raise ValueError("url_template ausente")
        sample = self.url_template.format(id=1)
        parsed = urlparse(sample)
        path = parsed.path.rstrip("/")
        parts = [p for p in path.split("/") if p]
        if not parts:
            raise ValueError("path do template inválido")
        parts = parts[:-1]
        new_path = "/" + "/".join(parts) + "/"
        return urlunparse((parsed.scheme, parsed.netloc, new_path, "", "", ""))

    def _parse_index_into_cache(self, html: str, index_url: str) -> None:
        soup = BeautifulSoup(html, "lxml")
        for a in soup.select("a[href]"):
            text = a.get_text(" ", strip=True)
            m = CHAPTER_LINK_TEXT.search(text)
            if not m:
                continue
            href = a.get("href")
            if not href:
                continue
            cid = int(m.group(1))
            full = urljoin(index_url, href)
            self._index_cache[cid] = full

    def _ensure_index_cache(self) -> None:
        if self._index_loaded:
            return
        self._index_loaded = True
        if not self.url_template:
            return
        try:
            idx_url = self._story_index_url()
        except ValueError as e:
            print(
                json.dumps(
                    {
                        "level": "WARN",
                        "status": "index_url_derive_failed",
                        "error": str(e),
                    }
                )
            )
            return
        if not self._allowed(idx_url):
            print(
                json.dumps(
                    {"level": "WARN", "status": "index_disallowed_by_robots", "url": idx_url}
                )
            )
            return
        try:
            resp = self._do_fetch(idx_url)
            self._parse_index_into_cache(resp.text, idx_url)
        except Exception as e:
            print(
                json.dumps(
                    {
                        "level": "WARN",
                        "status": "index_fetch_failed",
                        "url": idx_url,
                        "error": str(e),
                    }
                )
            )

    def _discovered_url_from_index(self, chapter_id: int) -> Optional[str]:
        self._ensure_index_cache()
        return self._index_cache.get(chapter_id)

    def _discover_via_prev_next(self, chapter_id: int) -> Optional[str]:
        store = self.cache_store
        if store is None or chapter_id <= 1:
            return None
        prev = store.load_json(chapter_id - 1)
        if not prev:
            return None
        nxt = prev.get("next")
        if not nxt or not isinstance(nxt, str):
            return None
        u = nxt.strip()
        return u or None

    def _fetch_single(self, chapter_id: int, url: str) -> Optional[str]:
        if not self._allowed(url):
            print(
                json.dumps(
                    {
                        "level": "WARN",
                        "chapter": chapter_id,
                        "status": "disallowed_by_robots",
                        "url": url,
                    }
                )
            )
            return None
        try:
            resp = self._do_fetch(url)
            return resp.text
        except requests.HTTPError as e:
            code = getattr(e.response, "status_code", None)
            if code != 404:
                print(
                    json.dumps(
                        {
                            "level": "ERROR",
                            "chapter": chapter_id,
                            "status": "fetch_failed",
                            "url": url,
                            "error": str(e),
                        }
                    )
                )
            return None
        except Exception as e:
            print(
                json.dumps(
                    {
                        "level": "ERROR",
                        "chapter": chapter_id,
                        "status": "fetch_failed",
                        "url": url,
                        "error": str(e),
                    }
                )
            )
            return None

    def fetch(self, chapter_id: int, url: str) -> tuple[Optional[str], str]:
        """
        Retorna (html, url_efetiva).
        Se html é None, url_efetiva é a última URL tentada sem sucesso.
        """
        effective_url = url
        html = self._fetch_single(chapter_id, effective_url)
        if html is not None:
            return html, effective_url

        alt = self._discovered_url_from_index(chapter_id)
        if alt and alt != effective_url:
            print(
                json.dumps(
                    {
                        "level": "INFO",
                        "status": "url_discovered_index",
                        "chapter": chapter_id,
                        "url": alt,
                    }
                )
            )
            html = self._fetch_single(chapter_id, alt)
            if html is not None:
                return html, alt
            effective_url = alt

        alt2 = self._discover_via_prev_next(chapter_id)
        if alt2 and alt2 not in (url, effective_url):
            print(
                json.dumps(
                    {
                        "level": "INFO",
                        "status": "url_discovered_next",
                        "chapter": chapter_id,
                        "url": alt2,
                    }
                )
            )
            html = self._fetch_single(chapter_id, alt2)
            if html is not None:
                return html, alt2
            effective_url = alt2

        print(
            json.dumps(
                {
                    "level": "WARN",
                    "chapter": chapter_id,
                    "status": "url_not_found",
                    "error_code": ErrorCode.JOB_URL_DISCOVERY_FAILED,
                    "url": url,
                }
            )
        )
        return None, effective_url

