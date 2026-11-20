"""The looping driver's record and its failure ledger (spec 2026-11-19-batch-train-truth R8,
R9, R13).

Two host-local files in the scope's state directory, each written atomically and neither
named in `fr.triage.state_ref.REF_FILES`, so neither rides on the state ref:

- `driver.yaml` (`DriverRecord`): who drove last (pid, started), whether a supervisor runs
  it and its restarts, the last pass and the last refusal (cause, message, time, fr
  version, resume command). Needs you now shows a stopped driver from it (`stopped`).
- `driver-failures.yaml` (`Ledger`, `schema: 1`): per failure cause its kind (refusal,
  transient, crash), count, first and last seen, last message, fr version, exception class
  and the tracking issue once `fr triage drive failures --file --yes` filed one.

Neither is a registered artifact kind: the triage state directory is never committed by
default.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from fr.artifacts.atomic import write_text_atomic
from fr.triage.errors import TriageError

RECORD_FILE = "driver.yaml"
FAILURES_FILE = "driver-failures.yaml"
FAILURES_COMMAND = "fr triage drive failures --file --yes"
"""What turns a recurring cause into a tracked issue: every refusal line ends with it."""

FailureKind = Literal["refusal", "transient", "crash"]


class LastRefusal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cause: str
    message: str
    at: datetime
    fr_version: str
    resume: str


class DriverRecord(BaseModel):
    """`driver.yaml`."""

    model_config = ConfigDict(extra="forbid")

    pid: int
    started: datetime | None = None
    supervised: int | None = None  # the supervisor's pid
    restarts: int = 0
    last_crash: str | None = None
    last_pass: datetime | None = None
    last_refusal: LastRefusal | None = None


class Cause(BaseModel):
    """One cause in the ledger."""

    model_config = ConfigDict(extra="forbid")

    kind: FailureKind
    count: int
    first: datetime
    last: datetime
    message: str
    fr_version: str
    exception: str | None = None
    issue: str | None = None  # `<owner/repo>#<n>`, once filed
    filed_count: int = 0  # the count the issue last carried


class Ledger(BaseModel):
    """`driver-failures.yaml`."""

    model_config = ConfigDict(extra="forbid")

    schema_: int = 1
    causes: dict[str, Cause] = {}

    def by_count(self) -> list[tuple[str, Cause]]:
        """Most frequent cause first, then the latest, then by name."""
        return sorted(
            self.causes.items(), key=lambda kv: (-kv[1].count, -kv[1].last.timestamp(), kv[0])
        )


def _load(path: Path) -> object:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise TriageError(f"{path}: unreadable: {exc}") from exc


def _dump(data: dict[str, object]) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def load_ledger(state_dir: Path) -> Ledger:
    """The ledger in *state_dir*; empty when there is none."""
    path = state_dir / FAILURES_FILE
    if not path.exists():
        return Ledger()
    data = _load(path) or {}
    if not isinstance(data, dict):
        raise TriageError(f"{path}: not a mapping")
    try:
        return Ledger.model_validate(
            {"schema_": data.get("schema", 1), "causes": data.get("causes") or {}}
        )
    except ValidationError as exc:
        raise TriageError(f"{path}: invalid {FAILURES_FILE}: {exc}") from exc


def save_ledger(state_dir: Path, ledger: Ledger) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    causes = {k: v.model_dump(mode="json") for k, v in ledger.causes.items()}
    write_text_atomic(
        state_dir / FAILURES_FILE, _dump({"schema": ledger.schema_, "causes": causes})
    )


Filed = dict[str, tuple[str | None, int]]
"""What a filing changed, per cause: its `issue` and `filed_count`."""


def filed(ledger: Ledger) -> Filed:
    """*ledger*'s filing fields, per cause: compared before and after a filing."""
    return {cause: (entry.issue, entry.filed_count) for cause, entry in ledger.causes.items()}


def save_filed(state_dir: Path, changed: Filed, filed_from: Ledger) -> Ledger:
    """Write a filing's *changed* causes into the ledger AS IT STANDS NOW (p1a-r8): a
    running driver may have counted failures while the filing talked to the forge, so the
    ledger is read again and only `issue` and `filed_count` are taken from the filing. A
    cause the ledger no longer has comes back whole, from *filed_from*. The ledger saved."""
    current = load_ledger(state_dir)
    for cause, (issue, count) in changed.items():
        entry = current.causes.get(cause)
        if entry is None:
            current.causes[cause] = filed_from.causes[cause]
            continue
        current.causes[cause] = entry.model_copy(update={"issue": issue, "filed_count": count})
    save_ledger(state_dir, current)
    return current


def record_failure(
    state_dir: Path,
    kind: FailureKind,
    cause: str,
    message: str,
    now: datetime,
    fr_version: str,
    *,
    exception: str | None = None,
) -> Cause:
    """Count one failure of *cause* in the ledger (R9); the entry as it now stands."""
    ledger = load_ledger(state_dir)
    old = ledger.causes.get(cause)
    entry = Cause(
        kind=kind,
        count=(old.count if old else 0) + 1,
        first=old.first if old else now,
        last=now,
        message=message,
        fr_version=fr_version,
        exception=exception if exception is not None else (old.exception if old else None),
        issue=old.issue if old else None,
        filed_count=old.filed_count if old else 0,
    )
    ledger.causes[cause] = entry
    save_ledger(state_dir, ledger)
    return entry


def load_record(state_dir: Path) -> DriverRecord | None:
    """`driver.yaml` in *state_dir*, or None when no driver wrote one."""
    path = state_dir / RECORD_FILE
    if not path.exists():
        return None
    try:
        return DriverRecord.model_validate(_load(path) or {})
    except ValidationError as exc:
        raise TriageError(f"{path}: invalid {RECORD_FILE}: {exc}") from exc


def save_record(state_dir: Path, record: DriverRecord) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    write_text_atomic(
        state_dir / RECORD_FILE, _dump(record.model_dump(mode="json", exclude_none=True))
    )


def _current(state_dir: Path) -> DriverRecord:
    """This process's record: the one on disk when this pid wrote it, else a fresh one
    that keeps the supervisor's counts (a restarted child keeps its supervisor's record)."""
    try:
        old = load_record(state_dir)
    except TriageError:
        old = None
    pid = os.getpid()
    if old is None:
        return DriverRecord(pid=pid)
    if old.pid == pid:
        return old
    return old.model_copy(update={"pid": pid, "started": None})


def record_supervisor(
    state_dir: Path,
    *,
    supervisor: int,
    child: int | None,
    restarts: int,
    last_crash: str | None,
) -> DriverRecord:
    """The supervisor's view of its driver on `driver.yaml` (R13): who supervises, the restart
    count and the last crash. *child* is the driver's pid, None between a crash and the next
    start (the record keeps the dead one's)."""
    try:
        old = load_record(state_dir)
    except TriageError:
        old = None
    pid = child if child is not None else (old.pid if old else 0)
    base = old if old is not None else DriverRecord(pid=pid)
    update: dict[str, object] = {"pid": pid, "supervised": supervisor, "restarts": restarts}
    if last_crash is not None:
        update["last_crash"] = last_crash
    if child is not None and (old is None or old.pid != child):
        update["started"] = None
    record = base.model_copy(update=update)
    save_record(state_dir, record)
    return record


def record_start(state_dir: Path, now: datetime, supervisor: int | None) -> DriverRecord:
    """A looping driver started (R12, R14): its pid and time, and its supervisor's pid when it
    has one. An unsupervised driver forgets an earlier supervisor's counts; a supervised one
    keeps what that supervisor wrote."""
    update: dict[str, object] = {"started": now, "supervised": supervisor}
    if supervisor is None:
        update.update(restarts=0, last_crash=None)
    record = _current(state_dir).model_copy(update=update)
    save_record(state_dir, record)
    return record


def record_refusal(
    state_dir: Path, cause: str, message: str, resume: str, now: datetime, fr_version: str
) -> DriverRecord:
    """The refusal that stopped this driver, on `driver.yaml` (R8)."""
    refusal = LastRefusal(cause=cause, message=message, at=now, fr_version=fr_version,
                          resume=resume)  # fmt: skip
    record = _current(state_dir).model_copy(update={"last_refusal": refusal})
    save_record(state_dir, record)
    return record


def record_pass(state_dir: Path, now: datetime) -> DriverRecord:
    """A pass that ended cleanly: its time, which a stopped driver's need is weighed
    against (a scope with no lease has no other record of it)."""
    record = _current(state_dir)
    if record.started is None:
        record = record.model_copy(update={"started": now})
    record = record.model_copy(update={"last_pass": now})
    save_record(state_dir, record)
    return record


def stopped(record: DriverRecord | None, lease_last_pass: datetime | None) -> LastRefusal | None:
    """The refusal that stopped the scope's driver, while it is newer than the last pass
    (the lease's, or the record's own); None once a driver passed again."""
    if record is None or record.last_refusal is None:
        return None
    passes = [t for t in (lease_last_pass, record.last_pass) if t is not None]
    if passes and max(passes) >= record.last_refusal.at:
        return None
    return record.last_refusal


def stopped_line(refusal: LastRefusal) -> str:
    """The one line a stopped driver is shown by: why, how to resume, how to file it."""
    return (
        f"the driver stopped at {refusal.at.isoformat()} ({refusal.cause}): {refusal.message}; "
        f"resume: {refusal.resume}; track it: {FAILURES_COMMAND}"
    )


DriverView = tuple[DriverRecord | None, datetime | None]
"""`driver.yaml` and the lease's last pass: what a page shows a stopped driver from."""


def view_inputs(state_dir: Path) -> DriverView:
    """What a page needs to show a stopped driver: `driver.yaml` and the lease's last pass.
    A page is a view, so a file it cannot read shows nothing rather than refusing."""
    from fr.triage.lease import load_lease

    try:
        record = load_record(state_dir)
    except TriageError:
        return None, None
    try:
        lease = load_lease(state_dir)
    except TriageError:
        lease = None
    return record, lease.last_pass if lease is not None else None
