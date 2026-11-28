"""The run write ledger: what a mutating `fr run` command wrote, committed once.

Spec 2026-11-27-run-write-ledger. gh#610 §3.C: fr commits its own record writes.

Every mutating command (start/adopt/advance/resolve/claim) is wrapped in
`commits_run_writes`: while it runs, each cursor save and each journal
append it makes is noted here, and on the way out — success, refusal or
traceback alike, since a write that landed must not be lost to an exit path —
every noted path is committed ONCE, per repo root, through `commit_records`,
which never fails the command. `save_run_state` and `adopt_run` stay pure.

Engine code: no `typer`, no `rich` and no `fr.commands` import
(`tests/unit/test_run_writes_layering.py`).
"""

from __future__ import annotations

import datetime as _dt
import functools
import os
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar, cast

from fr.artifacts.commit import CommitOutcome
from fr.records_commit import commit_records
from fr.run.model import RunState, run_path, save_run_state


@dataclass
class ResolveGuard:
    """What the step-record engine needs to undo a `resolve` it drove (p3-r3).

    `originals` holds the bytes of every path this command wrote — the cursor,
    the usage capture, the spec journal a `--no-questions` clears into, the PR
    render — remembered BEFORE the write, so a refusal or a crash can put each
    one back. `landed` turns true once any commit landed: from then on the
    tree must stay equal to HEAD, never be restored behind it.
    `before_commit` runs once, immediately before the first commit, and names
    extra paths to record in it (the engine's tracked record file, deleted).
    """

    originals: dict[Path, bytes | None] = field(default_factory=dict)
    landed: bool = False
    before_commit: Callable[[], list[Path]] | None = None
    prepared: bool = False


@dataclass
class RunWrites:
    verb: str
    step: str | None = None
    item: str | None = None
    # The state word the subject ends in, when the command knows it better
    # than the cursor does (p3-r1): a member resolve/claim has no record of its
    # own in `steps`, and a cleared cli gate is `pending` again on disk.
    outcome: str | None = None
    loaded_cursor: str | None = None
    last: RunState | None = None
    paths: dict[Path, list[Path]] = field(default_factory=dict)
    # The outcome of the last commit this command made — the step-record
    # engine reports it in its one line (spec 2026-09-25 §5.C.2.4).
    last_outcome: CommitOutcome | None = None
    guard: ResolveGuard | None = None
    # p3-r10: the step-record engine prints its own one line naming the
    # commit, so `commit_records`' "fr: committed …" echo would be a second.
    quiet: bool = False
    # `adopt --supersede`: the run this command replaced. Its subject names it
    # (spec 2026-10-05-run-upgrade-midflight §C), so the replaced cursor is
    # findable in history.
    supersedes: str | None = None

    def remember(self, path: Path) -> None:
        """Keep `path`'s bytes as they are now, before this command writes it."""
        if self.guard is not None and path not in self.guard.originals:
            self.guard.originals[path] = path.read_bytes() if path.is_file() else None

    def note(self, repo_root: Path, path: Path) -> None:
        self.paths.setdefault(repo_root, []).append(path)

    def message(self) -> str:
        run = self.last.run if self.last is not None else "?"
        if self.supersedes is not None:
            return f"chore(fr): run {run} — adopt, supersedes {self.supersedes}"
        step = self.step or self.loaded_cursor or (self.last.cursor if self.last else None)
        parts = [self.verb]
        if step:
            parts.append(step)
        if self.item:
            parts.append(self.item)
        record = self.last.steps.get(step) if (self.last is not None and step) else None
        if self.outcome is not None:
            parts.append(self.outcome)
        elif record is not None:
            parts.append(record.state)
        return f"chore(fr): run {run} — {' '.join(parts)}"

    def commit(self) -> CommitOutcome | None:
        """Commit what has been noted so far, once per repo root, and forget it.

        Returns the last root's `CommitOutcome`, or `None` when nothing was
        pending — a caller deciding whether to print "push it" (p4-r1) must
        tell "nothing to commit" from "committed" from "refused".
        """
        guard = self.guard
        if guard is not None and not guard.prepared and self.paths:
            guard.prepared = True
            if guard.before_commit is not None:
                root = next(iter(self.paths))
                for path in guard.before_commit():
                    self.note(root, path)
        pending, self.paths = self.paths, {}
        for root in pending:
            extra = self._stealth_head(root)
            if extra is not None:
                pending[root].append(extra)
        outcome: CommitOutcome | None = None
        for root, paths in pending.items():
            outcome = commit_records(root, paths, self.message(), quiet=self.quiet)
            if guard is not None and outcome.committed:
                guard.landed = True
        if outcome is not None:
            self.last_outcome = outcome
        return outcome

    def _stealth_head(self, root: Path) -> Path | None:
        """Under stealth, every run write records the product head it describes beside
        the cursor (`<run-id>.stealth.json`, R24 "resume"): the pushed head of the
        product branch, so the state never describes code that is not pushed yet."""
        from fr.artifacts.paths import STEALTH, outside_repo
        from fr.placement import stealth
        from fr.run.model import run_path

        if self.last is None or outside_repo(root) != STEALTH:
            return None
        runs = run_path(root, self.last.run).parent
        path = stealth.placement_file(runs, self.last.run)
        self.remember(path)
        return stealth.write_placement_file(root, runs, self.last.run, self.last.branch)


RUN_WRITES: ContextVar[RunWrites | None] = ContextVar("fr_run_writes", default=None)


def note_record_write(repo_root: Path, path: Path, state: RunState | None = None) -> None:
    """Record that this command wrote `path` (a no-op outside a wrapped command)."""
    writes = RUN_WRITES.get()
    if writes is None:
        return
    writes.note(repo_root, path)
    if state is not None:
        writes.last = state


def remember(path: Path) -> None:
    """Keep `path`'s current bytes for the step-record engine's restore
    (a no-op unless the engine drives this command)."""
    writes = RUN_WRITES.get()
    if writes is not None:
        writes.remember(path)


def note_subject(*, step: str, item: str | None, outcome: str) -> None:
    """Name the unit this command acted on in its commit subject (p3-r1)."""
    writes = RUN_WRITES.get()
    if writes is not None:
        writes.step, writes.item, writes.outcome = step, item, outcome


def commit_run_writes_now() -> CommitOutcome | None:
    """Commit this command's writes BEFORE it prints a dispatch brief.

    The brief is the line a naive `tail -1` parses (see `_print_member_dispatch`),
    so `commit_records`' stderr report must not land after it — in a harness
    that merges stdout and stderr it would become the last line.

    Returns the `CommitOutcome` (or `None` if nothing was pending) so a caller
    that goes on to print a "push it" line knows whether this invocation's
    commit actually landed (p4-r1).
    """
    writes = RUN_WRITES.get()
    if writes is not None:
        return writes.commit()
    return None


def note_loaded(state: RunState) -> None:
    """The cursor as the command found it — the step `advance` acted on."""
    writes = RUN_WRITES.get()
    if writes is not None and writes.loaded_cursor is None:
        writes.loaded_cursor = state.cursor


_Cmd = TypeVar("_Cmd", bound=Callable[..., None])


def commits_run_writes(
    verb: str,
    outcome: Callable[[dict[str, Any]], str | None] | None = None,
    after: Callable[[RunWrites, dict[str, Any]], None] | None = None,
) -> Callable[[_Cmd], _Cmd]:
    """Commit every record the wrapped command wrote, once, on every exit path.

    `outcome` reads the subject's closing state word off the command's own
    arguments (`resolve --state`, `claim --abandoned`) — the state the command
    was asked to record, which the cursor alone cannot always say (p3-r1).
    `after` runs only when the command RETURNED (not on a refusal), before the
    commit, so whatever it writes lands in the same commit.
    """

    def decorate(fn: _Cmd) -> _Cmd:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> None:
            writes = RunWrites(
                verb=verb,
                step=kwargs.get("step_id"),
                item=kwargs.get("item"),
                outcome=outcome(kwargs) if outcome is not None else None,
            )
            token = RUN_WRITES.set(writes)
            try:
                fn(*args, **kwargs)
                if after is not None:
                    after(writes, kwargs)
            finally:
                RUN_WRITES.reset(token)
                writes.commit()

        return cast(_Cmd, wrapper)

    return decorate


def now() -> str:
    return _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat()


def fr_version() -> str:
    """The running fr's version, recorded by `fr run start` (R16)."""
    from fr import __version__

    return __version__


def capture_usage(
    repo_root: Path, state: RunState, at: str, *, require_sessions: bool = False
) -> None:
    """Write this host's usage capture and note it for the command's commit.
    Never raises (`fr.usage.capture.capture`)."""
    from fr.usage.capture import capture
    from fr.usage.file import usage_path

    remember(usage_path(repo_root, state.run))
    # `ambient=True`: a step resolve's caller is the run's orchestrator, so its
    # own session is evidence (spec 2026-10-02-opencode-observe-2 §C).
    path = capture(
        repo_root, state, at, os.environ, ambient=True, require_sessions=require_sessions
    )
    if path is not None:
        note_record_write(repo_root, path)


def save_run_state_noted(repo_root: Path, state: RunState) -> Path:
    """`save_run_state`, noted for the command's closing commit.

    `RunStateConflictError` propagates: the CLI wrapper turns it into exit 2.
    """
    remember(run_path(repo_root, state.run))
    path = save_run_state(repo_root, state)
    note_record_write(repo_root, path, state)
    return path
