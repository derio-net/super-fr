"""Forge-error classification on every backend (spec 2026-10-06-forge-remainder
§4.C, R4; Test Plan 9).

`fr.hostclient.forge_error_kind` reads any `FORGE_ERRORS` member, so the fr-vk
bridge's rate-limit guard backs a tick off on a GitLab or Gitea rate limit too,
not only on GitHub's — and still re-raises anything that is not one.
"""

from __future__ import annotations

from typing import Any

import pytest
from fr.gh import GhError
from fr.glab import GlabError
from fr.hostclient import forge_error_kind
from fr.tea import TeaError


@pytest.mark.parametrize(
    ("exc", "kind"),
    [
        (GhError("API rate limit exceeded", stderr="HTTP 403: API rate limit exceeded"), "rate_limit"),
        (GlabError("boom", stderr="429 Too Many Requests: rate limit reached"), "rate_limit"),
        (TeaError("429 Too Many Requests: rate limit exceeded"), "rate_limit"),
        (GlabError("403 Forbidden: API rate limit exceeded"), "rate_limit"),
        (GhError("HTTP 404: Not Found", stderr="HTTP 404"), "info"),
        (GlabError("404 Not Found"), "info"),
        (TeaError("x", stderr="404 not found"), "info"),
        (GlabError("connection reset by peer"), "warn"),
        (TeaError("HTTP 502 Bad Gateway"), "warn"),
        (GlabError("permission denied"), "unknown"),
        (ValueError("429 rate limit"), "unknown"),
    ],
)  # fmt: skip
def test_forge_error_kind_classifies_every_backend(exc: BaseException, kind: str) -> None:
    assert forge_error_kind(exc) == kind


def _pushed(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    from fr_vk import bridge_cli

    pushed: list[str] = []

    def fake_push(*, reason: str) -> None:
        pushed.append(reason)

    monkeypatch.setattr(bridge_cli._metrics, "push_failure_total", fake_push)
    return pushed


@pytest.mark.parametrize(
    "exc",
    [
        GlabError("boom", stderr="429 Too Many Requests: rate limit reached"),
        TeaError("429 Too Many Requests: rate limit exceeded"),
        GhError("x", stderr="HTTP 403: API rate limit exceeded"),
    ],
)
def test_the_bridge_guard_backs_off_on_any_forges_rate_limit(
    monkeypatch: pytest.MonkeyPatch, exc: Exception
) -> None:
    from fr_vk import bridge_cli

    pushed = _pushed(monkeypatch)

    def boom() -> Any:
        raise exc

    assert bridge_cli._gh_rate_limit_guard(boom) is None
    assert pushed == ["gh_rate_limited"]  # dashboards key on this reason


def test_the_bridge_guard_reraises_a_non_rate_limit_glab_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fr_vk import bridge_cli

    pushed = _pushed(monkeypatch)

    def boom() -> Any:
        raise GlabError("permission denied", stderr="403 Forbidden")

    with pytest.raises(GlabError):
        bridge_cli._gh_rate_limit_guard(boom)
    assert pushed == []
