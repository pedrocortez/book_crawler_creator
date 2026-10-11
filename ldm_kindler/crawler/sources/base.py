"""Contrato de uma fonte (site) de web novel.

O pipeline (``FetchClient`` → ``parse_chapter`` → ``clean_html`` → builders) é
o mesmo para todos os sites. O que muda de um site para outro fica isolado numa
subclasse de :class:`NovelSource`:

* como deduzir o template ``{id}`` a partir do link de um capítulo;
* onde fica o índice da obra e como ler os links de capítulos dele;
* como extrair o número do capítulo de uma URL/título;
* quais seletores CSS contêm título, conteúdo e links anterior/próximo;
* o que remover do conteúdo (anúncios, navegação, botões de compartilhar).

Os padrões desta classe implementam o layout WordPress/Fictioneer usado pela
Illusia; um site novo normalmente só sobrescreve parte deles.
"""
from __future__ import annotations

import re
from typing import ClassVar, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from ldm_kindler.crawler.parse import CHAPTER_REGEX_TITLE, CHAPTER_REGEX_URL

CHAPTER_LINK_TEXT = re.compile(r"Capítulo\s+(\d+)", re.IGNORECASE)

_CHAPTER_SLUG_RE = re.compile(r"^(cap[ií]tulo[-_])(\d+)(?:[-_].*)?$", re.IGNORECASE)
_NAMESPACE_PART_RE = re.compile(r"[^a-z0-9._-]+")


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


def story_index_url_from_template(url_template: str) -> str:
    """Deriva a página da obra: remove o sufixo -capitulo-{id} do último segmento quando existir.

    Evita `.../obra-capitulo-{id}` virar só `.../story/`, que lista o site e mistura links (ex.: cap. 1).
    """
    if not url_template:
        raise ValueError("url_template ausente")
    sample = url_template.format(id=1)
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


def sanitize_namespace(namespace: str) -> Optional[str]:
    """Normaliza um namespace de cache (``a/b``) para nomes de pasta seguros.

    Cada parte vira minúsculas com ``[a-z0-9._-]``; partes vazias, ``.`` e ``..``
    são descartadas, impedindo path traversal. Devolve ``None`` se nada sobrar.
    """
    parts = []
    for raw in re.split(r"[\\/]+", namespace or ""):
        part = _NAMESPACE_PART_RE.sub("-", raw.lower()).strip("-.")
        if part:
            parts.append(part)
    return "/".join(parts) or None


class NovelSource:
    """Fonte genérica; subclasses sobrescrevem só o que o site faz diferente."""

    #: Identificador estável (usado na API, CLI e no namespace do cache).
    name: ClassVar[str] = "generic"
    #: Nome exibido na interface.
    label: ClassVar[str] = "Genérico (WordPress)"
    #: Domínios atendidos (subdomínios e ``www.`` também casam).
    hosts: ClassVar[Tuple[str, ...]] = ()
    #: Exemplo de link de capítulo, mostrado como placeholder na interface.
    example_url: ClassVar[str] = "https://site.com/obra/capitulo-1/"

    # ── Seletores da página de capítulo ──────────────────────────────────────
    title_selector: ClassVar[str] = "h1.entry-title"
    content_selector: ClassVar[str] = "div.entry-content"
    prev_selector: ClassVar[str] = "a.prev, a[rel=prev]"
    next_selector: ClassVar[str] = "a.next, a[rel=next]"
    #: Removidos de dentro do conteúdo antes da limpeza genérica (anúncios etc.).
    content_junk_selectors: ClassVar[Tuple[str, ...]] = ()

    def matches(self, url: str) -> bool:
        """True se a URL pertence a um dos ``hosts`` desta fonte."""
        try:
            host = (urlparse((url or "").strip()).hostname or "").lower()
        except ValueError:
            return False
        return any(host == h or host.endswith("." + h) for h in self.hosts)

    # ── URLs ─────────────────────────────────────────────────────────────────
    def derive_template(self, chapter_url: str) -> tuple[str, int, str]:
        """Link de um capítulo → (url_template com ``{id}``, id, prefixo de path da obra)."""
        return derive_template_from_chapter_url(chapter_url)

    def normalize_story_prefix(self, prefix: str) -> str:
        """Ajusta o prefixo de path da obra usado para bloquear URLs de outras obras.

        Padrão: obra é uma pasta (``/story/obra/``), então garante a ``/`` final
        para ``/story/obra`` não aceitar ``/story/obra-2/``.
        """
        return prefix if prefix.endswith("/") else prefix + "/"

    def story_index_url(self, url_template: str) -> str:
        """URL da página da obra (lista de capítulos) a partir do template."""
        return story_index_url_from_template(url_template)

    def parse_index(self, html: str, index_url: str) -> Dict[int, str]:
        """Lê o índice da obra e devolve ``{id do capítulo: URL absoluta}``."""
        found: Dict[int, str] = {}
        soup = BeautifulSoup(html, "lxml")
        for a in soup.select("a[href]"):
            m = CHAPTER_LINK_TEXT.search(a.get_text(" ", strip=True))
            href = a.get("href")
            if not m or not href:
                continue
            # Primeira ocorrência ganha (evita sidebar/rodapé sobrescrever o link certo do índice)
            found.setdefault(int(m.group(1)), urljoin(index_url, href))
        return found

    # ── Identificação do capítulo ────────────────────────────────────────────
    def chapter_id_from_url(self, url: str) -> Optional[int]:
        matches = CHAPTER_REGEX_URL.findall(url or "")
        return int(matches[-1]) if matches else None

    def chapter_id_from_title(self, title: str) -> Optional[int]:
        m = CHAPTER_REGEX_TITLE.search(title or "")
        return int(m.group(1)) if m else None

    def extract_chapter_id(self, title: str, url: str) -> Optional[int]:
        cid = self.chapter_id_from_title(title)
        return cid if cid is not None else self.chapter_id_from_url(url)

    # ── Cache ────────────────────────────────────────────────────────────────
    def cache_namespace(self, url_template: Optional[str]) -> Optional[str]:
        """Pasta do cache para a obra (``<fonte>/<host>-<obra>``).

        Isola capítulos de mesmo número entre sites e obras diferentes. Usa a
        página da obra quando dá para derivá-la; senão, o trecho do template
        antes de ``{id}``.
        """
        if not url_template:
            return None
        try:
            story_url = self.story_index_url(url_template)
        except (ValueError, KeyError, IndexError):
            story_url = url_template.split("{id}", 1)[0]
        parsed = urlparse(story_url)
        host = (parsed.hostname or "").removeprefix("www.")
        story = parsed.path.strip("/").replace("/", "-")
        key = "-".join(p for p in (host, story) if p)
        return sanitize_namespace(f"{self.name}/{key}")

    def describe(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "label": self.label,
            "hosts": list(self.hosts),
            "example_url": self.example_url,
        }

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name!r}>"


class GenericSource(NovelSource):
    """Fallback para sites sem fonte dedicada (comportamento original)."""
