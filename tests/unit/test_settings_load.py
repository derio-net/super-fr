"""The loader reads the default ref, never the working tree (spec R2, R4)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.settings import SettingsError, disabled, forge_allows, load_settings

from tests.unit.settings_repo import git as _git
from tests.unit.settings_repo import land_on_main as _land_on_main
from tests.unit.settings_repo import make_repo


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return make_repo(tmp_path)


def test_no_file_is_every_default_with_source_default(repo: Path) -> None:
    eff = load_settings(repo)
    assert eff.settings.git.push == "auto"
    assert set(eff.sources.values()) == {"default"}
    assert eff.pending_edit is None


def test_a_file_on_the_default_branch_is_read_with_source_repo(repo: Path) -> None:
    _land_on_main(repo, "artifacts:\n  gates: off\nforge:\n  comments: false\n")
    eff = load_settings(repo)
    assert eff.settings.artifacts.gates == "off"
    assert eff.settings.forge.comments == "off"
    assert eff.sources["artifacts.gates"] == "repo"
    assert eff.sources["forge.comments"] == "repo"
    assert eff.sources["forge.labels"] == "default"
    assert disabled(repo, "gates") and not disabled(repo, "acceptance")
    assert not forge_allows(repo, "comments") and forge_allows(repo, "labels")


def test_an_edit_on_the_working_tree_or_feature_branch_is_ignored(repo: Path) -> None:
    _land_on_main(repo, "artifacts:\n  gates: off\n")
    _git(repo, "checkout", "-q", "-b", "feat/x")
    (repo / ".fr" / "settings.yaml").write_text("artifacts:\n  gates: on\n")
    _git(repo, "commit", "-qam", "relax")
    assert load_settings(repo).settings.artifacts.gates == "off"
    (repo / ".fr" / "settings.yaml").write_text("artifacts:\n  gates: on\n  acceptance: off\n")
    eff = load_settings(repo)
    assert eff.settings.artifacts.acceptance == "on"
    assert eff.pending_edit is not None
    assert "settings.yaml" in eff.pending_edit


def test_a_new_uncommitted_file_is_a_pending_edit_not_a_setting(repo: Path) -> None:
    (repo / ".fr").mkdir()
    (repo / ".fr" / "settings.yaml").write_text("artifacts:\n  gates: off\n")
    eff = load_settings(repo)
    assert eff.settings.artifacts.gates == "on"
    assert eff.pending_edit is not None


def test_no_origin_reads_the_local_default_branch_and_says_so(tmp_path: Path) -> None:
    work = tmp_path / "w"
    _git(tmp_path, "init", "-q", "-b", "main", str(work))
    _land_on_main_local(work, "git:\n  push: ask\n")
    eff = load_settings(work)
    assert eff.settings.git.push == "ask"
    assert "no origin" in eff.ref_note


def _land_on_main_local(work: Path, text: str) -> None:
    (work / ".fr").mkdir(exist_ok=True)
    (work / ".fr" / "settings.yaml").write_text(text)
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "s")


def test_no_origin_never_reads_head_as_policy(tmp_path: Path) -> None:
    work = tmp_path / "w"
    _git(tmp_path, "init", "-q", "-b", "main", str(work))
    (work / "a").write_text("x")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "seed")
    _git(work, "checkout", "-q", "-b", "feat/x")
    _land_on_main_local(work, "artifacts:\n  acceptance: off\n")
    eff = load_settings(work)
    assert eff.settings.artifacts.acceptance == "on"
    assert eff.pending_edit is not None


def test_no_origin_and_no_default_branch_is_defaults_with_a_note(tmp_path: Path) -> None:
    work = tmp_path / "w"
    _git(tmp_path, "init", "-q", "-b", "trunkish", str(work))
    _land_on_main_local(work, "artifacts:\n  acceptance: off\n")
    eff = load_settings(work)
    assert eff.settings.artifacts.acceptance == "on"
    assert set(eff.sources.values()) == {"default"}
    assert "no default branch" in eff.ref_note


def test_a_local_branch_named_like_the_remote_ref_cannot_supply_policy(repo: Path) -> None:
    _land_on_main(repo, "artifacts:\n  gates: off\n")
    _git(repo, "branch", "origin/main")
    _git(repo, "checkout", "-q", "origin/main")
    (repo / ".fr" / "settings.yaml").write_text("artifacts:\n  gates: on\n")
    _git(repo, "commit", "-qam", "relax")
    assert _git(repo, "rev-parse", "--verify", "refs/heads/origin/main").strip()
    assert load_settings(repo).settings.artifacts.gates == "off"


def test_an_unservable_placement_is_refused_by_the_loader(repo: Path) -> None:
    _land_on_main(repo, "placement: stealth\n")
    with pytest.raises(SettingsError, match="not yet available in this fr"):
        load_settings(repo)


def test_quiet_in_the_repo_file_is_refused_pointing_at_the_fr_branch(repo: Path) -> None:
    _land_on_main(repo, "placement: quiet\n")
    with pytest.raises(SettingsError, match="fr settings init --quiet"):
        load_settings(repo)


def test_unparseable_yaml_names_the_file(repo: Path) -> None:
    _land_on_main(repo, "a: [unclosed\n")
    with pytest.raises(SettingsError, match=r"\.fr/settings\.yaml"):
        load_settings(repo)


def test_an_unknown_key_on_the_default_branch_is_refused(repo: Path) -> None:
    _land_on_main(repo, "forge:\n  nope: on\n")
    with pytest.raises(SettingsError, match="forge.nope"):
        load_settings(repo)


def test_not_a_repo_or_empty_repo_is_defaults(tmp_path: Path) -> None:
    assert load_settings(tmp_path).settings.placement == "repo"
    work = tmp_path / "empty"
    _git(tmp_path, "init", "-q", "-b", "main", str(work))
    assert load_settings(work).settings.placement == "repo"


def test_unknown_feature_names_are_a_programming_error(repo: Path) -> None:
    with pytest.raises(ValueError, match="spec"):
        disabled(repo, "spec")
    with pytest.raises(ValueError, match="pr_body"):
        forge_allows(repo, "pr_body")


def test_a_git_read_failure_is_a_refusal_not_absent(repo: Path) -> None:
    """Absent (path not in the tree) is defaults; a failing git read is never defaults."""
    from fr.settings import load as load_mod

    _land_on_main(repo, "artifacts:\n  gates: off\n")
    load_mod._CACHE.clear()
    sha = _git(repo, "rev-parse", "refs/remotes/origin/main").strip()
    assert load_mod._show(repo, sha) is not None
    assert load_mod._show(repo, sha, ".fr/nope.yaml") is None
    with pytest.raises(SettingsError, match="cannot read"):
        load_mod._show(repo, "0" * 40)


def test_a_non_main_remote_default_is_read(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _git(repo, "branch", "-m", "trunk")
    (repo / ".fr").mkdir()
    (repo / ".fr" / "settings.yaml").write_text("artifacts:\n  gates: off\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "s")
    _git(repo, "push", "-q", "origin", "trunk")
    _git(repo, "remote", "set-head", "origin", "trunk")
    _git(repo, "update-ref", "-d", "refs/remotes/origin/main")
    eff = load_settings(repo)
    assert eff.settings.artifacts.gates == "off"
    assert eff.ref == "refs/remotes/origin/trunk"


def test_a_remote_with_tracking_refs_but_no_default_refuses(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _git(repo, "push", "-q", "origin", "main:feature")
    _git(repo, "fetch", "-q", "origin")
    _git(repo, "remote", "set-head", "origin", "-d")
    _git(repo, "update-ref", "-d", "refs/remotes/origin/main")
    with pytest.raises(SettingsError, match="git fetch origin"):
        load_settings(repo)


def test_a_remote_that_was_never_fetched_is_defaults_never_the_local_branch(
    tmp_path: Path,
) -> None:
    """The bootstrap state (`git init; git remote add origin <url>`): a local main carrying
    a policy is NOT applied — deleting tracking refs must not hand policy to a local branch."""
    repo = tmp_path / "boot"
    _git(tmp_path, "init", "-q", "-b", "main", str(repo))
    _git(repo, "remote", "add", "origin", "https://example.invalid/r")
    (repo / ".fr").mkdir()
    (repo / ".fr" / "settings.yaml").write_text("artifacts:\n  acceptance: off\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "s")
    eff = load_settings(repo)
    assert eff.settings.artifacts.acceptance == "on"
    assert eff.ref is None
    assert eff.source == "defaults"
    assert "remote `origin` has no tracking refs yet" in eff.ref_note


def test_deleting_tracking_refs_does_not_hand_policy_to_a_local_branch(repo: Path) -> None:
    _git(repo, "remote", "set-head", "origin", "-d")
    _git(repo, "update-ref", "-d", "refs/remotes/origin/main")
    (repo / ".fr").mkdir()
    (repo / ".fr" / "settings.yaml").write_text("artifacts:\n  gates: off\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "local relax")
    eff = load_settings(repo)
    assert eff.settings.artifacts.gates == "on"
    assert eff.source == "defaults"


def test_a_never_fetched_remote_with_no_commits_is_defaults(tmp_path: Path) -> None:
    repo = tmp_path / "boot"
    _git(tmp_path, "init", "-q", "-b", "main", str(repo))
    _git(repo, "remote", "add", "origin", "https://example.invalid/r")
    eff = load_settings(repo)
    assert eff.ref is None
    assert eff.source == "defaults"


def _pr_checkout(tmp_path: Path, committed: str | None) -> Path:
    """actions/checkout's depth-1 PR shape: a remote, and ONLY refs/remotes/pull/1/merge."""
    src = tmp_path / "src"
    _git(tmp_path, "init", "-q", "-b", "main", str(src))
    (src / "README.md").write_text("x\n")
    if committed is not None:
        (src / ".fr").mkdir()
        (src / ".fr" / "settings.yaml").write_text(committed)
    _git(src, "add", "-A")
    _git(src, "commit", "-qm", "merge")
    pr = tmp_path / "pr"
    _git(tmp_path, "init", "-q", str(pr))
    _git(pr, "remote", "add", "origin", "https://example.invalid/r")
    _git(pr, "fetch", "-q", "--depth=1", f"file://{src}", "+HEAD:refs/remotes/pull/1/merge")
    _git(pr, "checkout", "-q", "refs/remotes/pull/1/merge")
    return pr


def test_ci_with_no_default_ref_reads_heads_committed_file_and_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    pr = _pr_checkout(tmp_path, "artifacts:\n  gates: off\n")
    monkeypatch.setenv("CI", "true")
    eff = load_settings(pr)
    load_settings(pr)
    assert eff.settings.artifacts.gates == "off"
    assert eff.source == "head"
    assert eff.ref == "HEAD"
    assert "HEAD" in eff.ref_note
    err = capsys.readouterr().err
    assert err.count("HEAD's committed tree") == 1, err


def test_ci_head_source_never_reads_the_working_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pr = _pr_checkout(tmp_path, None)
    (pr / ".fr").mkdir()
    (pr / ".fr" / "settings.yaml").write_text("artifacts:\n  gates: off\n")
    monkeypatch.setenv("CI", "true")
    eff = load_settings(pr)
    assert eff.source == "head"
    assert eff.settings.artifacts.gates == "on"
    assert eff.pending_edit is not None


def test_the_pr_checkout_outside_ci_is_defaults_not_head(tmp_path: Path) -> None:
    """Without CI the PR shape is R2 step 2 with no local default: defaults and a note,
    never HEAD (a branch must not supply its own policy)."""
    pr = _pr_checkout(tmp_path, "artifacts:\n  gates: off\n")
    eff = load_settings(pr)
    assert eff.source == "defaults"
    assert eff.settings.artifacts.gates == "on"


def test_ci_with_tracking_refs_but_no_default_reads_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = make_repo(tmp_path)
    _land_on_main(repo, "artifacts:\n  gates: off\n")
    _git(repo, "push", "-q", "origin", "main:feature")
    _git(repo, "fetch", "-q", "origin")
    _git(repo, "remote", "set-head", "origin", "-d")
    _git(repo, "update-ref", "-d", "refs/remotes/origin/main")
    monkeypatch.setenv("CI", "true")
    eff = load_settings(repo)
    assert eff.source == "head"
    assert eff.settings.artifacts.gates == "off"


def test_ci_with_a_default_ref_still_reads_the_default_ref(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CI", "true")
    eff = load_settings(repo)
    assert eff.source == "remote"
    assert eff.ref == "refs/remotes/origin/main"


def test_an_unpushed_local_main_is_not_read_when_origin_exists(repo: Path) -> None:
    (repo / ".fr").mkdir()
    (repo / ".fr" / "settings.yaml").write_text("artifacts:\n  gates: off\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "unpushed")
    eff = load_settings(repo)
    assert eff.settings.artifacts.gates == "on"
    assert eff.pending_edit is not None
