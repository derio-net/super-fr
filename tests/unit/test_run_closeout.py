"""`fr.run.closeout.closeout_brief` — spec 2026-09-25-fr-goal-closeout-defects
§3.D.1.

A pure function: everything it prints is derived from the `RunState` handed
to it and the artifacts (spec, plan, journals) that state names — nothing
else, since it is read by a brand-new session that inherits none of the
delivering session's context.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.journal.model import JournalEntry, append_journal_entry, journal_path
from fr.run.closeout import CloseoutNotReadyError, closeout_brief
from fr.run.model import RunState, StepRecord
from fr.test_support import build_plan_journal

SPEC_SLUG = "2026-09-30-fixture"
SPEC_REL = f"docs/superpowers/specs/{SPEC_SLUG}-design.md"
PLAN_REL = f"docs/superpowers/plans/{SPEC_SLUG}"
PR_URL = "https://github.com/derio-net/super-fr/pull/1"
BRANCH = "feat/x"


def _spec_file(repo_root: Path, *, with_test_plan: bool) -> None:
    path = repo_root / SPEC_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "# Fixture\n\n## Background\n\ntext\n"
    if with_test_plan:
        body += "\n## Test Plan\n\n1. do the thing.\n"
    path.write_text(body)


def _plan_dir(repo_root: Path) -> None:
    (repo_root / PLAN_REL).mkdir(parents=True, exist_ok=True)


def _state(*, deliver_done: bool = True) -> RunState:
    return RunState(
        run="r1",
        workflow="fr-goal@1",
        branch=BRANCH,
        started="2026-09-30T00:00:00Z",
        cursor="deliver",
        steps={
            "brainstorm": StepRecord(state="done", emitted={"spec": SPEC_REL}),
            "plan": StepRecord(state="done", emitted={"plan": PLAN_REL}),
            "deliver": StepRecord(
                state="done" if deliver_done else "running", emitted={"pr": PR_URL}
            ),
        },
    )


def _spec_out_of_scope_finding(repo_root: Path) -> None:
    """A finding raised against the spec journal, resolved out-of-scope."""
    path = journal_path(repo_root, "spec", SPEC_SLUG)
    append_journal_entry(
        path,
        SPEC_SLUG,
        JournalEntry(
            kind="finding",
            scope="spec",
            id="sf1",
            created="2026-09-30T00:00:00",
            state="open",
            title="a spec-scope finding",
        ),
    )
    append_journal_entry(
        path,
        SPEC_SLUG,
        JournalEntry(
            kind="finding",
            scope="spec",
            id="sf1-resolved",
            created="2026-09-30T00:00:01",
            state="open",
            resolves="sf1",
            out_of_scope=True,
            title="resolves sf1: a spec-scope finding",
        ),
    )


def _plan_out_of_scope_finding(repo_root: Path) -> None:
    build_plan_journal(
        repo_root,
        SPEC_SLUG,
        [
            {"kind": "finding", "id": "pf1", "state": "open", "title": "a plan-scope finding"},
            {
                "kind": "finding",
                "id": "pf1-resolved",
                "resolves": "pf1",
                "state": "open",
                "out_of_scope": True,
                "title": "resolves pf1: a plan-scope finding",
            },
        ],
    )


def test_closeout_brief_orders_every_section_correctly(tmp_path: Path) -> None:
    _spec_file(tmp_path, with_test_plan=True)
    _plan_dir(tmp_path)
    _spec_out_of_scope_finding(tmp_path)
    _plan_out_of_scope_finding(tmp_path)

    brief = closeout_brief(tmp_path, _state())

    def idx(needle: str) -> int:
        pos = brief.find(needle)
        assert pos != -1, f"{needle!r} missing from:\n{brief}"
        return pos

    i_branch = idx(BRANCH)
    i_pr = idx(PR_URL)
    i_spec = idx(SPEC_REL)
    i_plan = idx(PLAN_REL)
    i_verify = idx(f"fr isolation verify-merge --branch {BRANCH}")
    i_stop = idx("STOP")
    i_test_plan = idx(f"Test Plan: {SPEC_REL}")
    i_spec_finding = idx(
        f"fr journal resolve --scope spec --slug {SPEC_SLUG} --id sf1 "
        "--state deferred --tracked-by <#N>"
    )
    i_plan_finding = idx(
        f"fr journal resolve --scope plan --slug {SPEC_SLUG} --id pf1 "
        "--state deferred --tracked-by <#N>"
    )
    i_status = idx("fr status")
    i_archive = idx(f"fr archive {PLAN_REL}")
    i_housekeeping_pr = idx("housekeeping PR")
    i_down = idx(f"fr isolation down --branch {BRANCH}")

    assert (
        i_branch
        < i_pr
        < i_spec
        < i_plan
        < i_verify
        < i_stop
        < i_test_plan
        < i_spec_finding
        < i_plan_finding
        < i_status
        < i_archive
        < i_housekeeping_pr
        < i_down
    )


def test_closeout_brief_omits_test_plan_line_when_the_spec_has_none(tmp_path: Path) -> None:
    _spec_file(tmp_path, with_test_plan=False)
    _plan_dir(tmp_path)

    brief = closeout_brief(tmp_path, _state())

    assert "Test Plan" not in brief


def test_closeout_brief_refuses_a_run_whose_deliver_is_not_done(tmp_path: Path) -> None:
    _spec_file(tmp_path, with_test_plan=False)
    _plan_dir(tmp_path)

    with pytest.raises(CloseoutNotReadyError, match="deliver"):
        closeout_brief(tmp_path, _state(deliver_done=False))
