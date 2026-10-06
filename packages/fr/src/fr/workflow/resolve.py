"""Workflow shape resolution — repo > shipped (spec §4.A, Phase 6).

Mirrors `fr.models`' repo-over-user precedent:

    docs/superpowers/workflows/<name>.yaml     # repo override / repo-authored
    plugins/super-fr/workflows/<name>.yaml     # shipped

`fr-goal` with no argument resolves `fr-goal`; `fr-goal ux-research`
resolves that name through the same order. Override is WHOLESALE — a repo
file of a given name is used exactly as parsed, never merged field-by-field
or step-by-step with the shipped manifest of the same name.

**Where "shipped" lives at runtime — three places, in this order.** Unlike
`fr.models` (a small harness→tier→model dict a repo or operator can plausibly
hand-author), shipped *workflow manifests* travel with the super-fr plugin's
own source tree (`plugins/super-fr/workflows/` — see the CI tripwire in
`tests/unit/test_tripwire_shipped_workflows.py`) and are not something a
consumer repo's checkout contains. So the lookup is:

1. `docs/superpowers/workflows/<name>.yaml` — the repo's own override, which
   wins wholesale;
2. `$FR_SHIPPED_WORKFLOWS_DIR/<name>.yaml` when that variable is set — the
   explicit escape, for tests and for any harness that is not Claude Code;
3. the copy **inside the `fr` wheel** (`fr/workflows/`,
   `packaged_shipped_workflows_dir()`) — version-matched with the running
   `fr` by construction;
4. `~/.claude/plugins/marketplaces/derio-net--super-fr/plugins/super-fr/
   workflows/<name>.yaml` — the Claude Code plugin clone
   (`default_shipped_workflows_dir()`, the same marketplace-clone convention
   `fr.plan_validator_wrapper` and `fr.isolation.local` use).

**Step 3 exists because steps 1, 2 and 4 are all absent by default on a
non-Claude-Code host** (review r5-b5). A hermes pod gets hooks and a SOUL
block from `fr hermes install`, not a marketplace clone; an OpenCode consumer
never has one either; and `$FR_SHIPPED_WORKFLOWS_DIR` was documented nowhere
operator-facing. Verified on a clean `uv tool install` with an empty `HOME`:
`fr run start fr-goal` failed with "unknown workflow shape", and `fr workflow
check --all` reported "no workflow shapes found" *and exited 0*, so smoke step
§8.0.3 passed while nothing was installed.

**Step 3 comes BEFORE step 4** (review r5-e14). The wheel copy ships with the
`fr` that will execute the shape, so it can never disagree with the code
reading it; the marketplace clone is updated independently and an operator who
upgrades `fr` without re-running `install.sh` would otherwise keep resolving a
**stale** shape — silently, at the wrong granularity. An operator who really
does want the clone to win still has step 2, which is explicit and therefore
cannot surprise anyone.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from fr import _shipped
from fr._shipped import MARKETPLACE_ROOT
from fr.workflow.model import WorkflowError, WorkflowManifest, parse_manifest

if TYPE_CHECKING:
    from fr.parser import Plan

REPO_WORKFLOWS_REL = Path("docs") / "superpowers" / "workflows"
SHIPPED_WORKFLOWS_REL = Path("plugins") / "super-fr" / "workflows"


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


PACKAGED_WORKFLOWS_DIRNAME = "workflows"
"""The wheel-internal copy of `plugins/super-fr/workflows/`, as `fr/workflows/`.

Generated, never hand-edited — `packages/fr/src/fr/workflows/README.md` says
so and `tests/unit/test_tripwire_shipped_workflows.py` fails when it diverges
from the plugin directory. Addressed as a data DIRECTORY under the `fr`
package rather than as `fr.workflows`: it carries no `__init__.py` (it is
data, not code), so `resources.files("fr.workflows")` would raise
`ModuleNotFoundError` on a normal install.
"""


def packaged_shipped_workflows_dir() -> Path | None:
    """The shipped manifests that travel inside the `fr` wheel, or `None`.

    The materialisation (zip-safe `as_file`, process-lifetime extraction) is
    `fr._shipped.packaged_dir`'s; `None` means "this source contributes
    nothing", never an error.
    """
    return _shipped.packaged_dir(PACKAGED_WORKFLOWS_DIRNAME)


def shipped_workflow_dirs(shipped_root: Path | None = None) -> list[Path]:
    """The shipped sources, in lookup order (see the module docstring).

    An explicit `shipped_root` (or `$FR_SHIPPED_WORKFLOWS_DIR`) wins outright:
    it is what a test or a non-Claude-Code harness set on purpose. Otherwise
    the wheel's own copy comes first and the marketplace clone last, so an
    `fr` upgrade cannot be shadowed by a clone nobody re-installed.

    One list, built once, so `resolve_workflow` and `fr workflow check --all`
    cannot search different places — a discovery that finds a shape the
    resolver would not (or the reverse) is exactly how "`--all` is green but
    the run fails" happens.
    """
    return _shipped.shipped_dirs(
        env_var="FR_SHIPPED_WORKFLOWS_DIR",
        plugin_rel=SHIPPED_WORKFLOWS_REL,
        packaged=packaged_shipped_workflows_dir(),
        shipped_root=shipped_root,
    )


def resolve_workflow(
    name: str, repo_root: Path, *, shipped_root: Path | None = None
) -> WorkflowManifest:
    """Resolve shape `name`: a repo-authored manifest wins wholesale over the
    shipped one of the same name; falls back to shipped when absent.

    Raises `WorkflowError` naming EVERY searched path when none exists, so
    the operator sees exactly where to put an override — and, when the shape
    was expected to be shipped, which installation is missing it.
    """
    candidates = _shipped.lookup_candidates(
        name, repo_root / REPO_WORKFLOWS_REL, shipped_workflow_dirs(shipped_root)
    )

    for path in candidates:
        if path.is_file():
            return parse_manifest(path.read_text())

    searched = " and ".join(str(p) for p in candidates)
    raise WorkflowError(f"unknown workflow shape {name!r} — searched {searched}")


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
