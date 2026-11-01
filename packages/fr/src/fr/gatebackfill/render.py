"""The dry run's summary and the repo-file commands its decisions imply
(spec 2026-11-01-gate-backfill §A, §E, R1, R11).

Backfill never writes a repo file: it prints, for the repo's own chore PR, the exact commands.
"""

from __future__ import annotations

import shlex
from pathlib import Path

from fr.gatebackfill.candidates import PLANS_REL, find_spec, split_key
from fr.gatebackfill.model import PlanEntry

ACCEPTED = {
    "plan": "owed, adopt, tick, na, park, review (tick/na only on a live plan)",
    "spec": "owed, adopt, na, park, review",
    "row": "owed, adopt, na, park, review",
    "issue": "owed, adopt, park, review (close it by hand to drop it)",
}


def _unticked(root: Path, name: str, phase: int) -> tuple[list[str], str | None]:
    """`(unticked step ids, why not)` of a live plan's phase."""
    from fr.parser import PlanSchemaError, parse

    d = root / PLANS_REL / name
    if not d.is_dir():
        archived = (root / "docs/superpowers/implemented/plans" / name).is_dir()
        return (
            [],
            "an archived plan is frozen" if archived else f"plan {name} is not in this checkout",
        )
    try:
        plan = parse(d, enforce_fr_version=False)
    except PlanSchemaError as exc:
        return [], f"plan {name} cannot be read: {exc}"
    for doc in plan.phases:
        if doc.phase.number == phase:
            return [sid for sid, st in doc.state.steps.items() if st.state == " "], None
    return [], f"plan {name} has no phase {phase}"


def decision_commands(entry: PlanEntry, root: Path) -> tuple[list[str], str | None]:
    """`(commands, refusal)` for a `tick` or `na` decision (R11's table); any other decision
    prints nothing. A refusal names the decisions the key's kind accepts."""
    kind = entry.decision_kind
    if kind not in ("tick", "na"):
        return [], None
    k, name, n = split_key(entry.key)
    accepted = f"; {entry.key} accepts: {ACCEPTED[k]}"
    reason = entry.note.strip()
    if kind == "na" and not reason:
        return [], f"{entry.key}: `na` needs a note (the reason){accepted}"
    if k == "plan" and n is not None:
        steps, why = _unticked(root, name, n)
        if why:
            return [], f"{entry.key}: {kind} refused: {why}{accepted}"
        plan_dir = shlex.quote((PLANS_REL / name).as_posix())
        if kind == "tick":
            return [f"fr plan edit {plan_dir} --tick {sid}" for sid in steps], None
        note = shlex.quote(f"n/a: {reason}")
        return [
            f"fr plan edit {plan_dir} --tick {sid} --state - --note {note}" for sid in steps
        ], None
    if kind == "na" and k == "spec" and n is not None:
        spec = find_spec(root, name)
        if spec is None:
            return [], f"{entry.key}: spec not found in this checkout{accepted}"
        return [
            f"fr closeout outcome --spec {shlex.quote(spec)} --step {n} --na "
            f"--reason {shlex.quote(reason)} --supersede"
        ], None
    if kind == "na" and k == "row":
        return [
            f"fr acceptance set-status --id {shlex.quote(name)} --status manual "
            f"--notes {shlex.quote(reason)}"
        ], None
    hint = ""
    if k == "spec" and n is not None:
        spec = find_spec(root, name) or "<spec>"
        hint = (
            f"; record it ran: fr closeout outcome --spec {shlex.quote(spec)} --step {n} "
            '--ran --evidence "<what>" --supersede'
        )
    return [], f"{entry.key}: {kind} refused: no command for this kind{hint}{accepted}"


def open_issue_refusals(entries: list[PlanEntry], sources: dict[str, str]) -> list[str]:
    """A bare `owed` on an `issue:` key that is itself an OPEN issue (*sources*: key -> where the
    fold found it) files no tracker and leaves no marker for the closed-issue link: the only
    route is adopting it, or a manifest entry carrying its own `issue:` (p2-r2)."""
    out = []
    for e in entries:
        if e.decision_kind == "owed" and sources.get(e.key) == "issue":
            ref = e.key.removeprefix("issue:")
            out.append(
                f"{e.key}: owed refused: it is itself an open issue; adopt it "
                f"(decision: adopt {ref}) or give the manifest entry an issue:"
            )
    return out


def row_reconcile(root: Path) -> list[str]:
    """`not-implemented` rows whose effective strategy is post-merge, moved to `walk-owed`."""
    from fr.acceptance.model import AcceptanceError, load_matrix
    from fr.gatebackfill.candidates import row_spec
    from fr.verification.effective import is_post_merge
    from fr.verification.rows import spec_verification

    try:
        matrix = load_matrix(root / "docs/acceptance/matrix.yaml")
    except (AcceptanceError, OSError):
        return []
    out = []
    for r in matrix.rows:
        if r.status != "not-implemented":
            continue
        try:
            strategy = spec_verification(root, row_spec(root, tuple(r.origin))).strategy(r)
            if is_post_merge(strategy, root):
                out.append(
                    f"fr acceptance set-status --id {shlex.quote(r.id)} --status walk-owed "
                    '--notes "post-merge walk owed (gate backfill)"'
                )
        except Exception:  # noqa: BLE001 — an unreadable spec or strategy lists nothing
            continue
    return out


def tracked_rows(entries: list[PlanEntry]) -> list[str]:
    """`set-status --issue` for each `row:` entry that already has a tracker."""
    out = []
    for e in entries:
        k, name, _ = split_key(e.key)
        if k == "row" and e.tracker.ref and e.decision_kind in ("owed", "adopt"):
            ref = shlex.quote(e.tracker.ref)
            out.append(
                f"fr acceptance set-status --id {shlex.quote(name)} --issue {ref} "
                f'--notes "tracked by {e.tracker.ref}"'
            )
    return out


def _line(e: PlanEntry) -> str:
    if e.pr is not None:
        pr = f"PR #{e.pr.number} ({e.pr.basis}{', planning' if e.pr.planning else ''})"
    elif e.ambiguous:
        pr = f"PRs {', '.join(f'#{n}' for n in e.ambiguous)} (ambiguous)"
    else:
        pr = "no delivering PR"
    extra = []
    if e.age_days is not None:
        extra.append(f"{e.age_days}d old")
    if e.ticked:
        extra.append(f"ticked {e.ticked}")
    if e.why:
        extra.append(e.why)
    tail = f" [{'; '.join(extra)}]" if extra else ""
    return f"  {e.key}  gate={e.gate or '-'}  {pr}  -> {e.decision}{tail}"


def summary(
    entries: list[PlanEntry], *, plan_file: Path, notes: list[str], root: Path
) -> tuple[str, list[str]]:
    """`(text, refusals)`: the dry run's summary. Every candidate is one line; parked ones sit
    under their own heading; refusals are the decisions whose command does not exist."""
    live = [e for e in entries if e.decision_kind != "park"]
    parked = [e for e in entries if e.decision_kind == "park"]
    lines = [f"Candidates ({len(live)})"]
    lines += [_line(e) for e in live] or ["  none"]
    unresolved = [e for e in live if e.pr is None]
    if unresolved:
        lines += ["", "No delivering PR: add `pr:` in a manifest (--from); never written:"]
        lines += [f"  {e.key}" for e in unresolved]
    if parked:
        lines += ["", f"Parked ({len(parked)})"] + [_line(e) for e in parked]
    commands: list[str] = []
    refusals: list[str] = []
    for e in entries:
        cmds, refusal = decision_commands(e, root)
        commands += cmds
        if refusal:
            refusals.append(refusal)
    commands += tracked_rows(entries)
    reconcile = row_reconcile(root)
    if commands or reconcile:
        lines += ["", "Commands for the repo's own chore PR (nothing was run):"]
        lines += [f"  {c}" for c in [*commands, *reconcile]]
    if notes:
        lines += ["", "Notes"] + [f"  {n}" for n in notes]
    lines += ["", f"plan file: {plan_file}"]
    return "\n".join(lines), refusals
