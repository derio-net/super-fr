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

import atexit
import contextlib
import os
from importlib import resources
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


_RESOURCE_STACK = contextlib.ExitStack()
atexit.register(_RESOURCE_STACK.close)
"""Keeps an `as_file` extraction alive for the process's lifetime.

A zipped install has no real `fr/workflows/` directory; `as_file` makes one,
and it exists only until its context closes. Callers read the manifests after
`packaged_shipped_workflows_dir()` returns, so the context has to outlive the
call — process lifetime is the honest scope, and `atexit` cleans it up.
"""

_PACKAGED_DIR_CACHE: Path | None = None
_PACKAGED_DIR_CACHED = False
"""Memoised: on a zipped install `as_file` extracts, which is not free, and
this is consulted on every shape lookup. Two names rather than a sentinel
object because `None` is a legitimate cached ANSWER ("this install ships no
packaged workflows"), not merely "not looked up yet"."""

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

    Materialised through `importlib.resources.as_file`, not by assuming the
    package lives on the filesystem: a zipped wheel (`zipimport`, a PEX, a
    frozen bundle) has no real directory, and `as_file` extracts one. The
    extraction is registered on an `atexit`-scoped `ExitStack` rather than
    closed immediately, because the caller reads the files AFTER this returns
    — closing the context first would delete the very directory being handed
    back.

    `None` when the install has no `fr/workflows/` data (an older wheel, or a
    loader that cannot produce a path at all). Callers treat that as "this
    source contributes nothing", never as an error.
    """
    global _PACKAGED_DIR_CACHE, _PACKAGED_DIR_CACHED
    if _PACKAGED_DIR_CACHED:
        return _PACKAGED_DIR_CACHE

    resolved: Path | None = None
    try:
        root = resources.files("fr") / PACKAGED_WORKFLOWS_DIRNAME
        if root.is_dir():
            resolved = Path(_RESOURCE_STACK.enter_context(resources.as_file(root)))
    except (ModuleNotFoundError, FileNotFoundError, TypeError, OSError):
        resolved = None
    _PACKAGED_DIR_CACHE = resolved if (resolved and resolved.is_dir()) else None
    _PACKAGED_DIR_CACHED = True
    return _PACKAGED_DIR_CACHE


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
    dirs: list[Path] = []
    if shipped_root is not None:
        dirs.append(shipped_root)
    else:
        override = os.environ.get("FR_SHIPPED_WORKFLOWS_DIR")
        if override:
            dirs.append(Path(override))
    packaged = packaged_shipped_workflows_dir()
    if packaged is not None:
        dirs.append(packaged)
    marketplace = Path.home() / MARKETPLACE_ROOT / SHIPPED_WORKFLOWS_REL
    if marketplace not in dirs:
        dirs.append(marketplace)
    return dirs


def resolve_workflow(
    name: str, repo_root: Path, *, shipped_root: Path | None = None
) -> WorkflowManifest:
    """Resolve shape `name`: a repo-authored manifest wins wholesale over the
    shipped one of the same name; falls back to shipped when absent.

    Raises `WorkflowError` naming EVERY searched path when none exists, so
    the operator sees exactly where to put an override — and, when the shape
    was expected to be shipped, which installation is missing it.
    """
    repo_path = repo_root / REPO_WORKFLOWS_REL / f"{name}.yaml"
    candidates = [repo_path] + [d / f"{name}.yaml" for d in shipped_workflow_dirs(shipped_root)]

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
