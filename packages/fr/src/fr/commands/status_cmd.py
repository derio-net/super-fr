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
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer
from rich.console import Console

from fr.commands.common import (
    PlanReport,
    build_plan_report,
    require_migrated_layout,
    resolve_repo_root,
)
from fr.labels import FR_SYNCED
from fr.parser import PlanSchemaError

if TYPE_CHECKING:
    from fr.archive import DefaultRef, MergeEvidence
    from fr.ghclient import GhClient
    from fr.parser import Plan

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


@dataclass(frozen=True)
class _Sweep:
    """The four buckets of the repo-wide sweep (spec 2026-09-23 §3.B)."""

    evidence: MergeEvidence
    archivable: list[str]
    """Merged (see ``_merged``) and locally complete, manual phases included."""
    merged_manual_open: list[tuple[str, list[int]]]
    """Merged, but these local phase numbers are still open."""
    complete_unmerged: list[str]
    """Locally complete, not merged — or merge state unknown (``ref is None``)."""
    in_progress: list[str]
    """Everything else, a plan the working tree cannot parse included."""


def _merged(name: str, plan: Plan, evidence: MergeEvidence) -> bool:
    """Every agentic phase of the WORKING-TREE plan is complete on the ref.

    ``agentic_landed`` alone is judged from the ref's copy of the plan, so a
    phase added on the branch after an earlier merge would not block it
    (f-p2-local-phases); each local agentic phase must be in ``landed_phases``.
    """
    landed = evidence.landed_phases.get(name, frozenset())
    return name in evidence.agentic_landed and all(
        p.phase.number in landed for p in plan.phases if p.phase.tag == "agentic"
    )


def _sweep_lists(repo_root: Path) -> _Sweep:
    """Bucket every plan dir under docs/superpowers/plans/ by merge evidence
    from the default branch's remote-tracking ref (fetched first)."""
    from fr.archive import PLANS_REL, merge_evidence
    from fr.parser import parse
    from fr.render import plan_locally_complete

    evidence = merge_evidence(repo_root, fetch=True)
    sweep = _Sweep(evidence, [], [], [], [])
    plans_dir = repo_root / PLANS_REL
    names = (
        sorted(p.name for p in plans_dir.iterdir() if (p / "_meta.yaml").exists())
        if plans_dir.is_dir()
        else []
    )
    for name in names:
        try:
            plan = parse(plans_dir / name)
        except PlanSchemaError:
            sweep.in_progress.append(name)
            continue
        open_phases = [p.phase.number for p in plan.phases if not plan_locally_complete(p)]
        complete = bool(plan.phases) and not open_phases
        if _merged(name, plan, evidence):
            if complete:
                sweep.archivable.append(name)
            else:
                sweep.merged_manual_open.append((name, open_phases))
        elif complete:
            sweep.complete_unmerged.append(name)
        else:
            sweep.in_progress.append(name)
    return sweep


def _sweep_json(sweep: _Sweep) -> dict[str, Any]:
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
        "unparsed_on_ref": list(ev.unparsed_on_ref),
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


def _unknown_ref_blocks(sweep: _Sweep) -> list[_Block]:
    """No resolvable default ref: nothing is merged, so every locally
    complete plan is listed as unknown rather than archivable."""
    hint = f"{sweep.evidence.ref_error}; try git fetch / git remote set-head origin -a"
    return [_block(f"merge state unknown ({hint})", sweep.complete_unmerged)]


def _known_ref_blocks(sweep: _Sweep, ref: DefaultRef) -> list[_Block]:
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


def _sweep_text(sweep: _Sweep) -> str:
    ref = sweep.evidence.ref
    blocks = _unknown_ref_blocks(sweep) if ref is None else _known_ref_blocks(sweep, ref)
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
        sweep = _sweep_lists(resolve_repo_root())
        if output_format == "json":
            console.print_json(_json.dumps(_sweep_json(sweep)))
        else:
            console.print(_sweep_text(sweep), markup=False, highlight=False, soft_wrap=True)
        return

    gh = _make_gh_client()
    try:
        report = build_plan_report(plan_dir, gh)
    except PlanSchemaError as e:
        err_console.print(f"parse error: {e}")
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
