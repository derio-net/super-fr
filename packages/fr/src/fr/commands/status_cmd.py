"""`fr status` CLI — read-only plan report (2026-06-05 dispatch-guards spec).

The safely-allowlistable audit verb: same read pipeline as `fr apply`'s
dry-run (via `vk.commands.common.build_plan_report`, so the two can never
drift) but with no mutation vocabulary and no `--yes` to misfire. Exit 0
even when drift exists — it's a report, not a gate. Allowlist as
`fr status*`.

Exit codes: 0 report printed (drift included); 2 usage / legacy layout;
5 plan parse error.
"""

from __future__ import annotations

import json as _json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer
from rich.console import Console
from rich.markup import escape

from fr.closeout import HeldSpec, Owed, OwedArtifacts, PlanSweep, owed_artifacts
from fr.commands.common import (
    PlanReport,
    build_plan_report,
    require_migrated_layout,
    resolve_repo_root,
)
from fr.git import GitUnavailableError
from fr.labels import FR_SYNCED
from fr.parser import PlanSchemaError

if TYPE_CHECKING:
    from fr.archive import DefaultRef, MergeEvidence
    from fr.ghclient import GhClient

console = Console()
err_console = Console(stderr=True)

# Lifecycle labels a phase can carry (one at a time) — see render._lifecycle_label.
# Matched against RENDERED labels, which are always fr:* (the renderer
# translates legacy spellings) — no legacy entries needed here.
_LIFECYCLE = ("fr:ready", "fr:blocked", "fr:in-progress", "fr:pr-ready", "manual")


def _make_gh_client() -> GhClient:
    """Factory hook — tests monkeypatch this (same seam as apply_cmd)."""
    from fr.hostclient import client_for

    return client_for(Path.cwd())


def _phase_line(report: PlanReport, phase_n: int) -> str:
    """One table line: ticks · tracking issue · lifecycle / next action."""
    plan = report.plan
    phase = next(p for p in plan.phases if p.phase.number == phase_n)
    ri = report.rendered.issue_per_phase[phase_n]
    steps = phase.state.steps
    ticked = sum(1 for s in steps.values() if s.state in ("x", "-"))
    tracking = phase.phase.tracking_issue or "—"

    if ri.state == "CLOSED":
        status = "complete (closed)"
    else:
        lifecycle = next(
            (ld.name for ld in ri.labels if ld.name in _LIFECYCLE and ld != FR_SYNCED), None
        )
        status = lifecycle or "—"
    suppressed = {s.phase_number for s in report.diff.suppressed}
    if phase_n in suppressed:
        status = "would refuse create (locally complete)"
    elif phase.phase.tracking_issue is None:
        status = f"would create Issue ({status})"
    return f"  phase {phase_n}: {ticked}/{len(steps)} steps · {tracking} · {status}"


def _report_text(report: PlanReport, evidence: MergeEvidence) -> str:
    from fr.archive import archive_blockers

    lines = [report.header]
    for phase in report.plan.phases:
        lines.append(_phase_line(report, phase.phase.number))
    if report.diff.suppressed:
        lines.append("")
        lines.append("completion guard:")
        for s in report.diff.suppressed:
            lines.append(f"  phase {s.phase_number}: {s.reason}")
    if report.rendered.warnings:
        lines.append("")
        lines.append("warnings:")
        for w in report.rendered.warnings:
            lines.append(f"  [{w.severity}] {w.message}")
    if not archive_blockers(report.plan, report.observed, evidence):
        lines.append("")
        lines.append(
            f"plan complete — run `fr archive {report.plan.repo_relative_dir}` to move it "
            f"to implemented/."
        )
    return "\n".join(lines)


def _report_json(report: PlanReport, evidence: MergeEvidence) -> dict[str, Any]:
    from fr.archive import archive_blockers
    from fr.commands.apply_cmd import _mutation_to_json

    return {
        "plan": report.plan.meta.plan,
        "header": report.header,
        "mutations": [_mutation_to_json(m) for m in report.diff.mutations],
        "suppressed": [
            {"phase_number": s.phase_number, "reason": s.reason} for s in report.diff.suppressed
        ],
        "warnings": [
            {"severity": w.severity, "message": w.message} for w in report.rendered.warnings
        ],
        "phases": [
            {
                "number": p.phase.number,
                "title": p.phase.title,
                "tag": p.phase.tag,
                "tracking_issue": p.phase.tracking_issue,
                "steps_ticked": sum(1 for s in p.state.steps.values() if s.state in ("x", "-")),
                "steps_total": len(p.state.steps),
                "projected_state": report.rendered.issue_per_phase[p.phase.number].state,
            }
            for p in report.plan.phases
        ],
        "archive_ready": not archive_blockers(report.plan, report.observed, evidence),
    }


def _sweep_lists(repo_root: Path) -> PlanSweep:
    """Bucket every plan dir under docs/superpowers/plans/ by merge evidence
    from the default branch's remote-tracking ref (fetched first).

    The bucketing itself (``PlanSweep``, the "archivable" predicate) lives in
    ``fr.closeout`` so ``owed_artifacts`` (§C) shares it rather than
    re-deriving "merged and locally complete" a second time
    (2026-09-28-closeout-always spec §C).
    """
    from fr.archive import merge_evidence
    from fr.closeout import plan_sweep

    evidence = merge_evidence(repo_root, fetch=True)
    return plan_sweep(repo_root, evidence)


def _behind_ref(repo_root: Path, sweep: PlanSweep) -> int | None:
    """Commits HEAD lacks from the default ref, when HEAD is strictly BEHIND
    it (an ancestor, not equal); None otherwise — a diverged feature branch is
    not stale, its own work is the point (gh#811).

    The sweep reads plans and owed artifacts from the working tree but merge
    evidence from the fetched ref, and its header names that ref. In a base
    clone that has not pulled a merge, the merged plan is simply not on disk,
    so no bucket lists it and the report reads as "nothing owed" against a
    ref it never evaluated. Saying so is the fix; pulling is the operator's
    call, since a read-only verb never moves a branch."""
    from fr.git import git_answer

    ref = sweep.evidence.ref
    if ref is None:
        return None
    try:
        if git_answer(repo_root, "merge-base", "--is-ancestor", "HEAD", ref.ref).returncode:
            return None
        count = git_answer(repo_root, "rev-list", "--count", f"HEAD..{ref.ref}")
    except GitUnavailableError:
        return None
    n = int(count.stdout.strip() or 0) if count.returncode == 0 else 0
    return n or None


def _behind_block(behind: int | None, sweep: PlanSweep) -> _Block:
    ref = sweep.evidence.ref
    if not behind or ref is None:
        return []
    return [
        f"working tree is {behind} commit(s) behind {ref.ref} — this report lists what is "
        "on disk, so it is stale: pull the default branch (`git pull --ff-only`) and re-run."
    ]


def _sweep_json(sweep: PlanSweep, owed: OwedArtifacts, behind: int | None) -> dict[str, Any]:
    ev = sweep.evidence
    return {
        "archivable": sweep.archivable,
        "merged_manual_open": [name for name, _ in sweep.merged_manual_open],
        "complete_unmerged": sweep.complete_unmerged,
        "in_progress": sweep.in_progress,
        "default_ref": (
            None
            if ev.ref is None
            else {
                "ref": ev.ref.ref,
                "sha": ev.ref.sha,
                "fetched": ev.fetched,
                "fetch_error": ev.fetch_error,
            }
        ),
        "ref_error": ev.ref_error,
        "behind_ref": behind,
        "unparsed_on_ref": list(ev.unparsed_on_ref),
        # §C: everything `owed_artifacts` reports, alongside the buckets
        # above (unchanged) — new keys, nothing removed or renamed.
        "owed": [{"kind": o.kind, "path": str(o.path), "clear": o.clear} for o in owed.owed],
        "held": [{"spec": h.spec, "note": h.note} for h in owed.held],
    }


_Block = list[str]
"""One blank-line-delimited section of the sweep's text output."""


def _block(heading: str, rows: list[str]) -> _Block:
    return [f"{heading} ({len(rows)}):", *(f"  {r}" for r in rows)]


def _archivable_block(names: list[str], on: str) -> _Block:
    """The only bucket that prints a command: one `fr archive` per plan."""
    from fr.archive import PLANS_REL

    if not names:
        return [f"no merged plans waiting to be archived ({on})."]
    block = [f"merged but not archived: agentic phases on {on} ({len(names)}):"]
    for name in names:
        block += [f"  {name}", f"    fr archive {PLANS_REL}/{name}"]
    return block


def _manual_open_row(name: str, phases: list[int]) -> str:
    label = "phase" if len(phases) == 1 else "phases"
    return f"{name}  ({label} {', '.join(map(str, phases))})"


def _unknown_ref_blocks(sweep: PlanSweep) -> list[_Block]:
    """No resolvable default ref: nothing is merged, so every locally
    complete plan is listed as unknown rather than archivable."""
    hint = f"{sweep.evidence.ref_error}; try git fetch / git remote set-head origin -a"
    return [_block(f"merge state unknown ({hint})", sweep.complete_unmerged)]


def _known_ref_blocks(sweep: PlanSweep, ref: DefaultRef) -> list[_Block]:
    ev = sweep.evidence
    blocks: list[_Block] = []
    if ev.fetch_error:
        blocks.append([f"(fetch failed: {ev.fetch_error}; using the local {ref.ref} ref)"])
    blocks.append(_archivable_block(sweep.archivable, f"{ref.ref} @ {ref.sha}"))
    if sweep.merged_manual_open:
        rows = [_manual_open_row(n, p) for n, p in sweep.merged_manual_open]
        blocks.append(_block("merged, manual phases still open", rows))
    if sweep.complete_unmerged:
        heading = f"complete locally, not yet on {ref.ref} (waiting for merge)"
        blocks.append(_block(heading, sweep.complete_unmerged))
    if ev.unparsed_on_ref:
        heading = f"could not parse on {ref.ref} with this fr; merge state unknown"
        blocks.append(_block(heading, list(ev.unparsed_on_ref)))
    return blocks


def _owed_block(owed: tuple[Owed, ...]) -> _Block:
    """Every owed kind but ``plan`` — that one already has its own line in
    ``_archivable_block`` above, and printing it twice would just be noise.
    Empty (not even a heading) when nothing is owed, so a clean repo's
    report is unchanged (2026-09-28-closeout-always §C)."""
    entries = [o for o in owed if o.kind != "plan"]
    if not entries:
        return []
    block = [f"owed ({len(entries)}):"]
    for o in entries:
        block += [f"  {o.path}", f"    {o.clear}"]
    return block


def _held_block(held: tuple[HeldSpec, ...]) -> _Block:
    """One line per held spec — visible, but not owed (R5)."""
    return [f"held live (spec): {h.spec} — {h.note}" for h in held]


def _sweep_text(sweep: PlanSweep, owed: OwedArtifacts, behind: int | None) -> str:
    ref = sweep.evidence.ref
    blocks = [b for b in [_behind_block(behind, sweep)] if b]
    blocks += _unknown_ref_blocks(sweep) if ref is None else _known_ref_blocks(sweep, ref)
    owed_block = _owed_block(owed.owed)
    if owed_block:
        blocks.append(owed_block)
    held_block = _held_block(owed.held)
    if held_block:
        blocks.append(held_block)
    if sweep.in_progress:
        blocks.append(_block("in progress", sweep.in_progress))
    return "\n\n".join("\n".join(b) for b in blocks)


def status_command(
    plan_dir: Path | None = typer.Argument(
        None,
        help=(
            "Path to plan folder. Omit for a repo-wide sweep that buckets every plan by "
            "whether its agentic phases are on the default branch (fetched first): merged "
            "and archivable, merged with manual phases open, complete locally but waiting "
            "for merge, and in progress."
        ),
    ),
    output_format: str = typer.Option(
        "text",
        "--format",
        help="Output format: text (default, human-readable) or json.",
    ),
) -> None:
    """Read-only plan report: tick counts, dispatch state, drift, archive hint.

    With no PLAN_DIR, fetches the default remote and sweeps
    docs/superpowers/plans/ into four buckets. A plan is merged only when every
    agentic phase is complete on the default branch's remote-tracking ref
    (e.g. origin/main); local completeness alone never counts.

    \b
    - merged but not archived: prints its own `fr archive <plan-dir>` line
    - merged, manual phases still open: names the open phases
    - complete locally, not yet on the default branch: waiting for merge
    - in progress: everything else

    With no resolvable default ref, complete plans are listed as "merge state
    unknown". The sweep is gh-free: for a dispatched plan, `fr archive`'s
    merged-PR gate may still refuse a plan listed here. Never mutates GitHub
    (a fetch moves only remote-tracking refs). Safe to allowlist as
    `fr status*`.
    """
    require_migrated_layout()
    if output_format not in ("text", "json"):
        err_console.print(f"--format must be 'text' or 'json', got {output_format!r}")
        raise typer.Exit(2)

    if plan_dir is None:
        repo_root = resolve_repo_root()
        sweep = _sweep_lists(repo_root)
        # One merge-evidence read for the whole sweep (#544) — reused here,
        # never re-fetched.
        owed = owed_artifacts(repo_root, sweep.evidence)
        behind = _behind_ref(repo_root, sweep)
        if output_format == "json":
            console.print_json(_json.dumps(_sweep_json(sweep, owed, behind)))
        else:
            text = _sweep_text(sweep, owed, behind)
            console.print(text, markup=False, highlight=False, soft_wrap=True)
        return

    gh = _make_gh_client()
    try:
        report = build_plan_report(plan_dir, gh)
    except PlanSchemaError as e:
        err_console.print(f"parse error: {escape(str(e))}")
        raise typer.Exit(5) from e

    # The nudge and `archive_ready` share one merge-evidence read (#544).
    from fr.archive import merge_evidence

    evidence = merge_evidence(resolve_repo_root(), fetch=True)
    if output_format == "json":
        console.print_json(_json.dumps({"plans": [_report_json(report, evidence)]}))
    else:
        console.print(_report_text(report, evidence))
        section = _acceptance_section(resolve_repo_root())
        if section:
            console.print(section)


def _acceptance_section(root: Path) -> str | None:
    """One-line acceptance nag (2026-07-04 spec, decision 1b). Only when the
    repo has adopted a matrix — unadopted repos are the hook's business, not
    every status call's. Best-effort read-only."""
    matrix_path = root / "docs" / "acceptance" / "matrix.yaml"
    if not matrix_path.exists():
        return None
    try:
        from collections import Counter

        from fr.acceptance.check import open_rows
        from fr.acceptance.model import load_matrix

        matrix = load_matrix(matrix_path)
        counts = Counter(r.status for r in matrix.rows)
        summary = ", ".join(f"{s}: {n}" for s, n in sorted(counts.items())) or "empty"
        n_open = len(open_rows(matrix))
        return f"\nAcceptance: {summary} — {n_open} open (details: fr acceptance status)"
    except Exception as e:  # noqa: BLE001 — a broken matrix must not break status
        return f"\nAcceptance: matrix unreadable ({e}) — fr acceptance check"
