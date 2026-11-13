"""The `lens-review` evidence gate at resolve (spec 2026-11-12-review-lenses R9-R11,
§3.C): the feature-level evidence target, the reviewer map, each lens reviewer's
return, and the derived `lenses` witness.

The OpenCode run-tree fixture is moved into the step's window: `ses_gen1` and
`ses_gen2` (both `general`) are the two reviewers, their returns rewritten per test.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.run.model import load_run_state

from tests.unit.lens_review_support import (
    RESOLVE,
    at_lens_review,
    finding,
    lens,
    lens_evidence,
    plan_journal,
    review_lens_return,
)
from tests.unit.opencode_fixture import opencode_env
from tests.unit.test_run_cli import _invoke_as_harness, _squash
from tests.unit.test_run_review_return_resolve import _review_window

BOTH = ("security", "tests")
GOOD = {
    "ses_gen1": review_lens_return(
        "security", ("src/app.py", "src/auth/token.py"), "l-security-r1 | in | a shell string"
    ),
    "ses_gen2": review_lens_return("tests", ("src/app.py",)),
}
REVIEW = {"kind": "review", "id": "lens-rev", "title": "lens review"}


def _resolve(repo: Path, shipped: Path, env: dict[str, str | None], *evidence: str):
    argv = [*RESOLVE, "--state", "done"]
    for pair in evidence:
        argv += ["--evidence", pair]
    return _invoke_as_harness(repo, shipped, argv, env)


def _ready(tmp_path: Path, returns: dict[str, str] | None = None, lenses=BOTH):
    repo, shipped, opened = at_lens_review(tmp_path, lenses=lenses)
    plan_journal(repo, REVIEW, *finding("l-security-r1", "in"))
    db = _review_window(tmp_path, opened, {**GOOD, **(returns or {})})
    return repo, shipped, opencode_env(db)


def _not_done(repo: Path) -> None:
    record = load_run_state(repo, "r1").steps["lens-review"]
    assert record.state == "running"
    assert "lenses" not in lens_evidence(repo)


MAP = "reviewer=security=ses_gen1,tests=ses_gen2"


# --- (a) the empty set ---------------------------------------------------------


def test_an_empty_set_resolves_with_no_review_and_no_reviewer(tmp_path: Path) -> None:
    repo, shipped, _ = at_lens_review(tmp_path)

    result = _resolve(repo, shipped, {"FR_HARNESS": None})

    assert result.exit_code == 0, result.output
    assert lens_evidence(repo)["lenses"] == "none"
    assert "review" not in lens_evidence(repo)


def test_lenses_is_never_the_callers_to_pass(tmp_path: Path) -> None:
    repo, shipped, _ = at_lens_review(tmp_path)

    result = _resolve(repo, shipped, {"FR_HARNESS": None}, "lenses=none")

    assert result.exit_code == 2, result.output
    assert "not yours to pass" in _squash(result.output)
    _not_done(repo)


# --- (b) a set of two ------------------------------------------------------------


def test_complete_returns_resolve_and_record_the_witness(tmp_path: Path) -> None:
    repo, shipped, env = _ready(tmp_path)

    result = _resolve(repo, shipped, env, "review=lens-rev", MAP)

    assert result.exit_code == 0, result.output
    evidence = lens_evidence(repo)
    assert evidence["lenses"] == "security=2:l-security-r1;tests=1:none"
    assert evidence["findings"] == "l-security-r1"
    assert "unobserved" not in evidence


def test_a_lens_with_no_reviewer_is_refused_with_its_brief(tmp_path: Path) -> None:
    from fr.lenses.resolve import effective_lenses

    repo, shipped, env = _ready(tmp_path)

    result = _resolve(repo, shipped, env, "review=lens-rev", "reviewer=security=ses_gen1")

    assert result.exit_code == 2, result.output
    out = _squash(result.output)
    assert "tests" in out and "no reviewer" in out
    assert _squash(effective_lenses(repo)["tests"].brief)[:60] in out
    assert "l-tests-r<k>" in out
    _not_done(repo)


def test_a_rule_lens_with_no_reviewer_names_its_rule_and_file(tmp_path: Path) -> None:
    config = "require:\n  - paths: [src/auth/**]\n    lenses: [security]\n"
    repo, shipped, opened = at_lens_review(tmp_path, config=config)
    plan_journal(repo, REVIEW)
    env = opencode_env(_review_window(tmp_path, opened, GOOD))

    result = _resolve(repo, shipped, env, "review=lens-rev", "reviewer=tests=ses_gen2")

    assert result.exit_code == 2, result.output
    out = _squash(result.output)
    assert "security" in out and "src/auth/**" in out and "src/auth/token.py" in out
    _not_done(repo)


@pytest.mark.parametrize(
    ("reviewer", "says"),
    [
        ("reviewer=security=ses_gen1,tests=ses_gen1", "named for two lenses"),
        ("reviewer=security=ses_gen1,tests=ses_nope", "ses_nope names no subagent"),
        ("reviewer=security=ses_gen1,tests=ses_gen2,errors=ses_gen2", "not in this feature"),
        ("reviewer=ses_gen1", "<lens>=<dispatch-id>"),
    ],
)
def test_a_bad_reviewer_map_is_refused(tmp_path: Path, reviewer: str, says: str) -> None:
    repo, shipped, env = _ready(tmp_path)

    result = _resolve(repo, shipped, env, "review=lens-rev", reviewer)

    assert result.exit_code == 2, result.output
    assert says in _squash(result.output)
    _not_done(repo)


@pytest.mark.parametrize(
    ("tests_return", "says"),
    [
        ("I read it all and it is fine.", "no review-lens block"),
        (review_lens_return("security", ("src/app.py",)), "names lens security"),
        (review_lens_return("tests", ("seed.md",)), "seed.md"),
        ("```review-lens\nlens: tests\nexamined: src/app.py\n```\n", "no review-findings block"),
        (review_lens_return("tests", ("src/app.py",), "l-tests-r1 | in | x"), "l-tests-r1"),
        (review_lens_return("tests", ("src/app.py",), "l-security-r2 | in | x"), "l-security-r2"),
    ],
)
def test_a_return_that_does_not_match_is_refused(
    tmp_path: Path, tests_return: str, says: str
) -> None:
    repo, shipped, env = _ready(tmp_path, {"ses_gen2": tests_return})

    result = _resolve(repo, shipped, env, "review=lens-rev", MAP)

    assert result.exit_code == 2, result.output
    out = _squash(result.output)
    assert says in out
    assert "tests" in out
    _not_done(repo)


def test_a_returned_finding_journaled_with_another_scope_is_refused(tmp_path: Path) -> None:
    repo, shipped, opened = at_lens_review(tmp_path, lenses=BOTH)
    plan_journal(repo, REVIEW, *finding("l-security-r1", "out"))
    env = opencode_env(_review_window(tmp_path, opened, GOOD))

    result = _resolve(repo, shipped, env, "review=lens-rev", MAP)

    assert result.exit_code == 2, result.output
    out = _squash(result.output)
    assert "l-security-r1" in out and "review_scope" in out
    _not_done(repo)


def test_an_open_lens_finding_is_refused(tmp_path: Path) -> None:
    repo, shipped, opened = at_lens_review(tmp_path, lenses=BOTH)
    plan_journal(repo, REVIEW, finding("l-security-r1", "in")[0])
    env = opencode_env(_review_window(tmp_path, opened, GOOD))

    result = _resolve(repo, shipped, env, "review=lens-rev", MAP)

    assert result.exit_code == 2, result.output
    assert "l-security-r1" in _squash(result.output)
    _not_done(repo)


def test_a_review_entry_with_a_phase_is_not_the_features(tmp_path: Path) -> None:
    repo, shipped, env = _ready(tmp_path)
    plan_journal(repo, {"kind": "review", "id": "rev-p1", "phase": 1, "title": "phase 1"})

    result = _resolve(repo, shipped, env, "review=rev-p1", MAP)

    assert result.exit_code == 2, result.output
    assert "rev-p1" in _squash(result.output)
    _not_done(repo)


# --- (c) the set is computed at resolve -------------------------------------------


def test_a_lens_added_after_the_brief_is_owed(tmp_path: Path) -> None:
    repo, shipped, env = _ready(tmp_path, lenses=("security",))
    plan_journal(repo, lens("tests"))

    result = _resolve(repo, shipped, env, "review=lens-rev", "reviewer=security=ses_gen1")

    assert result.exit_code == 2, result.output
    assert "tests" in _squash(result.output)
    _not_done(repo)


# --- (d) unreadable returns -------------------------------------------------------


def test_unreadable_returns_are_noted_and_the_map_still_checked(tmp_path: Path) -> None:
    repo, shipped, opened = at_lens_review(tmp_path, lenses=BOTH)
    plan_journal(repo, REVIEW, *finding("l-security-r1", "in"))
    env = opencode_env(_review_window(tmp_path, opened, GOOD), session=None)

    short = _resolve(repo, shipped, env, "review=lens-rev", "reviewer=security=ses_gen1")
    assert short.exit_code == 2, short.output
    assert "tests" in _squash(short.output)

    result = _resolve(repo, shipped, env, "review=lens-rev", MAP)

    assert result.exit_code == 0, result.output
    evidence = lens_evidence(repo)
    assert evidence["lenses"] == "security=unobserved:l-security-r1;tests=unobserved:none"
    assert "reviewer-return" in evidence["unobserved"].split(",")


def test_unreadable_returns_still_refuse_an_open_lens_finding(tmp_path: Path) -> None:
    repo, shipped, opened = at_lens_review(tmp_path, lenses=BOTH)
    plan_journal(repo, REVIEW, finding("l-security-r1", "in")[0])
    env = opencode_env(_review_window(tmp_path, opened, GOOD), session=None)

    result = _resolve(repo, shipped, env, "review=lens-rev", MAP)

    assert result.exit_code == 2, result.output
    _not_done(repo)


# --- (e) other plan findings are not this gate's ----------------------------------


def test_a_plan_finding_that_is_not_a_lens_finding_does_not_gate(tmp_path: Path) -> None:
    repo, shipped, env = _ready(tmp_path)
    plan_journal(
        repo,
        {"kind": "finding", "id": "p1-r1", "phase": 1, "title": "x", "state": "open",
         "review_scope": "in"},
    )  # fmt: skip

    result = _resolve(repo, shipped, env, "review=lens-rev", MAP)

    assert result.exit_code == 0, result.output
    assert lens_evidence(repo)["findings"] == "l-security-r1"


# --- review p3-r1, p3-r4: what else must refuse ------------------------------------

DISABLED_RULE_LENS = "disable: [security]\nrequire:\n  - paths: [src/**]\n    lenses: [security]\n"


@pytest.mark.parametrize("evidence", ["findings", "review, reviewer, findings"])
def test_a_flat_plan_journal_step_without_lenses_is_not_a_feature_review(
    tmp_path: Path, evidence: str
) -> None:
    """Only the step declaring `lenses` is reviewed against the feature: any other
    flat step keeps the refusal it had, so open plan findings never pass it."""
    from tests.unit.lens_review_support import LENS_SHAPE

    shape = LENS_SHAPE.replace("[lenses, review, reviewer, findings]", f"[{evidence}]")
    repo, shipped, _ = at_lens_review(tmp_path, shape=shape)

    result = _resolve(repo, shipped, {"FR_HARNESS": None})

    assert result.exit_code == 2, result.output
    assert "names no phase" in _squash(result.output)
    assert load_run_state(repo, "r1").steps["lens-review"].state == "running"


@pytest.mark.parametrize("state", ["done", "failed"])
def test_a_lens_set_fr_cannot_compute_refuses_the_resolve(tmp_path: Path, state: str) -> None:
    from tests.unit.lens_review_support import commit_paths

    repo, shipped, env = _ready(tmp_path)
    commit_paths(repo, {".fr/lenses.yaml": DISABLED_RULE_LENS}, "a rule on a disabled lens")

    argv = [*RESOLVE, "--state", state, "--evidence", "review=lens-rev", "--evidence", MAP]
    result = _invoke_as_harness(repo, shipped, argv, env)

    assert result.exit_code == 2, result.output
    assert "security" in _squash(result.output)
    _not_done(repo)


def test_a_review_entry_older_than_the_step_is_refused(tmp_path: Path) -> None:
    from fr.journal.model import JournalEntry, append_journal_entry, journal_path

    from tests.unit.lens_review_support import PLAN

    repo, shipped, env = _ready(tmp_path)
    append_journal_entry(
        journal_path(repo, "plan", PLAN),
        PLAN,
        JournalEntry(
            kind="review", scope="plan", id="old-rev", title="an earlier review",
            created="2020-01-01T00:00:00+00:00",
        ),
    )  # fmt: skip

    result = _resolve(repo, shipped, env, "review=old-rev", MAP)

    assert result.exit_code == 2, result.output
    assert "old-rev" in _squash(result.output)
    _not_done(repo)


def test_a_named_reviewer_still_running_is_noted_unobserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A reviewer fr sees dispatched but whose return it cannot read yet: the
    block check is skipped for it, and the record says so."""
    from fr.commands import run_cmd
    from fr.run.observed import ChildDispatch

    repo, shipped, env = _ready(tmp_path)
    real = run_cmd._dispatches_since

    def _tests_reviewer_has_not_returned(since: str | None):
        found = real(since)
        assert found is not None
        return [
            ChildDispatch(d.agent_id, d.agent_type, d.started, None)
            if d.agent_id == "ses_gen2"
            else d
            for d in found
        ]

    monkeypatch.setattr(run_cmd, "_dispatches_since", _tests_reviewer_has_not_returned)

    result = _resolve(repo, shipped, env, "review=lens-rev", MAP)

    assert result.exit_code == 0, result.output
    evidence = lens_evidence(repo)
    assert evidence["lenses"] == "security=2:l-security-r1;tests=unobserved:none"
    assert "reviewer-return" in evidence["unobserved"].split(",")
