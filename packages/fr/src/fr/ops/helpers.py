"""Safety helpers for ops (spec 2026-10-22-fr-ops R10, §F): `seal`, `secret`, `clip`,
`scratch`. Tool-neutral: the encryption, secret-reading and cleanup commands are the
caller's strings; nothing here names a tool.

`cleanup_guard` is the one temp-file/cleanup context manager `seal` and `scratch` share:
its cleanups run on every exit path, SIGINT and SIGTERM included.
"""

from __future__ import annotations

import contextlib
import os
import shlex
import shutil
import signal
import stat
import subprocess
import tempfile
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

from fr.ops.probe import DEFAULT_TIMEOUT, TIMED_OUT, run_probe

CLIPBOARD_TOOLS: tuple[tuple[str, ...], ...] = (
    ("pbcopy",),
    ("wl-copy",),
    ("xclip", "-selection", "clipboard"),
    ("clip.exe",),
)
_SIGNALS = (signal.SIGINT, signal.SIGTERM)


class HelperError(Exception):
    """A helper refused or failed; the message says why (never a secret)."""


class _Interrupted(BaseException):
    def __init__(self, signum: int) -> None:
        self.signum = signum


@contextlib.contextmanager
def cleanup_guard() -> Iterator[list[Callable[[], None]]]:
    """Yield a list of cleanups to run (in reverse) on every exit: normal, an
    exception, SIGINT or SIGTERM. A signal unwinds as `_Interrupted`, which is turned
    into the conventional `128 + n` exit after the cleanups ran."""
    cleanups: list[Callable[[], None]] = []

    def handler(signum: int, _frame: object) -> None:
        raise _Interrupted(signum)

    previous = {s: signal.signal(s, handler) for s in _SIGNALS}
    try:
        yield cleanups
    except _Interrupted as e:
        _run(cleanups)
        raise SystemExit(128 + e.signum) from None
    else:
        _run(cleanups)
    finally:
        _run(cleanups)  # an exception path; a no-op once emptied
        for s, old in previous.items():
            signal.signal(s, old)


def _run(cleanups: list[Callable[[], None]]) -> None:
    while cleanups:
        fn = cleanups.pop()
        try:
            fn()
        except Exception:  # noqa: BLE001, S110 — cleanup is best effort, all of it runs
            pass


def _unlink(path: Path) -> Callable[[], None]:
    return lambda: path.unlink(missing_ok=True)


def _inside(path: Path, root: Path) -> bool:
    try:
        return path.resolve().is_relative_to(root.resolve())
    except OSError:
        return False


def _run_child(
    argv: Sequence[str], *, stdin: bytes | None = None
) -> subprocess.CompletedProcess[bytes]:
    """Run `argv` and wait; a signal during the wait kills the child before the
    cleanups run."""
    proc = subprocess.Popen(
        argv, stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL
    )
    try:
        proc.communicate(stdin)
    except BaseException:
        proc.kill()
        proc.wait()
        raise
    return subprocess.CompletedProcess(list(argv), proc.returncode)


def _checked_target(target: Path, repo_root: Path) -> Path:
    """The target, absolute, refused unless it lies inside the repo with no symlink on
    the way (the target itself or any parent below the repo root): a planted link
    would otherwise make the final rename overwrite a file elsewhere."""
    lexical = Path(os.path.normpath(target if target.is_absolute() else Path.cwd() / target))
    for base in (repo_root, repo_root.resolve()):
        try:
            rel = lexical.relative_to(base)
        except ValueError:
            continue
        walk = base
        for part in rel.parts:
            walk = walk / part
            if walk.is_symlink():
                raise HelperError(f"{walk} is a symlink; refusing to seal through it")
        break
    else:
        raise HelperError(f"{lexical} is outside the repo ({repo_root}); refusing to seal it")
    if not _inside(lexical, repo_root):
        raise HelperError(f"{lexical} resolves outside the repo; refusing to seal it")
    return lexical


def seal(encrypt: str, target: Path, plaintext: bytes, *, repo_root: Path) -> int:
    """Encrypt `plaintext` into `target` through the caller's command.

    `{in}`: a 0600 plaintext temp file under `$TMPDIR` (refused when that is inside the
    repo); `{out}`: an empty 0600 temp file beside the target; `{target}`: the target's
    path as a name. Every substitution is shell-quoted. The target is replaced, as
    bytes, only when the command exited 0 and `{out}` is non-empty; on any other end the
    target is untouched, both temps are gone and the return is non-zero."""
    tmp_root = Path(tempfile.gettempdir())
    if _inside(tmp_root, repo_root):
        raise HelperError(
            f"TMPDIR ({tmp_root}) resolves inside the repo; plaintext must not land there — "
            "point TMPDIR elsewhere"
        )
    target = _checked_target(target, repo_root)
    with cleanup_guard() as cleanups:
        fd, in_name = tempfile.mkstemp(prefix=".seal-in-", dir=tmp_root)
        in_path = Path(in_name)
        cleanups.append(_unlink(in_path))
        with os.fdopen(fd, "wb") as f:
            f.write(plaintext)
        fd, out_name = tempfile.mkstemp(prefix=".seal-out-", dir=target.parent)
        os.close(fd)
        out_path = Path(out_name)
        cleanups.append(_unlink(out_path))
        command = (
            encrypt.replace("{in}", shlex.quote(str(in_path)))
            .replace("{out}", shlex.quote(str(out_path)))
            .replace("{target}", shlex.quote(str(target)))
        )
        rc = _run_child(["bash", "-euo", "pipefail", "-c", command]).returncode
        if rc != 0:
            return rc
        if out_path.stat().st_size == 0:
            return 1
        mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o644
        os.chmod(out_path, mode)
        os.replace(out_path, target)
        return 0


def read_value(source: str, repo_root: Path, *, timeout: float = DEFAULT_TIMEOUT) -> str:
    """The value a `--from` command prints, read live; its output is never echoed."""
    rc, out = run_probe(source, repo_root, timeout=timeout)
    value = out.rstrip("\n")
    if rc == TIMED_OUT:
        raise HelperError("the value could not be read (timed out)")
    if rc != 0 or not value:
        raise HelperError(f"the value could not be read (exit {rc})")
    return value


def secret(source: str, command: Sequence[str], *, repo_root: Path) -> int:
    """Run `command` with the value of `source` on its stdin; the value never goes to
    this process's stdout."""
    value = read_value(source, repo_root)
    return _run_child(list(command), stdin=value.encode()).returncode


def clip(source: str, *, repo_root: Path) -> int:
    """Put the value of `source` on the clipboard, through the first tool found."""
    for tool in CLIPBOARD_TOOLS:
        if shutil.which(tool[0]):
            value = read_value(source, repo_root)
            return _run_child(list(tool), stdin=value.encode()).returncode
    names = ", ".join(t[0] for t in CLIPBOARD_TOOLS)
    raise HelperError(f"no clipboard tool on PATH (looked for {names})")


def scratch(cleanup: str, command: Sequence[str]) -> int:
    """Run `command`, then `cleanup`, whatever the command's end (success, failure,
    SIGINT, SIGTERM). Returns the command's exit status."""
    with cleanup_guard() as cleanups:
        cleanups.append(
            lambda: subprocess.run(["bash", "-c", cleanup], stdin=subprocess.DEVNULL, check=False)
        )
        return _run_child(list(command)).returncode
