"""The fr-herdr package skeleton (spec §3.C; plan phase 1).

Phase 1 only wires the package: it imports, it registers under the
`fr.runners` entry-point group as `herdr`, and its stub runner refuses every
item. The real run-unit behaviour arrives in phase 2.
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


def test_the_registered_entry_point_loads_the_stub_runner() -> None:
    from fr_dispatch.registry import available_runners
    from fr_herdr.runner import HerdrRunner

    ep = available_runners()["herdr"]
    assert ep.load() is HerdrRunner  # type: ignore[attr-defined]


def test_stub_runner_is_named_herdr() -> None:
    from fr_herdr.runner import HerdrRunner

    assert HerdrRunner().name == "herdr"


@pytest.mark.parametrize("unit", get_args(Unit))
def test_stub_runner_refuses_every_unit(unit: Unit) -> None:
    from fr_herdr.runner import HerdrRunner

    item = WorkItem(
        id=f"super-fr/{unit}",
        unit=unit,
        workflow="fr-goal",
        repo="derio-net/super-fr",
        parent=None,
        inputs=(),
    )
    assert HerdrRunner().can_dispatch(item) is False
