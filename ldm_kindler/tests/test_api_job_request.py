from __future__ import annotations

import pytest
from pydantic import ValidationError

from ldm_kindler.api import JobRequest


def test_generic_request_remains_backwards_compatible() -> None:
    request = JobRequest(
        url_template="https://example.com/capitulo-{id}/",
        start=1,
        end=3,
    )

    assert request.source == "generic"
    assert request.start == 1
    assert request.end == 3


def test_central_novel_request_defaults_to_first_and_detects_last() -> None:
    request = JobRequest(
        source="central_novel",
        source_url="https://centralnovel.com/series/the-beginning-after-the-end/",
    )

    assert request.url_template is None
    assert request.start == 1
    assert request.end is None


def test_central_novel_request_rejects_other_hosts() -> None:
    with pytest.raises(ValidationError, match="centralnovel.com"):
        JobRequest(
            source="central_novel",
            source_url="https://centralnovel.com.evil.example/series/x/",
        )


def test_generic_request_still_requires_end_and_url() -> None:
    with pytest.raises(ValidationError):
        JobRequest(start=1)
