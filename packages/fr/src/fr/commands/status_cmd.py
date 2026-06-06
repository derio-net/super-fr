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

from fr.commands.common import PlanReport, build_plan_report, require_migrated_layout
from fr.labels import FR_SYNCED
from fr.parser import PlanSchemaError
from fr.render import archive_gate

if TYPE_CHECKING:
    from fr.ghclient import GhClient

console = Console()
err_console = Console(stderr=True)

# Lifecycle labels a phase can carry (one at a time) — see render._lifecycle_label.
# Matched against RENDERED labels, which are always fr:* (the renderer
# translates legacy spellings) — no legacy entries needed here.
_LIFECYCLE = ("fr:ready", "fr:blocked", "fr:in-progress", "fr:pr-ready", "manual")


def _make_gh_client() -> GhClient:
    """Factory hook — tests monkeypatch this (same seam as apply_cmd)."""
    from fr.real_ghclient import RealGhClient

    return RealGhClient()


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


def _report_text(report: PlanReport) -> str:
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
    if not archive_gate(report.plan, report.observed):
        lines.append("")
        lines.append(
            f"plan complete — run `fr archive {report.plan.repo_relative_dir}` to move it "
            f"to implemented/."
        )
    return "\n".join(lines)


def _report_json(report: PlanReport) -> dict[str, Any]:
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
        "archive_ready": not archive_gate(report.plan, report.observed),
    }


def status_command(
    plan_dir: Path = typer.Argument(..., help="Path to plan folder."),
    output_format: str = typer.Option(
        "text",
        "--format",
        help="Output format: text (default, human-readable) or json.",
    ),
) -> None:
    """Read-only plan report: tick counts, dispatch state, drift, archive hint.

    Never mutates GitHub. Safe to allowlist as `fr status*`.
    """
    require_migrated_layout()
    if output_format not in ("text", "json"):
        err_console.print(f"--format must be 'text' or 'json', got {output_format!r}")
        raise typer.Exit(2)

    gh = _make_gh_client()
    try:
        report = build_plan_report(plan_dir, gh)
    except PlanSchemaError as e:
        err_console.print(f"parse error: {e}")
        raise typer.Exit(5) from e

    if output_format == "json":
        console.print_json(_json.dumps({"plans": [_report_json(report)]}))
    else:
        console.print(_report_text(report))
