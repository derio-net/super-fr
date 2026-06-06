"""Shared CLI helpers — only `resolve_repo_root` survives the v1→v2 retirement."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fr.diff import Diff
    from fr.ghclient import GhClient
    from fr.parser import Plan
    from fr.states import GhState, RenderedState


def resolve_repo_root(cwd: Path | None = None) -> Path:
    """Resolve the repo root for a vk command.

    Honors `$VK_REPO_ROOT` first (so integration tests can point a
    command at `tmp_path` without spawning a fake git repo), then
    falls back to `git rev-parse --show-toplevel` (run from `cwd` if
    given), then to `Path.cwd()`.

    The returned path is always `.resolve()`-d so callers can safely
    use `Path.is_relative_to` / `Path.relative_to` against other
    resolved paths, even when the source value (env var, git output,
    or cwd) traversed a symlink.

    The empty string is treated like an unset env var (we fall through
    to git) — keeping `VK_REPO_ROOT=""` as a way to disable the
    override without unsetting it.
    """
    override = os.environ.get("VK_REPO_ROOT")
    if override:
        return Path(override).resolve()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        )
        return Path(result.stdout.strip()).resolve()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return (cwd or Path.cwd()).resolve()


def require_migrated_layout(repo_root: Path | None = None) -> None:
    """Hard-stop (exit 2) when the legacy archived-plans/ layout exists.

    2026-06-05 dispatch-guards spec: the canonical archive location is
    `docs/superpowers/implemented/{plans,specs}/`. Every verb that resolves
    the superpowers tree — read or mutating — refuses to run on a legacy
    layout so the migration happens at first use of the new version. (A
    banner would get overlooked; nothing here mutates, so a read verb
    refusing is still side-effect-free.) Exemptions: `fr migrate dirs`
    itself and verbs that never resolve the tree (isolation, init, skills,
    --version).

    No-op when there is no superpowers tree at all (e.g. running --help
    in an unrelated directory) — the guard targets repos that have plans.
    """
    root = repo_root if repo_root is not None else resolve_repo_root()
    sp = root / "docs" / "superpowers"
    legacy_dirs = [d for d in (sp / "archived-plans", sp / "archived-specs") if d.is_dir()]
    if legacy_dirs:
        import typer

        # Plain echo, not rich — rich soft-wraps and can split the
        # copy-pasteable `fr migrate dirs --yes` across lines.
        for d in legacy_dirs:
            typer.echo(f"legacy layout detected: {d}", err=True)
        typer.echo(
            "The archive location moved to docs/superpowers/implemented/. "
            "Run `fr migrate dirs --yes`, then commit the rename.",
            err=True,
        )
        raise typer.Exit(2)


# ---------------------------------------------------------------------------
# Shared read path for `fr apply` (dry-run) and `fr status` — extracting it
# means the two verbs can never drift (2026-06-05 spec, "New CLI verbs").


def plan_header(plan: Plan) -> str:
    """One factual line: created date + age, tick counts, dispatch state.

    Information, not heuristics (2026-06-05 postmortem): a month-old
    never-dispatched plan announces itself without any threshold machinery.
    Age formatting lives here in the CLI layer so the render/diff chain
    stays clock-free and pure.
    """
    import datetime as _dt

    created = plan.meta.created
    age = ""
    try:
        days = (_dt.date.today() - _dt.date.fromisoformat(created)).days
        age = f" ({days} days ago)"
    except ValueError:
        pass
    total = sum(len(p.state.steps) for p in plan.phases)
    ticked = sum(1 for p in plan.phases for s in p.state.steps.values() if s.state in ("x", "-"))
    dispatched = sum(1 for p in plan.phases if p.phase.tracking_issue)
    if dispatched == 0:
        dispatch_state = "never dispatched"
    else:
        dispatch_state = f"{dispatched}/{len(plan.phases)} phases dispatched"
    return (
        f"plan: {plan.meta.plan} · created {created}{age} · "
        f"{ticked}/{total} steps · {dispatch_state}"
    )


@dataclass(frozen=True)
class PlanReport:
    """Everything the read path produces for one plan."""

    plan: Plan
    observed: GhState
    rendered: RenderedState
    diff: Diff
    header: str


def build_plan_report(plan_dir: Path, gh: GhClient, *, force: bool = False) -> PlanReport:
    """parse -> observe -> render -> diff, no mutations.

    Raises PlanSchemaError; callers map it to exit 5.
    """
    from fr.diff import diff as _diff
    from fr.observe import observe as _observe
    from fr.parser import parse as _parse
    from fr.render import render as _render

    plan = _parse(plan_dir)
    observed = _observe(plan, gh)
    rendered = _render(plan, observed)
    d = _diff(rendered, observed, plan=plan, force_create=force)
    return PlanReport(
        plan=plan, observed=observed, rendered=rendered, diff=d, header=plan_header(plan)
    )
