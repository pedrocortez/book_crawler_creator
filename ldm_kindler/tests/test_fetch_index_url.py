from __future__ import annotations

from ldm_kindler.crawler.fetch import FetchClient


def test_story_index_strips_capitulo_suffix_on_same_segment():
    c = FetchClient(url_template="https://site/story/obra-longa-capitulo-{id}/")
    assert c._story_index_url() == "https://site/story/obra-longa/"


def test_story_index_nested_when_slug_repeats():
    c = FetchClient(url_template="https://site/story/work-slug/work-slug-capitulo-{id}/")
    assert c._story_index_url() == "https://site/story/work-slug/"


def test_story_index_three_part_path():
    c = FetchClient(
        url_template="https://site/story/pasta/cdi-circulo-da-inevitabilidade-capitulo-{id}/"
    )
    assert c._story_index_url() == "https://site/story/pasta/cdi-circulo-da-inevitabilidade/"
