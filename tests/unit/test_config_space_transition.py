"""Old configuration paths past the end of S1's transition (spec 2026-11-28-s1-followups
R2, R3, R10; plan P1.T2.S1).

Every test forces its side of the gate by monkeypatching `fr.config.transition.refusing`,
so a release into 9.2 turns none of them red. Past the gate a reader that finds a
configuration file only at its old path refuses (exit 2), naming the old path, the new
path and `fr migrate artifacts --yes`; the movers (`fr repos sync`, `fr repair`, the
migration) still read and move it."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.artifacts import run_migrations
from fr.artifacts.commit import commit_migration
from fr.cli import app
from fr.config import space, transition
from typer.testing import CliRunner

from tests.unit.settings_repo import make_repo
from tests.unit.test_migration_config_kinds import FILES, _feature, _put, _quiet

pytestmark = pytest.mark.own_artifacts

runner = CliRunner()

PLAN_CONFIG = "docs/superpowers/plan-config.yaml"
MODELS = "docs/superpowers/models.yaml"
PROFILES = ".devcontainer/fr-profiles.yaml"
MIGRATE = "fr migrate artifacts --yes"


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv(transition.ENV, raising=False)
    space._OLD_NOTICED.clear()
    return home


@pytest.fixture
def ended(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transition, "refusing", lambda: True)


@pytest.fixture
def open_(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transition, "refusing", lambda: False)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    return path


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def _assert_refusal(err: BaseException, old: str, new: str) -> None:
    text = str(err)
    assert old in text and new in text and MIGRATE in text, text


# --- past the gate: readers refuse --------------------------------------------------------


@pytest.mark.usefixtures("ended")
def test_an_old_plan_config_alone_is_refused(root: Path) -> None:
    _write(root, PLAN_CONFIG, "plan: {}\n")
    with pytest.raises(transition.TransitionError) as caught:
        space.located(root, "plan-config")
    _assert_refusal(caught.value, PLAN_CONFIG, ".fr/plan-config.yaml")


@pytest.mark.usefixtures("ended")
def test_old_profile_declarations_alone_are_refused(root: Path) -> None:
    _write(root, PROFILES, "schema_version: 2\nprofiles: {}\n")
    with pytest.raises(transition.TransitionError) as caught:
        space.located(root, "profiles")
    _assert_refusal(caught.value, PROFILES, ".fr/profiles.yaml")


@pytest.mark.usefixtures("ended")
def test_a_reader_command_exits_2_naming_both_paths(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(root, MODELS, "opencode:\n  hard: m\n")
    monkeypatch.chdir(root)
    res = runner.invoke(app, ["models", "resolve", "--harness", "opencode", "--tier", "hard"])
    assert res.exit_code == 2, res.output
    assert "Traceback" not in res.output
    _assert_refusal(Exception(res.output), MODELS, ".fr/models.yaml")


@pytest.mark.usefixtures("ended")
def test_both_paths_present_reads_the_new_one_without_a_word(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(root, PLAN_CONFIG, "plan: {}\n")
    new = _write(root, ".fr/plan-config.yaml", "plan: {}\n")
    assert space.located(root, "plan-config") == new
    assert capsys.readouterr().err == ""


@pytest.mark.usefixtures("ended")
def test_under_quiet_without_fr_config_the_old_committed_file_is_refused(
    tmp_path: Path,
) -> None:
    root = _quiet(tmp_path)
    _put(root, MODELS, "opencode:\n  hard: m\n")  # committed on the default branch
    with pytest.raises(transition.TransitionError) as caught:
        space.located(root, "models")
    assert MIGRATE in str(caught.value)


# --- before the gate: S1's notice -------------------------------------------------------


@pytest.mark.usefixtures("open_")
def test_before_the_gate_the_old_path_is_read_with_one_notice(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old = _write(root, PLAN_CONFIG, "plan: {}\n")
    assert space.located(root, "plan-config") == old
    assert space.located(root, "plan-config") == old
    err = capsys.readouterr().err
    assert err.count("is at its old location; run fr migrate artifacts --yes") == 1


# --- the movers work on both sides --------------------------------------------------------


@pytest.mark.parametrize("side", [True, False])
def test_old_path_never_refuses(root: Path, monkeypatch: pytest.MonkeyPatch, side: bool) -> None:
    monkeypatch.setattr(transition, "refusing", lambda: side)
    old = _write(root, PLAN_CONFIG, "plan: {}\n")
    assert space.old_path(root, "plan-config") == old
    _write(root, ".fr/plan-config.yaml", "plan: {}\n")
    assert space.old_path(root, "plan-config") is None


@pytest.mark.usefixtures("ended")
def test_repos_sync_force_still_moves_the_old_plan_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repos = tmp_path / "repos"
    root = repos / "super-fr"
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    monkeypatch.setenv("FR_REPOS_DIR", str(repos))
    monkeypatch.setenv("FR_REPOS_MANIFEST", str(tmp_path / "repos.yaml"))
    old = _write(root, PLAN_CONFIG, "plan:\n  filename: custom\n")
    res = runner.invoke(app, ["repos", "sync", "derio-net/super-fr", "--yes"])
    assert res.exit_code == 0 and "SKIP" in res.output, res.output
    res = runner.invoke(app, ["repos", "sync", "derio-net/super-fr", "--yes", "--force"])
    assert res.exit_code == 0, res.output
    assert (root / ".fr/plan-config.yaml").is_file() and not old.exists()


@pytest.mark.usefixtures("ended")
def test_repair_still_reads_the_old_plan_config(root: Path) -> None:
    from fr.repair import repairable_plan_config

    old = _write(root, PLAN_CONFIG, "plan: {}\n")
    assert repairable_plan_config(root) == old


@pytest.mark.usefixtures("ended")
def test_the_migration_still_moves_every_old_path(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    _feature(root)
    for old, _new, text in FILES.values():
        _put(root, old, text)
    report = run_migrations(root, dry_run=False)
    assert report.ok, report.failed
    commit_migration(root, report, fr_version="9.9.9")
    for old, new, _text in FILES.values():
        assert not (root / old).exists(), old
        assert (root / new).exists(), new
