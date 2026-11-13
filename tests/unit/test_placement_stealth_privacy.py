"""Privacy and the target's traces (spec 2026-11-04-repo-feature-settings R24 "privacy",
"what reaches the target"; plan 2026-11-12-placement-resolver phase 4, task 4).

Every visibility is answered by the injected port (`fr.placement.stealth.visibility`):
no forge is called. The PR is opened through a fake forge client.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.isolation.types import IsolationError
from fr.placement import stealth
from fr.settings import SettingsError
from fr.triage.privacy import more_visible
from typer.testing import CliRunner

from tests.unit.settings_repo import git
from tests.unit.stealth_repo import stealth_home, stealth_pair, tracked_files

__all__ = ["stealth_home"]


def _visibility(monkeypatch: pytest.MonkeyPatch, answers: dict[str, str | None]) -> None:
    monkeypatch.setattr(
        stealth, "visibility", lambda repo, checkout=None: answers.get(repo, "private")
    )


def test_visibility_ordering() -> None:
    assert more_visible("public", "private") and more_visible("internal", "private")
    assert more_visible("public", "internal")
    assert not more_visible("private", "private") and not more_visible("private", "public")
    assert more_visible("unknown", "public") is False and more_visible("unknown", "private")
    # review p4-r8: an unrecognised TARGET visibility is read as private (fail closed)
    assert more_visible("public", "secret-ish") and more_visible("internal", "")
    assert more_visible("weird", "odd")


@pytest.mark.parametrize("tracking", ["public", "internal"])
def test_up_refuses_a_tracking_repo_more_visible_than_the_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tracking: str
) -> None:
    target, track = stealth_pair(tmp_path)
    _visibility(monkeypatch, {str(track): tracking, str(tmp_path / "origin.git"): "private"})
    with pytest.raises(IsolationError, match="R24 privacy") as caught:
        HostWorktreeTarget(target).up(
            profile=None, branch="feat/s", stealth=stealth.parse_ref(f"{track}@main")
        )
    assert tracking in str(caught.value)
    assert not (Path(os.environ["HOME"]) / ".cache").exists()


def test_up_refuses_an_unreadable_visibility_naming_the_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target, track = stealth_pair(tmp_path)
    _visibility(monkeypatch, {str(track): None})
    with pytest.raises(IsolationError, match=f"cannot read the visibility of {track}"):
        HostWorktreeTarget(target).up(
            profile=None, branch="feat/s", stealth=stealth.parse_ref(f"{track}@main")
        )


@pytest.mark.parametrize(("tracking", "target"), [("private", "public"), ("public", "public")])
def test_up_passes_the_same_or_less_visible_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tracking: str, target: str
) -> None:
    repo, track = stealth_pair(tmp_path)
    _visibility(monkeypatch, {str(track): tracking, str(tmp_path / "origin.git"): target})
    state = HostWorktreeTarget(repo).up(
        profile=None, branch="feat/s", stealth=stealth.parse_ref(f"{track}@main")
    )
    assert state.placement == "stealth"


def test_a_local_pair_is_private_on_both_sides_without_asking(tmp_path: Path) -> None:
    """The default port: a local path is private, so no forge is asked at all."""
    repo, track = stealth_pair(tmp_path)
    assert stealth.visibility(str(track)) == "private"
    stealth.check_privacy(stealth.parse_ref(f"{track}@main"), str(tmp_path / "origin.git"))


def test_init_stealth_refuses_a_public_tracking_repo_for_a_private_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Security relay (phase 4): `init --stealth` held no privacy guard of its own."""
    target, track = stealth_pair(tmp_path)
    _visibility(monkeypatch, {str(track): "public"})
    before = git(track, "rev-parse", "main")
    monkeypatch.chdir(target)
    result = CliRunner().invoke(
        app,
        ["settings", "init", "--stealth", f"{track}@main"],
        env={**os.environ, "VK_REPO_ROOT": str(target)},
    )
    assert result.exit_code == 2, result.output
    assert "R24 privacy" in " ".join(result.output.split())
    assert git(track, "rev-parse", "main") == before
    assert not (Path(os.environ["HOME"]) / ".cache").exists()


def test_the_push_seam_itself_refuses_without_a_privacy_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No caller can skip the guard: `commit_and_push` asks before it commits."""
    target, track = stealth_pair(tmp_path)
    ref = stealth.parse_ref(f"{track}@main")
    wt = stealth.ensure_worktree(target, ref)
    (wt / "x.txt").write_text("x\n")
    _visibility(monkeypatch, {str(track): "public"})
    called: list[object] = []
    with pytest.raises(SettingsError, match="R24 privacy"):
        stealth.commit_and_push(
            ref,
            wt,
            [wt / "x.txt"],
            "chore(fr): x",
            lambda *a: called.append(a),  # type: ignore[arg-type,return-value]
            target_remote=str(tmp_path / "origin.git"),
        )
    assert called == []
    assert "x.txt" not in tracked_files(track)


class _Forge:
    """A fake forge client recording every call; anything but `create_pr` is a trace."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def create_pr(self, repo: str, **kw: Any) -> dict[str, Any]:
        self.calls.append(("create_pr", {"repo": repo, **kw}))
        return {"number": 7, "url": "https://example.com/acme/widget/pull/7"}

    def __getattr__(self, name: str) -> Any:
        def call(*a: Any, **kw: Any) -> Any:
            self.calls.append((name, kw))
            return None

        return call


@pytest.fixture
def ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    target, track = stealth_pair(tmp_path)
    state = HostWorktreeTarget(target).up(
        profile=None, branch="feat/s", stealth=stealth.parse_ref(f"{track}@main")
    )
    monkeypatch.chdir(state.worktree)
    return state.worktree, track, tmp_path / "origin.git"


def _fr(root: Path, *argv: str):
    return CliRunner().invoke(app, list(argv), env={**os.environ, "VK_REPO_ROOT": str(root)})


def test_pr_create_opens_one_minimal_draft_and_nothing_else(
    ws: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import fr.commands.pr_cmd as pr_cmd

    root, track, _ = ws
    assert (
        _fr(root, "run", "start", "fr-goal", "--branch", "feat/s", "--run-id", "r1").exit_code == 0
    )
    forge = _Forge()
    monkeypatch.setattr(pr_cmd, "client_for", lambda _root: forge)
    monkeypatch.setattr(pr_cmd, "origin_slug", lambda _root: "acme/widget")
    marked = tmp_path / "marked.md"
    marked.write_text("summary\n<!-- fr-technical-debt -->\n")
    refused = _fr(root, "pr", "create", "--title", "t", "--body-file", str(marked))
    assert refused.exit_code == 2 and "fr markers" in " ".join(refused.output.split())
    plain = tmp_path / "plain.md"
    plain.write_text("A plain summary.\n")
    result = _fr(root, "pr", "create", "--title", "t", "--body-file", str(plain))
    assert result.exit_code == 0, result.output
    assert [name for name, _ in forge.calls] == ["create_pr"]
    assert forge.calls[0][1]["draft"] is True
    assert forge.calls[0][1]["body"] == "A plain summary.\n"
    again = _fr(root, "pr", "create", "--title", "t", "--body-file", str(plain))
    assert again.exit_code == 2  # one draft PR, never a second
    # the refusal READS the recorded PR's state; nothing else is written to the forge
    assert [name for name, _ in forge.calls] == ["create_pr", "pr_status_by_url"]
    assert not [n for n, _ in forge.calls if "label" in n or "comment" in n or "issue" in n]
    # the PR url is state: it went to the tracking repo, not the target
    cursor = git(track, "show", "main:local--origin/features/feat__s/docs/superpowers/runs/r1.yaml")
    assert "pull/7" in cursor


def test_push_sends_the_code_only(ws: tuple[Path, Path, Path]) -> None:
    root, track, origin = ws
    assert (
        _fr(root, "run", "start", "fr-goal", "--branch", "feat/s", "--run-id", "r1").exit_code == 0
    )
    (root / "code.txt").write_text("code\n")
    git(root, "add", "code.txt")
    git(root, "commit", "-qm", "feat(s): code")
    result = _fr(root, "push")
    assert result.exit_code == 0, result.output
    refs = sorted(line.split()[1] for line in git(origin, "show-ref").splitlines())
    assert refs == ["refs/heads/feat/s", "refs/heads/main"]
    assert git(origin, "log", "--format=%s", "main..feat/s").splitlines() == ["feat(s): code"]
    names = git(origin, "ls-tree", "-r", "--name-only", "feat/s").splitlines()
    assert not [n for n in names if n.startswith("docs/")]
    assert "local--origin/features/feat__s/docs/superpowers/runs/r1.yaml" in tracked_files(track)


# --- review p4-r7: the target's visibility is read through its own forge client ----------


class _VisForge:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.asked: list[str] = []

    def repo_visibility(self, repo: str) -> str:
        self.asked.append(repo)
        return self.answer


def test_an_scp_remote_is_parsed_to_its_host(monkeypatch: pytest.MonkeyPatch) -> None:
    import fr.hostclient as hostclient

    built: list[str] = []
    forge = _VisForge("private")
    monkeypatch.setattr(hostclient, "client_for_url", lambda url: built.append(url) or forge)
    assert stealth._forge_visibility("git@git.example:acme/widget.git", None) == "private"
    assert built == ["https://git.example/acme/widget.git"]
    assert forge.asked == ["acme/widget"]
    stealth._forge_visibility("ssh://git@git.example:2222/acme/widget.git", None)
    assert built[-1] == "https://git.example/acme/widget.git"


def test_the_targets_visibility_uses_the_checkouts_own_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A self-hosted target is read by the client its checkout resolves (its declared
    forge and host), never a GitHub client guessed from the URL."""
    import fr.hostclient as hostclient

    forge = _VisForge("internal")
    roots: list[Path] = []
    monkeypatch.setattr(hostclient, "client_for", lambda root: roots.append(root) or forge)
    monkeypatch.setattr(
        hostclient, "client_for_url", lambda url: pytest.fail(f"guessed a client for {url}")
    )
    checkout = tmp_path / "target"
    assert stealth._forge_visibility("git@git.example:acme/widget.git", checkout) == "internal"
    assert roots == [checkout]
    assert forge.asked == ["acme/widget"]


def test_check_privacy_passes_the_target_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple[str, Path | None]] = []

    def answer(repo: str, checkout: Path | None = None) -> str:
        seen.append((repo, checkout))
        return "private"

    monkeypatch.setattr(stealth, "visibility", answer)
    ref = stealth.parse_ref("git@track.example:me/track.git@main")
    stealth.check_privacy(ref, "git@git.example:acme/widget.git", target_root=tmp_path)
    assert ("git@git.example:acme/widget.git", tmp_path) in seen
