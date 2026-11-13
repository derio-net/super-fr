"""No fr file and no forge write reaches a stealth target (spec
2026-11-04-repo-feature-settings R24 "what reaches the target"; review p4-r3, p4-r5,
p4-r9). Local bare repos only; the forge is never called (a call would be a trace).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fr.cli import app
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.placement import stealth
from typer.testing import CliRunner

from tests.unit.settings_repo import git
from tests.unit.stealth_repo import stealth_home, stealth_pair

__all__ = ["stealth_home"]


@pytest.fixture
def ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    """(stealth workspace, tracking bare repo, target's bare origin); cwd in the workspace."""
    target, track = stealth_pair(tmp_path)
    state = HostWorktreeTarget(target).up(
        profile=None, branch="feat/s", stealth=stealth.parse_ref(f"{track}@main")
    )
    monkeypatch.chdir(state.worktree)
    return state.worktree, track, tmp_path / "origin.git"


def _fr(root: Path, *argv: str):
    return CliRunner().invoke(app, list(argv), env={**os.environ, "VK_REPO_ROOT": str(root)})


def _files(root: Path) -> set[str]:
    return {
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file() and ".git" not in p.relative_to(root).parts
    }


@pytest.mark.parametrize(
    "argv",
    [
        ("init", "agents"),
        ("init", "validator-wrapper"),
        ("init", "scaffold", "--profile", "dev", "--purpose", "p", "--ci", "none",
         "--tracking", "none"),
        ("init", "migrate", "--yes"),
        ("settings", "init"),
        ("settings", "init", "--quiet"),
    ],
)  # fmt: skip
def test_repo_configuration_writers_refuse_before_writing(
    ws: tuple[Path, Path, Path], argv: tuple[str, ...]
) -> None:
    root, _, origin = ws
    before = _files(root)
    refs_before = git(origin, "show-ref")
    result = _fr(root, *argv)
    assert result.exit_code == 2, result.output
    assert "placement stealth" in " ".join(result.output.split())
    assert _files(root) == before
    assert git(origin, "show-ref") == refs_before


def test_push_refuses_a_commit_carrying_an_fr_path(ws: tuple[Path, Path, Path]) -> None:
    root, _, origin = ws
    agent = root / ".claude/agents/fr-phase-executor.md"
    agent.parent.mkdir(parents=True)
    agent.write_text("an fr agent, written by hand\n")
    (root / "code.txt").write_text("code\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "feat(s): code")
    result = _fr(root, "push")
    assert result.exit_code == 2, result.output
    assert ".claude/agents/fr-phase-executor.md" in " ".join(result.output.split())
    assert "refs/heads/feat/s" not in git(origin, "show-ref")


def test_push_sends_a_code_only_commit(ws: tuple[Path, Path, Path]) -> None:
    root, _, origin = ws
    (root / "code.txt").write_text("code\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "feat(s): code")
    assert _fr(root, "push").exit_code == 0
    assert "refs/heads/feat/s" in git(origin, "show-ref")


def test_up_again_on_a_stealth_workspace_with_a_plan_needs_no_validator_wrapper(
    ws: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """Review p4-r4: the plans live in the tracking repo, so the product branch owes no
    scripts/validate-plans.sh, and re-entering the workspace does not demand one."""
    root, track, _ = ws
    made = _fr(root, "plan", "create", "--slug", "2026-11-12-s", "--target-repo", "derio-net/s")
    assert made.exit_code == 0, made.output
    assert not (root / "scripts/validate-plans.sh").exists()
    again = HostWorktreeTarget(tmp_path / "work").up(
        profile=None, branch="feat/s", stealth=stealth.parse_ref(f"{track}@main")
    )
    assert again.worktree == root


@pytest.mark.parametrize(
    "rel",
    [
        'docs/superpowers/plans/ünïcode "quoted".md',  # C-quoted by default
        "docs/superpowers/new\nline.md",  # a newline inside the name
        "Docs/Superpowers/plans/case.md",  # a case variant of fr's tree
        ".FR/settings.yaml",
    ],
)
def test_push_refuses_fr_paths_however_they_are_spelled(
    ws: tuple[Path, Path, Path], rel: str
) -> None:
    root, _, origin = ws
    path = root / rel
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n")
    except OSError:
        pytest.skip(f"this filesystem cannot hold {rel!r}")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "feat(s): code")
    result = _fr(root, "push")
    assert result.exit_code == 2, result.output
    assert "no fr file reaches the target" in " ".join(result.output.split())
    assert "refs/heads/feat/s" not in git(origin, "show-ref")


# --- review p4-r5: no forge write but the one draft PR reaches a stealth target ---------


class _RecordingForge:
    """Answers every read with nothing and records every call; a write is a trace."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def create_pr(self, repo: str, **kw: object) -> dict[str, object]:
        self.calls.append("create_pr")
        return {"number": 7, "url": "https://example.com/acme/widget/pull/7"}

    def __getattr__(self, name: str) -> object:
        def call(*a: object, **kw: object) -> object:
            self.calls.append(name)
            return None

        return call


@pytest.fixture
def forge(monkeypatch: pytest.MonkeyPatch) -> _RecordingForge:
    """The fake BELOW the guard: every factory (`client_for`, `client_for_url`) builds it
    through `client_for_backend`, so what reaches it is what the guard let through."""
    import fr.hostclient as hostclient

    fake = _RecordingForge()
    monkeypatch.setattr(hostclient, "_client_for_backend", lambda backend, host=None: fake)
    return fake


def _writes(forge: _RecordingForge) -> list[str]:
    from fr.placement.forge_guard import WRITE_METHODS

    return [c for c in forge.calls if c in WRITE_METHODS]


@pytest.mark.parametrize(
    "argv",
    [
        ("apply", "{plan}", "--yes"),
        ("undispatch", "{plan}", "--yes"),
        ("gate", "pass", "--pr", "1", "--gate", "tester", "--notes", "n", "--repo",
         "acme/widget", "--host", "example.com", "--yes"),
        ("gate", "backfill", "--yes"),
        ("debt", "issue", "--yes"),
        ("acceptance", "comment", "--pr", "1", "--yes"),
    ],
)  # fmt: skip
def test_forge_writers_refuse_and_write_nothing(
    ws: tuple[Path, Path, Path], forge: _RecordingForge, argv: tuple[str, ...]
) -> None:
    root, _, _ = ws
    made = _fr(root, "plan", "create", "--slug", "2026-11-12-s", "--target-repo", "acme/widget")
    assert made.exit_code == 0, made.output
    from fr.artifacts.paths import artifact_root

    plan = artifact_root(root) / "docs/superpowers/plans/2026-11-12-s"
    result = _fr(root, *(a.replace("{plan}", str(plan)) for a in argv))
    assert result.exit_code == 2, result.output
    assert _writes(forge) == []


def test_the_client_layer_refuses_every_write_but_the_draft_pr(
    ws: tuple[Path, Path, Path], forge: _RecordingForge
) -> None:
    from fr import gh
    from fr.hostclient import client_for, client_for_url
    from fr.placement.forge_guard import StealthForgeWriteError

    root, _, _ = ws
    for client in (client_for(root), client_for_url("https://example.com/acme/widget")):
        for write in ("create_issue", "comment_pr", "edit_pr_labels", "ensure_labels", "edit_pr"):
            with pytest.raises(StealthForgeWriteError, match="R24"):
                getattr(client, write)("acme/widget")
        assert client.create_pr("acme/widget", draft=True)["number"] == 7  # the one draft
        client.pr_view("acme/widget", 1)  # reads pass
    with pytest.raises(StealthForgeWriteError):
        gh.create_issue(repo="acme/widget", title="t", body="b", labels=[])
    assert _writes(forge) == ["create_pr", "create_pr"]


def test_outside_stealth_the_client_is_not_wrapped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, forge: _RecordingForge
) -> None:
    from fr.hostclient import client_for

    target, _ = stealth_pair(tmp_path)
    monkeypatch.chdir(target)
    assert client_for(target) is forge


def test_acceptance_init_names_the_stealth_placement(ws: tuple[Path, Path, Path]) -> None:
    """Review p4-r9: the refusal and the note name stealth and R24, not quiet and R23."""
    root, _, _ = ws
    refused = _fr(root, "acceptance", "init", "--refresh-ci")
    text = " ".join(refused.output.split())
    assert refused.exit_code == 2, refused.output
    assert "placement stealth" in text and "R24" in text and "quiet" not in text
    done = _fr(root, "acceptance", "init")
    text = " ".join(done.output.split())
    assert done.exit_code == 0, done.output
    assert "under placement stealth" in text and "R24" in text and "quiet" not in text
