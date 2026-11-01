"""P2.T1: tracker bodies, markers and the printed pass command (spec gate-backfill §F)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.archive_followups import owned_owed_key
from fr.gatebackfill import trackers as t

from tests.unit.gatebackfill_fixtures import ME

KEY = "plan:2026-04-02-fleet#p3"


def test_tracker_body_ends_with_the_pr_marker_then_the_owed_marker_and_is_owned() -> None:
    body = t.tracker_body(KEY, "fleet: phase 3", "devops", 41)
    lines = body.splitlines()
    assert lines[-2] == "<!-- fr-gate:devops pr:41 -->"
    assert lines[-1] == f"<!-- fr-owed:{KEY} -->"
    issue = {"number": 5, "body": body, "labels": ["fr:owed"], "author": {"login": ME}}
    assert owned_owed_key(issue, ME) == KEY


def test_fr_gate_marker_reads_only_an_exact_second_to_last_line() -> None:
    body = t.tracker_body(KEY, "x", "tester", 7)
    assert t.fr_gate_marker(body) == ("tester", 7)
    assert t.fr_gate_marker(body + "\n") == ("tester", 7)
    assert t.fr_gate_marker("a\n<!-- fr-gate:tester pr:7 -->\nb\nc") is None
    assert t.fr_gate_marker("a\n<!-- fr-gate:tester pr:7 x -->\n<!-- fr-owed:k -->") is None
    assert t.fr_gate_marker("<!-- fr-owed:k -->") is None


def test_the_pass_command_carries_notes_and_devops_names_a_run_or_the_escape() -> None:
    assert '--notes "' in t.pass_command("tester", 3)
    assert "--run" not in t.pass_command("tester", 3)
    assert t.pass_command("devops", 3).endswith("--no-run-evidence")
    assert t.pass_command("devops", 3, run_id="r-1").endswith("--run r-1")


def test_the_adopt_and_link_comments_end_with_their_markers() -> None:
    adopt = t.adopt_comment(KEY, "devops", 41)
    assert adopt.splitlines()[-1] == f"<!-- fr-gate-adopt:{KEY} gate:devops pr:41 -->"
    assert t.fr_adopt_marker(adopt) == (KEY, "devops", 41)
    assert t.fr_adopt_marker("nothing") is None
    link = t.link_comment(KEY, "example-org/widgets#9")
    assert link.splitlines()[-1] == f"<!-- fr-gate-link:{KEY} tracker:example-org/widgets#9 -->"


def test_run_for_head_is_none_without_a_cursor(tmp_path: Path) -> None:
    assert t.run_for_head(tmp_path, "feat/x") is None
    assert t.run_for_head(tmp_path, "") is None


@pytest.mark.parametrize("gate", ["tester", "devops"])
def test_body_names_the_delivering_pr(gate: str) -> None:
    assert f"Delivered by #12 (merged). Held by gate:{gate}" in t.tracker_body(KEY, "x", gate, 12)


# --- p2-r1: the key's own discharge command ---------------------------------------------------


def test_discharge_command_per_key_kind(tmp_path: Path) -> None:
    from fr.journal.model import JournalEntry, append_journal_entry, journal_path, owed_body

    from tests.unit.test_merge_evidence import _write_plan

    assert t.discharge_command("row:ops-walk", repo_root=tmp_path).startswith(
        "fr acceptance set-status --id ops-walk --status walked --walk "
    )
    spec = tmp_path / "docs/superpowers/specs" / "2026-10-20-widget-design.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("# Widget\n")
    out = t.discharge_command("spec:2026-10-20-widget#step4", repo_root=tmp_path)
    assert "fr closeout outcome --spec" in out and "--step 4 --ran" in out
    assert out.endswith("--supersede") and "--evidence" in out
    _write_plan(tmp_path, "2026-10-20-ops", [("manual", False)])
    plan = t.discharge_command("plan:2026-10-20-ops#p1", repo_root=tmp_path)
    assert plan.startswith("fr plan edit docs/superpowers/plans/2026-10-20-ops --tick P1.")
    assert t.discharge_command("issue:example-org/widgets#9", repo_root=tmp_path) == (
        "close example-org/widgets#9 by hand"
    )
    key = "row:ops-journal"
    entry = JournalEntry(
        kind="owed", scope="spec", id="owed-1", created="2026-10-11T10:00:00+00:00",
        title="owed", body=owed_body(what="w", why="y", how="h", key=key),
    )  # fmt: skip
    append_journal_entry(journal_path(tmp_path, "spec", "some-slug"), "some-slug", entry)
    got = t.discharge_command(key, repo_root=tmp_path)
    assert got.startswith("fr journal resolve --scope spec --slug some-slug --id owed-1 --state fixed")
