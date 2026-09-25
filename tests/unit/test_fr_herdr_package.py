"""The fr-herdr package wiring (spec §3.C; plan phase 1).

The package imports and registers under the `fr.runners` entry-point group as
`herdr`. The runner's behaviour is `test_fr_herdr_runner.py`'s.
"""

from __future__ import annotations

from typing import get_args

import pytest
from fr_dispatch.work_item import Unit, WorkItem


def test_fr_herdr_imports() -> None:
    import fr_herdr

    assert fr_herdr.HerdrRunner.name == "herdr"


def test_herdr_is_a_registered_runner() -> None:
    from fr_dispatch.registry import runner_names

    assert "herdr" in runner_names()


def test_the_registered_entry_point_loads_the_runner() -> None:
    from fr_dispatch.registry import available_runners
    from fr_herdr.runner import HerdrRunner

    ep = available_runners()["herdr"]
    assert ep.load() is HerdrRunner  # type: ignore[attr-defined]


def test_the_runner_is_named_herdr() -> None:
    from fr_herdr.runner import HerdrRunner

    assert HerdrRunner().name == "herdr"


_IDS: dict[str, str] = {
    "run": "derio-net/super-fr/run/2026-09-25-batch-lifecycle",
    "spec": "derio-net/super-fr/2026-09-25-triage-batches",
    "phase": "derio-net/super-fr/2026-09-25-triage-batches/2026-09-25-triage-batches/phase/1",
}


def test_every_unit_has_an_id() -> None:
    assert set(_IDS) == set(get_args(Unit))


@pytest.mark.parametrize("unit", get_args(Unit))
def test_the_runner_refuses_any_item_without_a_harness(unit: Unit) -> None:
    from fr_herdr.runner import HerdrRunner

    item = WorkItem(
        id=_IDS[unit],
        unit=unit,
        workflow="fr-goal",
        repo="derio-net/super-fr",
        parent=None,
        inputs=(),
    )
    assert HerdrRunner().can_dispatch(item) is False
