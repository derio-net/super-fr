"""The op status engine (spec 2026-10-22-fr-ops R3, R5, R7, R9, §C).

Pure over three injected ports, so its tests run no subprocess:

- a `Runner` runs a shell string with an env and returns `(exit, last line)`;
- an `IdentityResolver` turns an identity name into its env (R5);
- a `Journal` answers an op's latest recorded evidence (R7).

`status` evaluates, per op: a legacy `status: done`; `na_if` (skipped for an op
that `disables` something, which is never N/A); then `check` once per identity,
every identity having to pass; then, for an op that is not DONE, `escalate`.
It never writes. `order` is the `needs` topological sort `apply` runs in.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal, Protocol

from fr.ops.evidence import OpEvidence
from fr.ops.identity import IdentityError, IdentityResolver
from fr.ops.load import LoadedOp

State = Literal["DONE", "OPEN", "N/A", "UNVERIFIABLE", "CANNOT-VERIFY", "ESCALATE"]
NOT_DONE: frozenset[str] = frozenset({"OPEN", "UNVERIFIABLE", "CANNOT-VERIFY"})
NOT_FOUND = 127
"""A probe's exit when its command could not run (bash: command not found)."""
_REASON_MAX = 200


class Runner(Protocol):
    def __call__(self, command: str, env: Mapping[str, str]) -> tuple[int, str]: ...


class Journal(Protocol):
    def latest(self, op_id: str, *, runbook: bool) -> OpEvidence | None: ...


class OrderError(Exception):
    """A `needs` cycle, or a `needs` id no op carries."""


@dataclass(frozen=True)
class StatusRow:
    """One op's status: the ONE shape the text and JSON renderers both read."""

    op_id: str
    phase: str
    summary: str
    state: State
    how: str | None = None
    """Why it is DONE (`checked`, `attested`, `legacy`, `proof`) or N/A (`legacy`)."""
    reason: str | None = None
    identity: str | None = None
    """The identity a failing check ran as."""
    vacuous_if: str | None = None
    where: str = ""
    runbook: bool = False

    @property
    def label(self) -> str:
        return f"{self.state} ({self.how})" if self.how else self.state

    def as_row(self) -> dict[str, Any]:
        return {
            "op": self.op_id,
            "phase": self.phase,
            "state": self.state,
            "how": self.how,
            "label": self.label,
            "reason": self.reason,
            "identity": self.identity,
            "summary": self.summary,
            "vacuous_if": self.vacuous_if,
            "source": self.where,
            "runbook": self.runbook,
        }


class ShellRunner:
    """Runs a probe via `bash -euo pipefail -c` in the repo root, with the
    process env plus the identity's."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def __call__(self, command: str, env: Mapping[str, str]) -> tuple[int, str]:
        try:
            done = subprocess.run(
                ["bash", "-euo", "pipefail", "-c", command],
                cwd=self.repo_root,
                env={**os.environ, **env},
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return NOT_FOUND, "bash could not run"
        lines = [line for line in done.stdout.splitlines() if line.strip()]
        return done.returncode, lines[-1].strip() if lines else ""


def _clean(line: str, secrets: Iterable[str]) -> str:
    """A reason line with every identity value masked, cut to one short line."""
    for secret in secrets:
        if secret:
            line = line.replace(secret, "***")
    line = " ".join(line.split())
    return line if len(line) <= _REASON_MAX else line[: _REASON_MAX - 1] + "…"


def _check(lo: LoadedOp, row: StatusRow, runner: Runner, identities: IdentityResolver) -> StatusRow:
    check = lo.op.check
    assert check is not None
    names: Sequence[str | None] = lo.op.identities or (None,)
    for name in names:
        env: dict[str, str] = {}
        if name is not None:
            try:
                env = dict(identities(name))
            except IdentityError as e:
                return replace(row, state="CANNOT-VERIFY", reason=str(e), identity=name)
        rc, line = runner(check, env)
        if rc == 0:
            continue
        if rc == NOT_FOUND:
            reason = _clean(line, env.values()) or f"the check could not run (exit {rc})"
            return replace(row, state="CANNOT-VERIFY", reason=reason, identity=name)
        reason = _clean(line, env.values()) or f"exit {rc}"
        return replace(row, state="OPEN", reason=reason, identity=name)
    return replace(row, state="DONE", how="checked")


def _evaluate(
    lo: LoadedOp, runner: Runner, identities: IdentityResolver, journal: Journal
) -> StatusRow:
    op = lo.op
    row = StatusRow(
        op_id=op.id,
        phase=op.phase,
        summary=op.summary,
        state="OPEN",
        vacuous_if=op.vacuous_if,
        where=lo.where,
        runbook=lo.runbook,
    )
    if lo.legacy == "done":
        return replace(row, state="DONE", how="legacy")
    if lo.legacy == "n/a":
        return replace(row, state="N/A", how="legacy")
    if op.na_if and not op.disables:
        rc, line = runner(op.na_if, {})
        if rc == 0:
            return replace(row, state="N/A")
        if rc == NOT_FOUND:
            reason = _clean(line, ()) or "na_if could not run"
            return replace(row, state="CANNOT-VERIFY", reason=f"na_if: {reason}")
    if op.is_proof:
        ev = journal.latest(op.id, runbook=lo.runbook)
        if ev is not None and ev.result == "proof":
            row = replace(row, state="DONE", how="proof")
        else:
            row = replace(row, reason=(ev.reason if ev else None) or "awaiting a recorded proof")
    elif op.check is None:
        ev = journal.latest(op.id, runbook=lo.runbook)
        if ev is not None and ev.result == "attested":
            row = replace(row, state="DONE", how="attested")
        else:
            row = replace(row, state="UNVERIFIABLE", reason="no check: attest it, or write a check")
    else:
        row = _check(lo, row, runner, identities)
    if row.state in NOT_DONE and op.disables:
        lead = f"{row.reason} — " if row.reason else ""
        row = replace(row, reason=f"{lead}disables: {op.disables}")
    if row.state in NOT_DONE and op.escalate:
        rc, _ = runner(op.escalate, {})
        if rc == 0:
            row = replace(row, state="ESCALATE")
    return row


def status(
    ops: Iterable[LoadedOp],
    *,
    runner: Runner,
    identities: IdentityResolver,
    journal: Journal,
) -> list[StatusRow]:
    """Each op's status, in the order given. Reads only."""
    return [_evaluate(lo, runner, identities, journal) for lo in ops]


def exit_code(rows: Iterable[StatusRow]) -> int:
    """R3: 3 when anything ESCALATEs, else 1 when anything is OPEN,
    UNVERIFIABLE or CANNOT-VERIFY, else 0."""
    states = {r.state for r in rows}
    if "ESCALATE" in states:
        return 3
    return 1 if states & NOT_DONE else 0


def order(ops: Sequence[LoadedOp], *, known: set[str] | None = None) -> list[LoadedOp]:
    """`ops` in `needs` order, carrier order kept wherever `needs` allows.

    A need naming an op outside `ops` is ignored when it is in `known` (an op
    that exists but is not selected) and refused otherwise; a cycle is refused.
    Both before anything runs."""
    selected = {lo.op.id for lo in ops}
    allowed = selected | (known or set())
    for lo in ops:
        unknown = [n for n in lo.op.needs if n not in allowed]
        if unknown:
            raise OrderError(f"op {lo.op.id!r} needs unknown op(s): {', '.join(unknown)}")
    pending = list(ops)
    done: set[str] = set()
    out: list[LoadedOp] = []
    while pending:
        ready = next(
            (lo for lo in pending if all(n in done or n not in selected for n in lo.op.needs)),
            None,
        )
        if ready is None:
            names = ", ".join(lo.op.id for lo in pending)
            raise OrderError(f"`needs` cycle among: {names}")
        pending.remove(ready)
        done.add(ready.op.id)
        out.append(ready)
    return out
