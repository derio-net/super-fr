"""Tripwire: one cancelled-check rule (spec 2026-11-24-ci-economy R3, Design §A).

`fr.checkstate` is the one place a GitHub check's state becomes pass, pending or fail. A
second set literal that holds a cancelled state beside a failed one is a reader growing
its own rule, which is how a cancelled check came to read as failing in eight places. Two
readers are exempt on purpose: the GraphQL client's aggregate rollup (`real_ghclient`,
which GitHub folds before fr sees a cancel) and the GitLab client (outside the queue).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fr.checkstate import FAILED_STATES

pytestmark = pytest.mark.own_artifacts

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "packages" / "fr" / "src"
EXEMPT = {
    SRC / "fr" / "checkstate.py",
    SRC / "fr" / "real_ghclient.py",
    SRC / "fr" / "real_glabclient.py",
}
# A cancelled word beside any failed state or bucket is a second rule (p1-r3): the failed
# side is `fr.checkstate.FAILED_STATES` plus the `gh pr checks` bucket `fail`.
CANCELLED_WORDS = frozenset({"cancel", "cancelled", "canceled"})
FAILED_WORDS = frozenset(FAILED_STATES | {"fail"})


def _strings(node: ast.Set | ast.Tuple | ast.List) -> set[str]:
    return {
        e.value.lower()
        for e in node.elts
        if isinstance(e, ast.Constant) and isinstance(e.value, str)
    }


def check_state_sets(source: str) -> list[int]:
    """The line of every set, frozenset, tuple or list literal holding a cancelled check
    state beside any failed one (any case). `frozenset({...})` is a set literal inside a
    call."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Set | ast.Tuple | ast.List):
            values = _strings(node)
            if values & CANCELLED_WORDS and values & FAILED_WORDS:
                found.append(node.lineno)
    return found


@pytest.mark.parametrize(
    "source",
    [
        'X = frozenset({"fail", "cancel"})',
        'X = {"FAILURE", "ERROR", "CANCELLED"}',
        'X = ("failure", "cancelled")',
        'if b in {"fail", "cancel"}: pass',
        'X = frozenset(("Cancelled", "Failure"))',
        'X = {"CANCELLED", "TIMED_OUT", "ERROR"}',
        'X = ["cancelled", "stale"]',
        'X = ["fail", "cancel"]',
        'X = {"canceled", "failed"}',
    ],
)
def test_the_detector_finds_a_check_state_set(source: str) -> None:
    assert check_state_sets(source)


@pytest.mark.parametrize(
    "source",
    [
        'X = frozenset({"merged", "partial", "cancelled", "abandoned"})',
        'X = ("cancelled", "abandoned")',
        'X = {"fail", "pending", "pass"}',
    ],
)
def test_the_detector_leaves_batch_stages_and_other_sets_alone(source: str) -> None:
    assert check_state_sets(source) == []


def test_no_module_grows_its_own_cancelled_check_rule() -> None:
    offenders = [
        f"{path.relative_to(ROOT)}:{line}"
        for path in sorted(SRC.rglob("*.py"))
        if path not in EXEMPT
        for line in check_state_sets(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, (
        "a check-state set outside fr/checkstate.py; read the verdict from "
        f"fr.checkstate instead (spec 2026-11-24-ci-economy R3): {offenders}"
    )


def test_the_exempt_modules_exist() -> None:
    assert all(p.is_file() for p in EXEMPT)
