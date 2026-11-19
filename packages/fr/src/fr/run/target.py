"""Resolve an explicitly recorded merge target without changing the remote default."""

from __future__ import annotations

from pathlib import Path

from fr.artifacts.paths import unsafe_branch
from fr.git import GitUnavailableError, git_answer


class TargetError(ValueError):
    """The recorded target cannot safely provide review evidence."""


def target_ref(root: Path, branch: str | None) -> str | None:
    """The exact remote-tracking branch; None keeps legacy default-base behavior.

    An explicit but missing target never falls back to another branch or a local
    branch of the same name. Neither HEAD nor an arbitrary revision is a target.
    """
    if branch is None:
        return None
    why = unsafe_branch(branch)
    if why is not None or branch == "HEAD" or branch.startswith("refs/"):
        raise TargetError(f"invalid merge target {branch!r}: {why or 'use a branch name'}")
    try:
        # PR creation addresses origin_slug(), not checkout.defaultRemote.
        # Reviewing another remote's same-named branch would certify a different diff.
        remote = "origin"
        if git_answer(root, "remote", "get-url", remote).returncode != 0:
            raise TargetError("cannot resolve the merge target without the PR destination origin")
        ref = f"refs/remotes/{remote}/{branch}"
        found = git_answer(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
        if found.returncode != 0:
            raise TargetError(f"merge target {remote}/{branch} is not fetched; fetch it and retry")
        return ref
    except GitUnavailableError as error:
        raise TargetError(f"cannot read the merge target: {error}") from error
