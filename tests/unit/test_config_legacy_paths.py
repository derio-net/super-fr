"""The transition (spec 2026-11-19-event-driven-a-la-carte S1 R13; plan
2026-11-24-s1-configuration-homes P4.T3.S1).

Until the release the owed entry `s1-refuse-old-paths` names (R14), a reader of a moved
kind that finds the file only at its old path uses it, and prints one notice per process
naming `fr migrate artifacts --yes`. A file at its new path is read without a word.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.config import space

REPO = Path(__file__).resolve().parents[2]
NOTICE = "is at its old location; run fr migrate artifacts --yes"


@pytest.fixture(autouse=True)
def _fresh_notices() -> None:
    space._OLD_NOTICED.clear()


@pytest.fixture
def root(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    return tmp_path


def _put(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def _read_models(root: Path) -> object:
    from fr.models import load_models, repo_models_path

    return load_models(repo_models_path(root))


def _read_trackers(root: Path) -> object:
    from fr.tracker.model import load_trackers, repo_trackers_path

    return load_trackers(repo_trackers_path(root))


def _read_plan_config(root: Path) -> object:
    from fr.repair import plan_config_path

    return plan_config_path(root).read_text()


def _read_profiles(root: Path) -> object:
    from fr.isolation.types import profiles_config

    return profiles_config(root)


def _read_workflow(root: Path) -> object:
    from fr.workflow.resolve import resolve_workflow

    return resolve_workflow("mine", root, shipped_root=root / "no-shipped").workflow


def _read_strategy(root: Path) -> object:
    from fr.verification.resolve import resolved_strategy_path

    return resolved_strategy_path("candidate", root, shipped_root=root / "no-shipped").name


WORKFLOW = (REPO / "plugins/super-fr/workflows/fr-goal-light.yaml").read_text()
STRATEGY = (REPO / "plugins/super-fr/verifications/candidate.yaml").read_text()

READERS = {
    "models": (
        "docs/superpowers/models.yaml",
        ".fr/models.yaml",
        "opencode:\n  hard: m\n",
        _read_models,
    ),
    "trackers": (
        "docs/superpowers/trackers.yaml",
        ".fr/trackers.yaml",
        "github: {}\n",
        _read_trackers,
    ),
    "plan-config": (
        "docs/superpowers/plan-config.yaml",
        ".fr/plan-config.yaml",
        "plan: {}\n",
        _read_plan_config,
    ),
    "profiles": (
        ".devcontainer/fr-profiles.yaml",
        ".fr/profiles.yaml",
        "schema_version: 2\nprofiles: {}\n",
        _read_profiles,
    ),
    "workflow": (
        "docs/superpowers/workflows/mine.yaml",
        ".fr/workflows/mine.yaml",
        WORKFLOW,
        _read_workflow,
    ),
    "verification": (
        "docs/superpowers/verifications/candidate.yaml",
        ".fr/verifications/candidate.yaml",
        STRATEGY,
        _read_strategy,
    ),
}


@pytest.mark.parametrize("kind", sorted(READERS))
def test_a_file_only_at_its_old_path_is_read_with_one_notice(
    root: Path, kind: str, capsys: pytest.CaptureFixture[str]
) -> None:
    old, new, text, read = READERS[kind]
    _put(root, old, text)
    first = read(root)
    second = read(root)
    assert first == second and first not in (None, {}, "")
    err = capsys.readouterr().err
    # a directory kind names its directory, a file kind its file
    assert (
        err.count(NOTICE) == 1 and str(root / old.split("/mine")[0].split("/candidate")[0]) in err
    )


@pytest.mark.parametrize("kind", sorted(READERS))
def test_a_file_at_its_new_path_is_read_silently_and_wins(
    root: Path, kind: str, capsys: pytest.CaptureFixture[str]
) -> None:
    old, new, text, read = READERS[kind]
    _put(root, new, text)
    read(root)
    assert NOTICE not in capsys.readouterr().err


def test_located_prefers_the_new_path_when_both_exist(root: Path) -> None:
    _put(root, "docs/superpowers/models.yaml", "a: {}\n")
    new = _put(root, ".fr/models.yaml", "b: {}\n")
    assert space.located(root, "models") == new


def test_validate_plans_reads_the_old_plan_config_with_a_notice(root: Path) -> None:
    _put(
        root,
        "docs/superpowers/plan-config.yaml",
        'plan:\n  filename: "{name}.md"\n',
    )
    plan = _put(root, "docs/superpowers/plans/x.md", "# X\n\n**Status:** Not Started\n")
    done = subprocess.run(
        ["bash", str(REPO / "scripts/validate-plans.sh"), str(plan)],
        cwd=root,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": str(root)},
        check=False,
    )
    assert NOTICE in done.stderr, done.stderr + done.stdout


def test_a_manifest_read_from_a_quiet_configuration_space_is_guarded(
    root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A workflow's `kind: cli` argv and a strategy's commands are executable
    configuration (R7, plan finding p5-exec-manifests-guard): read from a quiet or
    stealth configuration space, they need its branch protected first."""
    from fr.config import protection

    checkout = tmp_path / "fr-config"
    quiet = space.ConfigSpace("quiet", checkout / ".fr", checkout, root, "origin/fr-config")
    monkeypatch.setattr(space, "config_space", lambda _root: quiet)
    asked: list[str] = []

    def refuse(_space: object, _client: object, what: str) -> None:
        asked.append(what)
        raise protection.ProtectionError(f"fr will not {what}")

    monkeypatch.setattr(protection, "require_protected", refuse)
    with pytest.raises(protection.ProtectionError):
        space.guard_manifest(root, checkout / ".fr/workflows/mine.yaml", "run it")
    space.guard_manifest(root, root / "docs/superpowers/workflows/mine.yaml", "run it")
    assert asked == ["run it"]  # the product checkout's old path is not asked
