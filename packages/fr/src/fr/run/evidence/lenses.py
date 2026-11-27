"""The feature's lens set, and the lens review's reviewers and returns (spec
2026-11-27-run-verdict R6, R7).

`lens_set_or_refuse` moved from `fr.commands.run_cmd` in slice 4, the lens reviewer and return
checks in slice 5. A lens set that cannot be computed is a `RunRefusal`, never an empty set in its
place. The reviewer checks refuse with `RunRefusal`; `lenses_witness` returns a `Verdict[str]`.

Engine code: no `typer`, no `rich` but `rich.markup`, no `fr.commands`
(`tests/unit/test_run_writes_layering.py`).
"""

from __future__ import annotations

import functools
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from rich.markup import escape

from fr.journal.model import JournalEntry
from fr.run.evidence.derived import derived_refusal_lines
from fr.run.evidence.journals import is_lens_finding
from fr.run.evidence.review import (
    dispatches_since,
    return_refusal,
    return_unobserved,
    verify_reviewer,
)
from fr.run.evidence.target import EvidenceTarget
from fr.run.model import RunState
from fr.run.unobserved import why_unobservable
from fr.run.verdict import RunRefusal, Say, Verdict, Warn
from fr.workflow.model import Step

if TYPE_CHECKING:
    from fr.lenses.accumulate import LensSet


def lens_set_or_refuse(key: str, repo_root: Path, state: RunState) -> LensSet:
    """The feature's lens set (`fr.lenses.accumulate.lens_set`), or a refusal naming
    why it cannot be told. Never an empty set in place of an error."""
    from fr.lenses.accumulate import lens_set
    from fr.lenses.model import LensError

    try:
        return lens_set(repo_root, state)
    except LensError as e:
        raise RunRefusal(
            (
                Say(
                    f"[red]{key}: refused — the feature's lens set cannot be computed: "
                    f"{escape(str(e))}. Nothing was written.[/red]",
                    soft_wrap=True,
                ),
            )
        ) from e


def owed_on(step: Step, lenses: LensSet | None) -> list[str]:
    """What `step` owes: its evidence, less `review`/`reviewer` on a lens review
    whose set is empty (R11, `fr.lenses.review.owed_evidence`)."""
    from fr.lenses.review import owed_evidence

    return owed_evidence(step.evidence, lenses.ids) if lenses is not None else list(step.evidence)


def lens_lines(repo_root: Path, lenses: LensSet, lens_id: str) -> list[str]:
    """What a refusal over `lens_id` prints (R10): its title, instruction text, why
    it is in the set, and the return rule: the brief for the reviewer still owed."""
    from fr.lenses.review import lens_review_rule, why_line

    entry = next(e for e in lenses.lenses if e.lens == lens_id)
    found = lenses.definitions.get(lens_id)
    lines = [f"lens {lens_id}" + (f": {found.title}" if found is not None else "")]
    lines.append(f"  in the set because: {why_line(entry)}")
    if found is not None:
        lines.extend(f"  {line}" for line in found.brief.strip().splitlines())
    lines.extend(f"  {line}" for line in lens_review_rule(lens_id).splitlines())
    return lines


def verify_lens_reviewers(
    key: str,
    value: str,
    state: RunState,
    lenses: LensSet,
    repo_root: Path,
    *,
    target: EvidenceTarget,
    opened: str | None,
    warn: Warn,
) -> dict[str, str]:
    """The lens review's `reviewer` map, `<lens>=<dispatch-id>,...`, checked
    against the set computed at this resolve — or `RunRefusal` (R10). Each id is then
    verified as a phase reviewer's is (`verify_reviewer`)."""
    hint = (
        "on the lens review, --evidence reviewer= is a map, one <lens>=<dispatch-id> per "
        "lens in the feature's set, comma-separated"
    )
    named: dict[str, str] = {}
    problems: list[str] = []
    for pair in value.split(","):
        lens_id, sep, agent = (part.strip() for part in pair.partition("="))
        if not sep or not lens_id or not agent:
            problems.append(f"{pair.strip()!r} is not <lens>=<dispatch-id>: {hint}")
            continue
        if lens_id in named:
            problems.append(f"lens {lens_id} is named twice")
            continue
        named[lens_id] = agent
    unknown = [lid for lid in named if lid not in lenses.ids]
    if unknown:
        problems.append(
            f"{', '.join(unknown)} not in this feature's lens set ({', '.join(lenses.ids)})"
            if lenses.ids
            else f"{', '.join(unknown)} not in this feature's lens set, which is empty"
        )
    by_agent: dict[str, list[str]] = {}
    for lens_id, agent in named.items():
        by_agent.setdefault(agent, []).append(lens_id)
    for agent, lens_ids in by_agent.items():
        if len(lens_ids) > 1:
            problems.append(
                f"{agent} is named for two lenses ({', '.join(lens_ids)}) — one reviewer "
                "per lens, each given only its own lens"
            )
    owed = [lid for lid in lenses.ids if lid not in named]
    lines = [f"- {p}" for p in problems]
    for lens_id in owed:
        lines.append(f"- lens {lens_id} has no reviewer named for it; dispatch one with:")
        lines.extend(f"    {line}" for line in lens_lines(repo_root, lenses, lens_id))
    if lines:
        raise RunRefusal(
            derived_refusal_lines(
                key, ["refused — the lens reviewers named do not cover the lens set:", *lines]
            )
        )
    for agent in named.values():
        verify_reviewer(key, agent, state, target=target, opened=opened, warn=warn)
    return named


def lenses_witness(
    key: str,
    repo_root: Path,
    lenses: LensSet,
    entries: list[JournalEntry],
    reviewers: Mapping[str, str] | None,
    since: str | None,
) -> Verdict[str]:
    """The derived `lenses` evidence (R11): per lens the number of changed files its
    reviewer examined, or `unobserved`, and the findings it raised —
    `security=2:l-security-r1;tests=5:none` — or `none` for an empty set. A refusal of
    the returns carries the warnings printed before it."""
    if not lenses.lenses:
        return Verdict("none")
    assert reviewers is not None  # owed while the set is non-empty, so verified above
    warnings: list[Say] = []
    try:
        seen = check_lens_returns(
            key, repo_root, lenses, entries, reviewers, since, warn=warnings.append
        )
    except RunRefusal as r:
        return Verdict(None, refusal=r.lines, exit_code=r.exit_code, warnings=tuple(warnings))
    witness = ";".join(
        f"{lens_id}={count}:{','.join(ids) or 'none'}" for lens_id, (count, ids) in seen.items()
    )
    return Verdict(witness, warnings=tuple(warnings))


def check_lens_returns(
    key: str,
    repo_root: Path,
    lenses: LensSet,
    entries: list[JournalEntry],
    reviewers: Mapping[str, str],
    since: str | None,
    *,
    warn: Warn,
) -> dict[str, tuple[str, list[str]]]:
    """Each lens reviewer's return matches its lens, the feature's diff and the
    plan journal — or `RunRefusal` (R9, R10). Per lens, `(files examined | unobserved,
    finding ids)`; where a return cannot be read the ids come from the journal and
    the check is noted `unobserved=reviewer-return`."""
    from fr.lenses.review import (
        LENS_ID_HINT,
        ReviewLensBlockError,
        lens_finding_ids,
        parse_review_lens,
    )
    from fr.run.review_return import ReviewFindingsBlockError, parse_review_findings

    journaled = {
        e.id: e
        for e in entries
        if e.kind == "finding" and e.resolves is None and is_lens_finding(e.id)
    }
    dispatched = dispatches_since(since)
    if dispatched is None:
        return_unobserved(
            key, "the lens reviewers", why_unobservable("subagent returns"), warn=warn
        )
    changed = set(lenses.changed) if lenses.changed is not None else None
    seen: dict[str, tuple[str, list[str]]] = {}
    problems: dict[str, list[str]] = {}
    for lens_id in lenses.ids:
        agent = reviewers[lens_id]
        mine = lens_finding_ids(lens_id)
        d = next((c for c in dispatched or () if c.agent_id == agent), None)
        if d is None or d.returned is None:
            if dispatched is not None:
                return_unobserved(
                    key, f"reviewer {agent}", "its return is not readable yet", warn=warn
                )
            seen[lens_id] = ("unobserved", [fid for fid in journaled if mine.match(fid)])
            continue
        mine_problems = problems.setdefault(lens_id, [])
        try:
            block = parse_review_lens(d.returned)
        except ReviewLensBlockError as e:
            mine_problems.append(f"{agent}: {e}")
            block = None
        else:
            if block is None:
                mine_problems.append(
                    f"reviewer {agent} returned no review-lens block — its return must end "
                    f"with one naming lens {lens_id} and the changed files it examined"
                )
        if block is not None and block[0] != lens_id:
            mine_problems.append(
                f"reviewer {agent} was named for lens {lens_id}, and its review-lens block "
                f"names lens {block[0]}"
            )
        elif block is not None and changed is not None:
            outside = [f for f in block[1] if f not in changed]
            if outside:
                mine_problems.append(
                    f"reviewer {agent} examined {', '.join(outside)}, which the feature "
                    "did not change — name the changed files you read"
                )
        elif block is not None:
            missing = [f for f in block[1] if f not in tracked_files(repo_root)]
            if missing:
                mine_problems.append(
                    f"reviewer {agent} examined {', '.join(missing)}, which is not a "
                    "tracked file of this checkout"
                )
        try:
            rows = parse_review_findings(
                d.returned,
                id_re=lens_finding_ids(lens_id),
                id_hint=f"{LENS_ID_HINT} for lens {lens_id} (l-{lens_id}-r<k>)",
            )
        except ReviewFindingsBlockError as e:
            mine_problems.append(f"{agent}: {e}")
            rows = None
        else:
            if rows is None:
                mine_problems.append(
                    f"reviewer {agent} returned no review-findings block — its return must "
                    "end with one (`none` when it raised nothing)"
                )
        ids = [fid for fid, _scope, _summary in rows or ()]
        absent = [fid for fid in ids if fid not in journaled]
        if absent:
            mine_problems.append(
                f"returned finding(s) not in the plan journal: {', '.join(absent)} (reviewer "
                f"{agent}) — journal each under its id with the reviewer's tag, global "
                "(`fr journal add --kind finding --id <id> --global --review-scope in|out ...`)"
            )
        for fid, scope, _summary in rows or ():
            entry = journaled.get(fid)
            if entry is not None and entry.review_scope != scope:
                mine_problems.append(
                    f"{fid} is journaled with review_scope {entry.review_scope} but {agent} "
                    f"tagged it {scope} — keep the reviewer's tag; reclassify by resolving it "
                    "out-of-scope"
                )
        count = str(len(block[1])) if block is not None else "0"
        seen[lens_id] = (count, ids)
    if any(problems.values()):
        lines: list[str] = []
        for lens_id, found in problems.items():
            if not found:
                continue
            lines.extend(f"- {p}" for p in found)
            lines.extend(f"    {line}" for line in lens_lines(repo_root, lenses, lens_id))
        return_refusal(
            key,
            lines,
            "Journal every returned finding under its id with the reviewer's tag, or "
            "re-dispatch a lens reviewer whose return is malformed; never edit a return.",
            who="the lens reviewers",
            bulleted=True,
        )
    return seen


@functools.cache
def tracked_files(repo_root: Path) -> frozenset[str]:
    """The paths git tracks in this checkout: what a lens reviewer may name where
    there is no remote and so no diff (review l-security-r2: `is_file()` accepted
    `../` paths and untracked files)."""
    from fr.git import git_answer

    listed = git_answer(repo_root, "ls-files", "-z")
    return frozenset(listed.stdout.split("\0")) - {""} if listed.returncode == 0 else frozenset()
