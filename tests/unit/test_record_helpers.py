"""R4: one record-placement helper; no test module keeps a placement function of its own."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.unit.record_helpers import write_record

pytestmark = pytest.mark.own_artifacts

HERE = Path(__file__).resolve().parent
MODULES = [
    *(
        f"test_migration_record_{name}.py"
        for name in (
            "contract",
            "delegated",
            "exit_gates",
            "input_unconfirmed",
            "questions",
            "shape",
            "status_split",
            "visual",
        )
    ),
    "test_record_acceptance_v8.py",
    "test_record_amendments.py",
    "test_record_lens.py",
]


def test_write_record_writes_the_exact_bytes_at_the_default_stem(tmp_path: Path) -> None:
    path = write_record(tmp_path, "x: 1\n")
    expected = tmp_path / "docs/superpowers/runs/r1.records/implement-phase__phase-1.yaml"
    assert path == expected
    assert path.read_bytes() == b"x: 1\n"


def test_a_stem_changes_the_file_name(tmp_path: Path) -> None:
    path = write_record(tmp_path, "x: 1\n", stem="deliver")
    assert path == tmp_path / "docs/superpowers/runs/r1.records/deliver.yaml"


def _places_a_record(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    strings = [n.value for n in ast.walk(fn) if isinstance(n, ast.Constant)]
    writes = [
        n
        for n in ast.walk(fn)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "write_text"
    ]
    return any(isinstance(s, str) and "r1.records" in s for s in strings) and bool(writes)


@pytest.mark.parametrize("name", MODULES)
def test_no_module_keeps_its_own_placement_function(name: str) -> None:
    tree = ast.parse((HERE / name).read_text())
    own = [
        n.name
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and _places_a_record(n)
    ]
    assert own == []
