"""`fr.ops.refresh` — the stale ops workspace (spec 2026-11-27-ops-gate-truth R1–R6, §A).

`drift` compares the ops workspace with a scratch tree of the default branch: real files on
both sides, read by the real loaders (`load_ops`, `test_plan_steps`).
"""

from __future__ import annotations

from fr.ops.refresh import Drift


def test_drift_differs_only_when_something_moved() -> None:
    assert not Drift((), (), (), False).differs
    assert Drift((), (), ("post",), False).differs
    assert Drift(("new",), (), (), False).differs
    assert Drift((), ("gone",), (), False).differs
    assert Drift((), (), (), True).differs
