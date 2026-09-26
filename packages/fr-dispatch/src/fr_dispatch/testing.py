"""Reusable runner contracts, for an adapter's own test suite.

**Run-unit contract** (spec 2026-09-25-triage-batches §3.C). A runner takes
batch work — `unit="run"` items dispatched by `fr triage batch dispatch` — when:

1. its class has a `from_env()` classmethod that builds it from environment
   and config alone (`check_constructible`; `registry.load_runner` calls it);
2. it has a non-empty `name`, `refresh()` runs, `slot_budget()` returns an int;
3. `can_dispatch(item)` accepts a run item — the cheap routing gate, consulted
   before `preflight` or any backend call;
4. `dispatch(item)` honours the payload: the brief and the model it carries
   reach the backend (`check_run_unit_contract`'s *sent* probe shows what did).

Explicit `AssertionError`s with messages, no pytest import: `fr_dispatch` does
not depend on a test framework, and a failed contract reads the same in any
runner. Never a bare `assert` — `python -O` strips those, and the contract would
pass everything (review r2p-f12a).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from fr_dispatch.work_item import RUN_PAYLOAD_KEYS, WorkItem, run_item_id

if TYPE_CHECKING:
    from fr_dispatch.protocols import Runner

__all__ = ["RUN_PAYLOAD_KEYS", "check_constructible", "check_run_unit_contract", "run_item"]


def run_item(
    repo: str = "example-org/alpha",
    run_id: str = "batch-contract",
    *,
    harness: str = "claude",
    model: str = "contract-model-7",
    brief: str = "/fr-goal contract brief",
    **extra: object,
) -> WorkItem:
    """A well-formed run item carrying every documented payload key."""
    payload: dict[str, object] = {
        "brief": brief,
        "harness": harness,
        "model": model,
        "branch": f"feat/{run_id}",
        "reserved_version": None,
        "issues": ["alpha#1", "alpha#2"],
        **extra,
    }
    return WorkItem(
        id=run_item_id(repo, run_id),
        unit="run",
        workflow="fr-goal",
        repo=repo,
        parent=None,
        inputs=(),
        payload=payload,
        tracking=None,
    )


def _require(ok: bool, message: str) -> None:
    """Raise `AssertionError(message)` unless *ok* — an assert that survives -O."""
    if not ok:
        raise AssertionError(message)


def check_constructible(runner_cls: type) -> None:
    """The class builds itself from the environment: a callable `from_env`."""
    factory = getattr(runner_cls, "from_env", None)
    _require(
        callable(factory),
        f"{runner_cls.__name__} has no from_env(): it cannot be constructed outside its own bridge",
    )


def check_run_unit_contract(runner: Runner, item: WorkItem, *, sent: Callable[[], str]) -> None:
    """Assert *runner* meets the run-unit contract for *item*.

    *sent* returns what the runner's backend received (a faked CLI's argv, a
    recorded request) as text; the brief and the model must both appear in it.
    `can_dispatch` is checked before anything that could reach a backend.
    """
    _require(
        isinstance(runner.name, str) and bool(runner.name), "runner.name must be a non-empty str"
    )
    runner.refresh()  # typed `-> None` by the protocol; the contract is that it runs
    budget = runner.slot_budget()
    _require(isinstance(budget, int) and budget >= 0, f"slot_budget() returned {budget!r}")
    _require(
        runner.can_dispatch(item),
        f"runner `{runner.name}` does not take run-unit work: can_dispatch refused {item.id}",
    )
    missing = [k for k in RUN_PAYLOAD_KEYS if k not in item.payload]
    _require(not missing, f"the contract item lacks payload keys {missing}")
    runner.dispatch(item)
    text = sent()
    for key in ("brief", "model"):
        value = str(item.payload[key])
        _require(
            value in text, f"dispatch did not pass the payload's {key} ({value!r}) to its backend"
        )
