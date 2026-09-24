"""Corpus harness for the agentic dispatch-verb lint (spec §2.D, §4.A).

The corpus is THIS REPO's real plan folders — `docs/superpowers/plans/`
plus `docs/superpowers/implemented/plans/` — read as captured evidence,
never constructed. A hand-written plan fixture would measure nothing: the
whole precision claim of the lint is that it scores zero hits on the way
super-fr actually writes steps about dispatch.

Phase 1 is the harness only; the detector itself lands in phase 2, which
consumes `corpus_plans()` and runs the REAL `fr.plan_ops.self_review`
over it — never a re-implementation of the gate's exemptions.
"""

from __future__ import annotations

import functools
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

from fr.parser import Plan, PlanSchemaError, parse

REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_PLANS = REPO_ROOT / "docs" / "superpowers" / "plans"
ARCHIVED_PLANS = REPO_ROOT / "docs" / "superpowers" / "implemented" / "plans"
CORPUS_ROOTS = (LIVE_PLANS, ARCHIVED_PLANS)

# Floors, per root and in aggregate. Today's corpus is 82 plans / 2113
# agentic steps (5 / 134 live, 77 / 1979 archived), so each floor keeps
# real headroom — see `test_the_corpus_was_actually_read`.
MIN_PLANS_PER_ROOT = 3
MIN_PLANS = 70
MIN_AGENTIC_STEPS = 1800


class Census(NamedTuple):
    """What the corpus reader actually managed to read."""

    plans_parsed: int
    plans_skipped: int
    agentic_steps: int


class CorpusStep(NamedTuple):
    """One agentic step, with the tick state the real gate exempts on."""

    plan_slug: str
    step_id: str
    state: str
    text: str


@functools.lru_cache(maxsize=1)
def _parse_corpus() -> tuple[tuple[Plan, ...], int]:
    """Every plan folder on disk, plus the count that could not be read.

    `enforce_fr_version=False` is deliberate and is what makes this a
    corpus rather than a sample. The version gate exists to stop an
    incompatible `fr` from EXECUTING a plan; `fr.parser.parse`'s own
    docstring says it "must never apply to a purely historical read", and
    `fr.spec.compute_status` already passes False for that reason. A
    precision measurement is exactly such a read. Enforcing it would drop
    38 archived plans whose `fr_version` ceiling a 4.x `fr` can never
    satisfy — 82 plans become 44, 2113 agentic steps become 1444 — and
    would couple these floors to the next major bump, on which 14 more
    plans would fall out and land the aggregate on exactly the floor.

    The 3 residual skips are genuine `PhaseDoc` validation failures in
    frozen archives. Nothing here rewrites a plan; the corpus is
    read-only (`.claude/rules/artifact-versioning.md`: archived artifacts
    are never migrated).
    """
    plans: list[Plan] = []
    skipped = 0
    for root in CORPUS_ROOTS:
        for entry in sorted(root.iterdir()):
            if not entry.is_dir():
                continue
            try:
                plans.append(parse(entry, enforce_fr_version=False))
            except PlanSchemaError:
                skipped += 1
    return tuple(plans), skipped


def corpus_plans() -> tuple[Plan, ...]:
    """The parsed corpus — phase 2's feed.

    Phase 2 runs `fr.plan_ops.self_review` over THESE, not over raw step
    text, so the gate's own agentic-only and `state == "x"` exemptions
    apply exactly as they do in production. A test that re-implemented
    them would be free to drift from the shipped gate, and a corpus test
    whose exemptions drift is measuring a lint nobody runs.
    """
    plans, _ = _parse_corpus()
    return plans


def _agentic_steps_of(plan: Plan) -> Iterator[CorpusStep]:
    for phase in plan.phases:
        if phase.phase.tag != "agentic":
            continue
        for task in phase.tasks:
            for step in task.steps:
                state = phase.state.steps.get(step.id)
                yield CorpusStep(
                    plan_slug=plan.dir.name,
                    step_id=step.id,
                    state=state.state if state is not None else " ",
                    text=step.text,
                )


def agentic_steps() -> Iterator[CorpusStep]:
    """Every agentic-phase step in the corpus, tick state included.

    The raw §2.D measurement is expressible from here; the gate-accurate
    one is `corpus_plans()` + `self_review`. Callers that care about what
    the shipped lint would flag must honour `state == "x"` themselves.
    """
    for plan in corpus_plans():
        yield from _agentic_steps_of(plan)


def corpus_census() -> Census:
    plans, skipped = _parse_corpus()
    return Census(
        plans_parsed=len(plans),
        plans_skipped=skipped,
        # `plans_skipped` is carried, not asserted: it is what makes an
        # unexpected mass-skip legible in the floor test's failure output.
        agentic_steps=sum(1 for plan in plans for _ in _agentic_steps_of(plan)),
    )


def test_agentic_steps_yields_slug_id_state_and_text():
    steps = list(agentic_steps())
    assert steps, "no agentic steps found in the corpus"
    for step in steps:
        assert step.plan_slug
        assert step.step_id
        assert step.state in {" ", "x", "-"}
        # `.strip()`, not `isinstance(..., str)`: a step whose text
        # vanished is a corpus defect that a type check waves through.
        assert step.text.strip()


def test_every_corpus_root_contributes():
    """Aggregate floors do not defend the roots individually.

    Live plans are 5 of 82 — rename or typo that root and the aggregate
    is still 77 plans / 1979 steps, comfortably over every floor, while
    the plans authors are writing RIGHT NOW (exactly where the gate is
    meant to bite) are never read at all.

    The floor is `min(MIN_PLANS_PER_ROOT, plan dirs actually present)`, not a
    flat 3: the live root shrinks each time a plan is archived, and it is
    legitimately near-empty whenever little is in flight. A renamed or typo'd
    root still fails (`is_dir`), and every plan the root does hold must still
    be read.
    """
    for root in CORPUS_ROOTS:
        assert root.is_dir(), f"corpus root missing: {root}"
        present = sum(1 for d in root.iterdir() if (d / "_meta.yaml").is_file())
        parsed = [p for p in corpus_plans() if root in p.dir.parents]
        floor = min(MIN_PLANS_PER_ROOT, present)
        assert len(parsed) >= floor, f"{root}: only {len(parsed)} of {present} plans read"


def test_the_corpus_was_actually_read():
    """Floors, because a skipping reader degrades silently into reading nothing.

    "Skip the unreadable, assert zero hits on the rest" passes just as
    green on a corpus of zero plans as on one of 82 — so the day a schema
    change makes every plan unparseable, the lint's precision claim would
    still report success while checking nothing. This repo's recurring
    defect is exactly that: a check that reports success while doing
    nothing. Precedent for the shape:
    `tests/unit/test_plan_folder_corpus.py::test_manifest_covers_the_corpus_exactly`,
    which exists so a fixture cannot silently drop out of its contract.
    """
    census = corpus_census()
    assert census.plans_parsed >= MIN_PLANS, census
    assert census.agentic_steps >= MIN_AGENTIC_STEPS, census
    assert len(list(agentic_steps())) == census.agentic_steps, census


# ---------------------------------------------------------------------------
# The precision claim, pinned (spec §4.A, §2.D)

DISPATCH_GATE_TOKEN = "#428"
"""The stable marker every dispatch-gate issue carries in its message.

Filtering on the message is the whole point: it runs the SHIPPED
`self_review`, so the gate's agentic-only and `state == "x"` exemptions
apply exactly as they do in production and cannot drift. Re-applying the
regexes to raw step text would re-implement those exemptions inside the
test — and 1827 of the corpus's 2113 agentic steps are ticked, so the
re-implementation would decide 86% of the corpus on its own.
"""


def dispatch_gate_hits() -> list[tuple[str, str]]:
    """(plan slug, message) for every dispatch-gate issue in the corpus."""
    from fr.plan_ops import self_review

    return [
        (plan.dir.name, issue.message)
        for plan in corpus_plans()
        for issue in self_review(plan)
        if DISPATCH_GATE_TOKEN in issue.message
    ]


def test_the_dispatch_gate_scores_zero_on_this_repos_own_plans():
    """Zero VERDICTS over every plan folder this repo has ever written.

    super-fr is a repo ABOUT dispatch — "GREEN: implement
    `fr_dispatch.tick()`", "assert `fr apply --yes` refuses to dispatch an
    unreachable plan". #428's literal `\\bdispatch\\b` scores 292 hits here
    and every one is a false positive (spec §2.D measured 237 on the
    smaller enforcing read); at error severity that gate would be switched
    off within a week of shipping. So the precision claim is PINNED, not
    asserted: any future widening of the patterns that would break
    super-fr's own plans fails here, in CI, instead of in an operator's
    run.

    This is the GATE-ACCURATE half, and on its own it is not enough. It
    sees only what the shipped gate sees, and the gate exempts ticked
    steps — 1835 of the corpus's 2113. A frameless `subagent_type[:=]`
    arm in the first cut of §4.A hit a real live plan
    (`2026-09-19-opencode-subagent-dispatch` P4.T1.S2) and this test
    stayed green, because that step is ticked. The pattern-level half
    below closes that hole; read the two together, plus
    `test_the_corpus_was_actually_read`, which is why "no hits" cannot
    pass green on a corpus of zero plans.
    """
    hits = dispatch_gate_hits()
    # The message names the plan, the step and the MATCHED TEXT, so a
    # widening is diagnosable from the CI log alone — nobody should have
    # to re-run the detector locally to find out what fired.
    assert not hits, "dispatch gate fired on the corpus:\n" + "\n".join(
        f"  {slug}: {' '.join(message.split())}" for slug, message in hits
    )


def pattern_hits() -> list[tuple[str, str, str, str]]:
    """(slug, step id, state, matched text) for every raw pattern hit.

    Deliberately applies NO exemptions — not the agentic-only one, not
    the ticked one. That is the opposite of re-implementing the gate's
    exemptions inside a test (which is what `corpus_plans()` exists to
    avoid): there is nothing here to drift from, because this half is
    measuring the PATTERNS, not the gate.
    """
    from fr.plan_ops import _DISPATCH_RES, _strip_fenced_code

    out = []
    for step in agentic_steps():
        scanned = _strip_fenced_code(step.text)
        for pattern in _DISPATCH_RES:
            m = pattern.search(scanned)
            if m is not None:
                out.append((step.plan_slug, step.step_id, step.state, " ".join(m.group(0).split())))
                break
    return out


def test_the_patterns_score_zero_on_every_corpus_step_ticked_or_not():
    """The precision claim, measured where the gate cannot see.

    A ticked step is exempt from the VERDICT for a good reason — it
    already ran — but it is still evidence about the PATTERNS, and 87% of
    the corpus is ticked. Measuring only the pending 278 is how a
    frameless `subagent_type[:=]` arm shipped a hit on a real live plan
    while every test stayed green. Worse, the exemption is temporal: the
    same plan, authored a week earlier, would have been unticked and the
    gate would have errored on it at authoring time, which is exactly
    when this gate is supposed to be usable.

    So: zero hits over all 2113 agentic steps, ticked and pending alike.
    """
    hits = pattern_hits()
    assert not hits, "dispatch patterns fired on the corpus:\n" + "\n".join(
        f"  {slug} {step_id} (state {state!r}): {matched!r}"
        for slug, step_id, state, matched in hits
    )
