"""Test Plan steps and `fr closeout outcome` (spec 2026-10-11-debt-engine §E, R17, R18)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml
from fr.cli import app
from fr.journal.model import journal_path, owed_fields, parse_journal
from fr.spec import test_plan_steps as plan_steps
from typer.testing import CliRunner

runner = CliRunner()

SLUG = "2026-10-11-widget"
SPEC_REL = f"docs/superpowers/specs/{SLUG}-design.md"
RUN_ID = "2026-10-11-feat-widget"

SPEC = """# Widget

## Requirements

1. not a Test Plan step

## Test Plan

Post-merge rows only.

1. Dispatch the workflow with `debt: true`. The issue is renamed
   in place, and no second issue is opened.
2. Second step.

   A continuation paragraph.
- A dash step
* A star step
  - nested, still step 4's
3. Fifth step

## Implementation Plans
"""


# --- the parser (R17) -----------------------------------------------------


def test_test_plan_steps_numbers_top_level_items_by_position() -> None:
    steps = plan_steps(SPEC)
    assert [s.n for s in steps] == [1, 2, 3, 4, 5]
    assert steps[0].text == (
        "Dispatch the workflow with `debt: true`. The issue is renamed in place, and no "
        "second issue is opened."
    )
    assert steps[1].text == "Second step. A continuation paragraph."
    assert steps[2].text == "A dash step"
    assert steps[3].text == "A star step - nested, still step 4's"
    assert steps[4].text == "Fifth step"


def test_a_test_plan_with_no_list_is_one_step() -> None:
    text = "# X\n\n## Test Plan\n\nRun the thing by hand\nand look.\n\n## Next\n"
    steps = plan_steps(text)
    assert [(s.n, s.text) for s in steps] == [(1, "Run the thing by hand and look.")]


def test_no_test_plan_is_no_steps() -> None:
    assert plan_steps("# X\n\n## Requirements\n\n1. a\n") == []


def test_a_list_inside_a_code_fence_is_not_a_step() -> None:
    text = "## Test Plan\n\n1. real\n\n```\n- not a step\n```\n2. also real\n"
    assert [s.text for s in plan_steps(text)] == ["real", "also real"]


# --- the verb (R18) -------------------------------------------------------


def _repo(tmp_path: Path, spec: str = SPEC) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / SPEC_REL).parent.mkdir(parents=True)
    (tmp_path / SPEC_REL).write_text(spec)
    cursor = tmp_path / "docs/superpowers/runs" / f"{RUN_ID}.yaml"
    cursor.parent.mkdir(parents=True)
    cursor.write_text(
        yaml.safe_dump(
            {
                "schema_version": 10,
                "run": RUN_ID,
                "workflow": "fr-goal@1",
                "branch": "feat/widget",
                "started": "2026-10-11T09:00:00Z",
                "cursor": "deliver",
                "steps": {
                    "spec": {"state": "done", "emitted": {"spec": SPEC_REL}},
                    "deliver": {"state": "done"},
                },
            }
        )
    )
    return tmp_path


def _outcome(*args: str):  # noqa: ANN202
    return runner.invoke(app, ["closeout", "outcome", "--run", RUN_ID, *args])


def _entries(root: Path):  # noqa: ANN202
    path = journal_path(root, "spec", SLUG)
    return parse_journal(path.read_text()) if path.exists() else []


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    return root


def test_na_over_a_range_writes_one_discovery_per_step(repo: Path) -> None:
    res = _outcome("--step", "1-3", "--na", "--reason", "in CI")
    assert res.exit_code == 0, res.output
    entries = _entries(repo)
    assert [(e.id, e.kind) for e in entries] == [
        ("test-plan-step-1", "discovery"),
        ("test-plan-step-2", "discovery"),
        ("test-plan-step-3", "discovery"),
    ]
    assert "in CI" in entries[0].body
    assert "Dispatch the workflow" in entries[0].body


def test_ran_writes_a_discovery_with_its_evidence(repo: Path) -> None:
    res = _outcome("--step", "2", "--ran", "--evidence", "issue #9 renamed")
    assert res.exit_code == 0, res.output
    (entry,) = _entries(repo)
    assert entry.id == "test-plan-step-2" and entry.kind == "discovery"
    assert "issue #9 renamed" in entry.body


def test_owed_writes_an_owed_entry_with_its_key(repo: Path) -> None:
    res = _outcome("--step", "4", "--owed", "--why", "needs the workflow on main")
    assert res.exit_code == 0, res.output
    (entry,) = _entries(repo)
    assert entry.id == "test-plan-step-4" and entry.kind == "owed"
    fields = owed_fields(entry)
    assert fields["owed_key"] == f"spec:{SLUG}#step4"
    assert fields["why"] == "needs the workflow on main"
    assert fields["what"] == "A star step - nested, still step 4's"
    assert f"fr journal resolve --scope spec --slug {SLUG} --id test-plan-step-4" in fields["how"]


@pytest.mark.parametrize(
    "args",
    [
        ["--step", "1"],
        ["--step", "1", "--ran", "--evidence", "e", "--na", "--reason", "r"],
        ["--step", "1", "--ran"],
        ["--step", "1", "--owed"],
        ["--step", "1", "--na"],
        ["--step", "1", "--ran", "--why", "w"],
        ["--step", "1", "--na", "--reason", "r", "--evidence", "e"],
    ],
)
def test_exactly_one_outcome_with_its_own_text(repo: Path, args: list[str]) -> None:
    res = _outcome(*args)
    assert res.exit_code == 2, res.output
    assert _entries(repo) == []


@pytest.mark.parametrize("step", ["0", "6", "3-9", "4-2", "x", "-1", "1-"])
def test_an_out_of_range_or_malformed_step_is_refused(repo: Path, step: str) -> None:
    res = _outcome("--step", step, "--na", "--reason", "r")
    assert res.exit_code == 2, res.output
    assert _entries(repo) == []


def test_a_step_already_recorded_is_refused_and_nothing_is_written(repo: Path) -> None:
    assert _outcome("--step", "2", "--na", "--reason", "r").exit_code == 0
    res = _outcome("--step", "1-3", "--ran", "--evidence", "e")
    assert res.exit_code == 2, res.output
    assert "test-plan-step-2" in res.output
    assert [e.id for e in _entries(repo)] == ["test-plan-step-2"]


def test_an_unknown_run_is_refused(repo: Path) -> None:
    res = runner.invoke(
        app, ["closeout", "outcome", "--run", "nope", "--step", "1", "--na", "--reason", "r"]
    )
    assert res.exit_code == 2, res.output


@pytest.mark.parametrize("bad", ["../x", "-x", "a/b"])
def test_a_run_id_that_is_not_a_bare_id_is_refused(repo: Path, bad: str) -> None:
    res = runner.invoke(
        app, ["closeout", "outcome", "--run", bad, "--step", "1", "--na", "--reason", "r"]
    )
    assert res.exit_code == 2, res.output


def test_a_spec_with_no_test_plan_is_refused(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    root = _repo(tmp_path, spec="# Widget\n\n## Requirements\n\n1. a\n")
    monkeypatch.chdir(root)
    res = _outcome("--step", "1", "--na", "--reason", "r")
    assert res.exit_code == 2, res.output
    assert "Test Plan" in res.output
