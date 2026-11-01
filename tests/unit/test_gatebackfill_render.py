"""The dry run's summary and the repo-file commands of R11
(spec 2026-11-01-gate-backfill §E)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.gatebackfill.model import PlanEntry, PrHit
from fr.gatebackfill.render import decision_commands, row_reconcile, summary

from tests.unit.gatebackfill_fixtures import SP, make_repo, row, write_matrix
from tests.unit.test_merge_evidence import _write_plan

PLAN = "2026-10-20-ops"


@pytest.fixture(autouse=True)
def _hermetic_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _e(key: str, decision: str, **kw: object) -> PlanEntry:
    return PlanEntry.model_validate({"key": key, "title": "t", "decision": decision, **kw})


def test_summary_lists_every_candidate_and_parks_under_their_own_heading(tmp_path: Path) -> None:
    pr = PrHit(number=41, basis="commit")
    entries = [
        _e("row:a", "owed", gate="tester", pr=pr),
        _e("row:b", "park", gate="tester", pr=pr),
        _e("row:c", "review", why="no gate"),
    ]

    text, refusals = summary(entries, plan_file=tmp_path / "p.yaml", notes=[], root=tmp_path)

    assert refusals == []
    head, _, parked = text.partition("Parked (1)")
    assert "row:a  gate=tester  PR #41 (commit)  -> owed" in head
    assert "row:c" in head and "No delivering PR" in head
    assert "row:b" in parked and "row:b" not in head


def test_tick_on_a_live_plan_prints_one_plan_edit_per_unticked_step(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _write_plan(repo, PLAN, [("manual", False), ("manual", True)])

    cmds, refusal = decision_commands(_e(f"plan:{PLAN}#p1", "tick"), repo)

    assert refusal is None
    assert cmds == [f"fr plan edit docs/superpowers/plans/{PLAN} --tick P1.T1.S1"]
    done, _ = decision_commands(_e(f"plan:{PLAN}#p2", "tick"), repo)
    assert done == []  # nothing left to tick


def test_na_prints_the_command_of_its_kind_and_needs_a_note(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _write_plan(repo, PLAN, [("manual", False)])
    spec = repo / SP / "specs" / "2026-05-01-thing-design.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("# t\n\n## Test Plan\n\n1. walk\n")

    plan_cmd, _ = decision_commands(_e(f"plan:{PLAN}#p1", "na", note="not needed"), repo)
    assert plan_cmd == [
        f"fr plan edit docs/superpowers/plans/{PLAN} --tick P1.T1.S1 --state - "
        "--note 'n/a: not needed'"
    ]
    spec_cmd, _ = decision_commands(_e("spec:2026-05-01-thing#step1", "na", note="moot"), repo)
    assert spec_cmd == [
        "fr closeout outcome --spec docs/superpowers/specs/2026-05-01-thing-design.md "
        "--step 1 --na --reason moot"
    ]
    row_cmd, _ = decision_commands(_e("row:a", "na", note="manual by nature"), repo)
    assert row_cmd == ["fr acceptance set-status --id a --status manual --notes 'manual by nature'"]

    _, refusal = decision_commands(_e("row:a", "na"), repo)
    assert refusal is not None and "needs a note" in refusal


def test_refused_cells_name_the_decisions_the_kind_accepts(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    archived = repo / SP / "implemented" / "plans"
    archived.mkdir(parents=True)
    _write_plan(repo, PLAN, [("manual", False)]).rename(archived / PLAN)

    for key, decision in (
        (f"plan:{PLAN}#p1", "tick"),  # archived plan is frozen
        ("row:a", "tick"),
        ("spec:2026-05-01-thing#step1", "tick"),
        ("issue:example-org/widgets#4", "na"),
    ):
        _, refusal = decision_commands(_e(key, decision, note="n"), repo)
        assert refusal is not None and "accepts:" in refusal, key
    assert "frozen" in (decision_commands(_e(f"plan:{PLAN}#p1", "tick"), repo)[1] or "")


def test_a_not_implemented_row_with_a_post_merge_strategy_is_moved_to_walk_owed(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    write_matrix(
        repo,
        [row("live-one", "not-implemented", verify="live"), row("plain", "not-implemented")],
    )

    cmds = row_reconcile(repo)

    assert len(cmds) == 1 and cmds[0].startswith("fr acceptance set-status --id live-one")
    assert "--status walk-owed" in cmds[0]
