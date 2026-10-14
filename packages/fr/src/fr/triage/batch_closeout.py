"""The collected close-out (spec 2026-10-14-exit-gates R15, R16, §E).

`fr triage batch closeout` closes out every landed batch that is not gated, not held and
not yet closed out, in ONE session and ONE housekeeping PR, on the branch
`chore/closeout-<YYYY-MM-DD>-<n>`. For each batch, in order:

1. `fr isolation verify-merge --branch <b> --default-branch <default>`: exit 1 (not
   verified) holds the batch; an exit 2 saying the merged branch's ref cannot be resolved
   (deleted at merge) disproves nothing and goes on; any other exit 2 is transient;
2. a batch whose gates passed: `fr closeout outcome --ran --evidence <gate-pass comment>`
   for each Test Plan step with no outcome yet;
3. `fr archive --branch <b> --no-issues` (finding filing moved to `deliver`, R10).

A batch whose step fails, or that could not be read, is reset to where it started and
moves nothing. A deterministic failure (verify-merge exit 1, an archive refusal, an
unreadable matrix or section) gets a durable `closeout_hold` event (the reason and the
item); a transient one (any other) leaves the batch owed and is only reported. Then
one commit, one push and one PR whose body lists its member batches in an
informational block (`MEMBERS_MARKER`) and carries one `Closes <owner/repo#n>` line per issue a
passed gate's rows cite (never one a narrowing decision names), so those issues close
when the PR merges, not before. Only after the PR is open does each included batch get
its `closeout` event, whose `archive` is the shared branch.

This module decides and sequences; it runs nothing itself. The worktree (`CloseoutTree`,
`fr.triage.gitseam.Worktree`) runs git and this `fr`, and the forge is the `GhClient`
adapter, so the batch modules' forge and git tripwires hold here too.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Callable, Collection, Iterable, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from fr.labels import held_gates
from fr.triage.batch import derive_batch_stage
from fr.triage.batch_drive import (
    LANDED,
    closeout_hold,
    closeout_of,
    collected_branch,
    collected_name,
    fact_ledger_unknown,
    fact_ledgers,
    next_collected,
)
from fr.triage.model import Batch, CollectedCloseout, Facts

__all__ = [
    "MEMBERS_MARKER",
    "CloseoutForge",
    "CloseoutResult",
    "CloseoutTree",
    "Member",
    "Step",
    "closeout_owed",
    "closeout_title",
    "closes_from_body",
    "collected_branch",
    "collected_name",
    "execute",
    "handback_brief",
    "issues_to_close",
    "member_steps",
    "members_from_body",
    "next_collected",
    "plan_lines",
    "recorded_closes",
    "step_ranges",
]

StepKind = Literal["verify-merge", "outcome", "archive"]

MEMBERS_MARKER = "<!-- fr:closeout-members "
"""How the housekeeping PR body's member block begins (`<!-- fr:closeout-members a,b -->`):
informational only; membership is what the verb records on the marker (p6b-r3)."""

UNRESOLVABLE_REF = "cannot resolve branch ref"
"""verify-merge's words for a merged branch gone everywhere: its one tolerated exit 2."""

_MEMBERS_RE = re.compile(r"<!-- fr:closeout-members ([a-z0-9,-]*) -->")
_CLOSES_RE = re.compile(r"^Closes ([\w.-]+/[\w.-]+#\d+)$", re.M)


class CloseoutTree(Protocol):
    """The scratch worktree the close-out runs in (`gitseam.Worktree`)."""

    def head(self) -> str: ...

    def run_fr(self, args: list[str]) -> tuple[int, str]: ...

    def reset_hard(self, sha: str) -> None: ...

    def squash_all(self, base: str, message: str) -> str | None: ...

    def push(self, branch: str, *, force: bool = False) -> None: ...


class CloseoutForge(Protocol):
    """The forge write the close-out makes (the `GhClient` adapter's method)."""

    def pr_create(self, repo: str, *, head: str, base: str, title: str, body: str) -> int: ...


@dataclass(frozen=True)
class Member:
    """One batch of a collected close-out, as the command read it.

    `run` is None for a batch with no run cursor (a debug batch): it still verifies its
    merge and archives. `passed` are the merged PR's passed post-merge gates; `evidence`
    the gate-pass comment's URL; `missing` the Test Plan steps with no outcome yet;
    `closes` the issues (`owner/repo#n`) the passed gates' rows cite, narrowed ones
    already removed (`issues_to_close`)."""

    batch: str
    branch: str
    run: str | None = None
    passed: tuple[str, ...] = ()
    evidence: str | None = None
    missing: tuple[int, ...] = ()
    closes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Step:
    kind: StepKind
    argv: tuple[str, ...]  # the `fr` arguments

    @property
    def line(self) -> str:
        return "fr " + shlex.join(self.argv)


@dataclass(frozen=True)
class CloseoutResult:
    branch: str
    done: tuple[str, ...]  # batch ids closed out, in order
    held: tuple[tuple[str, str], ...]  # (batch id, why): moved nothing, a hold event
    pr: int | None = None
    head: str | None = None  # the pushed head
    skipped: tuple[tuple[str, str], ...] = ()  # transient failures: owed still, no event


def closeout_owed(
    batches: Sequence[Batch],
    facts: Facts,
    closeouts: Iterable[CollectedCloseout] = (),
    *,
    named: Collection[str] = (),
    reserved: Collection[str] = (),
) -> list[Batch]:
    """R15's batches: landed, not gated, and not closed out (no close-out event, or one
    whose collected PR was closed unmerged). A batch held by an earlier close-out is owed
    only when *named* (the explicit retry). A landed batch whose merged PR's labels could
    not be read is not known ungated (p4-r1), so it waits."""
    stages = {b.id: derive_batch_stage(b, facts) for b in batches}
    ledgers = fact_ledgers(batches, facts, stages)
    unknown = fact_ledger_unknown(batches, facts, stages)
    markers = tuple(closeouts)
    out: list[Batch] = []
    for b in batches:
        if stages[b.id] not in LANDED or b.id in unknown:
            continue
        if closeout_of(b, markers) is not None:
            continue
        if closeout_hold(b) is not None and b.id not in named:
            continue
        if b.id in reserved:  # another collected close-out under way plans it (p6b-r7)
            continue
        ledger = ledgers.get(b.id)
        if ledger is not None and held_gates(ledger.labels):
            continue
        out.append(b)
    return out


def step_ranges(numbers: Sequence[int]) -> list[str]:
    """`fr closeout outcome --step` values: consecutive numbers folded to `N-M`."""
    out: list[str] = []
    for n in sorted(set(numbers)):
        if out and int(out[-1].rpartition("-")[2]) == n - 1:
            lo = out[-1].partition("-")[0]
            out[-1] = f"{lo}-{n}"
        else:
            out.append(str(n))
    return out


def issues_to_close(cited: Iterable[str], *, narrowed: Iterable[str]) -> tuple[str, ...]:
    """The issues to close: *cited*, never one a narrowing decision names (compared
    case-insensitively, as GitHub matches owner and repo)."""
    never = {n.lower() for n in narrowed}
    return tuple(dict.fromkeys(c for c in cited if c.lower() not in never))


def member_steps(m: Member, default: str) -> tuple[Step, ...]:
    """R15's steps for one batch, in order (the issue closes ride the PR body)."""
    verify = ("isolation", "verify-merge", "--repo", ".", "--branch", m.branch,
              "--default-branch", default)  # fmt: skip
    steps = [Step("verify-merge", verify)]
    if m.passed and m.run and m.evidence:
        steps += [
            Step(
                "outcome",
                (
                    "closeout",
                    "outcome",
                    "--run",
                    m.run,
                    "--step",
                    r,
                    "--ran",
                    "--evidence",
                    m.evidence,
                ),
            )  # fmt: skip
            for r in step_ranges(m.missing)
        ]
    steps.append(Step("archive", ("archive", "--branch", m.branch, "--no-issues")))
    return tuple(steps)


def plan_lines(members: Sequence[Member], branch: str, default: str) -> list[str]:
    """What `--yes` would do, without it."""
    lines = [f"collected close-out on {branch}, one PR:"]
    for m in members:
        lines += [f"  {m.batch}: {s.line}" for s in member_steps(m, default)]
        lines += [f"  {m.batch}: Closes {ref} when the PR merges" for ref in m.closes]
    return lines


def members_from_body(body: str) -> tuple[str, ...]:
    """The member batch ids a housekeeping PR body lists (`MEMBERS_MARKER`); () if none."""
    m = _MEMBERS_RE.search(body or "")
    return tuple(b for b in (m.group(1).split(",") if m else ()) if b)


def closes_from_body(body: str) -> tuple[str, ...]:
    """The `owner/repo#n` issues a housekeeping PR body closes (`Closes ...` lines)."""
    return tuple(_CLOSES_RE.findall(body or ""))


def recorded_closes(done: Sequence[Member], repo: str) -> tuple[str, ...]:
    """The issues the PR closes: the passed gates' row issues of its members (narrowed ones
    already out), in *repo* only (p6b-r5)."""
    mine = repo.lower() + "#"
    return tuple(dict.fromkeys(
        ref for m in done if m.passed for ref in m.closes if ref.lower().startswith(mine)
    ))  # fmt: skip


def pr_body(done: Sequence[Member], held: Sequence[tuple[str, str]], repo: str = "") -> str:
    """The housekeeping PR's body: its members (informational, never read back for
    membership); one `Closes` line per recorded issue."""
    ids = [m.batch for m in done]
    closes = (
        list(recorded_closes(done, repo))
        if repo
        else list(dict.fromkeys(ref for m in done if m.passed for ref in m.closes))
    )
    lines = [f"Collected close-out of {len(ids)} landed batch(es) (exit-gates R15):", "",
             *(f"- {m.batch} ({m.branch})" for m in done), "",
             f"{MEMBERS_MARKER}{','.join(ids)} -->"]  # fmt: skip
    if closes:
        lines += ["", *(f"Closes {ref}" for ref in closes)]
    if held:
        lines += ["", "Held, not in this PR:", *(f"- {b}: {w}" for b, w in held)]
    return "\n".join(lines)


def handback_brief(*, pr: int, branch: str, base: str, checks: Sequence[str]) -> str:
    """R27's one hand-back to the collected close-out's session: what is wrong with its PR
    and where to fix it. A second failure goes to the operator, not back here."""
    what = (
        f"conflicts with {base}"
        if tuple(checks) == ("merge conflict",)
        else f"has failing checks: {', '.join(checks) or 'unknown'}"
    )
    return (
        f"The collected close-out PR #{pr} on {branch} {what}.\n"
        f"Fix it on {branch}: merge origin/{base} in, resolve, run the failing checks "
        f"locally, and push; then run `fr triage batch closeout --branch {branch} --yes`, "
        f"which records the new head (the driver merges only a head the verb recorded). "
        f"This is its one hand-back: a second failure goes to the operator."
    )


def closeout_title(branch: str, batches: Sequence[str]) -> str:
    return f"chore: collected close-out {branch.removeprefix('chore/')} ({', '.join(batches)})"


def _why(step: Step, code: int, out: str) -> str:
    last = next((ln.strip() for ln in reversed(out.splitlines()) if ln.strip()), "")
    return f"`{step.line}` exited {code}" + (f": {last}" if last else "")


def execute(
    members: Sequence[Member],
    *,
    tree: CloseoutTree,
    forge: CloseoutForge,
    repo: str,
    default: str,
    branch: str,
    record: Callable[[str, str], None],
    hold: Callable[[str, str], None],
    say: Callable[[str], None],
    unreadable: Sequence[tuple[str, str]] = (),
    transient: Sequence[tuple[str, str]] = (),
) -> CloseoutResult:
    """Run every batch's steps in *tree* (on *branch*, cut from *default*), then one
    commit, one push and one PR. *hold*(batch id, why) each batch held (the *unreadable*
    ones first); *record*(batch id, branch) each batch the PR carries, only once it is
    open."""
    base = tree.head()
    done: list[Member] = []
    held: list[tuple[str, str]] = list(unreadable)
    skipped: list[tuple[str, str]] = list(transient)
    for m in members:
        start = tree.head()
        why = ""
        durable = False
        for step in member_steps(m, default):
            code, out = tree.run_fr(list(step.argv))
            if code == 0:
                continue
            if step.kind == "verify-merge" and code == 2 and UNRESOLVABLE_REF in out:
                say(f"{m.batch}: the merged branch {m.branch} is gone; verify-merge proves "
                    "nothing either way, the merged PR stands")  # fmt: skip
                continue
            why = _why(step, code, out)
            durable = (step.kind, code) == ("verify-merge", 1) or step.kind == "archive"
            break
        if why:
            tree.reset_hard(start)
            (held if durable else skipped).append((m.batch, why))
            continue
        done.append(m)
        say(f"{m.batch}: closed out on {branch}")
    for bid, why in held:
        hold(bid, why)
        say(f"{bid}: held, moved nothing: {why}")
    for bid, why in skipped:
        say(f"{bid}: not closed out this time (transient, still owed): {why}")
    ids = [m.batch for m in done]
    if not done:
        return CloseoutResult(branch, (), tuple(held), skipped=tuple(skipped))
    title = closeout_title(branch, ids)
    head = tree.squash_all(base, title)
    if head is None:
        say("nothing to commit: no PR opened")
        return CloseoutResult(branch, (), tuple(held), skipped=tuple(skipped))
    tree.push(branch)
    pr = forge.pr_create(repo, head=branch, base=default, title=title,
                         body=pr_body(done, [*held, *skipped], repo))  # fmt: skip
    for m in done:
        record(m.batch, branch)
    return CloseoutResult(branch, tuple(ids), tuple(held), pr, head, tuple(skipped))
