"""The configuration space resolver (spec 2026-11-19-event-driven-a-la-carte S1, #1653, §A).

Repo configuration lives in one `.fr/` directory at the root of the run's
**configuration space** (R1). This module is the one place that decides where that is
(R2); every reader of repo configuration asks it, and the tripwire
`tests/unit/test_tripwire_config_space.py` refuses a `.fr` path built anywhere else.

| Placement | `dir` (working-tree reads) | `default_ref` (reads at a commit) |
|---|---|---|
| `repo` | `<product checkout>/.fr` | `origin/<default>` |
| `quiet` | `~/.cache/fr/worktrees/<main checkout>/fr-config/.fr` | `origin/fr-config` |
| `stealth` | `<config clone>/<target-dir>/.fr` | `origin/<branch>-config` in that clone |

The stealth configuration clone is `~/.cache/fr/worktrees/<repo>/stealth--<slug>-config`,
beside the tracking clone. Both paths are computed here and nowhere else. fr's memory does
not move (`fr.artifacts.paths.space_for` still answers it).

Three reads: `ConfigSpace.dir` for working-tree readers, `at_default(rel)` for readers at the
default branch, and `at_pair(rel, base, head)` for readers that compare a branch with its
base. Under `quiet` and `stealth` a feature branch cannot change configuration, so
`at_pair` reads the configuration branch's tip for both sides (R3).

Under `quiet` and `stealth` the product checkout's own `.fr/` is ignored, except
`isolation-allow` (R8), and the first resolution in a process for that checkout prints
one stderr line naming the ignored files (R4).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping

_REPO: Final = "repo"
_QUIET: Final = "quiet"
_STEALTH: Final = "stealth"
"""The placements (`fr.artifacts.paths.REPO`, `QUIET`, `STEALTH`), named here so that
importing this module pulls in nothing: settings and lens parsing import it."""

SPACE_DIR: Final = ".fr"
"""The configuration directory's name at the root of every configuration space."""
CONFIG_BRANCH: Final = "fr-config"
"""Under quiet, the configuration branch (and its worktree's name)."""
CONFIG_SUFFIX: Final = "-config"
"""Under stealth, the configuration branch is the tracking `<branch>` plus this suffix, and
the configuration clone is the tracking clone's name plus it."""
ALLOWLIST: Final = "isolation-allow"
"""The base-clone edit allowlist: read in the product checkout under every placement (R8)."""

SPACE_FILES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "settings": "settings.yaml",
        "ci": "ci.yaml",
        "docs": "docs.yaml",
        "lenses": "lenses.yaml",
        "triage": "triage.yaml",
        "ops": "ops.yaml",
        "debt": "debt.yaml",
        "candidate-install": "candidate-install",
    }
)
"""key -> file name below `.fr/`: the configuration files readers name by key."""

PRODUCT_TRIAGE_STATE: Final = f"{SPACE_DIR}/triage-state"
"""Triage's working state below a product clone (`fr.triage.model.state_dir`). It is state,
not configuration, and S1's triage phase moves it to the host cache (R17); until then the
path is named here so no other module builds a `.fr` path."""


def rel(name: str) -> str:
    """The configuration file *name* (`ci.yaml`, or a key of `SPACE_FILES`) as a path
    relative to its space's root: `.fr/ci.yaml`."""
    below = _below(name)
    return f"{SPACE_DIR}/{below}" if below else SPACE_DIR


def _below(name: str) -> str:
    """*name* (`ci.yaml`, a `SPACE_FILES` key, or `.fr/ci.yaml`) relative to `.fr/`."""
    name = name.removeprefix("./")
    if name == SPACE_DIR:
        return ""
    name = name.removeprefix(f"{SPACE_DIR}/")
    return SPACE_FILES.get(name, name)


@dataclass(frozen=True)
class ConfigSpace:
    """Where one checkout's repo configuration lives (R1).

    `placement` is `repo`, `quiet` or `stealth`; `dir` is the `.fr/` directory working-tree
    readers read; `checkout` is the git checkout holding it (the product checkout, the
    `fr-config` worktree, or the stealth configuration clone); `product` is the product
    checkout the space was resolved for. `ref` is the configuration branch's
    remote-tracking name (None under `repo`, where the default branch is read live);
    `prefix` is `.fr`'s path inside the checkout's tree (`<target-dir>/.fr` under stealth)."""

    placement: str
    dir: Path
    checkout: Path
    product: Path
    ref: str | None = None
    prefix: str = SPACE_DIR

    @property
    def default_ref(self) -> str | None:
        """The ref reads at a commit use: `origin/<default>` under `repo` (None when the
        repo has no default branch fr can name), the configuration branch otherwise."""
        if self.ref is not None:
            return self.ref
        qualified = _default_qualified(self.product)
        if qualified is None:
            return None
        return qualified.removeprefix("refs/remotes/").removeprefix("refs/heads/")

    def file(self, name: str) -> Path:
        """The working-tree path of configuration file *name* (`ci.yaml`, a `SPACE_FILES`
        key, or `.fr/ci.yaml`)."""
        below = _below(name)
        return self.dir / below if below else self.dir

    def tree_path(self, name: str) -> str:
        """*name*'s path inside its checkout's tree: `.fr/<file>`, or under stealth
        `<target-dir>/.fr/<file>`."""
        below = _below(name)
        return f"{self.prefix}/{below}" if below else self.prefix

    def at_default(self, name: str) -> str | None:
        """*name* as the default ref has it (None: absent, or no such ref yet). Raises
        `SettingsError` on a git failure, which never reads as absent."""
        from fr.settings.load import read_at_default, show_at_commit

        path = self.tree_path(name)
        if self.ref is None:
            return read_at_default(self.product, path)
        repo = self._git_repo()
        if repo is None:
            return None
        sha = _commit(repo, f"refs/remotes/{self.ref}")
        return None if sha is None else show_at_commit(repo, sha, path)

    def at_pair(self, name: str, base: str, head: str) -> tuple[str | None, str | None]:
        """*name* at *base* and at *head* (R3). Under `repo` those are the two commits;
        under `quiet` and `stealth` a feature branch cannot change configuration, so both
        sides are the configuration branch's tip, whatever *base* and *head* are."""
        from fr.settings.load import show_at_commit

        if self.ref is None:
            path = self.tree_path(name)
            return show_at_commit(self.product, base, path), show_at_commit(
                self.product, head, path
            )
        text = self.at_default(name)
        return text, text

    def _git_repo(self) -> Path | None:
        """Where reads at the configuration branch run: the product clone under quiet (the
        `fr-config` worktree is a worktree of it, so it shares the object store and the
        remote-tracking ref), the configuration clone under stealth (None until it exists)."""
        if self.placement == _QUIET:
            return self.product
        return self.checkout if (self.checkout / ".git").exists() else None


def _commit(root: Path, qualified: str) -> str | None:
    from fr.git import GitUnavailableError, git_answer

    try:
        done = git_answer(root, "rev-parse", "--verify", "--quiet", f"{qualified}^{{commit}}")
    except GitUnavailableError:
        return None
    return done.stdout.strip() if done.returncode == 0 and done.stdout.strip() else None


def _default_qualified(root: Path) -> str | None:
    """The fully qualified default ref `fr.settings.load` reads policy from, or None."""
    from fr.git import GitUnavailableError, git_answer
    from fr.settings import SettingsError
    from fr.settings.load import _resolve_source

    try:
        if git_answer(root, "rev-parse", "--git-dir").returncode != 0:
            return None
        qualified, _, _, _ = _resolve_source(root)
    except GitUnavailableError, SettingsError:
        return None
    return qualified


def quiet_checkout(root: Path) -> Path:
    """Under quiet, the `fr-config` worktree: `~/.cache/fr/worktrees/<main checkout>/fr-config`,
    beside the `fr` worktree."""
    from fr.placement.quiet import worktree_path

    return worktree_path(Path(root)).parent / CONFIG_BRANCH


def stealth_checkout(root: Path, tracking: Path) -> Path:
    """Under stealth, the configuration clone: the tracking clone *tracking*'s path plus
    `-config` (`stealth--<slug>-config`)."""
    return tracking.with_name(f"{tracking.name}{CONFIG_SUFFIX}")


def config_space(root: Path) -> ConfigSpace:
    """The configuration space of the checkout at *root* (R1, R2).

    The placement is read as `fr.artifacts.paths.outside_repo` reads it (the marker, then
    the switch), never creating a worktree or asking a tracking repo: a configuration read
    must not have side effects."""
    from fr.artifacts.paths import outside_repo

    root = Path(root)
    placement = outside_repo(root) or _REPO
    if placement == _QUIET:
        checkout = quiet_checkout(root)
        space = ConfigSpace(_QUIET, checkout / SPACE_DIR, checkout, root, f"origin/{CONFIG_BRANCH}")
    elif placement == _STEALTH:
        from fr.placement.stealth import marker_tracking, worktree_path

        found = marker_tracking(root)
        assert found is not None
        ref, target = found
        checkout = stealth_checkout(root, worktree_path(root, ref))
        space = ConfigSpace(
            _STEALTH,
            checkout / target / SPACE_DIR,
            checkout,
            root,
            f"origin/{ref.branch}{CONFIG_SUFFIX}",
            f"{target}/{SPACE_DIR}",
        )
    else:
        return ConfigSpace(_REPO, root / SPACE_DIR, root, root)
    _notice_ignored(root, placement)
    return space


_NOTICED: set[str] = set()
"""Product checkouts whose ignored `.fr/` this process has already named (R4)."""


def ignored_product_files(root: Path) -> list[str]:
    """The product checkout's own `.fr/` files a quiet or stealth run ignores (R4): every
    file below it except `isolation-allow` (R8) and triage's working state."""
    base = Path(root) / SPACE_DIR
    if not base.is_dir():
        return []
    state = Path(root) / PRODUCT_TRIAGE_STATE
    found: list[str] = []
    for path in sorted(base.rglob("*")):
        if not path.is_file() or path.name == ALLOWLIST or path.is_relative_to(state):
            continue
        found.append(path.relative_to(base).as_posix())
    return found


def _notice_ignored(root: Path, placement: str) -> None:
    key = str(Path(root).resolve())
    if key in _NOTICED:
        return
    _NOTICED.add(key)
    files = ignored_product_files(root)
    if files:
        print(
            f"fr: ignoring the product checkout's {SPACE_DIR}/ under {placement}: "
            f"{', '.join(files)}",
            file=sys.stderr,
        )


def forge_ref(client: object, repo: str) -> str | None:
    """The ref a forge-side reader reads *repo*'s `.fr/<file>` at (R1): `fr-config` when
    that branch's `.fr/settings.yaml` carries a quiet switch, else None (the default
    branch).

    Only "there is no switch there" reads as no switch: a not-found (no branch, no file),
    a forge that cannot read a file at a ref (no `read_file_at_ref`, or the backend raising
    `UnsupportedForgeOperation`, glab and tea today), or a file naming no placement. Any
    other forge error propagates, and the text is validated as the local switch reader
    validates it (`fr.placement.quiet.parse_switch_text`), so an unreadable or malformed
    switch refuses (`SettingsError`), never reads as absent (review p1-r2)."""
    from fr.ghclient import UnsupportedForgeOperation
    from fr.settings.remote import _not_found

    reader = getattr(client, "read_file_at_ref", None)
    if reader is None:
        return None
    path = rel("settings")
    try:
        text = reader(repo=repo, path=path, ref=CONFIG_BRANCH)
    except Exception as exc:  # noqa: BLE001 — every backend's error; only these mean "none"
        if isinstance(exc, UnsupportedForgeOperation) or isinstance(
            exc.__cause__, UnsupportedForgeOperation
        ):
            return None
        if _not_found(exc):
            return None
        raise
    from fr.placement.quiet import parse_switch_text

    found = parse_switch_text(
        str(text), source=f"{repo}:{CONFIG_BRANCH}:{path}", branch=CONFIG_BRANCH
    )
    return None if found is None else CONFIG_BRANCH
