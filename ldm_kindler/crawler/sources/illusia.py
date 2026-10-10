"""Illusia (illusia.com.br) — tema WordPress/Fictioneer.

O layout da Illusia é o padrão de :class:`NovelSource`; esta classe só associa
os domínios à fonte (detecção automática e namespace de cache próprio).

Particularidades já cobertas pelos padrões:
  * capítulos em ``/story/<obra>/capitulo-<n>[-slug]/`` (slug muda por capítulo);
  * índice em ``/story/<obra>/`` com links de texto "Capítulo N";
  * ``a[rel=next]`` aponta para o próximo capítulo — e é a forma mais confiável
    de achá-lo, porque ``/capitulo-<n>/`` sem slug pode servir outra obra.
"""
from __future__ import annotations

from ldm_kindler.crawler.sources.base import NovelSource


class IllusiaSource(NovelSource):
    name = "illusia"
    label = "Illusia"
    hosts = ("illusia.com.br",)
    example_url = "https://illusia.com.br/story/cdi-circulo-da-inevitabilidade/capitulo-736-noite/"
