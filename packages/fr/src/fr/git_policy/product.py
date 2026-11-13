"""The ONE way the `fr` package pushes a product branch (review pr1431-r1).

A product branch is any branch of the product repo other than `fr` (quiet's artifact
branch): a run's feature branch, and the side branches `fr placement move` opens for a
PR. Every such push goes through `push_product_branch`, so the placement's guards hold
on all of them, not on `fr push` alone:

- **stealth** (R24 "what reaches the target": only the code commits): every commit the
  push adds (`commits_the_push_adds`, side branches of a merge included) is scanned for a
  path only fr writes and for a message naming fr; either refuses, before anything is
  pushed.
- **quiet** (R23): the checked-out feature branch must carry no fr artifact (the
  placement-drift reading); then the branch and `fr` go in one atomic push, with the
  pushed head recorded on `fr`. A move's side branch (pushed by `rev`) is built by fr
  itself from a verified copy and is pushed plainly.
- **repo**: a plain push.

Never forced. `tests/unit/test_tripwire_product_push.py` fails when any other module
runs `git push` against a product branch.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fr.git_policy.push import (
    PushRefusedError,
    _git,
    atomic_push,
    commits_the_push_adds,
    run_git,
)


def refuse_stealth_content(root: Path, remote: str, branch: str, rev: str = "HEAD") -> None:
    """Under stealth, refuse when a commit the push of *rev* to *branch* adds carries a
    path only fr writes, or a message naming fr (R24). No-op under any other placement."""
    from fr.artifacts.paths import STEALTH, outside_repo
    from fr.placement.stealth import fr_naming, fr_paths_in

    if outside_repo(root) != STEALTH:
        return
    commits = commits_the_push_adds(root, remote, branch, rev)
    found = fr_paths_in(root, commits)
    if found:
        raise PushRefusedError(
            f"under placement stealth no fr file reaches the target (R24), and the commits to "
            f"push carry {', '.join(found[:5])}{' ...' if len(found) > 5 else ''}. Remove "
            "them from those commits (fr keeps its state in the tracking repo) and push again"
        )
    named: list[str] = []
    for sha in commits:
        done = run_git(root, ["show", "-s", "--format=%B", sha])
        if done.returncode != 0:  # fail closed: a message fr cannot read is not pushed
            raise PushRefusedError(f"cannot read the message of commit {sha[:12]}")
        lines = fr_naming(done.stdout)
        if lines:
            named.append(f"{sha[:12]} ({lines[0]})")
    if named:
        raise PushRefusedError(
            "under placement stealth only the code commits reach the target (R24), and "
            f"{len(named)} commit message(s) to push name fr: {'; '.join(named[:5])}. Reword "
            "them and push again"
        )


def _refuse_quiet_drift(root: Path) -> None:
    """R23: under quiet the checked-out feature branch carries no fr artifact."""
    from fr.placement.drift import branch_drift, refusal

    found = branch_drift(root)
    if found is not None and found.files:
        raise PushRefusedError(refusal(found))


def push_product_branch(
    root: Path, remote: str, branch: str, *, code: bool = True, rev: str | None = None
) -> list[str]:
    """Push the product branch *branch* to *remote*; the refs pushed, in order.

    With no *rev*, *branch* is the branch checked out at *root*: under quiet it goes with
    `fr` in one atomic push (only `fr` when *code* is False). With *rev* (a branch fr
    built without checking it out), `<rev>:refs/heads/<branch>` is pushed plainly and
    its remote-tracking ref fetched."""
    from fr.artifacts.paths import QUIET, outside_repo

    root = Path(root)
    refuse_stealth_content(root, remote, branch, rev or "HEAD")
    placement = outside_repo(root)
    if rev is not None:
        _git(root, "push", "--quiet", remote, f"{rev}:refs/heads/{branch}")
        _git(root, "fetch", "--quiet", "--no-tags", remote,
             f"+refs/heads/{branch}:refs/remotes/{remote}/{branch}")  # fmt: skip
        return [branch]
    if placement != QUIET:
        _git(root, "push", "-u", remote, branch)
        return [branch]
    from fr.artifacts.paths import space_for

    if code:
        _refuse_quiet_drift(root)
    space = space_for(root)
    if code:
        _record_pushed_head(root, space)
    return atomic_push(root, space.root, remote, branch, code=code)


def _record_pushed_head(repo_root: Path, space: Any) -> None:
    """Quiet (review p5-r3): append the head about to be pushed to the feature's `HEADS`
    and commit it on `fr`, so the ONE atomic push carries the code and the record of it.
    A feature's merged status then outlives its branch's refs. Only a claimed feature
    root (one with `OWNER`) records; nothing is created for a branch with no fr work."""
    from fr.artifacts.commit import commit_paths
    from fr.artifacts.paths import FEATURE_HEADS, FEATURE_OWNER, feature_root
    from fr.placement.merged import record_head

    if space.feature is None:
        return
    froot = feature_root(space)
    if not (froot / FEATURE_OWNER).is_file():
        return
    done = run_git(repo_root, ["rev-parse", "--verify", "--quiet", "HEAD^{commit}"])
    head = done.stdout.strip() if done.returncode == 0 else ""
    if not head:
        return
    heads = froot / FEATURE_HEADS
    before = heads.read_bytes() if heads.is_file() else None
    path = record_head(froot, head)
    if path is None:
        return
    outcome = commit_paths(repo_root, [path], f"chore(fr): record pushed head {head[:12]}")
    if not (outcome.committed or outcome.unchanged):
        if before is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(before)
        raise PushRefusedError(f"cannot record the pushed head in {path}: {outcome.reason}")
