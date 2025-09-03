from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse
from urllib import robotparser

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ldm_kindler.constants import chapter_url


DEFAULT_HEADERS = {
    "User-Agent": "ldm-kindler/1.0 (+https://example.invalid; uso pessoal)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


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

    def __post_init__(self):
        self.session = ThrottleSession(self.min_delay, self.max_delay)
        self._robots = None

    def compose_url(self, chapter_id: int) -> str:
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

    @retry(
        reraise=True,
        retry=retry_if_exception_type((requests.HTTPError, requests.ConnectionError, requests.Timeout)),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=20),
    )
    def _do_fetch(self, url: str) -> requests.Response:
        resp = self.session.get(url, allow_redirects=True)
        if resp.status_code in (429, 500, 502, 503, 504):
            # log e erro para retry
            print(json.dumps({"level": "WARN", "status": "retryable_status", "code": resp.status_code, "url": url}))
            resp.raise_for_status()
        resp.raise_for_status()
        return resp

    def fetch(self, chapter_id: int, url: str) -> Optional[str]:
        if not self._allowed(url):
            print(json.dumps({"level": "WARN", "chapter": chapter_id, "status": "disallowed_by_robots", "url": url}))
            return None
        try:
            resp = self._do_fetch(url)
            return resp.text
        except Exception as e:
            print(json.dumps({
                "level": "ERROR",
                "chapter": chapter_id,
                "status": "fetch_failed",
                "url": url,
                "error": str(e),
            }))
            return None


