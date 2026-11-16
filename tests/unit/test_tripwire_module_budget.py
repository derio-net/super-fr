"""Line budget for the five largest modules (spec 2026-11-16 architecture-review-sweep, R12).

A budget is a review trigger, not a ceiling for the codebase. The module may not grow
past its budget, and the budget may not sit more than `MAX_HEADROOM` lines above the
module, so an extraction lowers it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = "packages/fr/src/fr/"
MAX_HEADROOM = 400

BUDGETS: dict[str, int] = {
    f"{SRC}commands/run_cmd.py": 8900,
    f"{SRC}commands/triage_batch_cmd.py": 7400,
    f"{SRC}isolation/local.py": 3200,
    f"{SRC}plan_ops.py": 2600,
    f"{SRC}triage/batch_drive.py": 2200,
}


def budget_problem(lines: int, budget: int) -> str | None:
    """Why `lines` against `budget` fails, or None when it holds."""
    if lines > budget:
        return f"{lines} lines is over its budget of {budget}"
    if budget - lines > MAX_HEADROOM:
        return f"budget {budget} is more than {MAX_HEADROOM} above {lines} lines: lower the budget"
    return None


def test_budget_problem_fires_on_planted_numbers() -> None:
    assert "over its budget" in (budget_problem(8901, 8900) or "")
    assert "lower the budget" in (budget_problem(8400, 8900) or "")
    assert budget_problem(8862, 8900) is None
    assert budget_problem(8500, 8900) is None


@pytest.mark.parametrize("path", sorted(BUDGETS))
def test_module_is_within_its_budget(path: str) -> None:
    lines = len((ROOT / path).read_text().splitlines())
    problem = budget_problem(lines, BUDGETS[path])
    assert problem is None, (
        f"{path}: {problem}. Move the new code into the module the report "
        "docs/superpowers/audits/2026-11-16-architecture-review.md names, or change the "
        "budget in this diff and say why in the PR."
    )
