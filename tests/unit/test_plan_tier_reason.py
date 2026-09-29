"""`fr plan self-review` wants a recorded reason for a tier above `standard`
(super-fr#813).

take 10 (#817): both one-phase plans declared `tier: hard` with nothing to say
why, which sent run A's executor to the most expensive model. `standard` is the
default; `hard` is a claim, and a claim is recorded where the plan's other
decisions are — the spec journal, as `tier-<plan>-p<N>`, the same shape as
`phase-split-<plan>-p<N>`.

Every repo is a `tmp_path` sandbox; nothing here touches the checkout.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from fr.journal.model import JournalEntry, append_journal_entry, journal_path
from fr.parser import Plan
from fr.parser import parse as parse_plan
from fr.plan_ops import PhaseSpec, ReviewIssue, _tier_issues, create
from fr.version_floor import CEILING_VERSION

from tests.unit.test_plan_phase_sizing import PLAN, SPEC_REL, SPEC_SLUG, _repo


def _plan(repo: Path, *tiers: str) -> Plan:
    specs = [
        PhaseSpec(
            number=i,
            title=f"Phase {i}",
            tag="agentic",
            tier=tier,  # type: ignore[arg-type]
            files=("x/**",),
            tasks=({"number": 1, "title": "t", "steps": [{"id": f"P{i}.T1.S1", "text": "do"}]},),
        )
        for i, tier in enumerate(tiers, start=1)
    ]
    plan = create(
        repo_root=repo,
        slug=PLAN,
        spec=SPEC_REL,
        target_repo="derio-net/own",
        fr_version=f">=4.20.0,<{CEILING_VERSION}",
        phases=specs,
        prose="# toy\n",
    )
    return parse_plan(plan.dir)


def _decide(repo: Path, entry_id: str, title: str) -> None:
    path = journal_path(repo, "spec", SPEC_SLUG)
    path.parent.mkdir(parents=True, exist_ok=True)
    append_journal_entry(
        path,
        SPEC_SLUG,
        JournalEntry(
            kind="decision",
            scope="spec",
            id=entry_id,
            created="2026-09-29T00:00:00+00:00",
            title=title,
        ),
    )


def _reason_errors(issues: list[ReviewIssue]) -> list[str]:
    return [i.message for i in issues if i.severity == "error" and "tier" in i.message]


def test_hard_without_a_recorded_reason_is_an_error_naming_the_fix(tmp_path: Path) -> None:
    plan = _plan(_repo(tmp_path), "hard")

    errors = _reason_errors(_tier_issues(plan))

    assert len(errors) == 1, errors
    assert "phase 1" in errors[0]
    assert "standard is the default" in errors[0]
    assert (
        f"fr journal add --scope spec --slug {SPEC_SLUG} --kind decision --id tier-{PLAN}-p1"
        in errors[0]
    )


@pytest.mark.parametrize("tier", ["standard", "mechanical"])
def test_standard_and_below_need_no_reason(tmp_path: Path, tier: str) -> None:
    assert _reason_errors(_tier_issues(_plan(_repo(tmp_path), tier))) == []


def test_a_tier_decision_clears_it(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _decide(repo, f"tier-{PLAN}-p1", "cross-cutting: touches the gate and every caller")
    assert _reason_errors(_tier_issues(_plan(repo, "hard"))) == []


def test_a_superseding_tier_decision_counts(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _decide(repo, f"tier-{PLAN}-p1-2", "ambiguous design: two readings of the spec")
    assert _reason_errors(_tier_issues(_plan(repo, "hard"))) == []


def test_a_tier_split_decision_for_the_phase_is_its_reason(tmp_path: Path) -> None:
    """A phase split off BECAUSE it needs another tier already says why."""
    repo = _repo(tmp_path)
    _decide(repo, f"phase-split-{PLAN}-p2", "tier: the migration needs hard")
    assert _reason_errors(_tier_issues(_plan(repo, "standard", "hard"))) == []


def test_a_decision_for_another_phase_does_not_clear_it(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _decide(repo, f"tier-{PLAN}-p1", "cross-cutting")
    errors = _reason_errors(_tier_issues(_plan(repo, "hard", "hard")))
    assert len(errors) == 1 and "phase 2" in errors[0], errors


def test_with_no_spec_journal_to_record_in_it_warns_rather_than_errs(tmp_path: Path) -> None:
    """A cross-repo spec's journal lives in its own repo, so there is nowhere
    here to record the reason: an error would be unclearable short of lowering
    the tier. Say it, as a warning (review of #834)."""
    plan = _plan(_repo(tmp_path), "hard")
    cross = "derio-net/elsewhere:docs/superpowers/specs/2026-09-28-toy-design.md"
    plan = replace(plan, meta=plan.meta.model_copy(update={"spec": cross}))

    issues = [i for i in _tier_issues(plan) if "tier: hard" in i.message]

    assert [i.severity for i in issues] == ["warn"], issues
    assert "no same-repo spec journal" in issues[0].message


def test_an_empty_titled_tier_decision_is_no_reason(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _decide(repo, f"tier-{PLAN}-p1", "   ")
    assert len(_reason_errors(_tier_issues(_plan(repo, "hard")))) == 1
