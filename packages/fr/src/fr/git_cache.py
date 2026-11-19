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
- a repository located by `GIT_DIR` / `GIT_COMMON_DIR` in the environment, or
  read with the legacy `GIT_CONFIG` file in the environment;
- a `reftable` repository (its refs are not files this module can stat);
- `extensions.worktreeConfig` (a per-worktree config file the list would miss);
- an `[include]` / `[includeIf]` path that cannot be resolved to a file
  (`%(prefix)/`, `~user/`, an empty or unparseable value), an include chain
  deeper than git's own limit (10), or an `include` key passed through the
  environment. Every other include is FOLLOWED: the included file joins the
  stat'd list whether or not its condition matches (over-invalidating is safe,
  a stale hit is not), and the per-worktree `HEAD` is stat'd so an `onbranch:`
  condition that flips is seen;
- a system config file whose path git would not name.
"""

from __future__ import annotations

import os
import re
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ABSENT = ("absent",)
"""The stat of a path that does not exist: its appearance is a change too."""

_CACHE: ContextVar[dict[Any, Any] | None] = ContextVar("fr_git_cache", default=None)

_UNKNOWN = "unknown"

_SYSTEM_MEMO: dict[tuple[str | None, ...], str] = {}
"""The system config path git names, per git binary and environment, for the process.

The path is compiled into the git binary (its prefix), so one answer serves every
scope; `GIT_CONFIG_NOSYSTEM` / `GIT_CONFIG_SYSTEM` are read before this memo is."""

MAX_INCLUDE_DEPTH = 10
"""git's own `MAX_INCLUDE_DEPTH`: a deeper chain (a cycle, say) declines."""

_SECTION = re.compile(r'^\s*\[\s*([A-Za-z0-9.-]+)\s*(?:"((?:[^"\\\n]|\\.)*)")?\s*\](.*)$')
_KEY = re.compile(r"^\s*([A-Za-z][A-Za-z0-9-]*)\s*(=\s*(.*))?$")
_ESCAPES = {"n": "\n", "t": "\t", "b": "\b", "\\": "\\", '"': '"'}

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
    if os.environ.get("GIT_CONFIG"):
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
    if _env_includes():
        return None
    roots = (*((Path(system),) if system else ()), *_global_configs(), common / "config")
    files: list[Path] = []
    for path in roots:
        if not _visit_config(path, 0, files):
            return None
    return Located(git_dir=git_dir, common_dir=common, config_files=tuple(files))


def head_target(located: Located, remote: str) -> str | None:
    """The branch `refs/remotes/<remote>/HEAD` names, read from its loose file, or None."""
    try:
        text = (located.common_dir / "refs" / "remotes" / remote / "HEAD").read_text()
    except OSError:
        return None
    prefix = f"ref: refs/remotes/{remote}/"
    line = text.strip()
    return (line.removeprefix(prefix) or None) if line.startswith(prefix) else None


def _visit_config(path: Path, depth: int, files: list[Path]) -> bool:
    """Add *path* and every file it includes to *files*; False when the cache must decline."""
    files.append(path)
    try:
        text = path.read_text(errors="replace")
    except FileNotFoundError:
        return True
    except OSError:
        return False
    if _WORKTREE_CONFIG.search(text):
        return False
    included = _include_paths(text)
    if included is None:
        return False
    for raw in included:
        target = _resolve_include(raw, path)
        if target is None or depth + 1 > MAX_INCLUDE_DEPTH:
            return False
        if not _visit_config(target, depth + 1, files):
            return False
    return True


def _include_paths(text: str) -> list[str] | None:
    """Every `include.path` / `includeIf.<cond>.path` value in *text*, or None when
    an include section or value is spelled in a form this reader does not parse."""
    found: list[str] = []
    section: str | None = None
    for line in text.splitlines():
        header = _SECTION.match(line)
        if header:
            name, sub, line = header.group(1).lower(), header.group(2), header.group(3)
            if name.startswith("include"):
                if not ((name == "include" and sub is None) or (name == "includeif" and sub)):
                    return None
                section = "include"
            else:
                section = name
            if not line.strip():
                continue
        elif line.lstrip().startswith("["):
            if "include" in line.lower():
                return None
            section = None
            continue
        if section != "include":
            continue
        stripped = line.strip()
        if not stripped or stripped[0] in "#;":
            continue
        key = _KEY.match(stripped)
        if key is None:
            return None
        if key.group(1).lower() != "path":
            continue
        value = _parse_value(key.group(3)) if key.group(2) is not None else None
        if not value:
            return None
        found.append(value)
    return found


def _parse_value(raw: str) -> str | None:
    """A config value as git reads it (quotes, escapes, comments), or None."""
    out: list[str] = []
    pending = ""
    quoted = False
    i = 0
    while i < len(raw):
        c = raw[i]
        if c == "\\":
            escaped = _ESCAPES.get(raw[i + 1]) if i + 1 < len(raw) else None
            if escaped is None:
                return None  # a continuation line or an unknown escape
            out.append(pending + escaped)
            pending = ""
            i += 2
            continue
        if c == '"':
            quoted = not quoted
        elif not quoted and c in "#;":
            break
        elif not quoted and c.isspace():
            pending += c
        else:
            out.append(pending + c)
            pending = ""
        i += 1
    return None if quoted else "".join(out)


def _resolve_include(raw: str, including: Path) -> Path | None:
    """An include path as git resolves it, or None when it is not a concrete file."""
    if "%(" in raw:
        return None
    if raw.startswith("~/"):
        home = os.environ.get("HOME")
        if not home:
            return None
        return Path(home) / raw[2:]
    if raw.startswith("~"):
        return None
    target = Path(raw)
    return target if target.is_absolute() else including.parent / target


def fingerprint(
    located: Located, remote: str | None, ref_names: tuple[str, ...]
) -> tuple[Any, ...]:
    """What the answer depends on, as `os.stat` sees it. Starts no process."""
    common = located.common_dir
    paths = [
        *located.config_files,
        # The per-worktree HEAD: an `includeIf "onbranch:..."` follows it.
        located.git_dir / "HEAD",
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
    """The system config path, "" for none, or `_UNKNOWN`. Asked of git once per process
    for each git binary (`_SYSTEM_MEMO`)."""
    if _truthy(os.environ.get("GIT_CONFIG_NOSYSTEM", "")):
        return ""
    configured = os.environ.get("GIT_CONFIG_SYSTEM")
    if configured is not None:
        return configured or _UNKNOWN
    binary = shutil.which("git")
    key = (
        os.path.realpath(binary) if binary else None,
        os.environ.get("GIT_EXEC_PATH"),
        os.environ.get("PREFIX"),
    )
    if key in _SYSTEM_MEMO:
        return _SYSTEM_MEMO[key]
    found = _ask_system_config(here)
    if found != _UNKNOWN:
        _SYSTEM_MEMO[key] = found
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
