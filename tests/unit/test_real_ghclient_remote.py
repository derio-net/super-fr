"""RealGhClient.list_dir / read_file build the right `gh api` invocations
(contents API) and fail-soft the way the cross-repo resolver expects (#339)."""

from __future__ import annotations

import pytest
from fr import gh as _gh
from fr.gh import GhError
from fr.real_ghclient import RealGhClient


def test_list_dir_builds_contents_jq_and_splits(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []

    def fake_run(args: list[str]) -> str:
        seen.append(args)
        return "01.yaml\n02.yaml\n_meta.yaml\n"

    monkeypatch.setattr(_gh, "_run_gh", fake_run)
    out = RealGhClient().list_dir("owner/repo", "docs/superpowers/plans/p")
    assert out == ["01.yaml", "02.yaml", "_meta.yaml"]
    assert seen == [
        ["api", "repos/owner/repo/contents/docs/superpowers/plans/p", "--jq", ".[].name"]
    ]


def test_list_dir_gherror_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(args: list[str]) -> str:
        raise GhError("404")

    monkeypatch.setattr(_gh, "_run_gh", boom)
    assert RealGhClient().list_dir("owner/repo", "docs/superpowers/plans/nope") == []


def test_read_file_uses_raw_accept_header(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []

    def fake_run(args: list[str]) -> str:
        seen.append(args)
        return "phase:\n  number: 1\n"

    monkeypatch.setattr(_gh, "_run_gh", fake_run)
    out = RealGhClient().read_file("owner/repo", "docs/superpowers/plans/p/01.yaml")
    assert out == "phase:\n  number: 1\n"
    assert seen == [
        [
            "api",
            "repos/owner/repo/contents/docs/superpowers/plans/p/01.yaml",
            "-H",
            "Accept: application/vnd.github.raw",
        ]
    ]


def test_read_file_propagates_gherror(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(args: list[str]) -> str:
        raise GhError("404")

    monkeypatch.setattr(_gh, "_run_gh", boom)
    with pytest.raises(GhError):
        RealGhClient().read_file("owner/repo", "docs/superpowers/plans/p/missing.yaml")
