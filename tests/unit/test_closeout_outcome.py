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


# --- review p3-r2 / p3-r9 -------------------------------------------------


def test_a_fenced_heading_neither_ends_nor_starts_the_test_plan() -> None:
    text = (
        "# X\n\n```\n## Test Plan\n- fenced, not the section\n```\n\n"
        "## Test Plan\n\n1. first\n\n   ```bash\n# set up\n   ```\n2. second\n\n"
        "## Next\n\n1. not a step\n"
    )
    assert [s.text for s in plan_steps(text)] == ["first ```bash # set up ```", "second"]


def test_an_empty_test_plan_is_one_step_that_says_so() -> None:
    assert [(s.n, s.text) for s in plan_steps("## Test Plan\n\n## Next\n")] == [
        (1, "(Test Plan section has no steps)")
    ]


def test_outcome_command_prints_one_pasteable_line_per_alternative() -> None:
    from fr.archive import outcome_command

    lines = outcome_command("--run r1", 3)
    assert lines == [
        "fr closeout outcome --run r1 --step 3 --ran --evidence '<what it showed>'",
        "fr closeout outcome --run r1 --step 3 --owed --why '<why not now>'",
        "fr closeout outcome --run r1 --step 3 --na --reason '<why it does not apply>'",
    ]


# --- review p3-r3(b) / p3-r7 ----------------------------------------------


def test_an_outcome_on_the_default_branch_says_the_journal_is_uncommitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    subprocess.run(["git", "checkout", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e", "-c", "user.name=t", "commit", "-qm", "seed"],
        cwd=root,
        check=True,
    )
    monkeypatch.chdir(root)
    res = _outcome("--step", "1", "--na", "--reason", "r")
    assert res.exit_code == 0, res.output
    assert "uncommitted" in res.output and "fr archive" in res.output


def test_an_owed_entry_written_to_an_old_stamp_journal_restamps_it(repo: Path) -> None:
    from fr.artifacts import ARTIFACT_KINDS

    path = journal_path(repo, "spec", SLUG)
    path.parent.mkdir(parents=True)
    path.write_text(
        "# Journal: x\n\n"
        "<!-- fr:journal kind=discovery scope=spec id=d1 created=2026-01-01T00:00:00 -->\n"
        "### d1 · discovery · t\n"
    )
    res = _outcome("--step", "4", "--owed", "--why", "later")
    assert res.exit_code == 0, res.output
    assert ARTIFACT_KINDS["journal"].read_version(path) == ARTIFACT_KINDS["journal"].current_version
    assert [e.id for e in _entries(repo)] == ["d1", "test-plan-step-4"]


# --- a step that names rows walks them (spec 2026-11-27-ops-gate-truth R8, R9) ---------

W_SLUG = "2026-11-27-gizmo"
W_SPEC = f"docs/superpowers/specs/{W_SLUG}-design.md"
W_FRAGMENT = f"docs/acceptance/features/{W_SLUG}.yaml"
W_TEXT = """# Gizmo

R1. it works.

## Verification

strategy: live
gate: devops
- r1: live — needs the merged build
- r2: live — two harnesses
- r3: none — unit tests

## Test Plan

1. [devops] (rows: r1) Run it live.
2. [devops] (rows: r2) Run it on both.
3. (rows: r3) Check the unit.
4. (rows: zz) Unknown row.
5. (rows: r1, r2) Both.
"""


def _w_row(rid: str, **extra: object) -> dict[str, object]:
    return {
        "id": rid,
        "capability": "Gizmo",
        "acceptance": f"{rid} works",
        "origin": [f"spec:{W_SLUG}#R1"],
        "status": "walk-owed",
        "notes": "owed",
        **extra,
    }


def _w_fragment(rows: list[dict[str, object]]) -> str:
    return yaml.safe_dump(
        {"schema_version": 1, "feature": W_SLUG, "repo": "acme/gizmo", "rows": rows},
        sort_keys=False,
    )


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout


def _walk_repo(tmp_path: Path, *, merged: bool = False, settings: str | None = None) -> Path:
    """A repo on `feat/gizmo` whose origin's `main` holds the spec (and, when *merged*, the
    rows' fragment); otherwise the fragment is pending on the branch."""
    from fr.acceptance.fold import clear_fold_cache

    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    root = tmp_path / "gizmo"
    (root / "docs/superpowers/specs").mkdir(parents=True)
    (root / W_SPEC).write_text(W_TEXT)
    (root / ".github/workflows").mkdir(parents=True)
    (root / ".github/workflows/ci.yml").write_text("on: push\n")
    if settings is not None:
        (root / ".fr").mkdir()
        (root / ".fr/settings.yaml").write_text(settings)
    rows = [
        _w_row("r1", issues=["acme/gizmo#7"]),
        _w_row("r2", harnesses=["a", "b"]),
        _w_row("r3"),
    ]
    (root / "docs/acceptance/features").mkdir(parents=True)
    _git(tmp_path, "init", "-q", "-b", "main", str(root))
    for k, v in (("user.email", "t@example.com"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(root, "config", k, v)
    _git(root, "remote", "add", "origin", str(bare))
    if merged:
        (root / W_FRAGMENT).write_text(_w_fragment(rows))
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "feat: gizmo spec")
    _git(root, "push", "-q", "-u", "origin", "main")
    _git(root, "fetch", "-q", "origin")
    _git(root, "checkout", "-q", "-b", "feat/gizmo")
    if not merged:
        (root / W_FRAGMENT).write_text(_w_fragment(rows))
        _git(root, "add", "-A")
        _git(root, "commit", "-qm", "rows")
    clear_fold_cache()
    return root


def _w(root: Path, monkeypatch: pytest.MonkeyPatch, *args: str):  # noqa: ANN202
    from fr.acceptance.fold import clear_fold_cache

    monkeypatch.chdir(root)
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    clear_fold_cache()
    return runner.invoke(app, ["closeout", "outcome", "--spec", W_SPEC, *args])


def _w_rows(root: Path) -> dict[str, object]:
    from fr.acceptance.fold import clear_fold_cache, load_effective

    clear_fold_cache()
    return {r.id: r for r in load_effective(root).rows}


def _commits(root: Path) -> int:
    return int(_git(root, "rev-list", "--count", "HEAD").strip())


def test_ran_on_a_step_naming_a_row_walks_it_in_the_same_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _walk_repo(tmp_path)
    before = _commits(root)

    res = _w(root, monkeypatch, "--step", "1", "--ran", "--evidence", "E")

    assert res.exit_code == 0, res.output
    assert _commits(root) == before + 1
    changed = _git(root, "show", "--name-only", "--format=", "HEAD").split()
    assert W_FRAGMENT in changed and any("journals" in p for p in changed)
    r1 = _w_rows(root)["r1"]
    assert r1.status == "walked"  # type: ignore[attr-defined]
    (walk,) = r1.walks  # type: ignore[attr-defined]
    assert (walk.strategy, walk.harness, walk.model, walk.outcome) == (
        "live", "operator", "human", "pass"
    )  # fmt: skip
    assert walk.evidence == "Test Plan step 1: E"
    assert "r1: walked" in res.output


def test_harness_and_model_override_the_walk_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _walk_repo(tmp_path)

    res = _w(root, monkeypatch, "--step", "1", "--ran", "--evidence", "E",
             "--harness", "h", "--model", "m")  # fmt: skip

    assert res.exit_code == 0, res.output
    (walk,) = _w_rows(root)["r1"].walks  # type: ignore[attr-defined]
    assert (walk.harness, walk.model) == ("h", "m")


def test_a_row_naming_two_harnesses_keeps_its_status_and_names_the_one_owed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _walk_repo(tmp_path)

    res = _w(root, monkeypatch, "--step", "2", "--ran", "--evidence", "E", "--harness", "a")

    assert res.exit_code == 0, res.output
    r2 = _w_rows(root)["r2"]
    assert r2.status == "walk-owed" and len(r2.walks) == 1  # type: ignore[attr-defined]
    assert "r2:" in res.output and "still owed: b" in res.output


@pytest.mark.parametrize("args", [["--na", "--reason", "x"], ["--owed", "--why", "y"]])
def test_na_and_owed_write_no_walk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, args: list[str]
) -> None:
    root = _walk_repo(tmp_path)

    res = _w(root, monkeypatch, "--step", "1", *args)

    assert res.exit_code == 0, res.output
    assert _w_rows(root)["r1"].walks == ()  # type: ignore[attr-defined]


def test_supersede_ran_adds_a_second_walk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _walk_repo(tmp_path)
    assert _w(root, monkeypatch, "--step", "1", "--ran", "--evidence", "E").exit_code == 0

    res = _w(root, monkeypatch, "--step", "1", "--ran", "--evidence", "F", "--supersede")

    assert res.exit_code == 0, res.output
    walks = _w_rows(root)["r1"].walks  # type: ignore[attr-defined]
    assert [w.evidence for w in walks] == ["Test Plan step 1: E", "Test Plan step 1: F"]


@pytest.mark.parametrize("step", ["3", "4"])
def test_an_unknown_row_or_a_row_on_strategy_none_refuses_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, step: str
) -> None:
    root = _walk_repo(tmp_path)
    head = _git(root, "rev-parse", "HEAD")

    res = _w(root, monkeypatch, "--step", step, "--ran", "--evidence", "E")

    assert res.exit_code == 2, res.output
    assert "nothing written" in res.output
    assert _git(root, "rev-parse", "HEAD") == head
    assert _git(root, "status", "--porcelain") == ""


def test_under_acceptance_off_the_pointer_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _walk_repo(tmp_path, settings="artifacts:\n  acceptance: off\n")

    res = _w(root, monkeypatch, "--step", "4", "--ran", "--evidence", "E")

    assert res.exit_code == 0, res.output
    changed = _git(root, "show", "--name-only", "--format=", "HEAD").split()
    assert W_FRAGMENT not in changed
    assert _w_rows(root)["r1"].walks == ()  # type: ignore[attr-defined]


def test_a_merged_row_is_amended_into_the_specs_fragment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _walk_repo(tmp_path, merged=True)

    res = _w(root, monkeypatch, "--step", "1", "--ran", "--evidence", "E")

    assert res.exit_code == 0, res.output
    fragment = yaml.safe_load((root / W_FRAGMENT).read_text())
    assert fragment.get("amendments"), fragment
    assert _w_rows(root)["r1"].status == "walked"  # type: ignore[attr-defined]


def test_the_freed_issue_gets_its_close_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _walk_repo(tmp_path)

    res = _w(root, monkeypatch, "--step", "1", "--ran", "--evidence", "E")

    assert res.exit_code == 0, res.output
    assert "acme/gizmo#7: every row citing it is walk-verified" in res.output
    assert "gh issue close 7 --repo acme/gizmo" in res.output


def test_a_run_spec_takes_the_run_and_walks_its_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _walk_repo(tmp_path)
    cursor = root / "docs/superpowers/runs/2026-11-27-feat-gizmo.yaml"
    cursor.parent.mkdir(parents=True)
    cursor.write_text(
        yaml.safe_dump(
            {
                "schema_version": 10,
                "run": "2026-11-27-feat-gizmo",
                "workflow": "fr-goal@1",
                "branch": "feat/gizmo",
                "started": "2026-11-27T09:00:00Z",
                "cursor": "deliver",
                "steps": {
                    "spec": {"state": "done", "emitted": {"spec": W_SPEC}},
                    "deliver": {"state": "done"},
                },
            }
        )
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "run")
    monkeypatch.chdir(root)
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    res = runner.invoke(
        app, ["closeout", "outcome", "--run", "2026-11-27-feat-gizmo", "--step", "1",
              "--ran", "--evidence", "E"],
    )  # fmt: skip

    assert res.exit_code == 0, res.output
    assert _w_rows(root)["r1"].status == "walked"  # type: ignore[attr-defined]
