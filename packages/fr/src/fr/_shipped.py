"""The shipped-resource directory walk, shared by every "repo > shipped" lookup.

`fr.workflow.resolve` (shape manifests) and `fr.verification.resolve`
(verification strategies) search the same four places in the same order; the
walk lives here once so the two cannot drift. The per-kind docstrings own the
*why* of the order (a wheel copy before the marketplace clone, an explicit env
override first); this module owns only the mechanics.

1. the repo's own directory (the caller prepends it — it is repo-relative);
2. `$<ENV_VAR>` when set;
3. the copy inside the `fr` wheel (`fr/<dirname>/`);
4. the Claude Code marketplace clone (`~/<MARKETPLACE_ROOT>/<plugin_rel>`).
"""

from __future__ import annotations

import atexit
import contextlib
import os
from importlib import resources
from pathlib import Path

MARKETPLACE_ROOT = Path(".claude") / "plugins" / "marketplaces" / "derio-net--super-fr"
"""The Claude Code marketplace-clone convention every "shipped resource"
lookup in this package uses (`fr.plan_validator_wrapper`,
`fr.isolation.local`). Public (no leading `_`) so a test can build the
expected default path by composing this constant instead of retyping the
literal string — one rename, one place to fix, given this repo has already
survived one marketplace rename (AGENTS.md, "Marketplace names are
`<org>--<repo>`")."""

_RESOURCE_STACK = contextlib.ExitStack()
atexit.register(_RESOURCE_STACK.close)
"""Keeps an `as_file` extraction alive for the process's lifetime.

A zipped install has no real `fr/<dirname>/` directory; `as_file` makes one,
and it exists only until its context closes. Callers read the manifests after
`packaged_dir()` returns, so the context has to outlive the call — process
lifetime is the honest scope, and `atexit` cleans it up.
"""

_PACKAGED_CACHE: dict[str, Path | None] = {}
"""Memoised per dirname: on a zipped install `as_file` extracts, which is not
free, and this is consulted on every lookup. `None` is a legitimate cached
ANSWER ("this install ships no such data"), hence a dict, not a sentinel."""


def packaged_dir(dirname: str) -> Path | None:
    """`fr/<dirname>/` materialised through `importlib.resources.as_file`, or `None`.

    Not assumed to live on the filesystem: a zipped wheel (`zipimport`, a PEX,
    a frozen bundle) has no real directory, and `as_file` extracts one. The
    directory carries no `__init__.py` (it is data), so it is addressed as a
    child of the `fr` package, never as `fr.<dirname>`.

    `None` when the install has no such data (an older wheel, or a loader that
    cannot produce a path at all) — callers treat that as "this source
    contributes nothing", never as an error.
    """
    if dirname in _PACKAGED_CACHE:
        return _PACKAGED_CACHE[dirname]

    resolved: Path | None = None
    try:
        root = resources.files("fr") / dirname
        if root.is_dir():
            resolved = Path(_RESOURCE_STACK.enter_context(resources.as_file(root)))
    except (ModuleNotFoundError, FileNotFoundError, TypeError, OSError):
        resolved = None
    _PACKAGED_CACHE[dirname] = resolved if (resolved and resolved.is_dir()) else None
    return _PACKAGED_CACHE[dirname]


def shipped_dirs(
    *,
    env_var: str,
    plugin_rel: Path,
    packaged: Path | None,
    shipped_root: Path | None = None,
) -> list[Path]:
    """The shipped sources, in lookup order (steps 2-4 of the module docstring).

    An explicit `shipped_root` (or `$env_var`) wins outright: it is what a test
    or a non-Claude-Code harness set on purpose. Otherwise the wheel's own copy
    comes first and the marketplace clone last, so an `fr` upgrade cannot be
    shadowed by a clone nobody re-installed.
    """
    dirs: list[Path] = []
    if shipped_root is not None:
        dirs.append(shipped_root)
    else:
        override = os.environ.get(env_var)
        if override:
            dirs.append(Path(override))
    if packaged is not None:
        dirs.append(packaged)
    marketplace = Path.home() / MARKETPLACE_ROOT / plugin_rel
    if marketplace not in dirs:
        dirs.append(marketplace)
    return dirs


def lookup_candidates(
    name: str, repo_dir: Path, shipped: list[Path], suffix: str = ".yaml"
) -> list[Path]:
    """Every path `name` could resolve to, repo first. Callers take the first file."""
    return [repo_dir / f"{name}{suffix}"] + [d / f"{name}{suffix}" for d in shipped]


def listing(repo_dir: Path, shipped: list[Path]) -> list[tuple[str, Path]]:
    """`(name, directory)` for every manifest, each name once, nearest source wins."""
    seen: dict[str, Path] = {}
    for d in [repo_dir, *shipped]:
        if d.is_dir():
            for p in sorted(d.glob("*.yaml")):
                seen.setdefault(p.stem, d)
    return sorted(seen.items())
