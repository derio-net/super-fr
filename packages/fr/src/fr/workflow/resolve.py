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

from fr.workflow.model import WorkflowError, WorkflowManifest, parse_manifest

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
