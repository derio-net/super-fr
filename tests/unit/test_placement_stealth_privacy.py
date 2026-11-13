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
        env={**os.environ, "FR_REPO_ROOT": str(target)},
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
    return CliRunner().invoke(app, list(argv), env={**os.environ, "FR_REPO_ROOT": str(root)})


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


def _backends(monkeypatch: pytest.MonkeyPatch, forge: _VisForge) -> list[tuple[str, str | None]]:
    import fr.hostclient as hostclient

    built: list[tuple[str, str | None]] = []
    monkeypatch.setattr(
        hostclient, "client_for_backend", lambda b, host=None: built.append((b, host)) or forge
    )
    return built


def _checkout(
    monkeypatch: pytest.MonkeyPatch, *, backend: str, declared: str | None, origin: str | None
) -> None:
    import fr._hosts as hosts

    monkeypatch.setattr(hosts, "detect_backend", lambda root: backend)
    monkeypatch.setattr(hosts, "declared_host", lambda root: declared)
    monkeypatch.setattr(hosts, "origin_hostname", lambda root: origin)


def test_an_scp_remote_is_parsed_to_its_host(monkeypatch: pytest.MonkeyPatch) -> None:
    import fr._hosts as hosts

    forge = _VisForge("private")
    built = _backends(monkeypatch, forge)
    monkeypatch.setattr(hosts, "backend_for_url", lambda url: "gitlab")
    assert stealth._forge_visibility("git@git.example:acme/widget.git", None) == "private"
    stealth._forge_visibility("ssh://git@git.example:2222/acme/widget.git", None)
    assert built == [("gitlab", "git.example"), ("gitlab", "git.example")]
    assert forge.asked == ["acme/widget", "acme/widget"]
    assert stealth.https_form("git@git.example:acme/widget.git") == (
        "https://git.example/acme/widget.git"
    )


def test_a_matching_self_hosted_checkout_passes_on_the_remotes_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A self-hosted target is read by its checkout's declared forge type, on the host of
    the remote the slug came from, never a GitHub client guessed from the URL."""
    forge = _VisForge("internal")
    built = _backends(monkeypatch, forge)
    _checkout(monkeypatch, backend="gitlab", declared="Git.Example:8443", origin=None)
    remote = "git@git.example:acme/widget.git"
    assert stealth._forge_visibility(remote, tmp_path) == "internal"
    assert built == [("gitlab", "git.example")]
    assert forge.asked == ["acme/widget"]


@pytest.mark.parametrize(
    ("backend", "declared", "origin", "remote"),
    [
        # the checkout's forge names another host than the remote's
        ("gitlab", "forge-a.example", None, "git@forge-b.example:acme/widget.git"),
        ("gitlab", None, "forge-a.example", "git@forge-b.example:acme/widget.git"),
        # a SaaS host with a mismatched backend: both sides would read as "no host"
        ("gitlab", None, "github.com", "git@github.com:acme/widget.git"),
        ("gitea", None, "github.com", "https://github.com/acme/widget"),
        ("github", None, "gitlab.com", "git@gitlab.com:acme/widget.git"),
        # gitea: `tea` cannot be pinned to a host
        ("gitea", None, "tea.example", "https://tea.example/acme/widget"),
    ],
)
def test_a_checkout_that_cannot_ask_the_remotes_host_is_unreadable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    backend: str,
    declared: str | None,
    origin: str | None,
    remote: str,
) -> None:
    """Asking another forge about `acme/widget` would answer for another repo of the same
    name: fr refuses, and the wrong forge is never asked."""
    wrong = _VisForge("private")
    built = _backends(monkeypatch, wrong)
    _checkout(monkeypatch, backend=backend, declared=declared, origin=origin)
    assert stealth._forge_visibility(remote, tmp_path) is None
    ref = stealth.parse_ref("/srv/track.git@main")
    with pytest.raises(SettingsError, match="cannot read the visibility"):
        stealth.check_privacy(ref, remote, target_root=tmp_path)
    assert built == [] and wrong.asked == []


def test_a_gitea_tracking_repo_is_unreadable(monkeypatch: pytest.MonkeyPatch) -> None:
    import fr._hosts as hosts

    wrong = _VisForge("private")
    built = _backends(monkeypatch, wrong)
    monkeypatch.setattr(hosts, "backend_for_url", lambda url: "gitea")
    assert stealth._forge_visibility("https://tea.example/me/track", None) is None
    assert built == [] and wrong.asked == []


def test_a_saas_checkout_on_its_own_forge_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge = _VisForge("private")
    built = _backends(monkeypatch, forge)
    _checkout(monkeypatch, backend="github", declared=None, origin="github.com")
    assert stealth._forge_visibility("git@github.com:acme/widget.git", tmp_path) == "private"
    assert built == [("github", "github.com")]


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
