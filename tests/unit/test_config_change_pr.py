"""A change to an existing configuration branch is a pull request; the legacy copy is
landed robustly at creation and brought in step after the merge (review p2-r1, p2-r7;
plan decision p2-config-changes-by-pr; spec 2026-11-19-event-driven-a-la-carte §B, R6).

Origins are LOCAL bare repos; the forge is the `fr.config.change.open_pr` seam.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from fr.config import change
from fr.config.space import quiet_config_space, write_settings
from fr.placement import quiet
from fr.settings import SettingsError, load_settings
from typer.testing import CliRunner

from tests.unit.settings_repo import git, make_repo
from tests.unit.test_placement_quiet import QUIET, push_fr_branch

NEW = "schema: 1\nplacement: quiet\nforge:\n  labels: off\n  comments: off\n"


@pytest.fixture
def prs(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, str]]:
    opened: list[tuple[str, str, str]] = []

    def fake(remote: str, head: str, base: str, title: str, body: str) -> str:
        opened.append((remote, head, base))
        return f"https://example.com/pr/{len(opened)}"

    monkeypatch.setattr(change, "open_pr", fake)
    return opened


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = make_repo(tmp_path)
    monkeypatch.chdir(root)
    env = {**os.environ, "FR_REPO_ROOT": str(root)}
    assert CliRunner().invoke(app, ["settings", "init", "--quiet"], env=env).exit_code == 0
    return root


def _origin(tmp_path: Path) -> Path:
    return tmp_path / "origin.git"


def _merge(tmp_path: Path, head: str, base: str = "fr-config") -> None:
    """The forge merges the pull request: *base* fast-forwards to *head* on origin."""
    origin = _origin(tmp_path)
    git(origin, "update-ref", f"refs/heads/{base}", git(origin, "rev-parse", head).strip())


def _other_clone(tmp_path: Path, name: str = "other") -> Path:
    other = tmp_path / name
    git(tmp_path, "clone", "-q", str(_origin(tmp_path)), str(other))
    git(other, "config", "user.name", "t")
    git(other, "config", "user.email", "t@example.invalid")
    return other


def test_a_change_to_an_existing_fr_config_opens_a_pull_request(
    repo: Path, tmp_path: Path, prs: list[tuple[str, str, str]], capsys: pytest.CaptureFixture[str]
) -> None:
    origin = _origin(tmp_path)
    before = {b: git(origin, "rev-parse", b).strip() for b in ("fr-config", "fr")}
    url = write_settings(quiet_config_space(repo), NEW, message="chore(fr): labels off")
    assert url == "https://example.com/pr/1" and url in capsys.readouterr().err
    assert {b: git(origin, "rev-parse", b).strip() for b in ("fr-config", "fr")} == before
    (remote, head, base) = prs[0]
    assert base == "fr-config" and head.startswith("fr-config-change/")
    assert remote == git(repo, "config", "--get", "remote.origin.url").strip()
    assert git(origin, "show", f"{head}:.fr/settings.yaml") == NEW
    assert git(origin, "rev-parse", f"{head}^").strip() == before["fr-config"]
    # a retry reuses the same branch
    assert write_settings(quiet_config_space(repo), NEW, message="chore(fr): labels off")
    assert prs[1][1] == head


def _merged(repo: Path, tmp_path: Path, prs: list[tuple[str, str, str]]) -> None:
    write_settings(quiet_config_space(repo), NEW, message="chore(fr): labels off")
    _merge(tmp_path, prs[0][1])
    git(repo, "fetch", "-q", "origin", "+refs/heads/fr-config:refs/remotes/origin/fr-config")
    quiet._CACHE.clear()


def test_after_the_merge_readers_refuse_naming_the_sync_and_write_nothing(
    repo: Path, tmp_path: Path, prs: list[tuple[str, str, str]]
) -> None:
    """Security review of decision 4c: no reader writes the old copy on its own, or a push
    straight to an unprotected fr-config would be copied silently."""
    _merged(repo, tmp_path, prs)
    fr_before = git(_origin(tmp_path), "rev-parse", "fr").strip()
    with pytest.raises(SettingsError) as caught:
        load_settings(repo)
    message = str(caught.value)
    assert "fr settings sync" in message and "fr settings sync --yes" in message
    assert "earlier version" in message
    assert git(_origin(tmp_path), "rev-parse", "fr").strip() == fr_before


def _sync(repo: Path, *argv: str):  # type: ignore[no-untyped-def]
    env = {**os.environ, "FR_REPO_ROOT": str(repo)}
    return CliRunner().invoke(app, ["settings", "sync", *argv], env=env)


def test_fr_settings_sync_previews_then_writes_the_old_copy(
    repo: Path, tmp_path: Path, prs: list[tuple[str, str, str]]
) -> None:
    _merged(repo, tmp_path, prs)
    origin = _origin(tmp_path)
    fr_before = git(origin, "rev-parse", "fr").strip()
    preview = _sync(repo)
    assert preview.exit_code == 0, preview.output
    assert "origin/fr-config:.fr/settings.yaml" in preview.output
    assert "origin/fr:settings.yaml" in preview.output
    assert "NOT a reviewed merge" in preview.output  # the test's merge is a fast-forward
    assert "--yes" in preview.output
    assert git(origin, "rev-parse", "fr").strip() == fr_before  # the preview writes nothing
    done = _sync(repo, "--yes")
    assert done.exit_code == 0, done.output
    assert git(origin, "show", "fr:settings.yaml") == NEW
    quiet._CACHE.clear()
    assert load_settings(repo).settings.forge.comments == "off"
    assert "in step" in _sync(repo).output


def test_sync_reports_a_merge_commit_of_a_change_branch(
    repo: Path, tmp_path: Path, prs: list[tuple[str, str, str]]
) -> None:
    write_settings(quiet_config_space(repo), NEW, message="chore(fr): labels off")
    other = _other_clone(tmp_path)
    git(other, "checkout", "-q", "fr-config")
    git(other, "merge", "-q", "--no-ff", "-m", f"Merge {prs[0][1]}", f"origin/{prs[0][1]}")
    git(other, "push", "-q", "origin", "fr-config")
    git(repo, "fetch", "-q", "origin", "+refs/heads/fr-config:refs/remotes/origin/fr-config")
    quiet._CACHE.clear()
    out = _sync(repo).output
    assert "merge of a fr-config-change/* branch" in out, out


def test_two_switches_edited_apart_name_both_refs_and_both_remedies(
    repo: Path, tmp_path: Path
) -> None:
    other = _other_clone(tmp_path)
    git(other, "checkout", "-q", "fr")
    (other / "settings.yaml").write_text("placement: quiet\n# by hand\n")
    git(other, "commit", "-qam", "by hand")
    git(other, "push", "-q", "origin", "fr")
    git(repo, "fetch", "-q", "origin", quiet.FETCH_REFSPEC)
    quiet._CACHE.clear()
    with pytest.raises(SettingsError) as caught:
        quiet.read_switch(repo)
    message = str(caught.value)
    assert "origin/fr-config:.fr/settings.yaml" in message
    assert "origin/fr:settings.yaml" in message
    assert "neither matches" in message and "by hand" in message
    assert "one was edited by hand" not in message
    assert _sync(repo, "--yes").exit_code == 2  # sync never picks a side


def test_the_legacy_write_rebases_onto_a_moved_fr_and_keeps_every_commit(
    repo: Path, tmp_path: Path, prs: list[tuple[str, str, str]]
) -> None:
    """Another clone pushed to `fr`, and this clone has an unpushed fr commit: the sync
    fetches, rebases, commits and pushes; nothing is lost or forced."""
    other = _other_clone(tmp_path)
    git(other, "checkout", "-q", "fr")
    (other / "features").mkdir()
    (other / "features" / "theirs.md").write_text("theirs\n")
    git(other, "add", "-A")
    git(other, "commit", "-qm", "their artifact")
    git(other, "push", "-q", "origin", "fr")
    wt = quiet.ensure_worktree(repo)
    (wt / "mine.md").write_text("mine\n")
    git(wt, "add", "mine.md")
    git(wt, "commit", "-qm", "my artifact")
    _merged(repo, tmp_path, prs)
    assert _sync(repo, "--yes").exit_code == 0
    origin = _origin(tmp_path)
    files = git(origin, "ls-tree", "-r", "--name-only", "fr").split()
    assert {"features/theirs.md", "mine.md", "settings.yaml"} <= set(files)
    assert git(origin, "show", "fr:settings.yaml") == NEW


def test_a_push_lost_to_a_concurrent_clone_is_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Creation from an old quiet switch whose legacy copy must change (a partial earlier
    write): the first push of `fr` loses a race and is retried after a fetch."""
    root = make_repo(tmp_path)
    push_fr_branch(root, QUIET)
    other = _other_clone(tmp_path)
    raced = []
    real = quiet._default_network(root)

    def net(argv: list[str]) -> subprocess.CompletedProcess[str]:
        if argv[:2] == ["git", "push"] and "refs/heads/fr:refs/heads/fr" in argv[-1] and not raced:
            raced.append(1)
            git(other, "checkout", "-q", "fr")
            (other / "theirs.md").write_text("x\n")
            git(other, "add", "-A")
            git(other, "commit", "-qm", "race")
            git(other, "push", "-q", "origin", "fr")
        return real(argv)

    quiet.write_legacy(root, NEW, "chore(fr): settings", network=net)
    origin = _origin(tmp_path)
    assert raced and git(origin, "show", "fr:settings.yaml") == NEW
    assert "theirs.md" in git(origin, "ls-tree", "--name-only", "fr").split()


def test_a_retry_after_a_partial_failure_lands_only_the_legacy_copy(
    tmp_path: Path, prs: list[tuple[str, str, str]]
) -> None:
    """fr-config already holds the text (the push of `fr` failed last time): no pull
    request, the legacy copy lands."""
    from tests.unit.test_placement_quiet import push_config_branch

    root = make_repo(tmp_path)
    push_fr_branch(root, QUIET)
    push_config_branch(root, NEW)
    assert write_settings(quiet_config_space(root), NEW, message="chore(fr): settings") is None
    assert prs == []
    assert git(_origin(tmp_path), "show", "fr:settings.yaml") == NEW


# --- stealth: the pull request goes to the tracking repo --------------------------------


def test_a_stealth_change_opens_a_pull_request_on_the_tracking_repo_then_syncs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prs: list[tuple[str, str, str]]
) -> None:
    from fr.config.space import stealth_config_space
    from fr.isolation.hostworktree import HostWorktreeTarget
    from fr.placement import stealth

    from tests.unit.stealth_repo import stealth_pair

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    stealth.reset_caches()
    target, track = stealth_pair(tmp_path)
    monkeypatch.chdir(target)
    env = {**os.environ, "FR_REPO_ROOT": str(target)}
    made = CliRunner().invoke(app, ["settings", "init", "--stealth", f"{track}@main"], env=env)
    assert made.exit_code == 0, made.output
    ref = stealth.parse_ref(f"{track}@main")
    state = HostWorktreeTarget(target).up(profile=None, branch="feat/s", stealth=ref)
    before = {b: git(track, "rev-parse", b).strip() for b in ("main", "main-config")}
    text = "placement: stealth\nartifacts:\n  gates: off\n"
    space = stealth_config_space(target, ref.text, stealth.target_dir(target))
    url = write_settings(space, text, message="chore(fr): gates off")
    assert url is not None
    assert {b: git(track, "rev-parse", b).strip() for b in ("main", "main-config")} == before
    remote, head, base = prs[0]
    assert remote == ref.repo and base == "main-config"
    assert git(track, "show", f"{head}:local--origin/.fr/settings.yaml") == text
    # the forge merges it; readers refuse until `fr settings sync --yes`
    git(track, "update-ref", "refs/heads/main-config", git(track, "rev-parse", head).strip())
    stealth.ensure_worktree(target, stealth.config_ref(ref))
    with pytest.raises(SettingsError, match="fr settings sync"):
        load_settings(state.worktree)
    env = {**os.environ, "FR_REPO_ROOT": str(state.worktree)}
    monkeypatch.chdir(state.worktree)
    done = CliRunner().invoke(app, ["settings", "sync", "--yes"], env=env)
    assert done.exit_code == 0, done.output
    assert git(track, "show", "main:local--origin/settings.yaml") == text
    assert load_settings(state.worktree).settings.artifacts.gates == "off"
