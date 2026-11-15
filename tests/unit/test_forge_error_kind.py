"""Forge-error classification on every backend (spec 2026-10-06-forge-remainder
§4.C, R4; Test Plan 9).

`fr.hostclient.forge_error_kind` reads any `FORGE_ERRORS` member, so a caller
can back off on a GitLab or Gitea rate limit too, not only on GitHub's — and
still re-raise anything that is not one.
"""

from __future__ import annotations

import pytest
from fr.gh import GhError, GhHostRefusedError
from fr.glab import GlabError
from fr.hostclient import forge_error_kind
from fr.tea import TeaError


@pytest.mark.parametrize(
    ("exc", "kind"),
    [
        (GhError("rate limited", stderr="HTTP 403: API rate limit exceeded"), "rate_limit"),
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
        # The host trust gate's refusal is no rate limit: never backed off (review p2-r2).
        (GhHostRefusedError("GitHub host 'ghe.example' is not one gh is logged into"), "unknown"),
    ],
)  # fmt: skip
def test_forge_error_kind_classifies_every_backend(exc: BaseException, kind: str) -> None:
    assert forge_error_kind(exc) == kind
