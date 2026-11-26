"""What the merge paths share (spec 2026-09-25-triage-batches §3.F; spec
2026-11-19-wave-merge-queue R22, R23): the merge method choice, the context a forge write
runs in, the required-checks rule (R4), and the one conflict-resolution rule a combination
is built by. The retired merge train's walk, its update path and `batch merge`'s own merge
loop are gone: every merge is an entry of the wave merge queue (`fr.triage.wave_queue`,
`fr.triage.queue_exec`).

Every forge operation is a `GhClient` adapter call (§3.J) and every git operation goes
through the checkout / worktree seam (`fr.triage.gitseam`), both passed in, so this module
runs no process itself and tests drive it with fakes.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from fr.checkstate import bucket_verdict
from fr.ghclient import MERGE_METHODS, GhClient
from fr.triage.batch_dispatch import TRIAGE_CONFIG_PATH
from fr.triage.batch_drive import ChecksVerdict, checks_verdict
from fr.triage.batch_version import (
    all_version_files,
    is_lockfile,
    only_version_changed,
    read_source,
)
from fr.triage.errors import ConfigError, TriageError
from fr.triage.gitseam import GitError
from fr.triage.model import VersionBlock


class MergeStopError(TriageError):
    """The queue stops here (exit 1): the message says why and what to do."""


class MergeConflictError(MergeStopError):
    """A real conflict: merge refused to resolve *paths* bringing *batch*'s PR at *head*
    up to date (spec 2026-10-06-verification-strategies §G; R19). Not a moved head, so a
    driver steps over it; it hands the conflict back to the batch's session. *onto* is the
    commit the queue was building it on, or, handed back, the stack target its brief names
    from *onto_ref*; *reissue* marks a free re-issue (wave-queue-gaps §A, R1-R3)."""

    def __init__(
        self, message: str, *, batch: str, head: str, paths: Sequence[str], onto: str = "",
        onto_ref: str = "", reissue: bool = False,
    ) -> None:  # fmt: skip
        super().__init__(message)
        self.batch, self.head, self.paths, self.onto = batch, head, tuple(paths), onto
        self.onto_ref, self.reissue = onto_ref, reissue


class WorktreeSeam(Protocol):
    """The scratch worktree the conflict probe merges in (batch-train-truth R17)."""

    path: Path

    def merge(self, ref: str) -> list[str]: ...
    def merge_base(self, ref: str) -> str: ...
    def show(self, ref: str, file: str) -> str | None: ...
    def abort_merge(self) -> None: ...


class CheckoutSeam(Protocol):
    path: Path

    def fetch(self) -> None: ...
    def default_branch(self) -> str: ...
    def show(self, ref: str, file: str) -> str | None: ...
    def add_worktree(self, where: Path, ref: str) -> Any: ...
    def remove_worktree(self, where: Path) -> None: ...
    def prune_worktrees(self) -> None: ...
    def rev_parse(self, ref: str) -> str: ...


@dataclass
class MergeContext:
    """What a forge write of the merge path runs in: the repo's client and clone, its
    `version:` block, its merge method, and what the pass read of it (`ci none`)."""

    client: GhClient
    checkout: CheckoutSeam
    repo: str
    version: VersionBlock | None
    method: str
    # The repo declares `ci none` on its default branch (R4): green on non-draft alone.
    ci_none: bool = False

    @property
    def main(self) -> str:
        return f"origin/{self.checkout.default_branch()}"


def choose_method(
    explicit: str | None, methods: dict[str, Any], *, configured: str | None = None
) -> str:
    """The merge method (spec §3.F step 2): *explicit*, else the repo's default,
    else *configured* (`.fr/triage.yaml`'s `merge_method`, cloud-triage §A: REST
    names no default), else the one method the repo allows.

    *methods* is `GhClient.repo_merge_methods`: `{default, allowed}`. An
    explicit or configured method the repo disallows is refused here, before
    anything merges, rather than by the forge mid-queue (review r3-f4).
    """
    allowed = sorted(str(m) for m in methods.get("allowed") or [] if m in MERGE_METHODS)
    if not allowed:
        raise ConfigError("the repo allows no merge method fr knows (merge, squash, rebase)")
    if explicit is not None:
        if explicit not in allowed:
            raise ConfigError(
                f"--method {explicit}: the repo does not allow it (allowed: {', '.join(allowed)})"
            )
        return explicit
    default = methods.get("default")
    if default in allowed:
        return str(default)
    if configured is not None:
        if configured not in allowed:
            raise ConfigError(
                f"merge_method: {configured} in {TRIAGE_CONFIG_PATH}: the repo does not allow it "
                f"(allowed: {', '.join(allowed)}); change it, or give --method"
            )
        return configured
    if len(allowed) == 1:
        return allowed[0]
    raise ConfigError(
        "the repo names no default merge method you may use; set `merge_method` in "
        f"{TRIAGE_CONFIG_PATH} or give --method ({', '.join(allowed)})"
    )


def pr_checks_verdict(
    client: GhClient, repo: str, number: int, *, ci_none: bool
) -> tuple[ChecksVerdict, tuple[str, ...]]:
    """R4 on the PR's head as the forge reports it now: the required checks when
    the branch has any, else every check; nothing reported is pending (gh#880).
    The one rule the driver pass, `batch merge` and the archive step merge by."""
    if ci_none:
        return checks_verdict([], {}, ci_none=True)
    required = client.pr_required_checks(repo, number)
    every = {} if required else _counts(client.pr_checks(repo, number))
    return checks_verdict(required, every, ci_none=False)


def live_checks(ctx: MergeContext, number: int) -> tuple[ChecksVerdict, tuple[str, ...]]:
    """`pr_checks_verdict` for the context's repo."""
    return pr_checks_verdict(ctx.client, ctx.repo, number, ci_none=ctx.ci_none)


def _counts(checks: Sequence[dict[str, Any]]) -> dict[str, int]:
    """`pr_checks` buckets as the `pass`/`fail`/`pending` counts R4 reads; a
    skipped check passes and a cancelled one is pending (`fr.checkstate`), as in the
    collected counts."""
    counts = {"pass": 0, "fail": 0, "pending": 0}
    for c in checks:
        counts[bucket_verdict(c.get("bucket"))] += 1
    return counts


def unresolvable(
    version: VersionBlock | None,
    show: Callable[[str, str], str | None],
    base: str,
    side: str,
    conflicted: list[str],
) -> list[str]:
    """The conflicted paths a merge may NOT resolve by taking the other side's file, and
    whether a relock must regenerate a lockfile it did take (spec §3.F step 3). *side* is
    the PR's ref and *base* the merge base; *show* reads a file at a ref.

    `git checkout --theirs` (or `--ours`) replaces the WHOLE file, so a declared version
    file is taken only when the PR's own change to it, from the merge base, is the
    version and nothing else (review r3-f2): then `set` re-applies the slot and
    nothing the PR wrote is lost. A lockfile the PR changed further is taken
    only when a `relock` is declared to regenerate it from the manifests.
    Everything else is a real conflict. The wave merge queue builds by the same rule
    (spec 2026-11-19-wave-merge-queue R6).
    """
    if version is None:
        return list(conflicted)
    old_text, new_text = show(base, version.source.file), show(side, version.source.file)
    if old_text is None or new_text is None:
        return list(conflicted)
    old, new = read_source(old_text, version.source), read_source(new_text, version.source)
    out: list[str] = []
    for path in conflicted:
        if not all_version_files([path], version.files):
            out.append(path)
            continue
        before, after = show(base, path), show(side, path)
        if (
            before is not None
            and after is not None
            and only_version_changed(before, after, old, new)
        ):
            continue
        if is_lockfile(path) and version.relock:
            continue
        out.append(path)
    return out


def merge_main(
    wt: WorktreeSeam, main: str, version: VersionBlock | None
) -> tuple[list[str], list[str]]:
    """Start merging *main* into the PR branch checked out in *wt*: the conflicted paths,
    and the ones merge will NOT resolve (`unresolvable`). The merge is left in progress:
    the caller takes main's side of the resolvable ones, or aborts it."""
    conflicted = wt.merge(main)
    if not conflicted:
        return conflicted, []
    if version is None:  # every conflicted path is a real conflict: no file to read
        return conflicted, list(conflicted)
    return conflicted, unresolvable(version, wt.show, wt.merge_base(main), "HEAD", conflicted)


def _clear_scratch(checkout: CheckoutSeam, where: Path, *, added: bool = False) -> str | None:
    """Remove the probe's scratch worktree at *where* and its registration. A removal git
    refuses falls back to deleting the directory (a probe's worktree never holds operator
    work), then `git worktree prune` forgets it, so a registration whose directory is gone
    never blocks the next `worktree add` there. *added*: this probe added it, so it is
    removed even when its directory is not there to see. Why it is still there, else None."""
    failed: str | None = None
    if added or where.exists():
        try:
            checkout.remove_worktree(where)  # which prunes too
            return None
        except GitError as exc:
            failed = str(exc)
            shutil.rmtree(where, ignore_errors=True)
    try:
        checkout.prune_worktrees()
    except GitError as exc:
        return f"{failed}; {exc}" if failed else str(exc)
    return failed if where.exists() else None


def trial_conflicts(
    checkout: CheckoutSeam,
    main: str,
    version: VersionBlock | None,
    head: str,
    *,
    scratch_root: Path | None = None,
    warn: Callable[[str], None] | None = None,
) -> list[str]:
    """R17: the paths on which PR head *head* really conflicts with *main* (what the queue's build
    would refuse), by a trial merge in a scratch worktree that is always aborted and
    removed. A version file whose PR change is the version alone, and a lockfile when the
    repo relocks, are resolved, not conflicts. Writes nothing the repo keeps. A scratch
    worktree the cleanup could not clear is said to *warn*; it never masks the verdict."""
    own = scratch_root is None
    root = Path(tempfile.mkdtemp(prefix="fr-conflict-probe-")) if scratch_root is None else (
        scratch_root
    )  # fmt: skip
    where = root / f"probe-{head[:12]}"
    wt: WorktreeSeam | None = None
    try:
        _clear_scratch(checkout, where)  # a probe's leftover: `worktree add` says if it stays
        wt = checkout.add_worktree(where, head)
        conflicted, refused = merge_main(wt, main, version)
        if conflicted:
            wt.abort_merge()
        return refused
    finally:
        try:  # cleanup never masks what is in flight, and never skips the temp root
            added = wt is not None
            left = _clear_scratch(checkout, where, added=added) if added or where.exists() else None
            if left is not None and warn is not None:
                warn(f"the conflict probe's scratch worktree {where} was not removed: {left}")
        finally:
            if own:
                shutil.rmtree(root, ignore_errors=True)
