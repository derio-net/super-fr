"""Hand-written `fr_version` floors (spec 2026-09-26-version-bump-churn §3.E, §7 item 5).

Only `>=X.Y.Z,<X.Y.Z` literals inside a Python string under `packages/*/src`
count, and only their lower bound. A lower bound newer than the base version
names a release that does not exist yet, so it must equal the predicted one.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "floors.py"
spec = importlib.util.spec_from_file_location("floors", SCRIPT)
assert spec and spec.loader
floors = importlib.util.module_from_spec(spec)
sys.modules["floors"] = floors
spec.loader.exec_module(floors)

SOURCE = '''\
"""Docstring mentioning demo>=1.0.0 and nothing else."""
# a comment: --fr-version '>=9.9.9,<10.0.0' is not a string literal
DEFAULT = ">=3.0.0,<5.0.0"
SPACED = ">= 4.2.0, <5.0.0"
REQ = "demo>=1.0.0"
NAMED = "demo>=1.0.0,<2.0.0"


def refusal(x):
    return f"floor it at '>=4.20.0,<5.0.0' for {x}."
'''


def test_floors_in_source_finds_only_fr_version_literals() -> None:
    found = [(f.lower, f.upper) for f in floors.floors_in_source(SOURCE)]
    assert found == [("3.0.0", "5.0.0"), ("4.2.0", "5.0.0"), ("4.20.0", "5.0.0")]


def test_floors_in_source_tolerates_unparseable_python() -> None:
    # A file that does not tokenize is not a reason to crash the gate; its
    # string-shaped floors are still found by the regex fallback.
    found = floors.floors_in_source('X = ">=4.0.0,<5.0.0"\ndef broken(:\n')
    assert [(f.lower, f.upper) for f in found] == [("4.0.0", "5.0.0")]


@pytest.mark.parametrize(
    ("path", "counts"),
    [
        ("packages/fr/src/fr/commands/plan_cmd.py", True),
        ("packages/fr-herdr/src/fr_herdr/x.py", True),
        ("packages/fr/tests/test_x.py", False),
        ("tests/unit/test_x.py", False),
        ("docs/superpowers/specs/x.md", False),
        ("packages/fr-opencode-plugin/src/index.ts", False),
        ("scripts/floors.py", False),
    ],
)
def test_only_python_under_packages_src_is_scanned(path: str, counts: bool) -> None:
    assert floors.is_floor_path(path) is counts


def test_scan_floors_walks_packages_src_only(tmp_path: Path) -> None:
    src = tmp_path / "packages" / "fr" / "src" / "fr"
    src.mkdir(parents=True)
    (src / "a.py").write_text('F = ">=4.24.0,<5.0.0"\n')
    tests = tmp_path / "packages" / "fr" / "tests"
    tests.mkdir(parents=True)
    (tests / "t.py").write_text('F = ">=9.0.0,<10.0.0"\n')
    (tmp_path / "top.py").write_text('F = ">=8.0.0,<9.0.0"\n')
    found = floors.scan_floors(tmp_path)
    assert [(file, f.lower) for file, f in found] == [("packages/fr/src/fr/a.py", "4.24.0")]


def test_this_repos_floors_are_found() -> None:
    lowers = {f.lower for _, f in floors.scan_floors(REPO)}
    assert {"3.0.0", "4.0.0", "4.20.0"} <= lowers


@pytest.mark.parametrize(
    ("lower", "base", "predicted", "ok"),
    [
        ("4.24.0", "4.23.0", "4.24.0", True),  # minor fragment predicts it
        ("4.24.0", "4.23.0", "4.23.1", False),  # patch fragment does not
        ("4.25.0", "4.23.0", "4.24.0", False),  # newer than base, not predicted
        ("4.23.0", "4.23.0", "4.24.0", True),  # at base: an existing release
        ("4.20.0", "4.23.0", "4.23.1", True),  # below base
        ("3.0.0", "4.23.0", "4.23.0", True),
        ("4.10.0", "4.9.0", "4.9.1", False),  # numeric, not lexical, compare
        ("4.9.0", "4.10.0", "4.10.0", True),
    ],
)
def test_lower_bound_ok(lower: str, base: str, predicted: str, ok: bool) -> None:
    assert floors.lower_bound_ok(lower, base, predicted) is ok


def test_new_floors_is_a_multiset_difference() -> None:
    before = 'A = ">=4.20.0,<5.0.0"\nB = ">=3.0.0,<5.0.0"\n'
    after = 'B = ">=3.0.0,<5.0.0"\nA = ">=4.20.0,<5.0.0"\nC = ">=4.24.0,<5.0.0"\n'
    assert [f.lower for f in floors.new_floors(before, after)] == ["4.24.0"]


def test_reformatting_a_historical_floor_introduces_no_new_lower_bound() -> None:
    before = 'A = ">=4.20.0,<5.0.0"\n'
    after = 'A = (\n    ">=4.20.0, <5.0.0"\n)\n'
    assert floors.new_floors(before, after) == []


def test_moving_an_upper_bound_introduces_no_new_lower_bound() -> None:
    before = 'A = ">=4.20.0,<5.0.0"\n'
    after = 'A = ">=4.20.0,<6.0.0"\n'
    assert floors.new_floors(before, after) == []


def test_a_brand_new_file_has_all_its_floors_new() -> None:
    assert [f.lower for f in floors.new_floors(None, 'A = ">=4.24.0,<5.0.0"\n')] == ["4.24.0"]
