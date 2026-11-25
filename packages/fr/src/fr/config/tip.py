"""The configuration branch's fetched tip, exported to run from (spec
2026-11-19-event-driven-a-la-carte R7; review p3-r2, plan decision
p3-execute-the-exported-tip).

A program fr runs from the configuration space under quiet and stealth runs from a private
directory holding that space's `.fr/` exactly as the freshly fetched, protected tip has it,
never from the configuration checkout, whose state `git status` cannot vouch for (index flags,
`core.fileMode`). The directories are removed by `fr.config.protection.forget()` and at exit.
"""

from __future__ import annotations

import atexit
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fr.config.space import ConfigSpace

_EXPORTS: dict[tuple[str, str, str], Path] = {}
"""`(git repo, tip sha, prefix)` -> the private directory holding that tip's `.fr/`."""


def export_checked(
    space: ConfigSpace,
    client: object | None,
    what: str,
    *,
    no_fetch: bool = False,
    command: str | None = None,
) -> Path:
    """A private directory (mode 0700, removed by `forget()` and at exit) holding the
    configuration space's `.fr/` exactly as the freshly fetched, protected tip has it, file
    modes included (`git archive`); a program fr runs from the configuration space runs from
    here, at `<dir>/<space.tree_path(name)>`. The configuration checkout's state never
    matters: index flags (`assume-unchanged`, `skip-worktree`) and `core.fileMode` can hide
    a local edit from `git status`, so fr does not run the working tree at all (security
    review of p3-run-the-checked-tip)."""
    import io
    import subprocess
    import sys
    import tarfile
    import tempfile

    from fr.config.protection import UncheckedTipError, _git_out, fetch_tip, require_protected

    require_protected(space, client, what)
    fetch_tip(space, what, no_fetch=no_fetch, command=command)
    assert space.ref is not None
    repo = space.product if space.placement != "stealth" else space.checkout
    sha = (
        _git_out(repo, "rev-parse", "--verify", "--quiet", f"refs/remotes/{space.ref}^{{commit}}")
        or ""
    ).strip()
    if not sha:
        raise UncheckedTipError(f"fr will not {what}: {space.ref} is not in {repo}")
    key = (str(repo), sha, space.prefix)
    if key in _EXPORTS and _EXPORTS[key].is_dir():
        return _EXPORTS[key]
    from fr.git import git_argv

    done = subprocess.run(
        git_argv(repo, "archive", "--format=tar", sha, "--", space.prefix),
        cwd=repo,
        capture_output=True,
        check=False,
    )
    if done.returncode != 0:
        raise UncheckedTipError(
            f"fr will not {what}: git could not export {space.prefix} at {space.ref} "
            f"({done.stderr.decode(errors='replace').strip()})"
        )
    out = Path(tempfile.mkdtemp(prefix="fr-config-tip-"))
    out.chmod(0o700)
    try:
        with tarfile.open(fileobj=io.BytesIO(done.stdout)) as tar:
            tar.extractall(out, filter="data")
    except (tarfile.TarError, OSError) as exc:
        _remove(out)
        raise UncheckedTipError(
            f"fr will not {what}: cannot export {space.prefix} at {space.ref}: {exc}"
        ) from exc
    _EXPORTS[key] = out
    print(
        f"fr: {what}: running {space.prefix}/ as {space.ref} has it at {sha[:12]} (the "
        f"configuration checkout's own files are not run)",
        file=sys.stderr,
    )
    return out


def _remove(path: Path) -> None:
    import shutil

    shutil.rmtree(path, ignore_errors=True)


def drop_exports() -> None:
    """Remove every exported tip directory."""
    for path in _EXPORTS.values():
        _remove(path)
    _EXPORTS.clear()


atexit.register(drop_exports)
