from __future__ import annotations

import json
import random
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
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
from ldm_kindler.crawler.parse import extract_chapter_id_from
from ldm_kindler.errors import ErrorCode

DEFAULT_HEADERS = {
    "User-Agent": "ldm-kindler/1.0 (+https://example.invalid; uso pessoal)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

CHAPTER_LINK_TEXT = re.compile(r"Capítulo\s+(\d+)", re.IGNORECASE)

_CHAPTER_SLUG_RE = re.compile(r"^(cap[ií]tulo[-_])(\d+)(?:[-_].*)?$", re.IGNORECASE)


def derive_template_from_chapter_url(url: str) -> tuple[str, int, str]:
    """Extrai chapter_id e devolve (url_template, chapter_id, story_path_prefix).

    Substitui o número do capítulo por `{id}` e descarta sufixos do slug (ex.:
    ``capitulo-736-noite`` vira ``capitulo-{id}``). Devolve também o prefixo de
    path da obra (tudo antes do segmento de capítulo, terminado em ``/``) para
    que o crawler possa rejeitar respostas que escapem para outra história
    (mesmo site, mas em outra rota — ex.: ``/story/era-dos-adeptos/``).

    Exemplos:
      >>> derive_template_from_chapter_url(
      ...     "https://illusia.com.br/story/cdi-circulo-da-inevitabilidade/capitulo-736-noite/"
      ... )
      ('https://illusia.com.br/story/cdi-circulo-da-inevitabilidade/capitulo-{id}/', 736, '/story/cdi-circulo-da-inevitabilidade/')
      >>> derive_template_from_chapter_url("https://site/cap/737/")
      ('https://site/cap/{id}/', 737, '/cap/')
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL vazia ou inválida")

    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"URL inválida (sem scheme/host): {url!r}")

    segments = parsed.path.split("/")

    def _story_prefix(chapter_segment_index: int) -> str:
        before = [s for s in segments[:chapter_segment_index] if s]
        if not before:
            return "/"
        return "/" + "/".join(before) + "/"

    # Procura segmento no formato `capitulo-<n>[-slug]`
    for i, seg in enumerate(segments):
        m = _CHAPTER_SLUG_RE.match(seg)
        if m:
            chapter_id = int(m.group(2))
            prefix = _story_prefix(i)
            segments[i] = f"{m.group(1)}{{id}}"
            new_path = "/".join(segments)
            return (
                urlunparse((parsed.scheme, parsed.netloc, new_path, "", "", "")),
                chapter_id,
                prefix,
            )

    # Fallback: segmento puramente numérico (ex.: `/cap/737/`)
    for i, seg in enumerate(segments):
        if seg.isdigit():
            chapter_id = int(seg)
            prefix = _story_prefix(i)
            segments[i] = "{id}"
            new_path = "/".join(segments)
            return (
                urlunparse((parsed.scheme, parsed.netloc, new_path, "", "", "")),
                chapter_id,
                prefix,
            )

    raise ValueError(
        f"Não foi possível identificar o número do capítulo em {url!r} "
        "(esperado segmento como 'capitulo-123' ou '/123/')."
    )


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
    # Quando o usuário passou um link de capítulo (start_url), seguir o `next` do
    # capítulo anterior é mais confiável do que adivinhar pela template (alguns
    # sites têm URLs colidentes entre obras diferentes — ex.: Fictioneer servindo
    # outra história em /capitulo-737/ sem slug).
    prefer_next_link: bool = False
    # Prefixo de path da obra (ex.: ``/story/cdi-circulo-da-inevitabilidade/``).
    # Qualquer URL (composta, descoberta ou pós-redirect) que NÃO comece com este
    # prefixo é considerada "cross-story" e rejeitada como se fosse 404.
    story_path_prefix: str | None = None

    _index_cache: Dict[int, str] = field(default_factory=dict, init=False, repr=False)
    _index_loaded: bool = field(default=False, init=False, repr=False)
    # Motivos ("status: url") das tentativas que falharam no último fetch().
    # Permite que a API mostre no log do job por que um capítulo ficou sem HTML.
    last_failure_reasons: List[str] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self):
        self.session = ThrottleSession(self.min_delay, self.max_delay)
        self._robots = None
        if self.story_path_prefix and not self.story_path_prefix.endswith("/"):
            self.story_path_prefix = self.story_path_prefix + "/"

    def _belongs_to_story(self, url: str) -> bool:
        """True se a URL pertence à obra atual (ou se nenhum prefixo foi definido).

        Compara apenas o início do path; ignora query/fragment. Sem
        ``story_path_prefix`` definido, considera tudo válido (modo legado).
        """
        if not self.story_path_prefix:
            return True
        try:
            return urlparse(url).path.startswith(self.story_path_prefix)
        except Exception:
            return False

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
        rp = robotparser.RobotFileParser(robots_url)
        # Não usar rp.read(): ele baixa via urllib com UA "Python-urllib", que
        # WAFs costumam responder com 403 — e o parser trata 403 como "tudo
        # proibido". Lemos pela nossa sessão (mesmo UA das páginas) e aplicamos
        # a RFC 9309: 4xx → tudo liberado; 5xx/erro de rede → tudo proibido.
        try:
            resp = self.session.get(robots_url)
            status = resp.status_code
            if 200 <= status < 300:
                rp.parse(resp.text.splitlines())
            elif 400 <= status < 500:
                rp.allow_all = True
            else:
                rp.disallow_all = True
        except Exception as e:
            status = None
            rp.disallow_all = True
            print(
                json.dumps(
                    {
                        "level": "WARN",
                        "status": "robots_fetch_failed",
                        "url": robots_url,
                        "error": str(e),
                    }
                )
            )
        if rp.disallow_all:
            print(
                json.dumps(
                    {
                        "level": "WARN",
                        "status": "robots_disallow_all",
                        "url": robots_url,
                        "code": status,
                    }
                )
            )
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
        """Deriva a página da obra: remove o sufixo -capitulo-{id} do último segmento quando existir.

        Evita `.../obra-capitulo-{id}` virar só `.../story/`, que lista o site e mistura links (ex.: cap. 1).
        """
        if not self.url_template:
            raise ValueError("url_template ausente")
        sample = self.url_template.format(id=1)
        parsed = urlparse(sample)
        path = parsed.path.rstrip("/")
        parts = [p for p in path.split("/") if p]
        if not parts:
            raise ValueError("path do template inválido")

        last = parts[-1]
        if re.match(r"(?i)^capitulo-\d+$", last) and len(parts) > 1:
            parts = parts[:-1]
        else:
            stripped = re.sub(r"(?i)-capitulo-\d+$", "", last)
            if stripped and stripped != last:
                if len(parts) >= 2 and stripped == parts[-2]:
                    parts = parts[:-1]
                else:
                    parts[-1] = stripped
            elif len(parts) > 1:
                parts = parts[:-1]
            elif re.match(r"(?i)^capitulo-\d+$", last):
                parts = []
            else:
                raise ValueError("Não foi possível derivar a URL do índice a partir do template")

        if not parts:
            new_path = "/"
        else:
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
            # Primeira ocorrência ganha (evita sidebar/rodapé sobrescrever o link certo do índice)
            if cid not in self._index_cache:
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
        if not self._belongs_to_story(url):
            print(
                json.dumps(
                    {
                        "level": "WARN",
                        "chapter": chapter_id,
                        "status": "cross_story_blocked",
                        "stage": "pre_fetch",
                        "url": url,
                        "expected_prefix": self.story_path_prefix,
                    }
                )
            )
            self.last_failure_reasons.append(f"cross_story_blocked: {url}")
            return None
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
            self.last_failure_reasons.append(f"disallowed_by_robots: {url}")
            return None
        try:
            resp = self._do_fetch(url)
            # Pós-redirect: o site pode ter respondido 200 mas servindo conteúdo
            # de outra obra (URL final fora do prefixo). Trata como 404 lógico
            # para que o fetch() siga para o próximo fallback.
            final_url = getattr(resp, "url", url) or url
            if not self._belongs_to_story(final_url):
                print(
                    json.dumps(
                        {
                            "level": "WARN",
                            "chapter": chapter_id,
                            "status": "cross_story_blocked",
                            "stage": "post_fetch",
                            "url": url,
                            "final_url": final_url,
                            "expected_prefix": self.story_path_prefix,
                        }
                    )
                )
                self.last_failure_reasons.append(f"cross_story_blocked: {final_url}")
                return None
            return resp.text
        except requests.HTTPError as e:
            code = getattr(e.response, "status_code", None)
            self.last_failure_reasons.append(f"http_{code}: {url}")
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
            self.last_failure_reasons.append(f"fetch_failed ({e}): {url}")
            return None

    def _try_candidate(
        self,
        chapter_id: int,
        candidate: Optional[str],
        strategy: str,
        *,
        already_tried: set[str],
    ) -> Optional[tuple[str, str]]:
        """Valida e tenta buscar uma URL candidata. Devolve (html, url) ou None.

        Centraliza a checagem de id no slug + dedupe + log de estratégia, para
        que tanto o caminho ``prefer_next_link=True`` quanto o fallback legado
        compartilhem a mesma lógica.
        """
        if not candidate or candidate in already_tried:
            return None
        # Bloqueia rapidamente URLs fora da obra antes mesmo do GET.
        if not self._belongs_to_story(candidate):
            print(
                json.dumps(
                    {
                        "level": "WARN",
                        "chapter": chapter_id,
                        "status": "cross_story_blocked",
                        "stage": "candidate",
                        "strategy": strategy,
                        "url": candidate,
                        "expected_prefix": self.story_path_prefix,
                    }
                )
            )
            self.last_failure_reasons.append(f"cross_story_blocked: {candidate}")
            return None
        url_id = extract_chapter_id_from("", candidate)
        if url_id is not None and url_id != chapter_id:
            print(
                json.dumps(
                    {
                        "level": "WARN",
                        "status": f"{strategy}_chapter_mismatch",
                        "chapter": chapter_id,
                        "url": candidate,
                        "parsed_from_url": url_id,
                    }
                )
            )
            self.last_failure_reasons.append(f"{strategy}_chapter_mismatch: {candidate}")
            return None
        print(
            json.dumps(
                {
                    "level": "INFO",
                    "status": "url_attempt",
                    "strategy": strategy,
                    "chapter": chapter_id,
                    "url": candidate,
                }
            )
        )
        already_tried.add(candidate)
        html = self._fetch_single(chapter_id, candidate)
        if html is not None:
            return html, candidate
        return None

    def fetch(self, chapter_id: int, url: str) -> tuple[Optional[str], str]:
        """Retorna (html, url_efetiva).

        Ordem das estratégias:
          * Se ``prefer_next_link``: ``next_link`` → ``template`` → ``index``.
          * Caso contrário (legado): ``template`` → ``index`` → ``next_link``.

        Se nenhuma der HTML válido, ``html`` é ``None`` e ``url_efetiva`` é a
        última URL tentada.
        """
        tried: set[str] = set()
        last_url = url
        self.last_failure_reasons = []

        def _strategy_fns():
            template_fn = lambda: url
            next_fn = lambda: self._discover_via_prev_next(chapter_id)
            index_fn = lambda: self._discovered_url_from_index(chapter_id)
            if self.prefer_next_link:
                return [("next_link", next_fn), ("template", template_fn), ("index", index_fn)]
            return [("template", template_fn), ("index", index_fn), ("next_link", next_fn)]

        for strategy, fn in _strategy_fns():
            try:
                candidate = fn()
            except Exception as e:
                print(
                    json.dumps(
                        {
                            "level": "WARN",
                            "status": "strategy_error",
                            "strategy": strategy,
                            "chapter": chapter_id,
                            "error": str(e),
                        }
                    )
                )
                continue
            if not candidate:
                continue
            last_url = candidate
            result = self._try_candidate(chapter_id, candidate, strategy, already_tried=tried)
            if result is not None:
                html, used_url = result
                if strategy != "template":
                    print(
                        json.dumps(
                            {
                                "level": "INFO",
                                "status": "url_resolved",
                                "strategy": strategy,
                                "chapter": chapter_id,
                                "url": used_url,
                            }
                        )
                    )
                return html, used_url

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
        return None, last_url

