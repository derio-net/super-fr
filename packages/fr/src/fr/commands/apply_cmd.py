"""`fr apply` CLI — render + observe + diff + apply for a plan.

Wires the library functions (`render`/`observe`/`diff`/`apply`) into
typer. Production resolves the repo's backend-appropriate client
(`RealGhClient`/`RealGlabClient`/`RealTeaClient`) via
`fr.hostclient.client_for`; tests inject `FakeGhClient` by monkeypatching
`_make_gh_client`.

The factory hook is the test seam — keep it. Replacing the module-level
function in tests is the cleanest way to swap the gh client without
threading dependency-injection plumbing through the whole library.

Exit code conventions (consistent across all v2 commands):
  0 = success
  2 = usage error or plan-edit refusal (e.g. flag combination invalid)
  4 = gh / network failure during apply
  5 = plan parse error
"""

from __future__ import annotations

import json as _json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer
from rich.console import Console

from fr import plan_ops
from fr.apply import apply
from fr.commands.common import PlanReport, build_plan_report, require_migrated_layout
from fr.diff import (
    Diff,
    IssueBodyChange,
    IssueCreate,
    IssueLabelChange,
    IssueStateChange,
    RepoLabelEnsure,
)
from fr.parser import Plan, PlanSchemaError
from fr.plan_ops import PlanEditError
from fr.render import archive_gate
from fr.workflow.model import WorkflowError
from fr.workflow.resolve import workflow_for_plan

if TYPE_CHECKING:
    from fr.ghclient import GhClient

console = Console()
err_console = Console(stderr=True)


def _make_gh_client() -> GhClient:
    """Factory hook for the GhClient. Tests monkeypatch this to inject FakeGhClient.

    Defaults to `hostclient.client_for(Path.cwd())`, which resolves to
    `RealGhClient`/`RealGlabClient`/`RealTeaClient` per the repo's
    configured/detected backend (see fr._hosts). Tests override by
    `monkeypatch.setattr(apply_cmd, "_make_gh_client", lambda: FakeGhClient())`.
    """
    from fr.hostclient import client_for

    return client_for(Path.cwd())


_GATE_RUN_ID = "fr-apply-reachability-gate"
"""Placeholder run id for `unit: run` shapes at the `fr apply` gate.

`build_items` needs one to compose a run item's identity (§4.D), and
`fr apply` gates a PLAN, not a run — there is no run id to pass. The gate
reads only `WorkItem.inputs` and never the id, so a fixed placeholder keeps
the graph constructible without inventing a run that does not exist.
"""


def _check_plan_reachable_on_origin_head(plan: Plan, repo_root: Path) -> list[Path]:
    """Return the artifacts this dispatch NEEDS that are not on origin/HEAD.

    Empty list = gate passes. Caller (`_apply_one`) refuses `--yes`
    when this returns non-empty.

    **Which artifacts those are is derived, not hardcoded** (spec §4.E,
    Phase 8): `required_inputs` reads the unmet needs off a shape, so the
    refusal is a consequence of that shape rather than a rule this function
    states. A shape that emitted its own plan (a `unit: run` goal) produces
    an empty requirement here, which is exactly the §4.E asymmetry.

    **Which shape is the PLAN's own** (spec §4.A.1, Phase 12): resolved via
    `workflow_for_plan`, not the module-level default this function used to
    read. A plan naming no shape still resolves `FR_GOAL_PHASE_DISPATCH`
    (`needs: [spec, plan]`), so the 2026-05-17 gate is unchanged for every
    plan in the wild; a plan naming a shape that does NOT resolve raises
    `WorkflowError` rather than falling back — gating on the wrong shape's
    inputs would let a dispatch through at the wrong granularity while
    reporting success.

    **It walks the item graph, it does not rebuild it** (review r5-a1). The
    derivation used to be a hand-rolled list here — `if "plan" in required:
    paths.append(...)` — running in parallel with `fr_dispatch.reachability`,
    and the two had already drifted: this one skipped a cross-repo *spec* by
    notation, while that one skipped any ref whose repo differed from
    `item.repo`, which for a cross-repo-TRACKED phase is the plan itself.
    §4.E promised one derived rule, so there is now one function:
    `build_items` applies `required_inputs` to produce the refs and
    `unreachable_inputs` answers them, for this caller and for a runner tick
    alike. Cross-repo skipping survives as a property of the data — a spec
    ref in another repo carries another repo's coordinate — rather than as a
    notation check written twice.

    `home_repo` is `plan.meta.target_repo`, because `repo_root` is a
    checkout of the repo the PLAN lives in. No `gh` is passed, so a
    cross-repo ref stays skipped and the operator stays trusted for it,
    exactly as the 2026-05-17 gate had it.

    Reaches `fr_dispatch` through the one sanctioned soft point
    (`tests/unit/test_import_direction.py`), and only from the
    `--to <runner>` path, which already refuses when that package is absent.

    Raises if origin/HEAD isn't resolvable locally — caller catches
    and re-raises with a setup hint.
    """
    from fr_dispatch.item_graph import build_items
    from fr_dispatch.reachability import unreachable_inputs

    # An item that cannot be CONSTRUCTED (a malformed tracking URL) is not
    # dispatchable and has no inputs to check, so it is accumulated and
    # dropped rather than raised: the gate answers "are the inputs merged",
    # and `tick` is what reports an unbuildable item. Raising here would
    # surface as `fr apply`'s origin/HEAD hint, which is the wrong advice.
    unbuildable: list[str] = []
    items = build_items(
        workflow_for_plan(plan, repo_root),
        plan,
        run_id=_GATE_RUN_ID,
        failures=unbuildable,
    )
    # Every phase item of one plan declares the SAME refs, so the flattened
    # list is de-duplicated: the operator is told what to merge once, not
    # once per phase.
    seen: dict[str, None] = {}
    for u in unreachable_inputs(items, repo_root, home_repo=plan.meta.target_repo):
        for p in u.paths:
            seen.setdefault(p, None)
    return [Path(p) for p in seen]


def _unverifiable_inputs_for(plan: Plan, repo_root: Path) -> list[str]:
    """Cross-repo inputs this gate cannot answer offline (review r5-e13).

    Skipping them is the documented default (the 2026-05-17 gate did the same),
    but a silent skip made a cross-repo dispatch look as verified as a local
    one. Reported, never refused: refusing would break every cross-repo plan
    that works today.
    """
    from fr_dispatch.item_graph import build_items
    from fr_dispatch.reachability import unverifiable_inputs

    unbuildable: list[str] = []
    items = build_items(
        workflow_for_plan(plan, repo_root), plan, run_id=_GATE_RUN_ID, failures=unbuildable
    )
    return [
        f"{ref.repo}:{ref.path}"
        for ref in unverifiable_inputs(items, home_repo=plan.meta.target_repo)
    ]


def _format_diff(d: Diff) -> str:
    """Human-readable summary of mutations."""
    if not d.mutations:
        # "in sync" would be misleading when the completion guard withheld
        # creates — the suppression block printed below explains the state.
        if d.suppressed:
            return "no pending mutations."
        return "no mutations — already in sync."
    lines: list[str] = []
    for m in d.mutations:
        if isinstance(m, RepoLabelEnsure):
            label_names = sorted(ld.name for ld in m.labels)
            lines.append(f"  ensure labels on {m.repo}: {label_names}")
        elif isinstance(m, IssueCreate):
            lines.append(f"  create Issue on {m.repo} for phase {m.phase_number}: {m.title!r}")
        elif isinstance(m, IssueLabelChange):
            lines.append(
                f"  edit labels on {m.repo}#{m.issue_number}: +{sorted(m.add)} -{sorted(m.remove)}"
            )
        elif isinstance(m, IssueStateChange):
            lines.append(f"  set state on {m.repo}#{m.issue_number} to {m.new_state}")
        elif isinstance(m, IssueBodyChange):
            lines.append(f"  update body on {m.repo}#{m.issue_number} ({len(m.new_body)} chars)")
    return "\n".join(lines)


def _mutation_to_json(m: Any) -> dict[str, Any]:
    """Serialise a mutation dataclass to a plain JSON-friendly dict."""
    if isinstance(m, RepoLabelEnsure):
        return {
            "kind": "RepoLabelEnsure",
            "repo": m.repo,
            "labels": sorted(ld.name for ld in m.labels),
        }
    if isinstance(m, IssueCreate):
        return {
            "kind": "IssueCreate",
            "repo": m.repo,
            "phase_number": m.phase_number,
            "title": m.title,
            "labels": sorted(m.labels),
        }
    if isinstance(m, IssueLabelChange):
        return {
            "kind": "IssueLabelChange",
            "repo": m.repo,
            "issue_number": m.issue_number,
            "add": sorted(m.add),
            "remove": sorted(m.remove),
        }
    if isinstance(m, IssueStateChange):
        return {
            "kind": "IssueStateChange",
            "repo": m.repo,
            "issue_number": m.issue_number,
            "new_state": m.new_state,
        }
    if isinstance(m, IssueBodyChange):
        return {
            "kind": "IssueBodyChange",
            "repo": m.repo,
            "issue_number": m.issue_number,
            "body_length": len(m.new_body),
        }
    return {"kind": type(m).__name__}


def _apply_one(
    plan_dir: Path, gh: GhClient, *, yes: bool, force: bool = False, to: str | None = None
) -> tuple[int, str, dict[str, Any]]:
    """Apply one plan with an injected GhClient.

    Returns (exit_code, text_output, json_output). `yes=False` is dry-run.
    `force=True` re-enables IssueCreate for locally-complete phases
    (overrides the completion guard — see `fr.diff.SuppressedCreate`).
    `to=<runner>` queues phases to a registry runner: queue lifecycle +
    `runner:<name>` labels are projected, and the reachability gate
    applies (remote runners pull the repo; plain tracking applies never
    pay it — super-fr split design).
    """
    try:
        report = build_plan_report(plan_dir, gh, force=force, queue_runner=to)
    except PlanSchemaError as e:
        return 5, f"parse error: {e}", {"plan": str(plan_dir), "parse_error": str(e)}

    plan = report.plan
    rendered = report.rendered
    d = report.diff

    parts = [report.header, _format_diff(d)]
    if d.suppressed:
        parts.append("\nrefused (completion guard):")
        for s in d.suppressed:
            parts.append(f"  phase {s.phase_number}: {s.reason}")
    if rendered.warnings:
        parts.append("\nwarnings:")
        for w in rendered.warnings:
            parts.append(f"  [{w.severity}] {w.message}")
    # Archive nudge — same gate as `fr archive`, so the surfaces agree.
    if not archive_gate(plan, report.observed):
        parts.append(
            f"\nplan complete — run `fr archive {plan.repo_relative_dir}` to move it "
            f"to implemented/."
        )

    json_out: dict[str, Any] = {
        "plan": plan.meta.plan,
        "mutations": [_mutation_to_json(m) for m in d.mutations],
        "suppressed": [{"phase_number": s.phase_number, "reason": s.reason} for s in d.suppressed],
        "warnings": [{"severity": w.severity, "message": w.message} for w in rendered.warnings],
        "applied": False,
        "failures": [],
        "created_issues": {},
        "tracking_issue_writeback_failures": [],
        "unreachable_paths": [],
        "unverifiable_inputs": [],
    }

    if not yes:
        return 0, "\n".join(parts), json_out

    # Completion-guard refusal: every would-be create was suppressed and no
    # Issue-level reconciliation remains (RepoLabelEnsure alone is vacuous).
    # Runs before the git gates — the refusal is about plan state, not git.
    meaningful = [m for m in d.mutations if not isinstance(m, RepoLabelEnsure)]
    if d.suppressed and not meaningful:
        lines = [
            parts[0],
            "",
            f"all {len(d.suppressed)} undispatched phase(s) are locally complete — "
            "nothing to dispatch.",
            "If this plan is done, run `fr archive` on it; to dispatch anyway, "
            "re-run with --force.",
        ]
        return 2, "\n".join(lines), json_out

    if to is None:
        # Tracking-only apply: no remote runner will pull this repo, so
        # the reachability gate doesn't apply (v3).
        return _do_mutations(plan_dir, gh, report, parts, json_out)

    if plan.repo_root is None:
        lines = [
            parts[0],
            "",
            "refuse to dispatch: plan is not in a git checkout — "
            "can't verify the plan is reachable to the runner's checkout.",
        ]
        return 2, "\n".join(lines), json_out

    try:
        missing = _check_plan_reachable_on_origin_head(plan, plan.repo_root)
    except WorkflowError as e:
        # The plan names a shape that does not resolve (§4.A.1). Reported on
        # its own, NOT through the origin/HEAD wrapper below: an operator
        # told to run `git remote set-head` for a typo'd workflow name would
        # be chasing the wrong thing entirely.
        lines = [
            parts[0],
            "",
            f"refuse to dispatch: {e}",
            "",
            "Author the shape under docs/superpowers/workflows/, or fix the "
            "`workflow:` key in the plan's _meta.yaml.",
        ]
        json_out["workflow_error"] = str(e)
        return 2, "\n".join(lines), json_out
    except Exception as e:  # noqa: BLE001 — wrap origin/HEAD errors with setup hint
        lines = [
            parts[0],
            "",
            f"refuse to dispatch: could not resolve origin/HEAD: {e}",
            "",
            "If origin/HEAD isn't set locally, run:",
            "  git remote set-head origin --auto",
        ]
        json_out["origin_head_error"] = str(e)
        return 2, "\n".join(lines), json_out
    unverifiable = _unverifiable_inputs_for(plan, plan.repo_root)
    if unverifiable:
        json_out["unverifiable_inputs"] = unverifiable
        parts.append("\nunverifiable offline (cross-repo; the operator is trusted for these):")
        parts.extend(f"  {ref}" for ref in unverifiable)

    if missing:
        lines = [
            parts[0],
            "",
            f"refuse to dispatch: {len(missing)} file(s) not at origin/HEAD:",
        ]
        for p in missing:
            lines.append(f"  {p}")
        lines.append("")
        lines.append(
            "Merge the plan + spec to the default branch first, then re-run `fr apply --yes`."
        )
        lines.append("(If origin/HEAD isn't set locally: `git remote set-head origin --auto`.)")
        json_out["unreachable_paths"] = [str(p) for p in missing]
        return 2, "\n".join(lines), json_out

    return _do_mutations(plan_dir, gh, report, parts, json_out)


def _do_mutations(
    plan_dir: Path,
    gh: GhClient,
    report: PlanReport,
    parts: list[str],
    json_out: dict[str, Any],
) -> tuple[int, str, dict[str, Any]]:
    """Execute the diffed mutations + tracking-issue writeback."""
    plan = report.plan
    d = report.diff
    result = apply(d, gh, plan=plan)
    writeback_failures: list[dict[str, Any]] = []
    for phase_n, url in result.created_issues.items():
        try:
            plan_ops.set_tracking_issue(plan_dir, phase_n, url)
        except (PlanEditError, OSError, PlanSchemaError) as e:
            writeback_failures.append({"phase_number": phase_n, "url": url, "error": str(e)})
    json_out["applied"] = True
    json_out["failures"] = [
        {"mutation": type(f.mutation).__name__, "error": f.error} for f in result.failures
    ]
    json_out["created_issues"] = {str(k): v for k, v in result.created_issues.items()}
    json_out["tracking_issue_writeback_failures"] = writeback_failures
    if result.failures:
        parts.append(f"\n{len(result.failures)} failure(s):")
        for f in result.failures:
            parts.append(f"  {type(f.mutation).__name__}: {f.error}")
    if writeback_failures:
        parts.append(f"\n{len(writeback_failures)} writeback failure(s):")
        for wf in writeback_failures:
            parts.append(
                f"  phase {wf['phase_number']}: writeback of "
                f"{wf['url']} failed: {wf['error']} "
                "(backfill `phase.tracking_issue` manually or re-run apply)"
            )
    if result.failures or writeback_failures:
        return 4, "\n".join(parts), json_out
    if result.created_issues:
        parts.append("\ncreated:")
        for phase_n, url in result.created_issues.items():
            parts.append(f"  phase {phase_n}: {url}")
    return 0, "\n".join(parts), json_out


def apply_command(
    plan_dir: Path | None = typer.Argument(None, help="Path to plan folder."),
    all_plans: bool = typer.Option(False, "--all", help="Walk all plans in current repo."),
    yes: bool = typer.Option(
        False,
        "--yes",
        help="Apply mutations. Without this flag, runs as a preview (dry-run is the default).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help=(
            "Override the completion guard: create Issues even for phases "
            "the plan marks locally complete (all steps ticked or "
            "completion.at set)."
        ),
    ),
    to: str | None = typer.Option(
        None,
        "--to",
        help=(
            "Queue phases to a registered runner (e.g. --to vk): adds the "
            "fr:* queue lifecycle + runner:<name> labels and enforces the "
            "reachability gate. Without --to, apply is tracking-only."
        ),
    ),
    output_format: str = typer.Option(
        "text",
        "--format",
        help="Output format: text (default, human-readable) or json.",
    ),
) -> None:
    """Apply a v2 plan to GitHub (render → observe → diff → mutate).

    Defaults to a preview. Pass --yes to actually mutate GitHub state.
    """
    require_migrated_layout()
    if all_plans and plan_dir is not None:
        err_console.print("--all and plan_dir are mutually exclusive")
        raise typer.Exit(2)
    if not all_plans and plan_dir is None:
        err_console.print("Either provide a plan_dir argument or use --all")
        raise typer.Exit(2)
    if output_format not in ("text", "json"):
        err_console.print(f"--format must be 'text' or 'json', got {output_format!r}")
        raise typer.Exit(2)

    if to is not None:
        # The one documented soft point (super-fr split design): dispatching
        # to a runner needs the fr-dispatch package; the base never imports
        # it otherwise.
        import importlib.util

        if importlib.util.find_spec("fr_dispatch") is None:
            err_console.print(
                "dispatching to a runner requires fr-dispatch — install it "
                "(e.g. `uv tool install --with fr-dispatch fr`) and re-run."
            )
            raise typer.Exit(2)
        from fr_dispatch.registry import runner_names

        names = runner_names()
        if to not in names:
            err_console.print(
                f"unknown runner {to!r} — registered runners: "
                + (", ".join(names) if names else "(none)")
            )
            raise typer.Exit(2)

    if all_plans:
        plans_dir = Path.cwd() / "docs" / "superpowers" / "plans"
        if not plans_dir.is_dir():
            err_console.print(f"plans dir not found: {plans_dir}")
            raise typer.Exit(2)
        targets = sorted(p for p in plans_dir.iterdir() if p.is_dir())
        if not targets:
            console.print("no plan folders found.")
            return
    else:
        assert plan_dir is not None
        # Refuse archived plans (#246): they are terminal, and apply would reopen
        # their already-closed Issues (agentic phases executed inline can never
        # satisfy the merged-PR completion signal). `--all` already walks only
        # plans/, so this guards the one remaining entry point — an explicit
        # `fr apply docs/superpowers/archived-plans/<plan>`. Anchored to the
        # canonical `superpowers/archived-plans` location so an unrelated dir
        # that merely happens to be named "archived-plans" isn't refused.
        resolved_parts = plan_dir.resolve().parts
        under_archived = any(
            resolved_parts[i] == "superpowers"
            and (
                resolved_parts[i + 1] == "archived-plans"
                or resolved_parts[i + 1 : i + 3] == ("implemented", "plans")
            )
            for i in range(len(resolved_parts) - 1)
        )
        if under_archived:
            err_console.print(
                f"refusing to apply archived/implemented plan: {plan_dir}\n"
                "Archived plans are terminal; applying one would reopen its closed "
                "Issues. (`fr apply --all` already walks only plans/.)"
            )
            raise typer.Exit(2)
        targets = [plan_dir]

    gh = _make_gh_client()
    overall_rc = 0
    json_results: list[dict[str, Any]] = []
    text_outputs: list[str] = []
    for t in targets:
        rc, text_output, json_output = _apply_one(t, gh, yes=yes, force=force, to=to)
        text_outputs.append(text_output)
        json_results.append(json_output)
        if rc != 0:
            overall_rc = max(overall_rc, rc)

    if output_format == "json":
        console.print_json(_json.dumps({"plans": json_results, "applied": yes}))
    else:
        for text_output in text_outputs:
            console.print(text_output)
        if not yes and overall_rc == 0:
            console.print("\n(dry-run; pass --yes to apply)")

    if overall_rc:
        raise typer.Exit(overall_rc)
