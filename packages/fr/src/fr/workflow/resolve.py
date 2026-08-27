"""Workflow shape resolution — repo > shipped (spec §4.A, Phase 6).

Mirrors `fr.models`' repo-over-user precedent:

    docs/superpowers/workflows/<name>.yaml     # repo override / repo-authored
    plugins/super-fr/workflows/<name>.yaml     # shipped

`fr-goal` with no argument resolves `fr-goal`; `fr-goal ux-research`
resolves that name through the same order. Override is WHOLESALE — a repo
file of a given name is used exactly as parsed, never merged field-by-field
or step-by-step with the shipped manifest of the same name.

**Where "shipped" lives at runtime.** Unlike `fr.models` (a small
harness→tier→model dict a repo or operator can plausibly hand-author),
shipped *workflow manifests* travel with the super-fr plugin's own source
tree (`plugins/super-fr/workflows/` — see the CI tripwire in
`tests/unit/test_tripwire_shipped_workflows.py`) and are not something a
consumer repo's checkout contains. The installed copy lives wherever the
Claude Code plugin was installed — `default_shipped_workflows_dir()`
follows the same marketplace-clone convention as
`fr.plan_validator_wrapper` and `fr.isolation.local`
(`~/.claude/plugins/marketplaces/derio-net--super-fr/...`), overridable via
`$FR_SHIPPED_WORKFLOWS_DIR` for tests and any non-Claude-Code harness.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from fr.workflow.model import WorkflowError, WorkflowManifest, parse_manifest

if TYPE_CHECKING:
    from fr.parser import Plan

REPO_WORKFLOWS_REL = Path("docs") / "superpowers" / "workflows"
SHIPPED_WORKFLOWS_REL = Path("plugins") / "super-fr" / "workflows"

MARKETPLACE_ROOT = Path(".claude") / "plugins" / "marketplaces" / "derio-net--super-fr"
"""The Claude Code marketplace-clone convention every "shipped resource"
lookup in this package uses (`fr.plan_validator_wrapper`,
`fr.isolation.local`). Public (no leading `_`) so a test can build the
expected default path by composing this constant instead of retyping the
literal string — one rename, one place to fix, given this repo has already
survived one marketplace rename (AGENTS.md, "Marketplace names are
`<org>--<repo>`")."""


def default_shipped_workflows_dir() -> Path:
    """Where shipped manifests live once the plugin is installed.

    Honors `$FR_SHIPPED_WORKFLOWS_DIR` first — tests, and any harness that
    is not Claude Code, can point this anywhere — then falls back to the
    marketplace clone path every other "shipped resource" lookup in this
    package already uses.
    """
    override = os.environ.get("FR_SHIPPED_WORKFLOWS_DIR")
    if override:
        return Path(override)
    return Path.home() / MARKETPLACE_ROOT / SHIPPED_WORKFLOWS_REL


def resolve_workflow(
    name: str, repo_root: Path, *, shipped_root: Path | None = None
) -> WorkflowManifest:
    """Resolve shape `name`: a repo-authored manifest wins wholesale over the
    shipped one of the same name; falls back to shipped when absent.

    Raises `WorkflowError` naming BOTH searched paths when neither exists,
    so the operator sees exactly where to put an override.
    """
    shipped_dir = shipped_root if shipped_root is not None else default_shipped_workflows_dir()
    repo_path = repo_root / REPO_WORKFLOWS_REL / f"{name}.yaml"
    shipped_path = shipped_dir / f"{name}.yaml"

    for path in (repo_path, shipped_path):
        if path.is_file():
            return parse_manifest(path.read_text())

    raise WorkflowError(
        f"unknown workflow shape {name!r} — searched {repo_path} and {shipped_path}"
    )


def workflow_for_plan(
    plan: Plan, repo_root: Path | None = None, *, shipped_root: Path | None = None
) -> WorkflowManifest:
    """The shape `plan` dispatches at (spec §4.A.1, Phase 12).

    `resolve_workflow` answers "given a name, which manifest?"; this
    answers the prior question dispatch actually asks — "given a plan on
    disk, which name?" — by reading `_meta.yaml`'s optional `workflow:`
    key and running it through the SAME repo > shipped lookup. There is
    no second search order and no second default constant.

    **No key means exactly today's behaviour**: `FR_GOAL_PHASE_DISPATCH`,
    the identical object `tick` and `fr apply --to` have always defaulted
    to, returned without touching the filesystem. That is what lets the
    live bridge keep ticking every pre-Phase-12 plan through the upgrade,
    and why a plan with no shape needs no `repo_root` at all.

    **A named shape that does not resolve raises `WorkflowError`** naming
    the plan and both searched paths — it is NEVER a fallback to the
    default. Falling back would dispatch a plan at the wrong granularity
    while reporting success, which is the failure mode this design has
    produced most often. For the same reason, a named shape with no repo
    root to search raises rather than quietly resolving only the shipped
    half of the order and calling that resolution.

    `repo_root` defaults to `plan.repo_root` — the bridge holds a `Plan`
    and no separate root, and a plan parsed inside a repo already knows
    where its overrides live.
    """
    from fr.workflow.shapes import FR_GOAL_PHASE_DISPATCH

    name = plan.meta.workflow
    if name is None:
        return FR_GOAL_PHASE_DISPATCH

    root = repo_root if repo_root is not None else plan.repo_root
    if root is None:
        raise WorkflowError(
            f"plan {plan.meta.plan!r} names workflow shape {name!r} but its repo root "
            f"is unknown — cannot search repo-authored shapes under "
            f"{REPO_WORKFLOWS_REL}"
        )

    try:
        return resolve_workflow(name, root, shipped_root=shipped_root)
    except WorkflowError as e:
        raise WorkflowError(f"plan {plan.meta.plan!r}: {e}") from e
