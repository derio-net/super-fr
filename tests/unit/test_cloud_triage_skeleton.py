"""Skeleton smoke for the cloud-triage branch (plan 2026-10-07-cloud-triage, P1.T1).

With no `forge.api` setting anywhere, the GitHub factory still hands back the
GraphQL-backed client: the default path is unchanged by this branch.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fr import hostclient
from fr.real_ghclient import RealGhClient


def test_github_backend_defaults_to_the_graphql_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FR_FORGE_API", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert not (tmp_path / ".config" / "fr" / "forge.yaml").exists()
    assert isinstance(hostclient.client_for_backend("github"), RealGhClient)
