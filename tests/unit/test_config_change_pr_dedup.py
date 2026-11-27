"""A configuration change is named by its kind, and a change whose pull request is already
open, or was closed unmerged, is not proposed again on every command (review finding
p4-r12; spec 2026-11-19-event-driven-a-la-carte §B).

Origins are LOCAL bare repos; the forge is the `fr.config.change.open_pr` and
`fr.config.change.prs_for_head` seams.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fr.config import change
from fr.config import migrate as m
from fr.settings import SettingsError

from tests.unit.test_migration_config_kinds import _quiet

TEXT = "opencode:\n  hard: m\n"


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("FR_CONFIG_REPROPOSE", raising=False)


def _forge(monkeypatch: pytest.MonkeyPatch, existing: list[dict[str, Any]]) -> list[str]:
    opened: list[str] = []
    asked: list[str] = []

    def fake_open(remote: str, head: str, base: str, title: str, body: str) -> str:
        opened.append(head)
        return "https://example.com/pr/new"

    def fake_state(remote: str, head: str) -> list[dict[str, Any]]:
        asked.append(head)
        return existing

    monkeypatch.setattr(change, "open_pr", fake_open)
    monkeypatch.setattr(change, "prs_for_head", fake_state)
    return opened


def _root(tmp_path: Path) -> Path:
    root = _quiet(tmp_path)
    assert m.ensure_space(root)
    return root


def test_the_change_branch_names_the_kind() -> None:
    assert change.change_branch(".fr/settings.yaml", "x").startswith("fr-config-change/settings-")
    assert change.change_branch(".fr/models.yaml", "x").startswith("fr-config-change/models-")
    mine = change.change_branch("t/.fr/workflows/mine.yaml", "x")
    assert mine.startswith("fr-config-change/workflows-mine-")
    assert change.change_branch(".fr/models.yaml", "x") != change.change_branch(
        ".fr/models.yaml", "y"
    )


def _pr(state: str, **over: Any) -> dict[str, Any]:
    return {
        "state": state,
        "url": "https://example.com/pr/7",
        "same_repo": True,
        "base": "fr-config",
        **over,
    }


def _push_proposal(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A real earlier proposal: its head branch on origin holds the change."""
    _forge(monkeypatch, [])
    m.QuietWriter(root).propose(".fr/models.yaml", TEXT, "chore(fr): models")


def test_an_open_pull_request_for_the_same_content_is_reused_not_reproposed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    _push_proposal(root, monkeypatch)
    opened = _forge(monkeypatch, [_pr("OPEN")])
    url = m.QuietWriter(root).propose(".fr/models.yaml", TEXT, "chore(fr): models")
    assert url == "https://example.com/pr/7" and opened == []


@pytest.mark.parametrize(
    "record",
    [
        _pr("OPEN", same_repo=False),  # a fork PR whose head carries the same name
        _pr("CLOSED", same_repo=False),
        _pr("OPEN", base="main"),  # not into the configuration branch
        _pr("CLOSED", base="main"),
    ],
)
def test_an_untrusted_earlier_pull_request_is_ignored_and_a_fresh_one_made(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, record: dict[str, Any]
) -> None:
    root = _root(tmp_path)
    opened = _forge(monkeypatch, [record])
    url = m.QuietWriter(root).propose(".fr/models.yaml", TEXT, "chore(fr): models")
    assert url == "https://example.com/pr/new" and len(opened) == 1


def test_an_open_pull_request_whose_head_lacks_the_bytes_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)  # no head branch was ever pushed: nothing proves the content
    opened = _forge(monkeypatch, [_pr("OPEN")])
    url = m.QuietWriter(root).propose(".fr/models.yaml", TEXT, "chore(fr): models")
    assert url == "https://example.com/pr/new" and len(opened) == 1


def test_a_closed_unmerged_pull_request_refuses_naming_it_and_how_to_repropose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    opened = _forge(monkeypatch, [_pr("CLOSED")])
    with pytest.raises(SettingsError, match="--repropose") as refused:
        m.QuietWriter(root).propose(".fr/models.yaml", TEXT, "chore(fr): models")
    assert "https://example.com/pr/7" in str(refused.value) and opened == []

    monkeypatch.setenv("FR_CONFIG_REPROPOSE", "1")
    url = m.QuietWriter(root).propose(".fr/models.yaml", TEXT, "chore(fr): models")
    assert url == "https://example.com/pr/new" and len(opened) == 1


def test_a_merged_or_absent_pull_request_proposes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    opened = _forge(monkeypatch, [_pr("MERGED")])
    assert m.QuietWriter(root).propose(".fr/models.yaml", TEXT, "m") == "https://example.com/pr/new"
    assert len(opened) == 1


def test_the_default_forge_read_keeps_only_same_repo_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fr.hostclient as hostclient

    class _Client:
        def list_prs_by_head(self, repo: str, head: str) -> list[dict[str, Any]]:
            return [
                {"number": 1, "state": "OPEN", "url": "u1", "isCrossRepository": True},
                {"number": 2, "state": "CLOSED", "url": "u2", "isCrossRepository": False},
            ]

        def pr_view(self, repo: str, number: int) -> dict[str, Any]:
            assert number == 2
            return {"base_ref": "fr-config", "head_oid": "abc"}

    monkeypatch.setattr(hostclient, "client_for_url", lambda _u: _Client())
    found = change._forge_prs_for_head("https://github.com/example-org/r.git", "h")
    assert found == [
        {"state": "CLOSED", "url": "u2", "same_repo": True, "base": "fr-config", "head_oid": "abc"}
    ]


def test_the_migrate_command_takes_repropose(tmp_path: Path) -> None:
    from fr.cli import app
    from typer.testing import CliRunner

    done = CliRunner().invoke(app, ["migrate", "artifacts", "--help"])
    assert "--repropose" in done.output


class _OpenClient:
    """A forge client for `_forge_open_pr`: *found* is what `open_pr_in_repo` answers,
    *base* the base `pr_view` reports for it."""

    def __init__(self, found: dict[str, Any] | None, base: str = "fr-config") -> None:
        self.found, self.base = found, base
        self.created: list[str] = []

    def open_pr_in_repo(self, repo: str, branch: str) -> dict[str, Any] | None:
        return self.found

    def open_pr_for_head(self, repo: str, branch: str) -> dict[str, Any] | None:
        raise AssertionError("the head filter alone matches a fork's PR (l-security-r4)")

    def pr_view(self, repo: str, number: int) -> dict[str, Any]:
        return {"base_ref": self.base, "head_oid": "abc"}

    def create_pr(self, repo: str, **kw: Any) -> dict[str, Any]:
        self.created.append(kw["base"])
        return {"url": "https://example.com/pr/new"}


def test_open_pr_reuses_only_a_same_repo_pull_request_into_the_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lens review l-security-r4: the open pull request reused is one whose head lives in the
    target repo (`open_pr_in_repo`) and that merges into the configuration branch."""
    import fr.hostclient as hostclient

    client = _OpenClient({"number": 3, "url": "https://example.com/pr/3"})
    monkeypatch.setattr(hostclient, "client_for_url", lambda _u: client)
    url = change._forge_open_pr("https://github.com/example-org/r.git", "h", "fr-config", "t", "b")
    assert url == "https://example.com/pr/3" and client.created == []


def test_open_pr_refuses_an_open_pull_request_into_another_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fr.hostclient as hostclient

    client = _OpenClient({"number": 3, "url": "https://example.com/pr/3"}, base="main")
    monkeypatch.setattr(hostclient, "client_for_url", lambda _u: client)
    with pytest.raises(SettingsError, match="into `main`, not `fr-config`"):
        change._forge_open_pr("https://github.com/example-org/r.git", "h", "fr-config", "t", "b")
    assert client.created == []


def test_a_failed_forge_read_of_earlier_proposals_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lens review l-errors-r3: a forge error must not read as "no earlier pull request",
    which would silently re-propose a change an operator closed unmerged."""
    import fr.hostclient as hostclient
    from fr.gh import GhError

    class _Broken:
        def list_prs_by_head(self, repo: str, head: str) -> list[dict[str, Any]]:
            raise GhError("gh: Server Error (HTTP 502)", stderr="HTTP 502")

    monkeypatch.setattr(hostclient, "client_for_url", lambda _u: _Broken())
    with pytest.raises(SettingsError, match="HTTP 502"):
        change._forge_prs_for_head("https://github.com/example-org/r.git", "h")


def test_a_forge_that_cannot_list_pull_requests_answers_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fr.hostclient as hostclient
    from fr.ghclient import UnsupportedForgeOperation

    class _Tea:
        def list_prs_by_head(self, repo: str, head: str) -> list[dict[str, Any]]:
            raise UnsupportedForgeOperation("list_prs_by_head", "tea")

    monkeypatch.setattr(hostclient, "client_for_url", lambda _u: _Tea())
    assert change._forge_prs_for_head("https://github.com/example-org/r.git", "h") == []


@pytest.mark.parametrize("where", ["run", "push"])
def test_a_git_timeout_is_a_refusal_not_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, where: str
) -> None:
    """Lens review l-errors-r4: a git call that times out says so and that nothing changed."""
    import subprocess

    real = subprocess.run

    def slow(argv: list[str], *a: Any, **kw: Any) -> Any:
        hit = ("rev-parse" in argv) if where == "run" else ("push" in argv)
        if hit:
            raise subprocess.TimeoutExpired(argv, 60)
        return real(argv, *a, **kw)

    root = _quiet(tmp_path)
    monkeypatch.setattr(change, "prs_for_head", lambda r, h: [])
    monkeypatch.setattr(change.subprocess, "run", slow)
    with pytest.raises(SettingsError, match="timed out") as refused:
        change.open_change(
            root, product=root, remote="https://github.com/example-org/r.git",
            base_branch="main", base_ref="origin/main", rel=".fr/models.yaml", text="x: 1\n",
            message="m",
        )  # fmt: skip
    assert "run the command again" in str(refused.value)
