"""The collected close-out (spec 2026-10-14-exit-gates R15, R16, §E).

`fr triage batch closeout` closes out every landed batch that is not gated and not yet
closed out, in ONE session and ONE housekeeping PR, on the branch
`chore/closeout-<YYYY-MM-DD>-<n>`. For each batch, in order:

1. `fr isolation verify-merge` (exit 1, not verified, holds the batch; exit 2, the merged
   branch is gone everywhere, disproves nothing and goes on);
2. a batch whose gates passed: `fr closeout outcome --ran --evidence <gate-pass comment>`
   for each Test Plan step with no outcome yet;
3. `fr archive --branch <b> --no-issues` (finding filing moved to `deliver`, R10);
4. the issues cited by the rows a passed gate gated are closed and lose
   `fr:awaiting-live`, never one a narrowing decision names.

A batch whose step fails (its archive holds: a Test Plan step with no outcome, say) is
reset to where it started: it moves nothing, gets no close-out event, and is named. Then
one commit, one push, one PR, and one close-out event per closed-out batch, whose
`archive` is the shared branch.

This module decides and sequences; it runs nothing itself. The worktree (`CloseoutTree`,
`fr.triage.gitseam.Worktree`) runs git and this `fr`, and the forge is the `GhClient`
adapter, so the batch modules' forge and git tripwires hold here too.
"""

from __future__ import annotations

import shlex
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from fr.labels import FR_AWAITING_LIVE, held_gates
from fr.triage.batch import derive_batch_stage
from fr.triage.batch_drive import (
    LANDED,
    closeout_event,
    collected_branch,
    collected_name,
    fact_ledger_unknown,
    fact_ledgers,
    next_collected,
)
from fr.triage.model import Batch, CloseoutEvent, Facts

__all__ = [
    "CloseoutForge",
    "CloseoutResult",
    "CloseoutTree",
    "Member",
    "Step",
    "closeout_owed",
    "closeout_title",
    "pending_collected",
    "collected_branch",
    "collected_name",
    "execute",
    "handback_brief",
    "issues_to_close",
    "member_steps",
    "next_collected",
    "plan_lines",
    "step_ranges",
]

StepKind = Literal["verify-merge", "outcome", "archive", "close"]


class CloseoutTree(Protocol):
    """The scratch worktree the close-out runs in (`gitseam.Worktree`)."""

    def head(self) -> str: ...

    def run_fr(self, args: list[str]) -> tuple[int, str]: ...

    def reset_hard(self, sha: str) -> None: ...

    def squash_all(self, base: str, message: str) -> str | None: ...

    def push(self, branch: str, *, force: bool = False) -> None: ...


class CloseoutForge(Protocol):
    """The forge writes the close-out makes (the `GhClient` adapter's methods)."""

    def pr_create(self, repo: str, *, head: str, base: str, title: str, body: str) -> int: ...

    def close_issue(self, repo: str, number: int, comment: str) -> None: ...

    def edit_issue_labels(
        self, repo: str, number: int, *, add: frozenset[str], remove: frozenset[str]
    ) -> None: ...


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
    argv: tuple[str, ...]  # the `fr` arguments, or the issue ref of a `close`

    @property
    def line(self) -> str:
        if self.kind == "close":
            return f"close {self.argv[0]} and remove {FR_AWAITING_LIVE.name}"
        return "fr " + shlex.join(self.argv)


@dataclass(frozen=True)
class CloseoutResult:
    branch: str
    done: tuple[str, ...]  # batch ids closed out, in order
    held: tuple[tuple[str, str], ...]  # (batch id, why): moved nothing, no event
    pr: int | None = None
    closed: tuple[str, ...] = ()
    failed: tuple[str, ...] = ()  # issue writes the forge refused: said, never fatal


def pending_collected(batch: Batch) -> CloseoutEvent | None:
    """The batch's close-out event when it is a collected close-out the driver recorded
    before its session started (gh#883) and whose PR has not merged: the verb reuses its
    branch, and takes it back if the batch holds."""
    event = closeout_event(batch)
    if event is None or event.archived is not None or not event.archive:
        return None
    return event if collected_name(event.archive) is not None else None


def closeout_owed(batches: Sequence[Batch], facts: Facts) -> list[Batch]:
    """R15's batches: landed, not gated, and not closed out (no close-out event, or only a
    collected one recorded but not merged). A landed batch whose merged PR's labels could
    not be read is not known ungated (p4-r1), so it waits."""
    stages = {b.id: derive_batch_stage(b, facts) for b in batches}
    ledgers = fact_ledgers(batches, facts, stages)
    unknown = fact_ledger_unknown(batches, facts, stages)
    out: list[Batch] = []
    for b in batches:
        if stages[b.id] not in LANDED or b.id in unknown:
            continue
        if closeout_event(b) is not None and pending_collected(b) is None:
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


def member_steps(m: Member) -> tuple[Step, ...]:
    """R15's four steps for one batch, in order."""
    steps = [Step("verify-merge", ("isolation", "verify-merge", "--repo", ".", "--branch",
                                   m.branch))]  # fmt: skip
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
    if m.passed:
        steps += [Step("close", (ref,)) for ref in m.closes]
    return tuple(steps)


def plan_lines(members: Sequence[Member], branch: str) -> list[str]:
    """What `--yes` would do, without it."""
    lines = [f"collected close-out on {branch}, one PR:"]
    for m in members:
        lines += [f"  {m.batch}: {s.line}" for s in member_steps(m)]
    return lines


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
        f"locally, and push. This is its one hand-back: the driver merges it once it is "
        f"green and mergeable, and a second failure goes to the operator."
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
    say: Callable[[str], None],
) -> CloseoutResult:
    """Run every batch's steps in *tree* (on *branch*, cut from *default*), then one
    commit, one push and one PR; *record*(batch id, branch) each batch closed out, and
    only then close its issues."""
    base = tree.head()
    done: list[Member] = []
    held: list[tuple[str, str]] = []
    for m in members:
        start = tree.head()
        why = ""
        for step in member_steps(m):
            if step.kind == "close":
                continue  # after the PR: an issue closes only for a batch that closed out
            code, out = tree.run_fr(list(step.argv))
            if code == 0:
                continue
            if step.kind == "verify-merge" and code == 2:
                say(f"{m.batch}: the merged branch {m.branch} is gone; verify-merge proves "
                    "nothing either way, the merged PR stands")  # fmt: skip
                continue
            why = _why(step, code, out)
            break
        if why:
            tree.reset_hard(start)
            held.append((m.batch, why))
            say(f"{m.batch}: held, moved nothing: {why}")
            continue
        done.append(m)
        say(f"{m.batch}: closed out on {branch}")
    ids = [m.batch for m in done]
    if not done:
        return CloseoutResult(branch, (), tuple(held))
    title = closeout_title(branch, ids)
    if tree.squash_all(base, title) is None:
        say("nothing to commit: no PR opened")
        return CloseoutResult(branch, (), tuple(held))
    tree.push(branch)
    body = "\n".join(
        [f"Collected close-out of {len(ids)} landed batch(es) (exit-gates R15):", "",
         *(f"- {m.batch} ({m.branch})" for m in done),
         *(["", "Held, not in this PR:", *(f"- {b}: {w}" for b, w in held)] if held else [])]
    )  # fmt: skip
    pr = forge.pr_create(repo, head=branch, base=default, title=title, body=body)
    for m in done:
        record(m.batch, branch)
    closed: list[str] = []
    failed: list[str] = []
    for m in done:
        for step in member_steps(m):
            if step.kind != "close":
                continue
            ref = step.argv[0]
            where, _, number = ref.rpartition("#")
            try:
                why = f"Closed by the collected close-out PR #{pr}: its gate passed."
                forge.close_issue(where, int(number), why)
                forge.edit_issue_labels(
                    where, int(number), add=frozenset(), remove=frozenset({FR_AWAITING_LIVE.name})
                )
                closed.append(ref)
            except Exception as exc:  # noqa: BLE001 - the close-out stands; said, retried by hand
                failed.append(f"{ref}: {exc}")
                say(f"{m.batch}: could not close {ref}: {exc}")
    return CloseoutResult(branch, tuple(ids), tuple(held), pr, tuple(closed), tuple(failed))
