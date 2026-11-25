"""`fr settings init --quiet`, `fr settings check` under quiet, and runner dispatch refused
under quiet (spec 2026-11-04 R3, R5, R22, R23 "known limitation", "not available here";
plan phase 3, task 5). Origins are LOCAL bare repos.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fr.artifacts.paths import KIND_DIRS, space_for
from fr.cli import app
from fr.settings import load_settings
from fr.settings.check import check_settings
from typer.testing import CliRunner

from tests.unit.settings_repo import git, make_repo
from tests.unit.test_placement_quiet import push_fr_branch


def _fr(repo: Path, *argv: str):  # type: ignore[no-untyped-def]
    return CliRunner().invoke(app, list(argv), env={**os.environ, "FR_REPO_ROOT": str(repo)})


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = make_repo(tmp_path)
    monkeypatch.chdir(root)
    return root


def test_init_quiet_creates_and_pushes_the_orphan_fr_branch(repo: Path, tmp_path: Path) -> None:
    head_before = git(repo, "rev-parse", "HEAD").strip()
    result = _fr(repo, "settings", "init", "--quiet")
    assert result.exit_code == 0, result.output
    origin = tmp_path / "origin.git"
    sha = git(origin, "rev-parse", "refs/heads/fr").strip()
    assert git(origin, "rev-list", "--parents", "-n1", sha).split() == [sha]  # orphan
    assert git(origin, "ls-tree", "--name-only", sha).split() == ["settings.yaml"]
    text = git(origin, "show", f"{sha}:settings.yaml")
    assert "\nplacement: quiet\n" in text
    assert "#  labels: on" in text or "#forge:" in text  # every other key commented
    flat = " ".join(text.split())
    assert "predates" in flat  # the known limitation
    assert "branch protection" in flat or "protect" in flat
    # nothing in the product checkout moved
    assert git(repo, "rev-parse", "HEAD").strip() == head_before
    assert not git(repo, "status", "--porcelain").strip()
    assert load_settings(repo).settings.placement == "quiet"
    assert space_for(repo).placement == "quiet"


def test_init_quiet_states_the_known_limitation_on_stdout(repo: Path) -> None:
    result = _fr(repo, "settings", "init", "--quiet")
    assert result.exit_code == 0, result.output
    assert "predates" in " ".join(result.output.split())


def test_init_quiet_refuses_when_origin_already_has_fr(repo: Path, tmp_path: Path) -> None:
    push_fr_branch(repo, None)
    before = git(tmp_path / "origin.git", "rev-parse", "refs/heads/fr").strip()
    result = _fr(repo, "settings", "init", "--quiet")
    assert result.exit_code == 2
    assert "already" in result.output
    assert git(tmp_path / "origin.git", "rev-parse", "refs/heads/fr").strip() == before
    assert _fr(repo, "settings", "init", "--quiet", "--force").exit_code == 2


def test_init_quiet_refuses_without_origin(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    solo = tmp_path / "solo"
    git(tmp_path, "init", "-q", "-b", "main", str(solo))
    git(
        solo,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@e.invalid",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "s",
    )
    monkeypatch.chdir(solo)
    result = _fr(solo, "settings", "init", "--quiet")
    assert result.exit_code == 2
    assert "origin" in result.output


def test_apply_to_a_runner_is_refused_under_quiet(repo: Path) -> None:
    push_fr_branch(repo, "schema: 1\nplacement: quiet\n")
    git(repo, "checkout", "-q", "-b", "feat/q")
    result = _fr(repo, "apply", "--all", "--to", "vk")
    assert result.exit_code == 2
    assert "quiet" in result.output


def test_check_accepts_the_quiet_file(repo: Path) -> None:
    push_fr_branch(repo, "schema: 1\nplacement: quiet\n")
    git(repo, "checkout", "-q", "-b", "feat/q")
    assert check_settings(repo) == []
    assert _fr(repo, "settings", "check").exit_code == 0


def test_check_applies_r22_under_quiet(repo: Path) -> None:
    push_fr_branch(repo, "schema: 1\nplacement: quiet\nforge:\n  report_comment: on\n")
    git(repo, "checkout", "-q", "-b", "feat/q")
    assert [p.id for p in check_settings(repo)] == ["report-comment-needs-repo-placement"]


def test_check_applies_r5_across_every_quiet_feature(repo: Path) -> None:
    push_fr_branch(repo, "schema: 1\nplacement: quiet\nartifacts:\n  gates: off\n")
    git(repo, "checkout", "-q", "-b", "feat/q")
    fr_root = space_for(repo).root
    plan = fr_root / "features" / "feat__other" / KIND_DIRS["plan"] / "deploy"
    plan.mkdir(parents=True)
    (plan / "ops.yaml").write_text(
        "schema_version: 1\nops:\n  - id: k\n    summary: s\n    phase: pre-merge\n"
        "    check: test -e key\n"
    )
    problems = check_settings(repo)
    assert [p.id for p in problems] == ["gates-off-with-ops"]
    assert "deploy" in problems[0].message


# --- S1 (spec 2026-11-19-event-driven-a-la-carte R5, R6): both switches, in step -----------


def test_init_quiet_writes_fr_config_and_the_identical_legacy_switch(
    repo: Path, tmp_path: Path
) -> None:
    from fr.placement.quiet import _read_legacy

    result = _fr(repo, "settings", "init", "--quiet")
    assert result.exit_code == 0, result.output
    origin = tmp_path / "origin.git"
    sha = git(origin, "rev-parse", "refs/heads/fr-config").strip()
    assert git(origin, "rev-list", "--parents", "-n1", sha).split() == [sha]  # orphan
    assert git(origin, "ls-tree", "-r", "--name-only", sha).split() == [".fr/settings.yaml"]
    new = git(origin, "show", f"{sha}:.fr/settings.yaml")
    old = git(origin, "show", "refs/heads/fr:settings.yaml")
    assert new == old and "\nplacement: quiet\n" in new
    assert load_settings(repo).ref == "refs/remotes/origin/fr-config"
    # an fr below S1 reads only the old file, and reads quiet from it
    legacy = _read_legacy(repo)
    assert legacy is not None and legacy.settings.placement == "quiet"


def test_init_quiet_refuses_when_origin_already_has_fr_config(repo: Path, tmp_path: Path) -> None:
    from tests.unit.test_placement_quiet import push_config_branch

    push_config_branch(repo, None)
    result = _fr(repo, "settings", "init", "--quiet")
    assert result.exit_code == 2
    assert "fr-config" in result.output and "already" in result.output
    assert git(tmp_path / "origin.git", "branch", "--list", "fr").strip() == ""


def test_write_settings_rewrites_both_switches_and_they_never_differ(
    repo: Path, tmp_path: Path
) -> None:
    from fr.config.space import quiet_config_space, write_settings

    assert _fr(repo, "settings", "init", "--quiet").exit_code == 0
    text = "schema: 1\nplacement: quiet\nforge:\n  labels: off\n"
    write_settings(quiet_config_space(repo), text, message="chore(fr): settings")
    origin = tmp_path / "origin.git"
    assert git(origin, "show", "refs/heads/fr-config:.fr/settings.yaml") == text
    assert git(origin, "show", "refs/heads/fr:settings.yaml") == text
    eff = load_settings(repo)
    assert eff.settings.forge.labels == "off" and eff.ref == "refs/remotes/origin/fr-config"
    # the second write is a no-op: no new commit on either branch
    heads = [git(origin, "rev-parse", b).strip() for b in ("fr-config", "fr")]
    write_settings(quiet_config_space(repo), text, message="chore(fr): settings")
    assert [git(origin, "rev-parse", b).strip() for b in ("fr-config", "fr")] == heads


def test_init_quiet_on_an_old_quiet_repo_creates_fr_config_from_the_old_switch(
    repo: Path, tmp_path: Path
) -> None:
    """Decision p2-create-at-init-and-migration: an existing quiet repo (switch only at
    `origin/fr:settings.yaml`) gets its configuration space at `fr settings init --quiet`,
    holding the old switch's bytes; the old file is untouched."""
    from tests.unit.test_placement_quiet import QUIET

    push_fr_branch(repo, QUIET)
    origin = tmp_path / "origin.git"
    fr_before = git(origin, "rev-parse", "refs/heads/fr").strip()
    result = _fr(repo, "settings", "init", "--quiet")
    assert result.exit_code == 0, result.output
    assert "fr-config" in result.output
    sha = git(origin, "rev-parse", "refs/heads/fr-config").strip()
    assert git(origin, "rev-list", "--parents", "-n1", sha).split() == [sha]  # orphan
    assert git(origin, "show", f"{sha}:.fr/settings.yaml") == QUIET
    assert git(origin, "rev-parse", "refs/heads/fr").strip() == fr_before
    assert load_settings(repo).ref == "refs/remotes/origin/fr-config"
