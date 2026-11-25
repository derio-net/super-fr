"""The transition (spec 2026-11-19-event-driven-a-la-carte S1 R13; plan
2026-11-24-s1-configuration-homes P4.T3.S1).

Until the release the owed entry `s1-refuse-old-paths` names (R14), a reader of a moved
kind that finds the file only at its old path uses it, and prints one notice per process
naming `fr migrate artifacts --yes`. A file at its new path is read without a word.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

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


WORKFLOW = (REPO / "plugins/super-fr/defaults/workflows/fr-goal-light.yaml").read_text()
STRATEGY = (REPO / "plugins/super-fr/defaults/verifications/candidate.yaml").read_text()

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


def _validate(root: Path, plan: Path, env: dict[str, str] | None = None) -> Any:
    return subprocess.run(
        ["bash", str(REPO / "scripts/validate-plans.sh"), str(plan)],
        cwd=root,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": str(root), **(env or {})},
        check=False,
    )


OWNER_MISSING = "missing **Owner:** line in header"


def _old_plan_config(root: Path) -> Path:
    """An old-path plan format that requires an `Owner` header, which the shipped default
    does not: the verdict on a plan without one shows which format was read."""
    _put(
        root,
        "docs/superpowers/plan-config.yaml",
        "header:\n  required:\n    - Status\n    - Owner\n",
    )
    return _put(
        root, "docs/superpowers/plans/2026-01-01-x.md", "# X\n\n**Status:** Not Started\n"
    )


def test_validate_plans_reads_the_old_plan_config_with_a_notice(root: Path) -> None:
    """Under `repo` (and with no `fr` to ask) the old file is read while only it exists:
    its rules take effect, with the notice."""
    plan = _old_plan_config(root)
    done = _validate(root, plan)
    assert NOTICE in done.stderr, done.stderr + done.stdout
    assert done.returncode != 0 and OWNER_MISSING in done.stdout + done.stderr
    (root / "docs/superpowers/plan-config.yaml").unlink()
    control = _validate(root, plan)  # the shipped default asks for no Owner
    assert control.returncode == 0, control.stdout + control.stderr


@pytest.mark.parametrize("placement", ["quiet", "stealth"])
def test_validate_plans_ignores_the_old_plan_config_under_quiet_and_stealth(
    root: Path, tmp_path_factory: pytest.TempPathFactory, placement: str
) -> None:
    """Lens review l-tests-r1: under quiet and stealth the plan format lives in the
    configuration space, and `fr.config.space.located` never reads the product worktree's
    old file there. With the configuration space's file absent, the validator does not fall
    back to it either: the old file's rules do not take effect."""
    plan = _old_plan_config(root)
    bin_dir = tmp_path_factory.mktemp("bin")
    config_file = bin_dir / "fr-config" / ".fr" / "plan-config.yaml"  # absent
    stub = bin_dir / "fr"
    stub.write_text(
        "#!/bin/sh\n"
        f"echo FR_PLACEMENT={placement}\n"
        f"echo FR_PLAN_CONFIG_FILE={config_file}\n"
    )
    stub.chmod(0o755)
    done = _validate(root, plan, {"FR_HARNESS_FR": str(stub)})
    assert NOTICE not in done.stderr, done.stderr
    assert "is ignored under placement " + placement in done.stderr, done.stderr
    assert done.returncode == 0, done.stderr + done.stdout
    assert OWNER_MISSING not in done.stdout + done.stderr
