"""R5: one hermetic-git fixture; the six modules activate it and keep no setenv copy."""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from tests.unit.hermetic_git import apply_hermetic_git, hermetic_git  # noqa: F401

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


@pytest.mark.usefixtures("hermetic_git")
def test_the_fixture_itself_sets_both_variables() -> None:
    assert os.environ["GIT_CONFIG_GLOBAL"] == os.devnull
    assert os.environ["GIT_CONFIG_NOSYSTEM"] == "1"


def _null_device(node: ast.expr) -> bool:
    if isinstance(node, ast.Constant):
        return node.value == "/dev/null"
    return isinstance(node, ast.Attribute) and node.attr == "devnull"


def test_no_test_module_sets_the_null_global_config_itself() -> None:
    """The shared helper is the one place `GIT_CONFIG_GLOBAL` is pointed at the null
    device; a module with another policy (a tmp config, a HOME) is not this copy."""
    offenders = []
    for path in sorted(HERE.glob("*.py")):
        if path.name == "hermetic_git.py":
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "setenv"
                and len(node.args) >= 2
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "GIT_CONFIG_GLOBAL"
                and _null_device(node.args[1])
            ):
                offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == [], f"call apply_hermetic_git / use hermetic_git instead: {offenders}"
