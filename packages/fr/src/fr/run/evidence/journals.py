"""The journals a review unit's evidence is checked against, and the checks on them (spec
2026-11-27-run-verdict R7).

Moved from `fr.commands.run_cmd` in slice 5: reading the plan, spec or debug journal a
target names (a journal fr cannot read is a `RunStateError`), the `review` entry check
(`RunRefusal`), and the derived `findings` witness (`Verdict[str]`).

Engine code: no `typer`, no `rich` but `rich.markup`, no `fr.commands`
(`tests/unit/test_run_writes_layering.py`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fr.journal.model import (
    JournalEntry,
    JournalParseError,
    effective_finding_states,
    journal_stamp_as_utc,
    parse_journal,
    phase_finding_states,
    resolve_journal_read_path,
    reviews_phase,
    spec_journal_slug,
    unauthorized_fixes,
)
from fr.run.debug_journal import require_debug_slug
from fr.run.evidence import refusal
from fr.run.evidence.target import EvidenceTarget
from fr.run.historical import findings_witness
from fr.run.model import RunState, RunStateError
from fr.run.steps import emitted_plan
from fr.run.verdict import RunRefusal, Say, Verdict


def plan_journal_entries(repo_root: Path, state: RunState) -> tuple[str, list[JournalEntry]]:
    """`(slug, entries)` of this run's PLAN journal. Raises `RunStateError`
    when the run has not recorded a plan yet, which is fail-closed: a gate that
    cannot read its source does not know whether it passed."""
    slug, _path = plan_journal_path(state, repo_root)
    return journal_entries(repo_root, "plan", slug, "--phase <n> ")


def plan_journal_path(state: RunState, repo_root: Path) -> tuple[str, Path]:
    plan_rel = emitted_plan(state)
    if plan_rel is None:
        raise RunStateError(
            "cannot verify evidence — no plan recorded yet (resolve the step "
            "that emits `plan` first)"
        )
    slug = Path(plan_rel).name
    return slug, resolve_journal_read_path(repo_root, "plan", slug)


def review_journal_entries(
    repo_root: Path, state: RunState, target: EvidenceTarget
) -> tuple[str, list[JournalEntry]]:
    """`(slug, entries)` of the journal `target` names — the plan journal, or
    the spec journal of the spec this run emitted. Fail-closed like the plan
    one: no spec recorded is a refusal, not an empty journal."""
    if target.feature:
        # The lens review: a plan journal that does not exist holds no lens finding
        # and no review, exactly as `lens_set` reads it (no lens added).
        slug, path = plan_journal_path(state, repo_root)
        if not path.exists():
            return slug, []
    if target.scope == "plan":
        return plan_journal_entries(repo_root, state)
    if target.scope == "debug":
        return journal_entries(repo_root, "debug", require_debug_slug(state), "")
    from fr.requirements import run_spec

    spec_rel = run_spec(state)
    if spec_rel is None:
        raise RunStateError(
            "cannot verify evidence — no spec recorded yet (resolve the step "
            "that emits `spec` first)"
        )
    return journal_entries(repo_root, "spec", spec_journal_slug(Path(spec_rel).stem), "")


def journal_entries(
    repo_root: Path, scope: Literal["plan", "spec", "debug"], slug: str, phase_flag: str
) -> tuple[str, list[JournalEntry]]:
    path = resolve_journal_read_path(repo_root, scope, slug)
    if not path.exists():
        raise RunStateError(
            f"cannot verify evidence — the {scope} journal {path} does not exist. "
            f"Record the review first: fr journal add --scope {scope} --slug {slug} "
            f"--kind review {phase_flag}..."
        )
    try:
        return slug, parse_journal(path.read_text())
    except (JournalParseError, OSError) as e:
        raise RunStateError(
            f"cannot verify evidence — {scope} journal {path} is unreadable: {e}"
        ) from e


def verify_review_entry(
    key: str,
    entry_id: str,
    *,
    slug: str,
    entries: list[JournalEntry],
    target: EvidenceTarget,
    since: str | None,
) -> None:
    """`entry_id` is a `kind=review` entry for `target` — or `RunRefusal`.

    A phase: the entry carries `phase=N` (`reviews_phase`, the one rule). The
    spec: the entry was created at or after the step opened (`since`) — a
    review recorded before spec-review began is not a review OF it.
    """
    from fr.run.telemetry import parse_timestamp

    scope = target.scope
    found = next((e for e in entries if e.id == entry_id), None)
    phase_flag = (
        f"--phase {target.phase} "
        if target.phase is not None
        else ("--global " if target.feature else "")
    )
    if found is None:
        raise RunRefusal(
            (
                Say(
                    f"[red]{key}: --evidence review={entry_id} names no entry in the {scope} "
                    f"journal for {slug}[/red]",
                    soft_wrap=True,
                ),
                Say(
                    f"  fr journal add --scope {scope} --slug {slug} --kind review {phase_flag}"
                    f'--title "{target.subject} review" '
                    "--body \"<findings raised, by id; or 'no findings'>\"",
                    markup=False,
                    soft_wrap=True,
                ),
            )
        )
    if target.phase is not None:
        if not reviews_phase(found, target.phase):
            raise RunRefusal(
                refusal(
                    f"[red]{key}: --evidence review={entry_id} is a {found.kind!r} entry"
                    + (f" for phase {found.phase}" if found.phase is not None else " with no phase")
                    + f" — evidence must be a `kind=review` entry carrying `phase={target.phase}`, "
                    "the same rule `fr journal check --require-reviews` applies[/red]"
                )
            )
        return
    if target.feature and (found.kind != "review" or found.phase is not None):
        raise RunRefusal(
            refusal(
                f"[red]{key}: --evidence review={entry_id} is a {found.kind!r} entry"
                + (f" for phase {found.phase}" if found.phase is not None else "")
                + " — the lens review's evidence is a global `kind=review` plan-journal entry "
                "(no phase)[/red]"
            )
        )
    if found.kind != "review":
        raise RunRefusal(
            refusal(
                f"[red]{key}: --evidence review={entry_id} is a {found.kind!r} entry — evidence "
                "must be a `kind=review` spec-journal entry[/red]"
            )
        )
    created = parse_timestamp(journal_stamp_as_utc(found.created))
    opened = parse_timestamp(since) if since else None
    if created is None or opened is None or created < opened.replace(microsecond=0):
        began = "this step opened" if target.feature else "spec-review began"
        raise RunRefusal(
            refusal(
                f"[red]{key}: --evidence review={entry_id} was created {found.created}, "
                f"before this step opened at {since} — a review recorded before {began} "
                "is not a review of it. Record the reviewer's findings, then a new "
                "`kind=review` entry.[/red]"
            )
        )


def target_finding_states(entries: list[JournalEntry], target: EvidenceTarget) -> dict[str, str]:
    """Every finding filed against `target` -> its effective state. A phase:
    `phase_finding_states`. The spec: every finding in its journal (a spec
    journal has no phases), through the SAME fold `fr journal check` reads."""
    if target.phase is not None:
        return dict(phase_finding_states(entries, target.phase))
    states = effective_finding_states(entries)
    return {
        e.id: states[e.id]
        for e in entries
        if e.kind == "finding"
        and e.resolves is None
        and e.id in states
        and (not target.feature or is_lens_finding(e.id))
    }


def is_lens_finding(fid: str) -> bool:
    """A lens review's finding (`l-<lens>-r<k>`): the only plan findings the
    feature target gates (spec 2026-11-12-review-lenses §3.C)."""
    from fr.lenses.review import LENS_FINDING_ID_RE

    return LENS_FINDING_ID_RE.match(fid) is not None


def closed_findings_witness(
    key: str, slug: str, entries: list[JournalEntry], target: EvidenceTarget
) -> Verdict[str]:
    """The `findings` evidence for `target` — or a refusal while any
    finding filed against it is still open.

    This is `superpowers:receiving-code-review`'s OUTCOME, which is the only
    part of "was the review received properly" fr can observe: every finding
    the review raised ends `fixed` or `refuted`, never dropped. It is the check
    `journal-check` already made once, before `deliver` — moved to the moment a
    finding is cheapest to act on, while the phase that caused it is still the
    one in hand.

    The value is the WITNESS, not a token: the ids fr saw closed, in the order
    they were raised, or `none`. A finding that genuinely belongs to a later
    phase is filed against THAT phase, and gates that phase's review instead.
    """
    subject, scope = target.subject, target.scope
    states = target_finding_states(entries, target)
    still_open = [fid for fid, st in states.items() if st == "open"]
    # The operator guard `fr journal check` applies (spec 2026-09-24 §A), read
    # from the same fold: an out-of-scope finding fixed without the operator.
    unauthorized = [fid for fid in unauthorized_fixes(entries) if fid in states]
    if unauthorized:
        lines = [
            Say(
                f"[red]{key}: refused — {len(unauthorized)} unauthorized fix(es) against "
                f"{subject}: {', '.join(unauthorized)} — moved from out-of-scope to fixed without "
                "`answered_by=operator`. Ask the operator, then:[/red]",
                soft_wrap=True,
            )
        ]
        lines.extend(
            Say(
                f"  fr journal resolve --scope {scope} --slug {slug} --id {fid} --state fixed "
                '--answered-by operator --note "<what the operator decided>"',
                markup=False,
                soft_wrap=True,
            )
            for fid in unauthorized
        )
        return Verdict(None, refusal=tuple(lines))
    if not still_open:
        return Verdict(findings_witness(states))
    lines = [
        Say(
            f"[red]{key}: refused — {len(still_open)} finding(s) filed against {subject} "
            f"are still open: {', '.join(still_open)}.[/red]",
            soft_wrap=True,
        ),
        Say(
            "  A review is received, not just requested "
            "(`superpowers:receiving-code-review`): verify each finding, then fix it with "
            "a test or refute it with reasoning — never drop it. Close each one:",
            soft_wrap=True,
        ),
    ]
    lines.extend(
        Say(
            f"  fr journal resolve --scope {scope} --slug {slug} --id {fid} --state fixed "
            '--note "<what changed, and the test that pins it>"',
            markup=False,
            soft_wrap=True,
        )
        for fid in still_open
    )
    later = (
        f" One that belongs to a later phase is filed against that phase, not {subject}."
        if target.phase is not None
        else ""
    )
    lines.append(
        Say(
            "  (or `--state refuted` with the reasoning, when the finding is wrong; "
            "`--state out-of-scope` when this change did not cause it)."
            f"{later} `--state failed` needs no evidence.",
            soft_wrap=True,
        )
    )
    return Verdict(None, refusal=tuple(lines))
