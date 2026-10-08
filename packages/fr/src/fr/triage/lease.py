"""The drive lease: one driver per scope, across hosts and cloud sessions (spec
2026-10-07-cloud-triage R9, §D).

`<state dir>/lease.yaml` rides on the state ref (`state_ref.REF_FILES`): `holder` (the
scope id and the driver identity), `generation`, `started`, `expires`, and `last_pass`
(when the holder last ran a whole pass, so a wake that comes too soon only renews). The
identity is
`host:<host id>` for a host driver and `cloud:<host id>` for a cloud driver: a restart
with a new pid, or a re-homed cloud session carrying the same host id, is the same holder.

Pure functions over the state directory, plus `acquire`, which writes the lease and then
runs the caller's compare-and-swap push (`state_ref.push_state`): of two drivers that
read the same old ref, the second push fails and its lease write is taken back. The same
holder renews its own lease, expired or not; any other driver is refused while the lease
is live (`LeaseHeld`), and an expired foreign lease is reported (`LeaseExpired`), taken
over only by `fr triage lease take --yes` (*force*). `drive_lock` stays the fast same-host
check before it.

`generation` tells a cloud driver's sessions apart, which the shared holder cannot (§D,
p6-r4): a self-re-home bumps it (`bump_generation`) before the new session is created,
and a renewal never lowers it. Absent reads as 0, and 0 is never written, so a lease no
session was re-homed onto stays byte-identical to one written before it existed.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from fr.triage.errors import TriageError

LEASE_FILE = "lease.yaml"
DEFAULT_INTERVAL_MIN = 5
DEFAULT_ROUTINE_MIN = 60
DriverKind = Literal["host", "cloud"]

__all__ = [
    "DEFAULT_INTERVAL_MIN",
    "DEFAULT_ROUTINE_MIN",
    "LEASE_FILE",
    "Lease",
    "LeaseExpired",
    "LeaseHeld",
    "TriageError",
    "acquire",
    "bump_generation",
    "driver_identity",
    "holder_of",
    "lease_duration",
    "load_lease",
    "mark_pass",
    "release",
    "take_or_renew",
]


class Lease(BaseModel):
    """`lease.yaml`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    holder: str
    generation: int = 0
    started: datetime
    expires: datetime
    last_pass: datetime | None = None

    def expired(self, now: datetime) -> bool:
        return now >= self.expires


class LeaseHeld(TriageError):  # noqa: N818 - the name the plan and spec use
    """Another driver holds a live lease."""

    def __init__(self, message: str, lease: Lease) -> None:
        super().__init__(message)
        self.lease = lease


class LeaseExpired(TriageError):  # noqa: N818 - the name the plan and spec use
    """Another driver's lease has expired: reported, taken only by the operator."""

    def __init__(self, message: str, lease: Lease) -> None:
        super().__init__(message)
        self.lease = lease


def driver_identity(kind: DriverKind, host: str) -> str:
    """`host:<host id>` or `cloud:<host id>` (R9)."""
    if kind not in ("host", "cloud"):
        raise ValueError(f"{kind!r} is not a driver kind (host or cloud)")
    return f"{kind}:{host}"


def holder_of(scope_id: str, identity: str) -> str:
    """The lease's holder: the scope id plus the driver identity."""
    return f"{scope_id} {identity}"


def lease_duration(
    interval_min: float = DEFAULT_INTERVAL_MIN, routine_min: float = DEFAULT_ROUTINE_MIN
) -> timedelta:
    """Three wake intervals plus the safety-net Routine's period: 3 × 5 + 60 = 75 minutes
    by default (§D)."""
    return timedelta(minutes=3 * interval_min + routine_min)


def load_lease(state_dir: Path) -> Lease | None:
    """The lease in *state_dir*; None when there is none. An unreadable one is refused
    (`TriageError`), never treated as free."""
    path = state_dir / LEASE_FILE
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return Lease.model_validate(data)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise TriageError(f"{path}: not a drive lease ({exc}); fix or remove it") from exc


def _write(state_dir: Path, lease: Lease) -> None:
    from fr.artifacts.atomic import write_text_atomic

    state_dir.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump(lease.model_dump(mode="json", exclude_defaults=True), sort_keys=False)
    write_text_atomic(state_dir / LEASE_FILE, body)


def _take_line(lease: Lease) -> str:
    return (
        f"the drive lease is held by {lease.holder}, started {lease.started.isoformat()}, "
        f"expires {lease.expires.isoformat()}"
    )


def take_or_renew(
    state_dir: Path,
    identity: str,
    now: datetime,
    *,
    scope_id: str,
    duration: timedelta | None = None,
    force: bool = False,
    generation: int = 0,
) -> Lease:
    """Take the lease when it is free, renew it when this holder has it (expired or not),
    and write it; `LeaseHeld` when another holder's lease is live, `LeaseExpired` when it
    has expired (nothing written either way). *force* (the operator's `lease take --yes`)
    takes it from anyone. *generation* is the taking session's: the lease keeps the
    greater of it and its own (whether that session is superseded is the caller's
    question, asked before it takes)."""
    holder = holder_of(scope_id, identity)
    until = now + (duration if duration is not None else lease_duration())
    current = load_lease(state_dir)
    if current is not None and current.holder == holder:
        new = current.model_copy(
            update={"expires": until, "generation": max(current.generation, generation)}
        )
    elif current is None or force:
        new = Lease(holder=holder, generation=generation, started=now, expires=until)
    elif current.expired(now):
        raise LeaseExpired(
            f"{_take_line(current)} and has expired; it is never taken over silently: "
            "`fr triage lease take --yes` takes it for this driver",
            current,
        )
    else:
        raise LeaseHeld(
            f"{_take_line(current)}; one driver runs per scope (stop that driver, or wait "
            "for its lease to expire)",
            current,
        )
    _write(state_dir, new)
    return new


def acquire(
    state_dir: Path,
    identity: str,
    now: datetime,
    *,
    scope_id: str,
    push: Callable[[], object] | None,
    duration: timedelta | None = None,
    force: bool = False,
    generation: int = 0,
) -> Lease:
    """`take_or_renew`, then *push* (the compare-and-swap push of the state ref; None when
    the scope has no ref). When the push fails, `lease.yaml` is put back byte for byte and
    the failure raised: a driver that lost the race holds nothing."""
    path = state_dir / LEASE_FILE
    before = path.read_bytes() if path.exists() else None
    got = take_or_renew(
        state_dir, identity, now, scope_id=scope_id, duration=duration, force=force,
        generation=generation,
    )  # fmt: skip
    if push is None:
        return got
    try:
        push()
    except BaseException:
        if before is None:
            path.unlink(missing_ok=True)
        else:
            from fr.artifacts.atomic import write_text_atomic

            write_text_atomic(path, before.decode("utf-8"))
        raise
    return got


def mark_pass(state_dir: Path, now: datetime) -> None:
    """Record that the holder ran a whole pass at *now* (a lease must exist)."""
    current = load_lease(state_dir)
    if current is None:
        raise TriageError(f"{state_dir / LEASE_FILE}: no lease to record a pass on")
    _write(state_dir, current.model_copy(update={"last_pass": now}))


def bump_generation(state_dir: Path) -> Lease:
    """Move the lease to the next generation (a self-re-home, §D) and write it; the caller
    pushes. A lease must exist."""
    current = load_lease(state_dir)
    if current is None:
        raise TriageError(f"{state_dir / LEASE_FILE}: no lease to move to a new generation")
    new = current.model_copy(update={"generation": current.generation + 1})
    _write(state_dir, new)
    return new


def release(state_dir: Path, identity: str, *, scope_id: str) -> bool:
    """Remove the lease on a clean stop, only while it is this holder's; whether it did."""
    current = load_lease(state_dir)
    if current is None or current.holder != holder_of(scope_id, identity):
        return False
    (state_dir / LEASE_FILE).unlink(missing_ok=True)
    return True
