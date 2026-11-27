"""`fr.ops.refresh` — the stale ops workspace (spec 2026-11-27-ops-gate-truth R1–R6, §A).

`drift` compares the ops workspace with a scratch tree of the default branch: real files on
both sides, read by the real loaders (`load_ops`, `test_plan_steps`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fr.ops.gate import StageFailed
from fr.ops.refresh import Drift, drift


def test_drift_differs_only_when_something_moved() -> None:
    assert not Drift((), (), (), False).differs
    assert Drift((), (), ("post",), False).differs
    assert Drift(("new",), (), (), False).differs
    assert Drift((), ("gone",), (), False).differs
    assert Drift((), (), (), True).differs


# ----------------------------------------------------------------------- drift (R1, R2, R5)

PLAN = "docs/superpowers/plans/p"
SPEC = "docs/superpowers/specs/2026-11-27-s-design.md"
OPS = """schema_version: 1
ops:
  - {id: pre, summary: create the thing, phase: pre-merge, check: 'false', apply: 'true'}
  - {id: post, summary: after merge, phase: post-merge, check: 'false', apply: 'true'}
"""
SPEC_TEXT = "# S\n\n## Test Plan\n\n- [devops] walk the stage\n- [tester] click the page\n"


def _side(root: Path, ops: str | None = OPS, spec: str | None = SPEC_TEXT) -> Path:
    if ops is not None:
        (root / PLAN).mkdir(parents=True)
        (root / PLAN / "ops.yaml").write_text(ops)
    if spec is not None:
        (root / SPEC).parent.mkdir(parents=True, exist_ok=True)
        (root / SPEC).write_text(spec)
    return root


def _drift(tmp_path: Path, **default: Any) -> Drift:
    ws = _side(tmp_path / "ws")
    tip = _side(tmp_path / "tip", **default)
    return drift(ws, tip, PLAN, SPEC)


def test_identical_trees_do_not_drift(tmp_path: Path) -> None:
    assert _drift(tmp_path) == Drift((), (), (), False)


def test_an_op_whose_apply_changed_is_changed(tmp_path: Path) -> None:
    d = _drift(tmp_path, ops=OPS.replace("after merge, phase: post-merge, check: 'false', "
                                          "apply: 'true'", "after merge, phase: post-merge, "
                                          "check: 'false', apply: 'echo fixed'"))  # fmt: skip
    assert d == Drift((), (), ("post",), False)


def test_an_op_only_on_one_side_is_added_or_removed(tmp_path: Path) -> None:
    extra = OPS + "  - {id: new, summary: n, phase: post-merge, check: 'false', apply: 'true'}\n"
    assert _drift(tmp_path, ops=extra) == Drift(("new",), (), (), False)
    only_pre = "\n".join(line for line in OPS.splitlines() if "id: post" not in line) + "\n"
    ws = _side(tmp_path / "ws2")
    assert drift(ws, _side(tmp_path / "tip2", ops=only_pre), PLAN, SPEC) == Drift(
        (), ("post",), (), False
    )


def test_a_changed_test_plan_step_sets_test_plan(tmp_path: Path) -> None:
    d = _drift(tmp_path, spec=SPEC_TEXT.replace("walk the stage", "walk it twice"))
    assert d == Drift((), (), (), True) and d.differs


def test_a_spec_missing_on_one_side_counts_as_changed(tmp_path: Path) -> None:
    assert _drift(tmp_path, spec=None).test_plan


def test_a_default_tree_without_the_plan_dir_is_refused_naming_it(tmp_path: Path) -> None:
    with pytest.raises(StageFailed) as exc:
        _drift(tmp_path, ops=None)
    assert PLAN in exc.value.why and exc.value.code == 2


@pytest.mark.parametrize("side", ["ws", "tip"])
def test_ops_that_do_not_load_on_either_side_are_refused(tmp_path: Path, side: str) -> None:
    bad = "schema_version: 1\nops:\n  - {id: x}\n"
    ws = _side(tmp_path / "ws", ops=bad if side == "ws" else OPS)
    tip = _side(tmp_path / "tip", ops=bad if side == "tip" else OPS)
    with pytest.raises(StageFailed) as exc:
        drift(ws, tip, PLAN, SPEC)
    assert exc.value.code == 2 and "cannot be read" in exc.value.why
