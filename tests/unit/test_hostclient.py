"""Tests for fr.hostclient — the single factory that turns "which backend"
into "which GhClient-shaped instance," replacing every hardcoded
RealGhClient() construction (see docs/superpowers/specs/
2026-07-09-multi-backend-git-host-adapters-design.md §3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr import _hosts, hostclient
from fr.real_ghclient import RealGhClient
from fr.real_glabclient import RealGlabClient
from fr.real_teaclient import RealTeaClient


@pytest.mark.parametrize(
    ("backend", "expected_type"),
    [
        ("github", RealGhClient),
        ("gitlab", RealGlabClient),
        ("gitea", RealTeaClient),
    ],
)
def test_client_for_dispatches_by_detected_backend(
    monkeypatch: pytest.MonkeyPatch, backend: str, expected_type: type, tmp_path: Path
) -> None:
    monkeypatch.setattr(_hosts, "detect_backend", lambda repo_root: backend)
    client = hostclient.client_for(tmp_path)
    assert isinstance(client, expected_type)
