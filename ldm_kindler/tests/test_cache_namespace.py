from __future__ import annotations

from pathlib import Path

from ldm_kindler.crawler.persist import CacheStore
from ldm_kindler.crawler.sources.base import sanitize_namespace


def test_sanitize_namespace_blocks_traversal():
    assert sanitize_namespace("../../etc/Passwd") == "etc/passwd"
    assert sanitize_namespace("central_novel/Obra X") == "central_novel/obra-x"
    assert sanitize_namespace("..") is None


def test_namespaces_do_not_collide(tmp_path: Path):
    a = CacheStore(tmp_path, namespace="illusia/obra-a")
    b = CacheStore(tmp_path, namespace="central_novel/obra-b")
    a.save_json(1, {"id": 1, "title": "A"})
    assert b.load_json(1) is None
    b.save_json(1, {"id": 1, "title": "B"})
    assert a.load_json(1)["title"] == "A"
    assert b.load_json(1)["title"] == "B"


def test_root_store_stats_and_clear_are_recursive(tmp_path: Path):
    legacy = CacheStore(tmp_path)
    legacy.save_json(1, {"id": 1})
    legacy.save_html(1, "<p/>")
    ns = CacheStore(tmp_path, namespace="central_novel/obra")
    ns.save_json(2, {"id": 2})

    stats = CacheStore(tmp_path).stats()
    assert stats["json"]["count"] == 2
    assert stats["html"]["count"] == 1

    removed = CacheStore(tmp_path).clear({"json"})
    assert removed == {"html": 0, "json": 2}
    assert ns.load_json(2) is None
    assert legacy.stats()["html"]["count"] == 1
