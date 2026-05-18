"""Tests for `vk.gh._classify_error` — port of the legacy bridge's
`_classify_gh_error` (concern M)."""

from __future__ import annotations

from vk.gh import _classify_error


def test_rate_limit_classified():
    assert _classify_error("HTTP 403: API rate limit exceeded") == "rate_limit"


def test_not_found_classified_info():
    assert _classify_error("HTTP 404: Not Found") == "info"


def test_unknown_returns_unknown():
    assert _classify_error("connection reset") == "warn"  # transient pattern
    assert _classify_error("something else") == "unknown"


def test_case_insensitive():
    assert _classify_error("Not Found") == "info"
    assert _classify_error("API Rate Limit exceeded HTTP 403") == "rate_limit"
