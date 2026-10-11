"""Registro das fontes (sites) suportadas.

Para adicionar um site: crie uma subclasse de ``NovelSource`` em um módulo
deste pacote e inclua uma instância em ``_SOURCES`` abaixo.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from ldm_kindler.crawler.sources.base import GenericSource, NovelSource
from ldm_kindler.crawler.sources.central_novel import CentralNovelSource
from ldm_kindler.crawler.sources.illusia import IllusiaSource

_GENERIC = GenericSource()
_SOURCES: Dict[str, NovelSource] = {
    s.name: s for s in (IllusiaSource(), CentralNovelSource(), _GENERIC)
}


def list_sources() -> List[NovelSource]:
    return list(_SOURCES.values())


def get_source(name: str) -> NovelSource:
    try:
        return _SOURCES[name]
    except KeyError:
        valid = ", ".join(sorted(_SOURCES))
        raise ValueError(f"Fonte desconhecida: {name!r} (válidas: {valid})") from None


def detect_source(url: Optional[str]) -> NovelSource:
    """Fonte cujo domínio casa com a URL; ``generic`` se nenhuma casar."""
    for source in _SOURCES.values():
        if source.matches(url or ""):
            return source
    return _GENERIC


def resolve_source(name: Optional[str], url: Optional[str]) -> NovelSource:
    """Fonte pelo nome explícito, ou detectada pela URL quando ``name`` é vazio/``auto``."""
    if name and name != "auto":
        return get_source(name)
    return detect_source(url)


__all__ = [
    "NovelSource",
    "GenericSource",
    "IllusiaSource",
    "CentralNovelSource",
    "list_sources",
    "get_source",
    "detect_source",
    "resolve_source",
]
