from __future__ import annotations

from pathlib import Path

import pytest

from ldm_kindler.crawler.persist import CacheStore


def test_namespaces_isolate_chapters_with_the_same_id(tmp_path: Path) -> None:
    first = CacheStore(tmp_path, namespace="centralnovel/obra-a")
    second = CacheStore(tmp_path, namespace="centralnovel/obra-b")

    first.save_json(1, {"id": 1, "title": "A"})
    second.save_json(1, {"id": 1, "title": "B"})

    assert first.load_json(1)["title"] == "A"
    assert second.load_json(1)["title"] == "B"
    assert first.json_path(1) != second.json_path(1)


@pytest.mark.parametrize(
    "namespace",
    ("../escape", "centralnovel/../../escape", "/absolute", "centralnovel\\obra"),
)
def test_rejects_unsafe_cache_namespace(tmp_path: Path, namespace: str) -> None:
    with pytest.raises(ValueError):
        CacheStore(tmp_path, namespace=namespace)


def test_stats_and_clear_include_legacy_and_namespaced_files(tmp_path: Path) -> None:
    legacy = CacheStore(tmp_path)
    namespaced = CacheStore(tmp_path, namespace="centralnovel/obra")
    legacy.save_html(1, "<p>legado</p>")
    namespaced.save_html(1, "<p>novo</p>")
    namespaced.save_json(1, {"id": 1})

    stats = legacy.stats()

    assert stats["html"]["count"] == 2
    assert stats["json"]["count"] == 1
    assert legacy.clear({"html"}) == {"html": 2, "json": 0}
    assert namespaced.json_path(1).exists()
