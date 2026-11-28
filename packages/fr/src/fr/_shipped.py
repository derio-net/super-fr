"""The shipped-defaults directory walk, shared by every "repo > shipped" lookup.

super-fr's shipped defaults have one home (spec 2026-11-19-event-driven-a-la-carte
R15): `plugins/super-fr/defaults/<kind>/` for `workflows`, `verifications` and
`lenses`, with one wheel copy at `fr/defaults/<kind>/` (written by
`scripts/sync-defaults-data.py`, guarded by
`tests/unit/test_tripwire_shipped_defaults.py`). `fr.workflow.resolve`,
`fr.verification.resolve` and `fr.lenses.resolve` all search, for a kind:

1. the repo's own directory, `.fr/<kind>/` (workflows and verifications only; the
   caller prepends it, and under quiet/stealth reads it through
   `fr.config.degraded`, whose fallback is this shipped walk);
2. `$FR_SHIPPED_DEFAULTS_DIR/<kind>/` when set (R16);
3. the per-kind `$FR_SHIPPED_<KIND>_DIR` when set, before fr 9.2 only, with one
   notice per process naming `FR_SHIPPED_DEFAULTS_DIR`; past the end of S1's
   transition (`fr.config.transition`) a set one is refused through the kind's own
   error type (spec 2026-11-28-s1-followups R6);
4. the copy inside the `fr` wheel (`fr/defaults/<kind>/`);
5. the Claude Code marketplace clone
   (`~/<MARKETPLACE_ROOT>/plugins/super-fr/defaults/<kind>/`).

The per-kind docstrings own the *why* of the order (a wheel copy before the
marketplace clone, an explicit env override first); this module owns the mechanics.
"""

from __future__ import annotations

import atexit
import contextlib
import os
import sys
from collections.abc import Callable
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
        root = resources.files("fr").joinpath(*dirname.split("/"))
        if root.is_dir():
            resolved = Path(_RESOURCE_STACK.enter_context(resources.as_file(root)))
    except ModuleNotFoundError, FileNotFoundError, TypeError, OSError:
        resolved = None
    _PACKAGED_CACHE[dirname] = resolved if (resolved and resolved.is_dir()) else None
    return _PACKAGED_CACHE[dirname]


DEFAULTS_ENV_VAR = "FR_SHIPPED_DEFAULTS_DIR"
"""One variable pointing the resolver at another defaults tree, holding `<kind>/` (R16)."""

LEGACY_ENV_VARS: dict[str, str] = {
    "workflows": "FR_SHIPPED_WORKFLOWS_DIR",
    "verifications": "FR_SHIPPED_VERIFICATIONS_DIR",
    "lenses": "FR_SHIPPED_LENSES_DIR",
}
"""The per-kind variables S1 replaces. Each names a flat directory of that kind's
manifests and works only before fr 9.2 (`fr.config.transition.refusing`)."""

KINDS: tuple[str, ...] = tuple(LEGACY_ENV_VARS)

PLUGIN_DEFAULTS_REL = Path("plugins") / "super-fr" / "defaults"
"""The canonical tree, relative to a super-fr checkout or the marketplace clone."""

PACKAGED_DEFAULTS_DIRNAME = "defaults"
"""The wheel copy, `fr/defaults/`, addressed as data under the `fr` package."""

_LEGACY_NOTICED: set[str] = set()
"""Legacy variables this process has already named (one notice per command)."""


def _kind(kind: str) -> str:
    if kind not in LEGACY_ENV_VARS:
        raise ValueError(f"unknown shipped-defaults kind {kind!r}: one of {', '.join(KINDS)}")
    return kind


def plugin_rel(kind: str) -> Path:
    """`plugins/super-fr/defaults/<kind>`."""
    return PLUGIN_DEFAULTS_REL / _kind(kind)


def marketplace_dir(kind: str) -> Path:
    """The marketplace clone's `<kind>` directory, under the current home."""
    return Path.home() / MARKETPLACE_ROOT / plugin_rel(kind)


def packaged_kind_dir(kind: str) -> Path | None:
    """`fr/defaults/<kind>/` inside the wheel, or `None` (see `packaged_dir`)."""
    return packaged_dir(f"{PACKAGED_DEFAULTS_DIRNAME}/{_kind(kind)}")


def _legacy_dir(kind: str) -> Path | None:
    """The per-kind variable's directory before fr 9.2 (with one notice); past the end
    of S1's transition a set one raises `fr.config.transition.LegacyEnvRefused`."""
    var = LEGACY_ENV_VARS[kind]
    value = os.environ.get(var)
    if not value:
        return None
    from fr.config import transition  # lazily: it needs fr.settings

    if transition.refusing():
        raise transition.LegacyEnvRefused(
            f"${var} is no longer read (fr 9.2 ended S1's transition): set "
            f"${DEFAULTS_ENV_VAR} to a tree holding {kind}/ instead, so "
            f"{DEFAULTS_ENV_VAR}/{kind}/ holds these manifests"
        )
    if var not in _LEGACY_NOTICED:
        _LEGACY_NOTICED.add(var)
        print(
            f"fr: ${var} is deprecated; set ${DEFAULTS_ENV_VAR} to a tree holding "
            f"{kind}/ instead (the per-kind variables stop working in fr 9.2)",
            file=sys.stderr,
        )
    return Path(value)


def env_dirs(kind: str) -> list[Path]:
    """The variable-named sources for *kind*, in order (steps 2-3 of the module docstring)."""
    dirs: list[Path] = []
    root = os.environ.get(DEFAULTS_ENV_VAR)
    if root:
        dirs.append(Path(root) / _kind(kind))
    legacy = _legacy_dir(_kind(kind))
    if legacy is not None:
        dirs.append(legacy)
    return dirs


def shipped_dirs(
    kind: str,
    *,
    packaged: Path | None,
    shipped_root: Path | None = None,
    error: Callable[[str], Exception] | None = None,
) -> list[Path]:
    """The shipped sources for *kind*, in lookup order (steps 2-5 of the module docstring).

    An explicit `shipped_root` (a flat directory of manifests) replaces both variables:
    it is what a test set on purpose. Otherwise the variables come first, then the
    wheel's own copy, and the marketplace clone last, so an `fr` upgrade cannot be
    shadowed by a clone nobody re-installed. *packaged* is the caller's wheel directory
    (normally `packaged_kind_dir(kind)`), passed in so a test can replace it.

    *error* is the caller's own error type: a per-kind variable refused past the end of
    S1's transition is re-raised as it, so each kind's commands report it as they report
    every other resolver failure (exit 2, spec 2026-11-28-s1-followups R6).
    """
    if shipped_root is not None:
        dirs: list[Path] = [shipped_root]
    else:
        from fr.config.transition import LegacyEnvRefused

        try:
            dirs = env_dirs(kind)
        except LegacyEnvRefused as e:
            if error is None:
                raise
            raise error(str(e)) from e
    if packaged is not None:
        dirs.append(packaged)
    marketplace = marketplace_dir(kind)
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
