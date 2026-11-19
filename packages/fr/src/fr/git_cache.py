"""A scoped cache for git answers fr asks many times per command (spec
`2026-11-19-local-suite-cost` R1, §3.A).

One fr command asks `fr.git.remote_name` and `fr.git.remote_default_ref` about
the same repository several times, and each answer costs two to four git
processes. Inside a **scope** (`scope()`, which `fr.cli`'s root group opens around
every command) a repeated question is answered from memory, as long as a
**fingerprint** of everything git read to produce it is unchanged. The
fingerprint is built from `os.stat` alone, never from git: the config files git
reads, the git environment, `packed-refs`, the remote's `HEAD` and every
remote-tracking ref the answer consulted. Any write to those (a fetch, a
`remote set-head`, a config edit, by fr or by anything else) moves a stat, and
the next question goes to git.

Outside a scope (`active()` is None: fr used as a library, a runner's tick, a
test calling the helpers directly) nothing is cached.

What is NEVER cached (`locate` gives None, or `fr.git` declines to store):

- a `GitRefusal`, and a `GitUnavailableError` (it propagates, nothing is stored);
- a root with no repository above it, or a bare repository (no `.git` to read);
- a repository located by `GIT_DIR` / `GIT_COMMON_DIR` in the environment;
- a `reftable` repository (its refs are not files this module can stat);
- `extensions.worktreeConfig` (a per-worktree config file the list would miss);
- an `[include]` / `[includeIf]` in any config file read, or an `include` key
  passed through the environment (the included files are not in the list);
- a system config file whose path git would not name.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ABSENT = ("absent",)
"""The stat of a path that does not exist: its appearance is a change too."""

_CACHE: ContextVar[dict[Any, Any] | None] = ContextVar("fr_git_cache", default=None)

_SYSTEM_CONFIG_KEY = ("git_cache", "system-config")
_UNKNOWN = "unknown"

_INCLUDE = re.compile(r"^\s*\[\s*include", re.IGNORECASE | re.MULTILINE)
_WORKTREE_CONFIG = re.compile(r"worktreeconfig", re.IGNORECASE)


@contextmanager
def scope() -> Iterator[None]:
    """Open a fresh cache for the duration of the block; nested scopes do not share."""
    token = _CACHE.set({})
    try:
        yield
    finally:
        _CACHE.reset(token)


def active() -> dict[Any, Any] | None:
    """The open scope's cache, or None outside any scope."""
    return _CACHE.get()


@dataclass(frozen=True)
class Located:
    """Where a repository's state lives, read without git."""

    git_dir: Path
    common_dir: Path
    config_files: tuple[Path, ...]
    """Every config file git reads for this repository (present or not)."""


def locate(root: Path) -> Located | None:
    """The repository *root* sits in, or None when the cache must not apply."""
    if os.environ.get("GIT_DIR") or os.environ.get("GIT_COMMON_DIR"):
        return None
    try:
        here = Path(root).resolve()
    except OSError:
        return None
    git_dir = _find_git_dir(here)
    if git_dir is None:
        return None
    common = git_dir
    commondir = git_dir / "commondir"
    if commondir.is_file():
        try:
            common = (git_dir / commondir.read_text().strip()).resolve()
        except OSError:
            return None
    if (common / "reftable").exists():
        return None
    system = _system_config(here)
    if system == _UNKNOWN:
        return None
    files = (*((Path(system),) if system else ()), *_global_configs(), common / "config")
    if _env_includes():
        return None
    for path in files:
        try:
            text = path.read_text(errors="replace")
        except FileNotFoundError:
            continue
        except OSError:
            return None
        if _INCLUDE.search(text):
            return None
        if path == common / "config" and _WORKTREE_CONFIG.search(text):
            return None
    return Located(git_dir=git_dir, common_dir=common, config_files=files)


def fingerprint(
    located: Located, remote: str | None, ref_names: tuple[str, ...]
) -> tuple[Any, ...]:
    """What the answer depends on, as `os.stat` sees it. Starts no process."""
    common = located.common_dir
    paths = [
        *located.config_files,
        common / "packed-refs",
        # `git remote` also lists the legacy remotes/ and branches/ entries.
        common / "remotes",
        common / "branches",
    ]
    if remote is not None:
        base = common / "refs" / "remotes" / remote
        paths.append(base / "HEAD")
        paths.extend(base / name for name in ref_names)
    env = tuple(
        sorted(
            (k, v)
            for k, v in os.environ.items()
            if k.startswith("GIT_") or k in ("HOME", "XDG_CONFIG_HOME")
        )
    )
    return (env, tuple((str(p), _stat(p)) for p in paths))


def _stat(path: Path) -> tuple[Any, ...]:
    try:
        st = os.stat(path)
    except OSError:
        return ABSENT
    return (st.st_mtime_ns, st.st_ctime_ns, st.st_size, st.st_ino)


def _looks_like_git_dir(path: Path) -> bool:
    return (path / "HEAD").is_file() and (path / "objects").is_dir() and (path / "refs").is_dir()


def _find_git_dir(here: Path) -> Path | None:
    """The git dir git's discovery would open from *here*, or None.

    Stops where git does (`GIT_CEILING_DIRECTORIES`) and gives None for a bare
    repository or anything that is not a plain `.git` directory or `gitdir:` file.
    """
    from fr.git import _ceiling_directories

    ceilings = _ceiling_directories()
    for candidate in (here, *here.parents):
        if candidate != here and candidate in ceilings:
            return None
        dot = candidate / ".git"
        if dot.is_dir():
            return dot.resolve()
        if dot.is_file():
            try:
                line = dot.read_text().strip()
            except OSError:
                return None
            if not line.startswith("gitdir:"):
                return None
            target = Path(line.removeprefix("gitdir:").strip())
            if not target.is_absolute():
                target = candidate / target
            try:
                resolved = target.resolve()
            except OSError:
                return None
            return resolved if resolved.is_dir() else None
        if dot.exists() or _looks_like_git_dir(candidate):
            return None
    return None


def _truthy(value: str) -> bool:
    return value.strip().lower() not in ("", "0", "false", "no", "off")


def _system_config(here: Path) -> str:
    """The system config path, "" for none, or `_UNKNOWN`. Asked of git once per scope."""
    if _truthy(os.environ.get("GIT_CONFIG_NOSYSTEM", "")):
        return ""
    configured = os.environ.get("GIT_CONFIG_SYSTEM")
    if configured is not None:
        return configured or _UNKNOWN
    cache = active()
    if cache is not None and _SYSTEM_CONFIG_KEY in cache:
        return str(cache[_SYSTEM_CONFIG_KEY])
    found = _ask_system_config(here)
    if cache is not None:
        cache[_SYSTEM_CONFIG_KEY] = found
    return found


def _ask_system_config(here: Path) -> str:
    from fr.git import GitUnavailableError, git_answer

    try:
        listed = git_answer(here, "config", "--system", "--list", "--show-origin")
        for line in listed.stdout.splitlines():
            if line.startswith("file:"):
                return line.removeprefix("file:").partition("\t")[0]
        missing = re.search(r"unable to read config file '([^']+)'", listed.stderr)
        if missing:
            return missing.group(1)
        named = git_answer(here, "var", "GIT_CONFIG_SYSTEM")
    except GitUnavailableError:
        return _UNKNOWN
    path = named.stdout.strip()
    return path if named.returncode == 0 and path else _UNKNOWN


def _global_configs() -> tuple[Path, ...]:
    configured = os.environ.get("GIT_CONFIG_GLOBAL")
    if configured:
        return (Path(configured),)
    home = Path(os.environ.get("HOME") or Path.home())
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else home / ".config"
    return (base / "git" / "config", home / ".gitconfig")


def _env_includes() -> bool:
    """An `include.*` / `includeIf.*` key passed through the environment."""
    if "include" in os.environ.get("GIT_CONFIG_PARAMETERS", "").lower():
        return True
    return any(
        k.startswith("GIT_CONFIG_KEY_") and v.strip().lower().startswith("include")
        for k, v in os.environ.items()
    )
