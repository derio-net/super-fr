"""The driver adapter (spec 2026-10-07-cloud-triage R10, R20, §E).

The wave driver's pass (`triage_batch_cmd._Driver.run_pass`, policy single-sourced, R13)
runs in two environments, and the adapter is what differs between them:

- the RUNNER a batch is dispatched through. The driver decides it, not the repo: the host
  adapter keeps today's choice (`--to`, else the batch's `launch.runner`, else the repo's
  `defaults.launch.runner`), the cloud adapter dispatches every batch through
  `claude-cloud`, whatever `.fr/triage.yaml` names, and reports a batch whose explicit
  `launch.runner` is another (`refusal`), which the pass then does not dispatch;
- `post_merge`, an operation of the environment (R20): the host runs the repo's argument
  list in its clone, as today; the cloud runs nothing (every new session installs the
  current release, and the driver updates itself), so `post_merge_restart` never follows.

The loop around the pass is the host adapter's (`fr triage batch drive`); the cloud one
is a pass per wake (`fr triage drive pass`). Both construct the same `_Driver` and call
the same `one_pass`, given one of these.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from fr.triage.errors import TriageError
from fr.triage.lease import DriverKind
from fr.triage.model import Batch

CLOUD_RUNNER = "claude-cloud"


class _Commands(Protocol):
    def run_command(self, argv: list[str]) -> str: ...


@runtime_checkable
class Driver(Protocol):
    """What the pass asks of the environment it runs in."""

    @property
    def name(self) -> str: ...

    @property
    def kind(self) -> DriverKind: ...

    def runner_for(self, batch: Batch, to: str | None = None) -> str | None:
        """The runner *batch* is dispatched through, given the operator's `--to`; None
        leaves it to the batch's `launch.runner`, else the repo's default. Raises
        `TriageError` when this driver cannot dispatch the batch (`refusal`)."""
        ...

    def refusal(self, batch: Batch) -> str | None:
        """Why this driver does not dispatch *batch*; None when it does."""
        ...

    def post_merge(self, checkout: _Commands, argv: Sequence[str]) -> bool:
        """Run the repo's `post_merge` *argv* where this driver runs; whether it ran."""
        ...


@dataclass(frozen=True)
class HostDriver:
    """`fr triage batch drive`: today's loop, on the operator's host (R10)."""

    name: str = "host"
    kind: DriverKind = "host"

    def runner_for(self, batch: Batch, to: str | None = None) -> str | None:
        return to

    def refusal(self, batch: Batch) -> str | None:
        return None

    def post_merge(self, checkout: _Commands, argv: Sequence[str]) -> bool:
        checkout.run_command(list(argv))
        return True


@dataclass(frozen=True)
class CloudDriver:
    """`fr triage drive pass`: one pass per wake of a long-lived cloud session (R10-R12)."""

    name: str = CLOUD_RUNNER
    kind: DriverKind = "cloud"
    runner: str = CLOUD_RUNNER

    def refusal(self, batch: Batch) -> str | None:
        named = batch.launch.runner
        if named and named != self.runner:
            return (
                f"its launch.runner is {named}, and this scope's driver dispatches through "
                f"{self.runner} only: set it (`fr triage batch edit {batch.id} --runner "
                f"{self.runner}`) or drive this batch from a host"
            )
        return None

    def runner_for(self, batch: Batch, to: str | None = None) -> str | None:
        if to and to != self.runner:
            raise TriageError(f"the cloud driver dispatches through {self.runner}, not {to}")
        why = self.refusal(batch)
        if why is not None:
            raise TriageError(f"batch {batch.id!r} is not dispatched: {why}")
        return self.runner

    def post_merge(self, checkout: _Commands, argv: Sequence[str]) -> bool:
        return False  # R20: nothing to install; each session starts on the current release


HOST = HostDriver()
CLOUD = CloudDriver()


@runtime_checkable
class Mailbox(Protocol):
    """A runner whose session actions the driver's AGENT executes (spec §F): the pass
    opens it on the scope's state directory, with the session statuses the agent wrote,
    and writes its pending requests to the outbox; `drive record` hands it the agent's
    results. `claude-cloud` implements it; fr never imports that package."""

    def open_mailbox(self, state_dir: Any, statuses: Any) -> None: ...

    def outbox(self) -> list[dict[str, Any]]: ...

    def record_results(self, results: list[dict[str, Any]]) -> list[str]: ...
