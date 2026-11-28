"""Who reviewed a unit, and whether the record matches what the reviewers returned (spec
2026-11-27-run-verdict R7).

Moved from `fr.commands.run_cmd` in slice 5: the `reviewer=historical` bound, the
separate-context reviewer check, and the reviewer-return check. Each refuses with
`RunRefusal`; a check that cannot observe notes its gate (`fr.run.unobserved`) and warns
through the caller's `warn`.

Engine code: no `typer`, no `rich` but `rich.markup`, no `fr.commands`
(`tests/unit/test_run_writes_layering.py`).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Literal, NoReturn

from rich.markup import escape

from fr.journal.model import JournalEntry
from fr.run import units
from fr.run.evidence import refusal
from fr.run.evidence.derived import derived_refusal_lines
from fr.run.evidence.target import EvidenceTarget
from fr.run.historical import HISTORICAL_REVIEWER
from fr.run.model import RunState
from fr.run.steps import emitted_plan
from fr.run.unobserved import note_unobserved, why_unobservable
from fr.run.verdict import RunRefusal, Say, Warn

if TYPE_CHECKING:
    from fr.run.observed import ChildDispatch


def refuse_unboundable_historical(
    key: str, target: EvidenceTarget, offered: Mapping[str, str]
) -> None:
    """`reviewer=historical` where no bound can apply — or return. A flat unit
    (spec-review) is refused: its review must postdate the step, and adoption
    never leaves it open. A phase unit must name the `review` entry the bound
    is checked against."""
    if target.phase is None:
        raise RunRefusal(
            refusal(
                f"[red]{key}: refused — reviewer={HISTORICAL_REVIEWER} is accepted only on a "
                "phase review unit; a spec review must be done by a reviewer dispatched after "
                "the step opened.[/red]"
            )
        )
    if "review" not in offered:
        raise RunRefusal(
            refusal(
                f"[red]{key}: refused — reviewer={HISTORICAL_REVIEWER} needs --evidence "
                "review=<entry-id>, the journal review it stands on.[/red]"
            )
        )


def verify_historical_bound(
    key: str,
    repo_root: Path,
    state: RunState,
    *,
    target: EvidenceTarget,
    entry_id: str,
    entries: list[JournalEntry],
) -> None:
    """The review entry `entry_id` meets spec §D's bound for `target`'s phase
    — or `RunRefusal` naming the clause it fails."""
    from fr.run.historical import historical_review_refusal
    from fr.run.visual import VisualRefusedError, owed_for_unit

    assert target.phase is not None
    entry = next(e for e in entries if e.id == entry_id)  # `verify_review_entry` found it
    try:
        owed = owed_for_unit(
            repo_root, plan_rel=emitted_plan(state), phase=target.phase, spec_rel=None
        )
    except VisualRefusedError as e:
        raise RunRefusal(derived_refusal_lines(key, e.lines)) from None
    attempt = units.last_attempt(state, key)
    why = historical_review_refusal(
        state,
        target.phase,
        entry,
        owes_visual=bool(owed),
        review_key=key,
        review_dispatched=attempt.dispatched if attempt is not None else None,
    )
    if why is not None:
        raise RunRefusal(
            refusal(f"[red]{key}: refused — reviewer={HISTORICAL_REVIEWER}: {escape(why)}.[/red]")
        )


def verify_reviewer(
    key: str,
    agent_id: str,
    state: RunState,
    *,
    target: EvidenceTarget,
    opened: str | None,
    expected_agent: str | None = None,
    warn: Warn,
) -> None:
    """`agent_id` is a SEPARATE context that reviewed this phase — or `RunRefusal`.

    2026-09-21 debug journal C6 (operator decision: separate-context review).
    The `review=<entry-id>` gate proved an entry EXISTS; on the #497 run the
    orchestrator typed that entry itself, reviewing nothing — #430 one layer
    down. So a review also names the subagent that did it, and fr checks two
    things: it is not the agent that IMPLEMENTED this phase (a context marking
    its own work), and — where the transcript is readable — this session really
    dispatched it after the review unit opened. Unobservable: warned, recorded
    as claimed, never silently.

    A spec review (`target.phase is None`, 2026-09-24 spec §E) has no
    implementer to exclude — the spec's author is the orchestrator, which has
    no agent id and so can never pass the dispatch check. Dispatches are read
    through `fr.run.observed` — Claude Code's transcript, OpenCode's child
    sessions (once the super-fr plugin exports the run session); on Hermes, or
    wherever the session cannot be read, the id is recorded as claimed.
    When the step names its reviewer (`expected_agent`, spec-review's
    `super-fr:fr-spec-reviewer`), an observed dispatch of any OTHER agent type
    is refused (review p4-f2) — every spelling `agent_name` folds matches.
    """
    # Imported here: `fr.run.brief` imports the lens checks, which import this module.
    from fr.run.brief import PHASE_EXECUTOR_AGENT

    phase = target.phase
    # The review unit's own holders are reviewers by construction: a reviewer
    # that claims the unit it reviews is not an implementer, and counting it
    # here would refuse the very reviewer the step dispatched.
    implementers = (
        {
            a.agent
            for record in state.steps.values()
            for unit_key in (record.units or {})
            if unit_key.startswith(f"phase/{phase}/") and unit_key != key
            for a in units.attempts(record, unit_key)
            if a.agent_type is not None and a.agent is not None
        }
        if phase is not None
        else set()
    )
    if agent_id in implementers:
        raise RunRefusal(
            refusal(
                f"[red]{key}: --evidence reviewer={agent_id} is the agent that IMPLEMENTED phase "
                f"{phase} — a review must come from a separate context, not the one whose work "
                "it judges. Dispatch a reviewer subagent and name its id.[/red]"
            )
        )
    # Through the session protocol (spec 2026-10-02-opencode-observe-2 §A):
    # the dispatch named by the id, among those since the review opened.
    dispatched = dispatches_since(opened)
    observed: ChildDispatch | Literal[False] | None = (
        None
        if dispatched is None
        else next((d for d in dispatched if d.agent_id == agent_id), False)
    )
    if observed and same_agent(observed.agent_type, PHASE_EXECUTOR_AGENT):
        # Review r1-11: a phase executor is an IMPLEMENTER by construction —
        # any phase's — so it is never the separate context a review needs.
        raise RunRefusal(
            refusal(
                f"[red]{key}: --evidence reviewer={agent_id} is a {PHASE_EXECUTOR_AGENT} "
                "dispatch — an implementer, not a reviewer. Dispatch a reviewer subagent.[/red]"
            )
        )
    if (
        observed
        and expected_agent is not None
        and not same_agent(observed.agent_type, expected_agent)
    ):
        raise RunRefusal(
            refusal(
                f"[red]{key}: --evidence reviewer={agent_id} is a {observed.agent_type!r} "
                f"dispatch — this step's reviewer is {expected_agent}. Dispatch that agent "
                "and name its id.[/red]"
            )
        )
    if observed is False:
        raise RunRefusal(
            refusal(
                f"[red]{key}: --evidence reviewer={agent_id} names no subagent this session "
                f"dispatched since the review opened at {opened}. The review must be done by "
                "a dispatched reviewer (a separate context), and named by the id its dispatch "
                "returned.[/red]"
            )
        )
    if observed is None:
        note_unobserved("reviewer")
        warn(
            Say(
                f"[yellow]{key}: could not verify reviewer {agent_id!r} — "
                f"{why_unobservable('subagent dispatches')}; recorded as claimed, unverified "
                "(evidence: unobserved=reviewer).[/yellow]",
                soft_wrap=True,
            )
        )


def same_agent(observed: str | None, expected: str) -> bool:
    """`observed` is `expected`, in any spelling `fr.run.observed.agent_name`
    folds: plugin-qualified or bare (`super-fr:fr-spec-reviewer` /
    `fr-spec-reviewer`), and OpenCode's tiered name (`fr-spec-reviewer-hard`)."""
    from fr.run.observed import agent_name

    if observed is None:
        return False
    return agent_name(observed) == agent_name(expected)


def check_returned_findings(
    key: str,
    entries: list[JournalEntry],
    phase: int,
    since: str | None,
    reviewer: str | None,
    *,
    warn: Warn,
) -> None:
    """Every finding a phase reviewer RETURNED is a plan-journal finding
    against `phase` with the reviewer's own scope tag — or `RunRefusal` (spec
    2026-10-02-opencode-observe-2 §E, R7).

    A child dispatched since the review opened is a reviewer of this unit when
    it is the one the record names (`reviewer`), or when its return carries a
    ```review-findings fence; each owes a well-formed block (`none` when it
    raised nothing). Any other child — a helper dispatched while receiving the
    review — owes nothing. The journal may hold MORE findings than the blocks
    (the orchestrator's own), never fewer. Where fr cannot read the session, or
    the named reviewer's return, the check is noted `unobserved=reviewer-return`
    and warned, never silently skipped."""
    from fr.run.review_return import ReviewFindingsBlockError, parse_review_findings

    dispatched = dispatches_since(since)
    if dispatched is None:
        return_unobserved(
            key, "the phase reviewers", why_unobservable("subagent returns"), warn=warn
        )
        return
    problems: list[str] = []
    returned: dict[str, tuple[str, str]] = {}  # id -> (scope, reviewer)
    for d in dispatched:
        named = reviewer is not None and d.agent_id == reviewer
        if d.returned is None:
            if named:
                return_unobserved(
                    key, f"reviewer {d.agent_id}", "its return is not readable yet", warn=warn
                )
            continue
        try:
            rows = parse_review_findings(d.returned)
        except ReviewFindingsBlockError as e:
            problems.append(f"{d.agent_id}: {e}")
            continue
        if rows is None:
            if named:
                problems.append(
                    f"reviewer {d.agent_id} returned no review-findings block — its return "
                    "must end with one (`none` when it raised nothing)"
                )
            continue
        for fid, scope, _summary in rows:
            if fid in returned:
                problems.append(
                    f"{fid} is returned by both {returned[fid][1]} and {d.agent_id} — "
                    "give each reviewer its own letter (p<N>a-r<k>, p<N>b-r<k>)"
                )
                continue
            returned[fid] = (scope, d.agent_id)
    # Phase N OR LATER (review p2-r3): the manifest files a finding that
    # belongs to a later phase against THAT phase, where it gates that review.
    journaled = {
        e.id: e
        for e in entries
        if e.kind == "finding" and e.resolves is None and e.phase is not None and e.phase >= phase
    }
    missing = [fid for fid in returned if fid not in journaled]
    if missing:
        problems.append(
            f"returned finding(s) not in the plan journal against phase {phase} or later: "
            + ", ".join(f"{fid} (reviewer {returned[fid][1]})" for fid in missing)
            + " — journal each under its id with the reviewer's tag "
            "(`fr journal add --kind finding --id <id> --review-scope in|out ...`)"
        )
    for fid, (scope, by) in returned.items():
        entry = journaled.get(fid)
        if entry is not None and entry.review_scope != scope:
            problems.append(
                f"{fid} is journaled with review_scope {entry.review_scope} but {by} "
                f"tagged it {scope} — keep the reviewer's tag; reclassify by resolving it "
                "out-of-scope"
            )
    if problems:
        return_refusal(
            key,
            problems,
            "Journal every returned finding under its id with the reviewer's tag, or "
            "re-dispatch a reviewer whose return is malformed; never edit a return.",
        )


def dispatches_since(since: str | None) -> list[ChildDispatch] | None:
    """The subagents this session dispatched since `since`, or None where fr cannot
    read the session. The one dispatch walk the reviewer check and both
    reviewer-return checks read."""
    from fr.run.observed import observed_session
    from fr.run.telemetry import parse_timestamp

    start = parse_timestamp(since) if since is not None else None
    view = observed_session(os.environ) if start is not None else None
    return view.dispatches(start) if view is not None and start is not None else None


def return_unobserved(key: str, who: str, why: str, *, warn: Warn) -> None:
    """A reviewer-return check skipped: warned and noted, never silent (§E)."""
    note_unobserved("reviewer-return")
    warn(
        Say(
            f"[yellow]{key}: could not read what {who} returned — {why}; the record is "
            "taken as claimed (evidence: unobserved=reviewer-return).[/yellow]",
            soft_wrap=True,
        )
    )


def return_refusal(
    key: str,
    problems: list[str],
    remedy: str,
    *,
    who: str = "the phase reviewers",
    bulleted: bool = False,
) -> NoReturn:
    """THE refusal of the reviewer-return checks (spec
    2026-10-02-opencode-observe-2 §E, 2026-11-12-review-lenses R10): the unit
    (its step and phase), every problem — each naming its reviewer and ids — on
    its own line, then what to do, as one `RunRefusal`. `bulleted` lines arrive formatted."""
    raise RunRefusal(
        derived_refusal_lines(
            key,
            [
                f"refused — the review record does not match what {who} returned:",
                *(problems if bulleted else [f"- {p}" for p in problems]),
                remedy,
            ],
        )
    )
