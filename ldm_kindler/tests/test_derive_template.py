from __future__ import annotations

import pytest

from ldm_kindler.crawler.fetch import derive_template_from_chapter_url


def test_derives_template_and_id_from_illusia_url():
    url = "https://illusia.com.br/story/cdi-circulo-da-inevitabilidade/capitulo-736-noite/"
    template, cid, prefix = derive_template_from_chapter_url(url)
    assert cid == 736
    assert (
        template
        == "https://illusia.com.br/story/cdi-circulo-da-inevitabilidade/capitulo-{id}/"
    )
    assert prefix == "/story/cdi-circulo-da-inevitabilidade/"


def test_strips_multi_word_slug_suffix():
    url = "https://x/cap/capitulo-12-titulo-com-traços/"
    template, cid, prefix = derive_template_from_chapter_url(url)
    assert cid == 12
    assert template == "https://x/cap/capitulo-{id}/"
    assert prefix == "/cap/"


def test_handles_url_without_trailing_slash():
    url = "https://x/cap/capitulo-1-intro"
    template, cid, prefix = derive_template_from_chapter_url(url)
    assert cid == 1
    assert template == "https://x/cap/capitulo-{id}"
    assert prefix == "/cap/"


def test_falls_back_to_numeric_segment():
    url = "https://site/livro/737/"
    template, cid, prefix = derive_template_from_chapter_url(url)
    assert cid == 737
    assert template == "https://site/livro/{id}/"
    assert prefix == "/livro/"


def test_chapter_without_slug_suffix():
    url = "https://site/story/x/capitulo-50/"
    template, cid, prefix = derive_template_from_chapter_url(url)
    assert cid == 50
    assert template == "https://site/story/x/capitulo-{id}/"
    assert prefix == "/story/x/"


def test_raises_on_missing_chapter_number():
    with pytest.raises(ValueError):
        derive_template_from_chapter_url("https://site/sobre/")


def test_raises_on_invalid_url():
    with pytest.raises(ValueError):
        derive_template_from_chapter_url("not-a-url")
    with pytest.raises(ValueError):
        derive_template_from_chapter_url("")


def test_derived_template_is_compatible_with_index_derivation():
    """O template gerado deve permitir ao FetchClient derivar o índice da obra."""
    from ldm_kindler.crawler.fetch import FetchClient

    template, _, _ = derive_template_from_chapter_url(
        "https://illusia.com.br/story/cdi-circulo-da-inevitabilidade/capitulo-736-noite/"
    )
    client = FetchClient(url_template=template)
    assert (
        client._story_index_url()
        == "https://illusia.com.br/story/cdi-circulo-da-inevitabilidade/"
    )
