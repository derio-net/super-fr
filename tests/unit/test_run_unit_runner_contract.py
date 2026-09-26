"""The run-unit runner contract and `load_runner` (spec 2026-09-25-triage-batches §3.C,
Test Plan 4).

`fr_dispatch.testing` is the reusable contract an adapter's own suite runs; this
file proves the contract itself bites, and that `load_runner` refuses what the
spec says it refuses. Runner entry points are faked by replacing
`fr_dispatch.registry.available_runners`; no real backend is touched.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest
from fr_dispatch import registry
from fr_dispatch.registry import RunnerLoadError, load_runner
from fr_dispatch.testing import (
    RUN_PAYLOAD_KEYS,
    check_constructible,
    check_run_unit_contract,
    run_item,
)
from fr_dispatch.work_item import WorkItem, run_item_id


class _EntryPoint:
    def __init__(self, obj: object) -> None:
        self.obj = obj

    def load(self) -> object:
        return self.obj


class _RunRunner:
    """A minimal conforming run-unit runner: records what reached its backend."""

    name = "fake"
    capabilities: frozenset[str] = frozenset({"git"})

    def __init__(self) -> None:
        self.sent: list[str] = []
        self.preflights = 0

    @classmethod
    def from_env(cls) -> _RunRunner:
        return cls()

    def preflight(self, items: Sequence[WorkItem]) -> str | None:
        self.preflights += 1
        return None

    def refresh(self) -> None:
        return None

    def slot_budget(self) -> int:
        return 1

    def existing_dispatches(self, items: Sequence[WorkItem]) -> set[str]:
        return set()

    def can_dispatch(self, item: WorkItem) -> bool:
        return item.unit == "run"

    def dispatch(self, item: WorkItem) -> str | None:
        p = item.payload
        self.sent.append(f"{p['harness']} {p['model']} {p['brief']}")
        return "handle-1"


class _PhaseOnly(_RunRunner):
    def can_dispatch(self, item: WorkItem) -> bool:
        return item.unit == "phase"


class _DropsModel(_RunRunner):
    def dispatch(self, item: WorkItem) -> str | None:
        self.sent.append(str(item.payload["brief"]))  # the model never reaches the backend
        return "h"


class _NoFromEnv:
    name = "bridge-only"

    def __init__(self, client: object) -> None:
        self.client = client


def _registry(monkeypatch: pytest.MonkeyPatch, **runners: object) -> None:
    monkeypatch.setattr(
        registry, "available_runners", lambda: {n: _EntryPoint(o) for n, o in runners.items()}
    )


# ------------------------------------------------------------ run_item


def test_run_item_is_a_well_formed_run_unit_with_the_full_payload() -> None:
    item = run_item()
    assert item.unit == "run"
    assert item.id == run_item_id(item.repo, "batch-contract")
    assert set(RUN_PAYLOAD_KEYS) <= set(item.payload)
    assert (item.workflow, item.parent, item.inputs, item.tracking) == ("fr-goal", None, (), None)


# ------------------------------------------------------------ the contract


def test_a_conforming_runner_passes() -> None:
    runner = _RunRunner()
    check_constructible(_RunRunner)
    check_run_unit_contract(runner, run_item(), sent=lambda: "\n".join(runner.sent))


def test_a_runner_that_only_takes_phases_is_refused_by_can_dispatch_before_preflight() -> None:
    runner = _PhaseOnly()
    with pytest.raises(AssertionError, match="can_dispatch"):
        check_run_unit_contract(runner, run_item(), sent=lambda: "\n".join(runner.sent))
    assert runner.preflights == 0
    assert runner.sent == []


def test_a_runner_that_drops_a_payload_value_fails_the_contract() -> None:
    runner = _DropsModel()
    with pytest.raises(AssertionError, match="model"):
        check_run_unit_contract(runner, run_item(), sent=lambda: "\n".join(runner.sent))


def test_a_runner_class_without_from_env_is_not_constructible() -> None:
    with pytest.raises(AssertionError, match="from_env"):
        check_constructible(_NoFromEnv)


def test_the_contract_still_bites_under_python_dash_o() -> None:
    """Review r2p-f12a: `python -O` strips bare `assert`, so the contract raises
    AssertionError explicitly. Run in a child interpreter with -O."""
    code = (
        "from fr_dispatch.testing import check_constructible\n"
        "class NoFromEnv: pass\n"
        "try:\n"
        "    check_constructible(NoFromEnv)\n"
        "except AssertionError as exc:\n"
        "    print('refused:', exc)\n"
        "else:\n"
        "    print('accepted')\n"
    )
    done = subprocess.run(
        [sys.executable, "-O", "-c", code], capture_output=True, text=True, check=True
    )
    assert done.stdout.startswith("refused:"), done.stdout + done.stderr
    assert "from_env" in done.stdout


def test_the_contract_module_has_no_bare_assert() -> None:
    """Every contract check is an explicit raise, so none disappears under -O."""
    import ast

    import fr_dispatch.testing as contract

    tree = ast.parse(Path(contract.__file__).read_text(encoding="utf-8"))
    assert not [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Assert)]


# ------------------------------------------------------------- load_runner


def test_load_runner_builds_through_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _registry(monkeypatch, fake=_RunRunner)
    assert isinstance(load_runner("fake"), _RunRunner)


def test_load_runner_refuses_a_name_no_package_registers(monkeypatch: pytest.MonkeyPatch) -> None:
    _registry(monkeypatch, fake=_RunRunner)
    with pytest.raises(RunnerLoadError, match=r"runner `nope` is not installed.*fr\.runners"):
        load_runner("nope")


def test_load_runner_refuses_a_runner_without_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _registry(monkeypatch, legacy=_NoFromEnv)
    with pytest.raises(
        RunnerLoadError, match="runner `legacy` cannot be constructed outside its own bridge"
    ):
        load_runner("legacy")


@pytest.mark.parametrize("name", ["vk", "cncd"])
def test_the_real_vk_and_cncd_runners_are_refused_by_the_from_env_check(name: str) -> None:
    with pytest.raises(RunnerLoadError, match="cannot be constructed outside its own bridge"):
        load_runner(name)


def test_payload_keys_are_documented_beside_work_item() -> None:
    import fr_dispatch.work_item as wi

    doc = wi.__doc__ or ""
    for key in RUN_PAYLOAD_KEYS:
        assert f"`{key}`" in doc, key
