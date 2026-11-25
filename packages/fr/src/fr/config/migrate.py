"""Moving repo configuration into its configuration space (spec
2026-11-19-event-driven-a-la-carte S1 §D, R9 to R12; plan 2026-11-24-s1-configuration-homes
phase 4).

`all_moved()` is the one table of the files S1 moves: each kind's old locator (relative to the
product checkout, or to the memory root for the settings file) and its place below `.fr/`.
`fr.artifacts.registry` builds the moved kinds from it and `fr.artifacts.config_migration`
registers their hops.

**Within one checkout** (`repo`, and `isolation-allow` under every placement) a hop is a
rename on disk; the migrate commit stages both paths, so git records a rename.

**Across spaces** (`quiet`, `stealth`, R10, R11) a hop writes the destination on the
configuration branch first, pushes it, and only then removes the product file, which
leaves the product in the product's migrate commit. Three cases (plan decision
p4-cross-space-cases):

1. The configuration branch does not exist yet: the hop CREATES it, one orphan commit
   holding the settings (the old switch's bytes, R6) and every file the migration would
   move there (`pending_files`), so one push carries the whole space and the later hops
   find their file already there. A refused push removes nothing.
2. The branch holds the file with the same bytes: the product file is removed.
3. The branch exists without the file: fr proposes it in a pull request
   (`fr.config.change.open_change`, honouring `git.pr`) and refuses that artifact,
   naming the pull request; the product file stays until the change is merged and the
   migration runs again. A branch holding the file with OTHER bytes is R12's refusal.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable, Collection
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol

from fr.config.space import ALLOWLIST, CONFIG_BRANCH
from fr.config.space import SPACE_DIR as SPACE_DIR
from fr.config.space import rel as rel

if TYPE_CHECKING:
    from fr.config.space import ConfigSpace

QUIET_FILES: Final = (
    "ci.yaml",
    "docs.yaml",
    "lenses.yaml",
    "triage.yaml",
    "ops.yaml",
    "debt.yaml",
    "candidate-install",
)
"""R11: the product checkout's own `.fr/` files that move to `fr-config` under quiet."""

LEGACY_ALLOWLIST: Final = ".fr-isolation-allow"
LEGACY_PROFILES: Final = ".devcontainer/fr-profiles.yaml"
SETTINGS: Final = "settings.yaml"
"""The old switch's name at the root of the memory branch (`fr`) and below a stealth
target's directory (R6)."""


@dataclass(frozen=True)
class Moved:
    """One moved kind: `old` (a glob relative to the product checkout) and `new` (the
    same file's place below `.fr/`, `*` matching `old`'s `*`). `across` says the new
    place is the configuration space (else the same checkout)."""

    kind: str
    old: str
    new: str
    across: bool = True

    @property
    def new_locator(self) -> str:
        return rel(self.new)

    def below(self, source: Path, product: Path) -> str:
        """*source*'s (an old-locator path) place below `.fr/`."""
        if "*" not in self.old:
            return self.new
        base = Path(self.old).parent
        name = source.relative_to(product / base).as_posix()
        return f"{Path(self.new).parent.as_posix()}/{name}"

    def product_of(self, path: Path) -> Path:
        """The product checkout an old-locator *path* sits in."""
        depth = len(Path(self.old).parts)
        return Path(*path.parts[: len(path.parts) - depth])


def legacy_dirs() -> dict[str, str]:
    """The R9 kinds' old repo-relative paths (`fr.artifacts.paths.LEGACY_CONFIG`)."""
    from fr.artifacts.paths import LEGACY_CONFIG

    return dict(LEGACY_CONFIG)


def _moved() -> tuple[Moved, ...]:
    old = legacy_dirs()
    return (
        Moved("workflow-config", f"{old['workflow']}/*.yaml", "workflows/*.yaml"),
        Moved("verification-config", f"{old['verification']}/*.yaml", "verifications/*.yaml"),
        Moved("models-config", old["models"], "models.yaml"),
        Moved("trackers-config", old["trackers"], "trackers.yaml"),
        Moved("plan-config", old["plan-config"], "plan-config.yaml"),
        Moved("profiles", LEGACY_PROFILES, "profiles.yaml"),
        Moved("isolation-allow", LEGACY_ALLOWLIST, ALLOWLIST, across=False),
    )


@cache
def all_moved() -> tuple[Moved, ...]:
    """Every file S1 moves into `.fr/` (R9, R8), by kind. Built on first use, never at
    import (review p4-r8): the old paths come from `fr.artifacts.paths`, and importing it
    runs `fr.artifacts`' registry, which imports this module."""
    return _moved()


def moved(kind: str) -> Moved:
    return {m.kind: m for m in all_moved()}[kind]


# --- where each locator is globbed ------------------------------------------------------


def space_root(product: Path) -> Path:
    """The directory `.fr/` hangs from in *product*'s configuration space: the product
    checkout under `repo`, the `fr-config` worktree under quiet, `<clone>/<target-dir>`
    under stealth."""
    from fr.config.space import config_space

    return config_space(Path(product)).dir.parent


def placement_of(product: Path) -> str:
    from fr.artifacts.paths import REPO, outside_repo

    return outside_repo(Path(product)) or REPO


def moved_roots(kind: str) -> Callable[[Path, int], list[Path]]:
    """`ArtifactKind.roots` of a moved kind: its old locator in the product checkout,
    its new one in the configuration space (the product, for `isolation-allow`)."""
    entry = moved(kind)

    def roots(repo_root: Path, index: int) -> list[Path]:
        if index == 0 or not entry.across:
            return [Path(repo_root)]
        return [space_root(repo_root)]

    return roots


def quiet_roots(repo_root: Path, index: int) -> list[Path]:
    """`quiet-config`'s roots: the product's `.fr/` (index 0) and `fr-config`'s (index
    1), under quiet only (R11). Under `repo` the product's `.fr/` IS the space."""
    from fr.artifacts.paths import QUIET

    if placement_of(repo_root) != QUIET:
        return []
    return [Path(repo_root)] if index == 0 else [space_root(repo_root)]


def quiet_owns(path: Path) -> bool:
    return path.name in QUIET_FILES and path.parent.name == SPACE_DIR


def quiet_stamp(path: Path) -> int | None:
    """`quiet-config`'s location stamp: 2 in the `fr-config` checkout (its HEAD is
    `fr-config`), 1 in a product checkout. Both are `.fr/<file>`: the location that
    differs is the checkout."""
    done = subprocess.run(
        ["git", "-C", str(path.parent), "symbolic-ref", "-q", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return 2 if done.stdout.strip() == f"refs/heads/{CONFIG_BRANCH}" else 1


def settings_roots(repo_root: Path, index: int) -> list[Path]:
    """`settings-location`'s roots: the old switch's directory (the `fr` worktree under
    quiet, `<tracking clone>/<target-dir>` under stealth) and the configuration space.
    Nothing under `repo`, whose settings were always `.fr/settings.yaml`."""
    from fr.artifacts.paths import QUIET, STEALTH

    placement = placement_of(repo_root)
    if placement not in (QUIET, STEALTH):
        return []
    if index == 1:
        return [space_root(repo_root)]
    old = _legacy_settings_dir(Path(repo_root), placement)
    return [old] if old is not None and old.is_dir() else []


def _legacy_settings_dir(product: Path, placement: str) -> Path | None:
    from fr.artifacts.paths import QUIET

    if placement == QUIET:
        from fr.placement.quiet import worktree_path

        path = worktree_path(product)
        return path if (path / ".git").exists() else None
    from fr.placement.stealth import marker_tracking
    from fr.placement.stealth import worktree_path as tracking_path

    found = marker_tracking(product)
    if found is None:
        return None
    ref, target = found
    return tracking_path(product, ref) / target


def settings_stamp(path: Path) -> int | None:
    """`settings-location`'s stamp: `.fr/settings.yaml` is 2; the old switch is 2 once
    the configuration branch holds the same bytes (it is then R6's legacy copy, not a
    second file for R12), else 1."""
    if Path(path).full_match(f"**/{rel(SETTINGS)}"):
        return 2
    held = _config_settings_for_legacy(Path(path))
    try:
        return 2 if held is not None and held == path.read_text() else 1
    except OSError:
        return 1


def _config_settings_for_legacy(path: Path) -> str | None:
    """The configuration branch's settings as last fetched, read from beside the old
    switch *path*: `origin/fr-config:.fr/settings.yaml` from the `fr` worktree (a linked
    worktree of the product repository), or the stealth configuration clone's
    `origin/<branch>-config:<target>/.fr/settings.yaml`."""
    from fr.settings.load import show_at_commit

    def sha(cwd: Path, ref: str) -> str | None:
        done = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
            capture_output=True,
            text=True,
            check=False,
        )
        return done.stdout.strip() or None

    head = subprocess.run(
        ["git", "-C", str(path.parent), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    if not head:
        return None
    top = Path(head).resolve()
    parent = path.parent.resolve()  # git answers the toplevel's real path (a symlinked HOME)
    if parent == top:  # quiet: the root settings.yaml of `fr`
        found = sha(top, f"refs/remotes/origin/{CONFIG_BRANCH}")
        return None if found is None else show_at_commit(top, found, rel(SETTINGS))
    target = parent.relative_to(top).as_posix()
    branch = subprocess.run(
        ["git", "-C", str(top), "symbolic-ref", "--short", "-q", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    clone = top.with_name(f"{top.name}-config")
    if not branch or not (clone / ".git").exists():
        return None
    found = sha(clone, f"refs/remotes/origin/{branch}-config")
    return None if found is None else show_at_commit(clone, found, f"{target}/{rel(SETTINGS)}")


# --- the stamp a body-stamped profiles file carries at its new place ----------------------

_STAMP_LINE = re.compile(r"^schema_version\s*:[^\r\n]*", re.MULTILINE)


def with_stamp(text: str, version: int) -> str:
    """*text* with its top-level `schema_version:` set to *version*, every other byte
    kept; a file with none gains one on top."""
    if _STAMP_LINE.search(text):
        return _STAMP_LINE.sub(f"schema_version: {version}", text, count=1)
    newline = "\r\n" if "\r\n" in text else "\n"
    return f"schema_version: {version}{newline}{text}"


# --- the configuration space's writer ----------------------------------------------------


class ProposedError(Exception):
    """A moved file waits in a pull request to the configuration branch: the product file
    stays until it merges (plan decision p4-cross-space-cases, case 3)."""


class SpaceWriter(Protocol):
    """What a cross-space hop needs of the configuration branch's remote."""

    def fetch(self) -> None: ...
    def exists(self) -> bool: ...
    def tip(self, tree_path: str) -> str | None: ...
    def create(
        self, files: dict[str, str], message: str, *, executable: Collection[str] = ()
    ) -> None: ...
    def propose(
        self, tree_path: str, text: str, message: str, *, executable: bool = False
    ) -> str: ...
    def refresh(self) -> None: ...


class QuietWriter:
    """`fr-config` on the product repository's origin."""

    def __init__(self, product: Path) -> None:
        self.product = Path(product)

    def fetch(self) -> None:
        from fr.placement import quiet

        quiet._fetch_both(self.product, quiet._default_network(self.product), None)

    def exists(self) -> bool:
        from fr.artifacts import paths
        from fr.placement import quiet

        common = paths._common_dir(self.product)
        return common is not None and quiet._ref_sha(common, paths.SWITCH_REF) is not None

    def tip(self, tree_path: str) -> str | None:
        from fr.config.space import _commit
        from fr.settings.load import show_at_commit

        sha = _commit(self.product, f"refs/remotes/origin/{CONFIG_BRANCH}")
        return None if sha is None else show_at_commit(self.product, sha, tree_path)

    def create(
        self, files: dict[str, str], message: str, *, executable: Collection[str] = ()
    ) -> None:
        from fr.placement import quiet

        quiet.create_config_branch(self.product, files, message, executable=executable)

    def propose(self, tree_path: str, text: str, message: str, *, executable: bool = False) -> str:
        from fr.artifacts import paths
        from fr.config.change import open_change
        from fr.placement import quiet

        quiet._check_config_refs(self.product)
        remote = quiet._git(self.product, "config", "--get", "remote.origin.url").stdout.strip()
        return open_change(
            self.product, product=self.product, remote=remote, base_branch=CONFIG_BRANCH,
            base_ref=paths.SWITCH_REF, rel=tree_path, text=text, message=message,
            executable=executable,
        )  # fmt: skip

    def refresh(self) -> None:
        from fr.placement import quiet

        quiet._check_config_refs(self.product)
        quiet.require_current_config_worktree(self.product)

    def legacy_settings(self) -> str | None:
        from fr.placement import quiet

        old = quiet.switch_texts(self.product)[1]
        return None if old is None else old[1]


class StealthWriter:
    """`<branch>-config` on the tracking repository."""

    def __init__(self, product: Path) -> None:
        from fr.placement.stealth import config_ref, marker_tracking

        self.product = Path(product)
        found = marker_tracking(self.product)
        if found is None:
            from fr.settings import SettingsError

            raise SettingsError(f"placement stealth: {product} carries no stealth marker")
        self.ref, self.target = found
        self.cref = config_ref(self.ref)

    @property
    def clone(self) -> Path:
        from fr.placement.stealth import worktree_path

        return worktree_path(self.product, self.cref)

    def fetch(self) -> None:
        from fr.placement.stealth import check_config_branch, ensure_worktree

        ensure_worktree(self.product, self.ref)
        if (self.clone / ".git").exists():
            check_config_branch(self.product, self.ref)
            ensure_worktree(self.product, self.cref)

    def exists(self) -> bool:
        from fr.placement.stealth import _remote_has

        return (self.clone / ".git").exists() or _remote_has(self.cref, self.product)

    def tip(self, tree_path: str) -> str | None:
        from fr.placement.stealth import _at_tip

        if not (self.clone / ".git").exists():
            self.refresh()
        return _at_tip(self.clone, self.cref, tree_path)

    def create(
        self, files: dict[str, str], message: str, *, executable: Collection[str] = ()
    ) -> None:
        from fr.placement.stealth import create_config_branch

        create_config_branch(self.product, self.ref, files, message, executable=executable)

    def propose(self, tree_path: str, text: str, message: str, *, executable: bool = False) -> str:
        from fr.config.change import open_change
        from fr.placement.stealth import _remote_ref, check_privacy, origin_url

        check_privacy(self.ref, origin_url(self.product), target_root=self.product)
        return open_change(
            self.clone, product=self.product, remote=self.ref.repo,
            base_branch=self.cref.branch, base_ref=_remote_ref(self.cref), rel=tree_path,
            text=text, message=message, executable=executable,
        )  # fmt: skip

    def refresh(self) -> None:
        from fr.placement.stealth import check_config_branch, ensure_worktree

        check_config_branch(self.product, self.ref)
        ensure_worktree(self.product, self.cref)

    def legacy_settings(self) -> str | None:
        from fr.placement.stealth import target_settings_texts

        return target_settings_texts(self.product, self.ref, self.target)[1]


def writer_for(product: Path) -> QuietWriter | StealthWriter:
    """The configuration space's writer for *product* (the tests' seam)."""
    from fr.artifacts.paths import QUIET

    return QuietWriter(product) if placement_of(product) == QUIET else StealthWriter(product)


def _message(product: Path, what: str) -> str:
    from fr.git_policy.templates import fr_message

    return fr_message(product, f"chore(fr): move {what} to the configuration space")


def pending_files(
    product: Path, space: ConfigSpace, *, executable: set[str] | None = None
) -> dict[str, str]:
    """Every file the migration would move into *space* (tree path -> text): the R9 kinds
    at their old paths and, under quiet, the product's R11 `.fr/` files. A profiles file
    goes at version 3 only when it is at version 2 already (its 1 -> 2 hop rewrites it in
    the product first; one still at 1 follows by a pull request)."""
    from fr.artifacts.paths import QUIET

    clean = _clean_tracked(product)
    landed = _landed(product, clean)
    out: dict[str, str] = {}
    for entry in all_moved():
        if not entry.across:
            continue
        for source in sorted(product.glob(entry.old)):
            refuse_link(product, source)
            if not source.is_file() or source.relative_to(product).as_posix() not in landed:
                continue
            if entry.kind == "profiles":
                from fr.artifacts.profiles_services import UnmigratableProfilesError
                from fr.settings import SettingsError

                try:
                    text = profiles_body(product, source)
                except SettingsError, UnmigratableProfilesError:
                    continue  # its own hop refuses it, naming why; the rest still move
            else:
                text = source_text(product, source)
            out[space.tree_path(entry.below(source, product))] = text
            if executable is not None and is_executable(product, source):
                executable.add(space.tree_path(entry.below(source, product)))
    if space.placement == QUIET:
        for name in QUIET_FILES:
            source = product / SPACE_DIR / name
            if not (source.is_file() or source.is_symlink()):
                continue
            refuse_link(product, source)
            if source.relative_to(product).as_posix() in landed:
                out[space.tree_path(name)] = source_text(product, source)
                if executable is not None and is_executable(product, source):
                    executable.add(space.tree_path(name))
    return out


def is_executable(product: Path, source: Path) -> bool:
    """Whether *source* goes onto the configuration branch as `100755`. A tracked file's
    bytes are the default branch's blob (`source_text`), so its mode is the default
    branch's too (review p7-r3, lens review l-security-r2): under `core.fileMode=false` a
    chmod is no change to git, and neither the working tree's bit nor a chmod committed
    only on this branch may make a reviewed 100644 file executable. An untracked file is
    never executable here: the default branch has no mode for it, and its move refuses
    (`_untracked`, verification v-r1)."""

    rel_path = Path(source).relative_to(product).as_posix()
    tracked = subprocess.run(
        ["git", "-C", str(product), "ls-files", "--error-unmatch", "--", rel_path],
        capture_output=True,
        check=False,
    )
    if tracked.returncode == 0:
        found = _default_commit(product)
        if found is None:
            return False
        listed = subprocess.run(
            ["git", "-C", str(product), "ls-tree", found[1], "--", rel_path],
            capture_output=True,
            text=True,
            check=False,
        )
        return (
            listed.returncode == 0
            and bool(listed.stdout.strip())
            and listed.stdout.split()[0] == "100755"
        )
    return False


def _default_commit(product: Path) -> tuple[str, str] | None:
    """The default ref a cross-space move compares against, or None (every move refuses,
    nothing rides along in a creation). Never the settings read's CI fallback to HEAD
    (verification v-r3): comparing HEAD with HEAD would accept a branch's own bytes, and a
    CI migration does reach the push (`move_across` has no CI exemption), so with no
    resolvable default ref the move refuses in CI too.

    It trusts the last fetch of the default ref, the same trust `fr.config.space.located`
    places in it; no fetch is added here. A shell that can move
    `refs/remotes/origin/<default>` locally can also rewrite the remote and its fetch
    refspec, so a fetch would close nothing, and a stale default ref only refuses more."""
    from fr.settings.load import default_commit

    found = default_commit(product)
    if found is None or found[0] == "HEAD":
        return None
    return found


def _landed(product: Path, clean: set[str]) -> set[str]:
    """The *clean* tracked files whose HEAD blob is exactly the default branch's (lens
    review l-security-r2): only these ride along in the creation, so a change committed on
    a feature branch, unreviewed, never becomes the configuration branch's first commit
    (its own hop refuses it, `source_text`). Untracked files are not in *clean*."""
    found = _default_commit(product)
    if found is None:
        return set()
    done = subprocess.run(
        ["git", "-C", str(product), "diff", "--name-only", found[1], "HEAD", "--"],
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        return set()
    differ = {line for line in done.stdout.splitlines() if line}
    present = subprocess.run(
        ["git", "-C", str(product), "ls-tree", "-r", "--name-only", found[1]],
        capture_output=True,
        text=True,
        check=False,
    )
    on_default = set(present.stdout.splitlines()) if present.returncode == 0 else set()
    return {p for p in clean if p not in differ and p in on_default}


def _clean_tracked(product: Path) -> set[str]:
    """The product's tracked files with no uncommitted change: only these ride along in
    the creation, so an edit the operator has not committed is never pushed (the CLI-entry
    gate's uncommitted veto holds that file's own hop back)."""

    def lines(*args: str) -> set[str]:
        done = subprocess.run(
            ["git", "-C", str(product), *args], capture_output=True, text=True, check=False
        )
        return {line for line in done.stdout.splitlines() if line}

    return lines("ls-files") - lines("diff", "--name-only", "HEAD")


def refuse_link(product: Path, source: Path) -> str:
    """*source*'s path relative to *product*, after refusing a symlink at it or at any
    directory between, or a path outside the checkout (`fr.config.space.link_problem`,
    review p4-sec-symlink): a moved file is pushed onto the configuration branch, and a
    link to `~/.ssh/...` must never be read for that, nor a file outside deleted."""
    from fr.config.space import link_problem
    from fr.settings import SettingsError

    product = Path(product)
    why = link_problem(product, Path(source))
    if why is not None:
        raise SettingsError(
            f"{why}: fr will not read, move or delete it through a link. Replace it with "
            "the file itself and run `fr migrate artifacts --yes` again (S1 R10)"
        )
    return Path(source).relative_to(product).as_posix()


def source_text(product: Path, source: Path) -> str:
    """The bytes a cross-space hop pushes for *source* (review p4-sec-symlink): never a
    symlink; a tracked file's blob as the product's DEFAULT branch committed it (lens review
    l-security-r2, like `fr.config.space.located`), refused while it has uncommitted
    changes (pushing the blob and deleting the edit would lose it) or while HEAD's blob
    differs from the default branch's (an unreviewed change must land there first). An
    untracked file is refused (`_untracked`): the default branch lacks it, so nobody
    reviewed it (verification v-r1)."""
    from fr.settings import SettingsError

    rel_path = refuse_link(product, source)

    def git(*args: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(["git", "-C", str(product), *args], capture_output=True, check=False)

    if not git("ls-files", "--error-unmatch", "--", rel_path).returncode == 0:
        if not Path(source).is_file():
            raise SettingsError(f"{rel_path} is not a regular file: fr will not move it")
        raise _untracked(rel_path)
    if git("diff", "--quiet", "HEAD", "--", rel_path).returncode != 0:
        raise SettingsError(
            f"{rel_path} has uncommitted changes: commit or stash them, then run "
            "`fr migrate artifacts --yes` again (fr pushes the committed file, S1 R10)"
        )
    shown = git("show", f"HEAD:{rel_path}")
    if shown.returncode != 0:
        raise SettingsError(f"cannot read {rel_path} at HEAD: {shown.stderr.decode().strip()}")
    return _as_default_has_it(product, rel_path, shown.stdout.decode("utf-8"))


def _untracked(rel_path: str) -> Exception:
    """The refusal for an untracked file a cross-space hop would move (verification v-r1,
    lens review l-security-r2). No kind that moves ACROSS legitimately carries an untracked
    file: the one untracked file S1 moves, the base clone's operator-managed allowlist, is
    `across=False` and renamed in its own checkout (R8), and stealth keeps the product file
    in place, so a refusal here loses nothing. Reading it from disk would let an
    agent-written `.fr/candidate-install` (mode 100755) become the configuration branch's
    first commit unreviewed."""
    from fr.settings import SettingsError

    return SettingsError(
        f"{rel_path} is not tracked, so the default branch has not committed it: fr moves "
        "only what the default branch has committed; commit it and land the change on the "
        "default branch first, then run `fr migrate artifacts --yes` again (S1 R10)"
    )


def _as_default_has_it(product: Path, rel_path: str, committed: str) -> str:
    """*committed* (HEAD's blob of *rel_path*) when the product's default branch has
    exactly those bytes; otherwise `SettingsError` (lens review l-security-r2)."""
    from fr.settings import SettingsError
    from fr.settings.load import show_at_commit

    found = _default_commit(product)
    if found is None:
        raise SettingsError(
            f"{rel_path}: fr cannot name the default branch, so it cannot tell whether this "
            "file was reviewed; fetch origin, then run `fr migrate artifacts --yes` again "
            "(S1 R10)"
        )
    ref = found[0].removeprefix("refs/remotes/").removeprefix("refs/heads/")
    at_default = show_at_commit(product, found[1], rel_path)
    if at_default is None:
        raise SettingsError(
            f"{rel_path} is not on the default branch ({ref}): fr moves only what the "
            "default branch has committed; land the change there first, then run "
            "`fr migrate artifacts --yes` again (S1 R10)"
        )
    if at_default != committed:
        raise SettingsError(
            f"{rel_path} differs from the default branch's copy ({ref}): fr moves only what "
            "the default branch has committed; land the change there first, then run "
            "`fr migrate artifacts --yes` again (S1 R10)"
        )
    return at_default


_STAMP_LINES = re.compile(r"^schema_version\s*:[^\r\n]*(\r?\n)?", re.MULTILINE)


def profiles_body(product: Path, source: Path) -> str:
    """The version-3 bytes a cross-space profiles move pushes for *source* (review p4-r4):
    the COMMITTED file (an untracked one is refused, `_untracked`), taken 1 -> 2 in memory
    when it is at version 1 (`fr.artifacts.profiles_services.services_text`) and stamped 3, so the
    configuration branch receives the final bytes in one move. The working tree may differ
    from the commit only by fr's own in-flight 1 -> 2 rewrite of it (the same text, stamped
    2 by the runner); any other difference is an operator's edit and refuses."""
    from fr.artifacts.profiles_services import services_text
    from fr.settings import SettingsError

    rel_path = refuse_link(product, source)

    def git(*args: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(["git", "-C", str(product), *args], capture_output=True, check=False)

    disk = Path(source).read_text()
    tracked = git("ls-files", "--error-unmatch", "--", rel_path).returncode == 0
    if tracked:
        shown = git("show", f"HEAD:{rel_path}")
        if shown.returncode != 0:
            raise SettingsError(f"cannot read {rel_path} at HEAD: {shown.stderr.decode().strip()}")
        committed = _as_default_has_it(product, rel_path, shown.stdout.decode("utf-8"))
    else:
        raise _untracked(rel_path)
    bom = "\ufeff" if committed.startswith("\ufeff") else ""
    plain = committed.removeprefix(bom)
    v2 = services_text(Path(source), plain)
    v2 = plain if v2 is None else v2
    if disk != committed and _STAMP_LINES.sub("", disk.removeprefix(bom)) != _STAMP_LINES.sub(
        "", v2
    ):
        raise SettingsError(
            f"{rel_path} has uncommitted changes: commit or stash them, then run "
            "`fr migrate artifacts --yes` again (fr pushes the committed file, S1 R10)"
        )
    return bom + with_stamp(v2, 3)


def ensure_space(
    product: Path,
    *,
    include: dict[str, str] | None = None,
    include_executable: Collection[str] = (),
) -> bool:
    """Create the configuration branch when it does not exist (R10, decision
    p2-phase4-migration-creates-config): the settings (the old switch's bytes, R6) and
    every pending file, in one orphan commit, pushed before anything leaves the product.
    Whether it created one. A configuration branch that exists already is checked for a
    foreign one and left alone."""
    from fr.config.space import config_space
    from fr.settings import SettingsError

    product = Path(product)
    space = config_space(product)
    writer = writer_for(product)
    writer.fetch()
    if writer.exists():
        writer.refresh()
        return False
    settings = writer.legacy_settings()
    if settings is None:
        raise SettingsError(
            f"placement {space.placement}: no switch to carry into the configuration space "
            f"(the old {SETTINGS} is missing); run `fr settings init` first"
        )
    executable: set[str] = set(include_executable)
    files = {
        space.tree_path(SETTINGS): settings,
        **pending_files(product, space, executable=executable),
    }
    files.update(include or {})
    from fr.settings import BranchRaceError

    try:
        writer.create(
            files,
            _message(product, f"{SPACE_DIR}/ ({len(files)} files)"),
            executable=executable,
        )
    except BranchRaceError:
        # Another host created the branch first (review p4-r1): what stands is read
        # like any existing configuration branch, never assumed to hold *files*.
        writer.fetch()
        writer.refresh()
        return False
    writer.refresh()
    return True


def move_across(
    product: Path,
    source: Path,
    below: str,
    transform: Callable[[str], str] | None = None,
    *,
    body: str | None = None,
) -> Path:
    """Move *source* to *below* (a path below `.fr/`) in *product*'s configuration space
    (R10): the destination is committed and pushed there first, and the product file is
    removed only once it is on the configuration branch. Returns the destination's
    working-tree path. Raises `SettingsError` (R12, a refused push) or `ProposedError`
    (a pull request opened; nothing removed). The bytes pushed are `source_text`'s (never
    a symlink's target, never an uncommitted edit), passed through *transform* when given
    (profiles writes its new stamp)."""
    from fr.config.space import config_space
    from fr.settings import SettingsError

    product = Path(product)
    space = config_space(product)
    if body is None:
        body = source_text(product, source)
        if transform is not None:
            body = transform(body)
    tree_path = space.tree_path(below)
    runnable = is_executable(product, source)
    writer = writer_for(product)
    writer.fetch()
    if not writer.exists():
        ensure_space(
            product, include={tree_path: body}, include_executable=[tree_path] if runnable else []
        )
        writer.fetch()  # read what the remote holds now, never what fr meant to push
        if not writer.exists():
            raise SettingsError(
                f"the configuration branch did not appear after its creation: {source} "
                "stays. Run `fr migrate artifacts --yes` again (S1 R10, review p4-r1)"
            )
    # The one gate before a product file leaves (review p4-r1): the configuration
    # branch's FETCHED tip holds the path with exactly the bytes moved.
    at_tip = writer.tip(tree_path)
    if at_tip is None:
        url = writer.propose(tree_path, body, _message(product, below), executable=runnable)
        raise ProposedError(
            f"{source} waits for review: fr proposed it as {tree_path} on the "
            f"configuration branch in {url}. The product file stays until that merges; "
            "then run `fr migrate artifacts --yes` again (S1 R10)"
        )
    if at_tip != body:
        raise SettingsError(
            f"both {source} and {tree_path} on the configuration branch exist, with "
            "different contents: fr will not choose between them. Keep the one you "
            "want (a pull request to the configuration branch, or delete the product "
            "file) and run `fr migrate artifacts --yes` again (S1 R12)"
        )
    writer.refresh()
    if space.placement == _STEALTH_PLACEMENT:
        _say_kept(product, source, space)
        return space.file(below)
    refuse_link(product, source)
    source.unlink()
    return space.file(below)


_STEALTH_PLACEMENT: Final = "stealth"
_KEPT_SAID: set[str] = set()


def _say_kept(product: Path, source: Path, space: ConfigSpace) -> None:
    """Under stealth the product file stays (R10 as amended, decision
    p4-stealth-keeps-product-file): say once the exact `git rm` the operator may run."""
    import sys

    rel_path = Path(source).relative_to(product).as_posix()
    line = (
        f"fr: {rel_path} moved to {space.ref} and stays in the product under stealth (fr "
        f"commits no deletion on the target's branch, and ignores this copy, R4); to remove "
        f"it yourself: git -C {product} rm -- {rel_path}"
    )
    if line not in _KEPT_SAID:
        _KEPT_SAID.add(line)
        print(line, file=sys.stderr)


def restore_committed(product: Path, source: Path) -> None:
    """Put a kept stealth source back to its committed bytes: fr's own in-flight 1 -> 2
    rewrite of a profiles file (`profiles_body` refused any other difference) must not stay
    in the target's working tree. An untracked file is left as it is."""
    rel_path = refuse_link(product, source)
    shown = subprocess.run(
        ["git", "-C", str(product), "show", f"HEAD:{rel_path}"], capture_output=True, check=False
    )
    if shown.returncode == 0 and Path(source).read_bytes() != shown.stdout:
        from fr.artifacts.atomic import write_text_atomic

        write_text_atomic(Path(source), shown.stdout.decode("utf-8"))


def stealth_keeps(path: Path) -> bool:
    """Whether a cross-space hop leaves *path* (an old-locator file) in the product: under
    stealth always (R10 as amended)."""
    for entry in all_moved():
        if entry.across and Path(path).full_match(f"**/{entry.old}"):
            return placement_of(entry.product_of(Path(path))) == _STEALTH_PLACEMENT
    return False


def kept_copy(path: Path) -> bool:
    """Whether *path* is a product file a stealth migration already moved and kept: under
    stealth, at an old locator, with the configuration branch's fetched tip holding exactly
    the bytes the move pushes. Such a file is not the kind's any more (`owns`), so it never
    reads as stale. Any failure to tell reads as not kept."""
    from fr.settings import SettingsError

    for entry in all_moved():
        if not entry.across or not Path(path).full_match(f"**/{entry.old}"):
            continue
        product = entry.product_of(Path(path))
        if placement_of(product) != _STEALTH_PLACEMENT:
            return False
        try:
            from fr.config.space import config_space

            space = config_space(product)
            if entry.kind == "profiles":
                body = profiles_body(product, Path(path))
            else:
                body = source_text(product, Path(path))
            repo = space._git_repo()
            if repo is None:
                return False
            from fr.config.space import _commit
            from fr.settings.load import show_at_commit

            sha = _commit(repo, f"refs/remotes/{space.ref}")
            held = (
                None
                if sha is None
                else show_at_commit(repo, sha, space.tree_path(entry.below(Path(path), product)))
            )
        except SettingsError, OSError, ValueError, UnicodeDecodeError:
            return False
        return held is not None and held == body
    return False


def moved_owns(kind: str) -> Callable[[Path], bool]:
    """`ArtifactKind.owns` of a moved kind: every match but a stealth-kept copy."""
    entry = moved(kind)

    def owns(path: Path) -> bool:
        if not entry.across or not Path(path).full_match(f"**/{entry.old}"):
            return True
        return not kept_copy(path)

    return owns
