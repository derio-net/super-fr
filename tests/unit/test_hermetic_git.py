"""R5: one hermetic-git fixture; the six modules activate it and keep no setenv copy."""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from tests.unit.hermetic_git import apply_hermetic_git

pytestmark = pytest.mark.own_artifacts

HERE = Path(__file__).resolve().parent
MODULES = [
    "test_gatebackfill_candidates.py",
    "test_gatebackfill_delivery.py",
    "test_gatebackfill_discharged.py",
    "test_gatebackfill_render.py",
    "test_merge_evidence.py",
    "test_status_owed.py",
]
_VARS = ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")


@pytest.mark.parametrize("prior", [None, "/somewhere/gitconfig"])
def test_the_variables_are_set_and_restored(prior: str | None) -> None:
    saved = {v: os.environ.get(v) for v in _VARS}
    try:
        for var in _VARS:
            if prior is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = prior
        mp = pytest.MonkeyPatch()
        apply_hermetic_git(mp)
        assert os.environ["GIT_CONFIG_GLOBAL"] == os.devnull
        assert os.environ["GIT_CONFIG_NOSYSTEM"] == "1"
        mp.undo()
        assert [os.environ.get(v) for v in _VARS] == [prior, prior]
    finally:
        for var, value in saved.items():
            if value is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = value


def _usefixtures_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "usefixtures":
                names |= {a.value for a in node.args if isinstance(a, ast.Constant)}
    return names


def _setenv_names(tree: ast.Module) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "setenv" and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    out.add(first.value)
    return out


@pytest.mark.parametrize("name", MODULES)
def test_the_module_activates_the_fixture_and_keeps_no_setenv_copy(name: str) -> None:
    tree = ast.parse((HERE / name).read_text())
    assert "hermetic_git" in _usefixtures_names(tree)
    assert not _setenv_names(tree) & set(_VARS)
