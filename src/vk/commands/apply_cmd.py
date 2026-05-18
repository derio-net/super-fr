"""`vk apply` CLI — render + observe + diff + apply for a plan.

Wires the library functions (`render`/`observe`/`diff`/`apply`) into
typer. Production uses `RealGhClient` (the gh-CLI wrapper); tests
inject `FakeGhClient` by monkeypatching `_make_gh_client`.

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

from vk import plan_ops
from vk.apply import apply
from vk.diff import (
    Diff,
    IssueBodyChange,
    IssueCreate,
    IssueLabelChange,
    IssueStateChange,
    RepoLabelEnsure,
    diff,
)
from vk.git import file_on_ref
from vk.observe import observe
from vk.parser import Plan, PlanSchemaError, parse
from vk.plan_ops import PlanEditError
from vk.render import render

if TYPE_CHECKING:
    from vk.ghclient import GhClient

console = Console()
err_console = Console(stderr=True)


def _make_gh_client() -> GhClient:
    """Factory hook for the GhClient. Tests monkeypatch this to inject FakeGhClient.

    Defaults to `RealGhClient` (subprocess wrapper around `gh`). Tests
    override by `monkeypatch.setattr(apply_cmd, "_make_gh_client", lambda: FakeGhClient())`.
    """
    from vk.real_ghclient import RealGhClient

    return RealGhClient()


def _check_plan_reachable_on_origin_head(plan: Plan, repo_root: Path) -> list[Path]:
    """Return plan files (and spec, if set) NOT present on origin/HEAD.

    Empty list = gate passes. Caller (`_apply_one`) refuses `--yes`
    when this returns non-empty.

    Raises if origin/HEAD isn't resolvable locally — caller catches
    and re-raises with a setup hint.
    """
    missing: list[Path] = []
    plan_dir = plan.dir
    for path in sorted(plan_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(repo_root)
        if not file_on_ref("origin/HEAD", str(rel), cwd=repo_root):
            missing.append(rel)
    if plan.meta.spec:
        # Cross-repo spec refs use `<owner>/<repo>:path/to/spec.md` notation
        # (e.g., the v2-bridge-cutover plan in agent-images references the
        # spec in superpowers-for-vk). The reachability check operates on
        # the LOCAL repo's git tree only; checking a file in a different
        # repo's tree from this repo's git is not meaningful — `git
        # ls-tree` would always return empty for the literal cross-repo
        # path. Skip the check for cross-repo specs; the operator is
        # trusted to keep the upstream spec correct.
        is_cross_repo = ":" in plan.meta.spec and "/" in plan.meta.spec.split(":", 1)[0]
        if not is_cross_repo:
            spec_rel = Path(plan.meta.spec)
            if not file_on_ref("origin/HEAD", str(spec_rel), cwd=repo_root):
                missing.append(spec_rel)
    return missing


def _format_diff(d: Diff) -> str:
    """Human-readable summary of mutations."""
    if not d.mutations:
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


def _apply_one(plan_dir: Path, gh: GhClient, *, yes: bool) -> tuple[int, str, dict[str, Any]]:
    """Apply one plan with an injected GhClient.

    Returns (exit_code, text_output, json_output). `yes=False` is dry-run.
    """
    try:
        plan = parse(plan_dir)
    except PlanSchemaError as e:
        return 5, f"parse error: {e}", {"plan": str(plan_dir), "parse_error": str(e)}

    observed = observe(plan, gh)
    rendered = render(plan, observed)
    d = diff(rendered, observed, plan=plan)

    parts = [f"plan: {plan.meta.plan}", _format_diff(d)]
    if rendered.warnings:
        parts.append("\nwarnings:")
        for w in rendered.warnings:
            parts.append(f"  [{w.severity}] {w.message}")

    json_out: dict[str, Any] = {
        "plan": plan.meta.plan,
        "mutations": [_mutation_to_json(m) for m in d.mutations],
        "warnings": [{"severity": w.severity, "message": w.message} for w in rendered.warnings],
        "applied": False,
        "failures": [],
        "created_issues": {},
        "tracking_issue_writeback_failures": [],
        "unreachable_paths": [],
    }

    if not yes:
        return 0, "\n".join(parts), json_out

    if plan.repo_root is None:
        lines = [
            parts[0],
            "",
            "refuse to dispatch: plan is not in a git checkout — "
            "can't verify the plan is reachable to the bridge or "
            "implementing agents.",
        ]
        return 2, "\n".join(lines), json_out

    try:
        missing = _check_plan_reachable_on_origin_head(plan, plan.repo_root)
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
            "Merge the plan + spec to the default branch first, then re-run `vk apply --yes`."
        )
        lines.append("(If origin/HEAD isn't set locally: `git remote set-head origin --auto`.)")
        json_out["unreachable_paths"] = [str(p) for p in missing]
        return 2, "\n".join(lines), json_out

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
    output_format: str = typer.Option(
        "text",
        "--format",
        help="Output format: text (default, human-readable) or json.",
    ),
) -> None:
    """Apply a v2 plan to GitHub (render → observe → diff → mutate).

    Defaults to a preview. Pass --yes to actually mutate GitHub state.
    """
    if all_plans and plan_dir is not None:
        err_console.print("--all and plan_dir are mutually exclusive")
        raise typer.Exit(2)
    if not all_plans and plan_dir is None:
        err_console.print("Either provide a plan_dir argument or use --all")
        raise typer.Exit(2)
    if output_format not in ("text", "json"):
        err_console.print(f"--format must be 'text' or 'json', got {output_format!r}")
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
        targets = [plan_dir]

    gh = _make_gh_client()
    overall_rc = 0
    json_results: list[dict[str, Any]] = []
    text_outputs: list[str] = []
    for t in targets:
        rc, text_output, json_output = _apply_one(t, gh, yes=yes)
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
