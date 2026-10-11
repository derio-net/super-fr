"""The debt engine over real git fixtures, a fake forge and a fixed clock
(spec 2026-10-11-debt-engine §A, R3/R4/R23)."""

from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.debt.engine import (
    DebtConfigError,
    OwedSources,
    compute,
    fold_owed,
    load_stale_days,
)
from fr.debt.model import OwedItem

from tests.unit.test_merge_evidence import _add_remote, _init, _publish, _write_plan

NOW = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)
SP = "docs/superpowers"


def _commit_at(repo: Path, msg: str, iso: str) -> None:
    env = {**os.environ, "GIT_AUTHOR_DATE": iso, "GIT_COMMITTER_DATE": iso}
    base = ["git", "-C", str(repo), "-c", "user.email=t@e", "-c", "user.name=t"]
    subprocess.run([*base, "add", "-A"], check=True, capture_output=True, env=env)
    subprocess.run(
        [*base, "-c", "commit.gpgsign=false", "commit", "-qm", msg],
        check=True,
        capture_output=True,
        env=env,
    )


class FakeForge:
    def __init__(self, prs: dict[str, dict[str, Any]] | None = None, issues: list | None = None):
        self.prs = prs or {}
        self.issues = issues or []
        self.asked: list[str] = []

    def pr_for_branch(self, branch: str) -> dict[str, Any] | None:
        self.asked.append(branch)
        return self.prs.get(branch)

    def owed_issues(self) -> list[dict[str, Any]]:
        return self.issues


def _run_cursor(repo: Path, plan: str, branch: str) -> None:
    p = repo / SP / "runs" / f"run-{plan}.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f"run: run-{plan}\nworkflow: fr-goal@1\nbranch: {branch}\n"
        "started: '2026-01-01T09:00:00Z'\ncursor: deliver\nsteps:\n"
        f"  plan:\n    state: done\n    emitted: {{plan: {SP}/plans/{plan}}}\n"
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = _init(tmp_path / "r")
    _add_remote(r, tmp_path / "o.git")
    return r


def _publish_at(repo: Path, iso: str, msg: str = "seed") -> None:
    _commit_at(repo, msg, iso)
    _publish(repo)


def test_archivable_plan_is_listed_with_command_and_merge_age(repo: Path) -> None:
    _write_plan(repo, "2026-01-01-done", [("agentic", True)])
    _publish_at(repo, "2026-10-01T12:00:00+00:00")
    report = compute(repo, forge=None, now=NOW, stale_days=14)
    [a] = report.plans.archivable
    assert a.name == "2026-01-01-done"
    assert a.command == f"fr archive {SP}/plans/2026-01-01-done"
    assert a.age_days == 10


def test_merge_age_is_the_last_default_ref_commit_touching_the_plan(repo: Path) -> None:
    d = _write_plan(repo, "p", [("agentic", False)])
    _publish_at(repo, "2026-08-01T12:00:00+00:00")
    _write_plan(repo, "p", [("agentic", True)])
    _publish_at(repo, "2026-10-09T12:00:00+00:00", "ticked")
    (repo / "unrelated").write_text("x")
    _publish_at(repo, "2026-10-10T12:00:00+00:00", "other")
    assert d.is_dir()
    [a] = compute(repo, forge=None, now=NOW, stale_days=14).plans.archivable
    assert a.age_days == 2


def test_in_progress_plan_is_stale_after_the_threshold(repo: Path) -> None:
    _write_plan(repo, "old", [("agentic", False)])
    _publish_at(repo, "2026-09-01T12:00:00+00:00")
    report = compute(repo, forge=None, now=NOW, stale_days=14)
    [s] = report.plans.stale
    assert s.name == "old" and s.idle_days == 40 and s.basis == "git"


def test_active_in_progress_plan_is_not_listed(repo: Path) -> None:
    _write_plan(repo, "fresh", [("agentic", False)])
    _publish_at(repo, "2026-10-05T12:00:00+00:00")
    assert compute(repo, forge=None, now=NOW, stale_days=14).plans.stale == ()


def test_run_branch_commits_keep_a_plan_active(repo: Path) -> None:
    _write_plan(repo, "branchy", [("agentic", False)])
    _run_cursor(repo, "branchy", "feat/x")
    _publish_at(repo, "2026-09-01T12:00:00+00:00")
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-b", "feat/x"], check=True)
    (repo / "w").write_text("1")
    _commit_at(repo, "work", "2026-10-10T12:00:00+00:00")
    assert compute(repo, forge=None, now=NOW, stale_days=14).plans.stale == ()


def test_pr_activity_keeps_a_plan_active_and_marks_the_basis(repo: Path) -> None:
    _write_plan(repo, "prd", [("agentic", False)])
    _run_cursor(repo, "prd", "feat/prd")
    _publish_at(repo, "2026-09-01T12:00:00+00:00")
    forge = FakeForge({"feat/prd": {"state": "OPEN", "updatedAt": "2026-10-10T00:00:00Z"}})
    report = compute(repo, forge=forge, now=NOW, stale_days=14)
    assert report.plans.stale == ()
    assert forge.asked == ["feat/prd"]
    assert report.sources["forge"].state == "read"
    stale = compute(repo, forge=FakeForge(), now=NOW, stale_days=14).plans.stale
    assert stale[0].basis == "git+forge"


def test_offline_falls_back_to_git_and_says_so(repo: Path) -> None:
    _write_plan(repo, "old", [("agentic", False)])
    _publish_at(repo, "2026-09-01T12:00:00+00:00")
    report = compute(repo, forge=None, now=NOW, stale_days=14)
    assert report.sources["forge"].state == "unavailable"
    assert "git alone" in report.sources["forge"].why


def test_a_forge_that_raises_is_unavailable_not_fatal(repo: Path) -> None:
    class Boom(FakeForge):
        def owed_issues(self) -> list[dict[str, Any]]:
            raise RuntimeError("401")

    _write_plan(repo, "old", [("agentic", False)])
    _publish_at(repo, "2026-09-01T12:00:00+00:00")
    report = compute(repo, forge=Boom(), now=NOW, stale_days=14)
    assert report.sources["forge"].state == "unavailable" and "401" in report.sources["forge"].why


def test_stale_days_from_config_override_and_unknown_key(repo: Path) -> None:
    assert load_stale_days(repo, None) == 14
    (repo / ".fr").mkdir()
    (repo / ".fr" / "debt.yaml").write_text("stale_days: 30\n")
    assert load_stale_days(repo, None) == 30
    assert load_stale_days(repo, 7) == 7
    (repo / ".fr" / "debt.yaml").write_text("stale_days: 30\nbogus: 1\n")
    with pytest.raises(DebtConfigError, match="bogus"):
        load_stale_days(repo, None)
    (repo / ".fr" / "debt.yaml").write_text("stale_days: soon\n")
    with pytest.raises(DebtConfigError):
        load_stale_days(repo, None)


def test_config_stale_days_drives_compute(repo: Path) -> None:
    (repo / ".fr").mkdir()
    (repo / ".fr" / "debt.yaml").write_text("stale_days: 60\n")
    _write_plan(repo, "old", [("agentic", False)])
    _publish_at(repo, "2026-09-01T12:00:00+00:00")
    report = compute(repo, forge=None, now=NOW)
    assert report.stale_days == 60 and report.plans.stale == ()


def _matrix(repo: Path, rows: list[dict[str, Any]], version: int = 5) -> None:
    p = repo / "docs" / "acceptance" / "matrix.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump({"schema_version": version, "org": "o", "repo": "r", "rows": rows}))


def _row(i: str, status: str, **kw: Any) -> dict[str, Any]:
    return {"id": i, "capability": "c", "acceptance": f"does {i}", "status": status, **kw}


def test_acceptance_counts_and_walked_dates(repo: Path) -> None:
    walk = {
        "strategy": "s", "harness": "h", "model": "m", "outcome": "pass",
        "at": "2026-09-30T10:00:00Z", "evidence": "e",
    }  # fmt: skip
    _matrix(
        repo,
        [
            _row("a", "not-implemented"),
            _row("b", "walk-owed"),
            _row("c", "walked", walks=[walk]),
            _row("d", "ci"),
        ],
    )
    _publish_at(repo, "2026-10-01T12:00:00+00:00")
    acc = compute(repo, forge=None, now=NOW, stale_days=14).acceptance
    assert acc.available and acc.by_status == {
        "not-implemented": 1, "walk-owed": 1, "walked": 1, "ci": 1,
    }  # fmt: skip
    [w] = [r for r in acc.rows if r.status == "walked"]
    assert w.walked_at == "2026-09-30T10:00:00Z"


def test_an_unreadable_matrix_is_unavailable_never_zero(repo: Path) -> None:
    _matrix(repo, [_row("a", "skipped")], version=4)
    _publish_at(repo, "2026-10-01T12:00:00+00:00")
    report = compute(repo, forge=None, now=NOW, stale_days=14)
    assert report.acceptance.available is False
    assert report.sources["matrix"].state == "unavailable"
    assert "skipped" in report.sources["matrix"].why or report.sources["matrix"].why


def test_owed_folds_rows_held_manual_phases_and_issues(repo: Path) -> None:
    _matrix(repo, [_row("b", "walk-owed")])
    _write_plan(repo, "held", [("agentic", True), ("manual", False)])
    _publish_at(repo, "2026-10-01T12:00:00+00:00")
    issues = [
        {
            "ref": "o/r#7",
            "title": "walk it",
            "body": "<!-- fr-owed:row:b -->",
            "labels": ["fr:owed"],
        },
        {"ref": "o/r#8", "title": "check live", "body": "no key", "labels": ["fr:awaiting-live"]},
    ]
    report = compute(repo, forge=FakeForge(issues=issues), now=NOW, stale_days=14)
    keys = {o.key: o.source for o in report.owed}
    assert keys == {"row:b": "row", "plan:held#p2": "plan", "issue:o/r#8": "issue"}
    assert [m.phases for m in report.plans.manual_open] == [(2,)]
    # row b counts under acceptance once; the plan item and the bare issue count as owed
    assert report.debt_total() == 1 + 2


def _item(key: str, source: str, title: str = "t") -> OwedItem:
    return OwedItem(key=key, source=source, title=title)  # type: ignore[arg-type]


def test_fold_owed_dedups_by_key_with_journal_then_row_winning() -> None:
    folded = fold_owed(
        OwedSources(
            journal=[_item("row:a", "journal", "from journal")],
            rows=[_item("row:a", "row"), _item("row:b", "row")],
            plans=[_item("plan:x#p1", "plan")],
            issues=[
                _item("plan:x#p1", "issue"),
                _item("row:b", "issue"),
                _item("issue:o/r#1", "issue"),
            ],
        )
    )
    assert {o.key: (o.source, o.title) for o in folded} == {
        "row:a": ("journal", "from journal"),
        "row:b": ("row", "t"),
        "plan:x#p1": ("plan", "t"),
        "issue:o/r#1": ("issue", "t"),
    }
    assert len(folded) == 4


def test_fold_owed_with_no_journal_source_is_the_phase_two_shape() -> None:
    assert fold_owed(OwedSources(rows=[_item("row:a", "row")])) == (_item("row:a", "row"),)
