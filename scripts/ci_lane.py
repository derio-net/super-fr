"""Which lane a CI run takes, and whether `ci-ok` passes it (spec 2026-11-24-ci-economy).

`ci.yml`'s first job, `classify`, picks one lane per run:

- `landed` (R5): a push to `main` whose sha already has a successful run of this CI
  workflow, triggered by a push to an `fr-queue/` branch. Only `validate-artifacts`
  runs again.
- `light` (R15, R16): a pull request whose diff changes nothing installable
  (`installable.is_installable`), nothing under `tests/` and nothing under `.github/`.
  The scoped tests run instead of the shards.
- `full`: everything else, and every answer this script cannot reach for sure.

`ci-ok` then asks `verdict` whether the needed jobs' results satisfy the lane (R17).

Subcommands:

    ci_lane.py classify --base <ref>                      (pull_request)
    ci_lane.py landed --sha <sha> --run <id> --repo <o/r> (push to main)
    ci_lane.py verdict                                    (ci-ok; reads LANE, NEEDS)

`classify` and `landed` append `lane=<lane>` (and `trusted_run=<id>`) to
`$GITHUB_OUTPUT`. Stdlib only, so it runs under `uv run --no-project`, like the other
scripts.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from installable import is_installable  # noqa: E402

FULL = "full"
LIGHT = "light"
LANDED = "landed"

# Paths outside the installable set that still change what the suite tests or how
# CI runs it (R15): a light lane over them would skip the very tests they change.
FULL_PREFIXES = ("tests/", ".github/")

Runner = Callable[..., subprocess.CompletedProcess[bytes]]


def lane_for(paths: Sequence[str]) -> str:
    """`light` when every path is non-installable and outside `tests/` and `.github/`;
    `full` otherwise, and for an empty list (a diff that names nothing proves nothing)."""
    if not paths:
        return FULL
    for path in paths:
        if is_installable(path) or path.startswith(FULL_PREFIXES):
            return FULL
    return LIGHT


def _git(args: Sequence[str], cwd: Path | None, env: Mapping[str, str] | None) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, env=_git_env(env)
    ).stdout


def _git_env(env: Mapping[str, str] | None) -> dict[str, str] | None:
    # The output file is ours; git sees the process environment otherwise.
    return None if env is None else {**os.environ, **env}


def pull_request_lane(
    base: str, *, cwd: Path | None = None, env: Mapping[str, str] | None = None
) -> str:
    """The lane of the pull request checked out at *cwd*.

    A `pull_request` checkout's HEAD is a merge commit whose second parent is the PR
    head; with one parent, HEAD is the head. The diff runs from the merge base with
    `origin/<base>` to that head, so a later change on the base is not the PR's. Any
    git failure reads `full`.
    """
    try:
        try:
            _git(["rev-parse", "--verify", "--quiet", "HEAD^2"], cwd, env)
            head = "HEAD^2"
        except subprocess.CalledProcessError:
            head = "HEAD"
        merge_base = _git(["merge-base", f"origin/{base}", head], cwd, env).decode().strip()
        diff = _git(
            ["diff", "--no-renames", "--name-only", "-z", merge_base, head, "--"], cwd, env
        )
    except (subprocess.CalledProcessError, OSError):
        return FULL
    return lane_for([os.fsdecode(p) for p in diff.split(b"\0") if p])


def _emit(pairs: Mapping[str, str], env: Mapping[str, str]) -> None:
    lines = "".join(f"{key}={value}\n" for key, value in pairs.items())
    target = env.get("GITHUB_OUTPUT")
    if target:
        with open(target, "a", encoding="utf-8") as fh:
            fh.write(lines)
    sys.stdout.write(lines)


def main(
    argv: Sequence[str] | None = None,
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="ci_lane.py")
    sub = parser.add_subparsers(dest="command", required=True)
    classify = sub.add_parser("classify", help="the lane of a pull request")
    classify.add_argument("--base", required=True)
    args = parser.parse_args(argv)
    environ: Mapping[str, Any] = os.environ if env is None else env

    if args.command == "classify":
        _emit({"lane": pull_request_lane(args.base, cwd=cwd, env=env)}, environ)
        return 0
    return 2  # pragma: no cover - argparse refuses an unknown command first


if __name__ == "__main__":
    raise SystemExit(main())
