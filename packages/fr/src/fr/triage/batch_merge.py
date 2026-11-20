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

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from fr.ghclient import MERGE_METHODS, BaseRules, GhClient
from fr.triage.approval import PatchIdOf
from fr.triage.batch_dispatch import TRIAGE_CONFIG_PATH
from fr.triage.batch_drive import ChecksVerdict, checks_verdict
from fr.triage.batch_version import (
    all_version_files,
    is_lockfile,
    only_version_changed,
    read_source,
)
from fr.triage.errors import TriageError
from fr.triage.model import VersionBlock

FAILING_BUCKETS = frozenset({"fail", "cancel"})


class MergeStopError(TriageError):
    """The queue stops here (exit 1): the message says why and what to do."""


class MergeConflictError(MergeStopError):
    """A real conflict: merge refused to resolve *paths* bringing *batch*'s PR at *head*
    up to date (spec 2026-10-06-verification-strategies §G; R19). Not a moved head, so a
    driver steps over it; it hands the conflict back to the batch's session."""

    def __init__(self, message: str, *, batch: str, head: str, paths: Sequence[str]) -> None:
        super().__init__(message)
        self.batch, self.head, self.paths = batch, head, tuple(paths)


class CheckoutSeam(Protocol):
    path: Path

    def fetch(self) -> None: ...
    def default_branch(self) -> str: ...
    def show(self, ref: str, file: str) -> str | None: ...
    def rev_parse(self, ref: str) -> str: ...


@dataclass
class MergeContext:
    """What a forge write of the merge path runs in: the repo's client and clone, its
    `version:` block, its merge method, and what the pass read of it (`ci none`, the base
    branch's rules, the patch-id reader)."""

    client: GhClient
    checkout: CheckoutSeam
    repo: str
    version: VersionBlock | None
    method: str
    say: Callable[[str], None]
    # The repo declares `ci none` on its default branch (R4): green on non-draft alone.
    ci_none: bool = False
    # The base branch's rules, read once per repo per pass (merge-train-safety §D, R12).
    rules: BaseRules = field(default_factory=BaseRules)
    # Reads a PR's patch-id at a head (spec 2026-11-19-wave-merge-queue R12): the approval
    # gate compares it; None judges approvals by `reaches` alone.
    patch_id_of: PatchIdOf | None = None

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
        raise TriageError("the repo allows no merge method fr knows (merge, squash, rebase)")
    if explicit is not None:
        if explicit not in allowed:
            raise TriageError(
                f"--method {explicit}: the repo does not allow it (allowed: {', '.join(allowed)})"
            )
        return explicit
    default = methods.get("default")
    if default in allowed:
        return str(default)
    if configured is not None:
        if configured not in allowed:
            raise TriageError(
                f"merge_method: {configured} in {TRIAGE_CONFIG_PATH}: the repo does not allow it "
                f"(allowed: {', '.join(allowed)}); change it, or give --method"
            )
        return configured
    if len(allowed) == 1:
        return allowed[0]
    raise TriageError(
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
    skipped check passes, as in the collected counts."""
    counts = {"pass": 0, "fail": 0, "pending": 0}
    for c in checks:
        bucket = c.get("bucket")
        counts[
            "fail" if bucket in FAILING_BUCKETS else "pending" if bucket == "pending" else "pass"
        ] += 1
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
