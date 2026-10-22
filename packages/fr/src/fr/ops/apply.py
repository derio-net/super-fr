"""`fr ops apply` (spec 2026-10-22-fr-ops R4, R11, §C): run ops in `needs` order.

Pure over the same ports as `fr.ops.engine` plus an `Applier` (runs an op's `apply:`
once, for one identity), a `Prompt` (the terminal) and a `record` callback (the
evidence writer), so its tests run no subprocess. Each op is checked first through
`engine.status` — the one definition of DONE — so a DONE or N/A op is skipped and
writes nothing. Probes and applies run under `fr.ops.probe` (minimal env, closed
stdin, timeout) except an `interactive: true` op, which runs with the operator's
terminal attached (`probe.run_interactive`) and so needs one.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from fr.ops.engine import Journal, Runner, StatusRow, clean_reason, order, status
from fr.ops.engine import OrderError as OrderError  # re-export for callers
from fr.ops.identity import IdentityError, IdentityResolver
from fr.ops.load import LoadedOp
from fr.ops.model import UndoNone
from fr.ops.probe import DEFAULT_TIMEOUT, NOT_FOUND, TIMED_OUT, run_interactive, run_probe

ALREADY_DONE = "already done, nothing written"


class ApplyRefused(Exception):  # noqa: N818
    """The run cannot proceed at all (exit 2): nothing further is attempted."""


class Applier(Protocol):
    def __call__(
        self, lo: LoadedOp, env: Mapping[str, str], interactive: bool
    ) -> tuple[int, str]: ...


class Prompt(Protocol):
    def has_terminal(self) -> bool: ...
    def confirm(self, text: str) -> bool: ...


class TtyPrompt:
    """The operator's terminal: `/dev/tty` for the question, so an agent's piped
    stdin can never answer it. `has_terminal` is the artifact gate's predicate."""

    def __init__(self, tty: str = "/dev/tty") -> None:
        self.tty = tty

    def has_terminal(self) -> bool:
        from fr.artifacts.trigger import is_interactive

        return is_interactive()

    def confirm(self, text: str) -> bool:
        try:
            with open(self.tty, "r+") as term:
                term.write(f"{text}\nProceed? [y/N] ")
                term.flush()
                return term.readline().strip().lower() in ("y", "yes")
        except OSError:
            return False


class Record(Protocol):
    def __call__(
        self,
        *,
        op: str,
        result: str,
        phase: str,
        identity: str | None = None,
        reason: str | None = None,
        attested_by: str | None = None,
    ) -> object: ...


@dataclass(frozen=True)
class ApplyStep:
    op_id: str
    outcome: str  # skipped | applied | failed | open | declined | not-ready | manual | unverifiable
    message: str


@dataclass
class ApplyResult:
    steps: list[ApplyStep] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(s.outcome in ("skipped", "applied") for s in self.steps)


class ShellApplier:
    """Runs an op's `apply:` through `fr.ops.probe`. Applies may legitimately run
    longer than a check, so the bound is ten times the probe timeout."""

    def __init__(
        self, repo_root: Path, *, passthrough: Sequence[str] = (), timeout: float = DEFAULT_TIMEOUT
    ) -> None:
        self.repo_root = repo_root
        self.passthrough = tuple(passthrough)
        self.timeout = timeout * 10

    def __call__(self, lo: LoadedOp, env: Mapping[str, str], interactive: bool) -> tuple[int, str]:
        command = lo.op.apply
        assert command is not None
        if interactive:
            return run_interactive(
                command, self.repo_root, extra=env, passthrough=self.passthrough
            ), ""
        rc, out = run_probe(
            command, self.repo_root, extra=env, passthrough=self.passthrough, timeout=self.timeout
        )
        if rc == TIMED_OUT:
            return rc, f"timed out after {self.timeout:g}s"
        if rc == NOT_FOUND and not out.strip():
            return rc, "bash could not run"
        lines = [line for line in out.splitlines() if line.strip()]
        return rc, lines[-1].strip() if lines else ""


def undo_text(lo: LoadedOp) -> str:
    undo = lo.op.undo
    if undo is None:
        return "none declared"
    return f"none: {undo.none}" if isinstance(undo, UndoNone) else undo


def confirmation_text(lo: LoadedOp) -> str:
    """What the prompt shows: the op, and for a mutating one its side effects and undo."""
    text = f"apply {lo.op.id} — {lo.op.summary}"
    if lo.op.mutating:
        effects = "; ".join(lo.op.side_effects) or "(none declared)"
        text += f"\n  MUTATING. side effects: {effects}\n  undo: {undo_text(lo)}"
    return text


def _confirmed(lo: LoadedOp, prompt: Prompt, yes: bool, yes_mutating: bool) -> bool:
    if yes_mutating if lo.op.mutating else yes:
        return True
    if prompt.has_terminal():
        return prompt.confirm(confirmation_text(lo))
    flag = "--yes-mutating" if lo.op.mutating else "--yes"
    raise ApplyRefused(f"op {lo.op.id!r} needs confirmation and there is no terminal: pass {flag}")


def apply_ops(
    ops: Iterable[LoadedOp],
    *,
    runner: Runner,
    applier: Applier,
    identities: IdentityResolver,
    journal: Journal,
    prompt: Prompt,
    record: Record,
    yes: bool = False,
    yes_mutating: bool = False,
    known: set[str] | None = None,
) -> ApplyResult:
    """Apply `ops` in dependency order, stopping at the first failure. Raises
    `OrderError` (cycle / unknown need) before anything runs, `ApplyRefused` when a
    confirmation or terminal is missing."""
    ordered = order(list(ops), known=known)
    result = ApplyResult()

    def step(op_id: str, outcome: str, message: str) -> None:
        result.steps.append(ApplyStep(op_id, outcome, message))

    def row_of(lo: LoadedOp) -> StatusRow:
        return status([lo], runner=runner, identities=identities, journal=journal)[0]

    for lo in ordered:
        op = lo.op
        row = row_of(lo)
        if row.state in ("DONE", "N/A"):
            step(op.id, "skipped", f"{op.id}: {row.label} — {ALREADY_DONE}")
            continue
        if row.state == "CANNOT-VERIFY":
            step(op.id, "failed", f"{op.id}: cannot verify ({row.reason}); not applied")
            break
        if op.phase == "post-merge" and op.ready:
            rc, line = runner(op.ready, {})
            if rc != 0:
                why = clean_reason(line, ()) or f"exit {rc}"
                step(
                    op.id, "not-ready", f"{op.id}: `ready:` does not pass yet ({why}); not applied"
                )
                break
        if not op.apply:
            by_hand = op.commands if isinstance(op.commands, str) else "; ".join(op.commands or ())
            step(
                op.id,
                "manual",
                f"{op.id}: no apply — do it by hand" + (f": {by_hand}" if by_hand else ""),
            )
            break
        if op.interactive and not prompt.has_terminal():
            raise ApplyRefused(f"op {op.id!r} is interactive and needs a terminal")
        if not _confirmed(lo, prompt, yes, yes_mutating):
            step(op.id, "declined", f"{op.id}: declined; nothing applied")
            break

        secrets: list[str] = []
        failed = False
        for name in op.identities or (None,):
            env: Mapping[str, str] = {}
            if name is not None:
                try:
                    env = identities(name)
                except IdentityError as e:
                    step(op.id, "failed", f"{op.id}: {e} (identity {name}); not applied")
                    return result
                secrets += list(env.values())
            rc, line = applier(lo, env, op.interactive)
            if rc != 0:
                reason = clean_reason(line, secrets, as_identity=name is not None) or f"exit {rc}"
                record(op=op.id, result="failed", phase=op.phase, identity=name, reason=reason)
                step(
                    op.id,
                    "failed",
                    f"{op.id}: apply failed{f' as {name}' if name else ''} ({reason}); "
                    f"undo: {undo_text(lo)}",
                )
                failed = True
                break
        if failed:
            break

        after = row_of(lo)
        if after.state == "DONE" or after.state == "UNVERIFIABLE":
            note = None if after.state == "DONE" else "applied; no check to confirm"
            record(op=op.id, result="done", phase=op.phase, reason=note)
            step(
                op.id,
                "applied",
                f"{op.id}: applied; {after.label if after.state == 'DONE' else note}",
            )
        else:
            record(
                op=op.id,
                result="open",
                phase=op.phase,
                identity=after.identity,
                reason=after.reason,
            )
            step(
                op.id,
                "open",
                f"{op.id}: applied but the check still reads {after.state} ({after.reason}); "
                f"undo: {undo_text(lo)}",
            )
            break
    return result
