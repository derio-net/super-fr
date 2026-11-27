"""R1-R3: one duplicate-key detector, owned by `fr.yamlio`."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml
from fr.yamlio import StrictLoader

pytestmark = pytest.mark.own_artifacts

_ROOT = Path(__file__).resolve().parents[2]
_YAMLIO = _ROOT / "packages" / "fr" / "src" / "fr" / "yamlio.py"


def test_a_repeated_key_is_refused_with_the_mappings_and_keys_marks() -> None:
    with pytest.raises(yaml.constructor.ConstructorError) as exc:
        yaml.load("a: 1\nb: 2\na: 3\n", Loader=StrictLoader)  # noqa: S506
    err = exc.value
    assert err.problem == "found duplicate key 'a'"
    assert err.context == "while constructing a mapping"
    assert err.context_mark is not None and err.context_mark.line == 0
    assert err.problem_mark is not None and err.problem_mark.line == 2


def test_distinct_keys_load_normally() -> None:
    assert yaml.load("a: 1\nb: {a: 2}\n", Loader=StrictLoader) == {"a": 1, "b": {"a": 2}}  # noqa: S506


def test_an_unhashable_key_is_skipped_by_the_duplicate_check() -> None:
    # The duplicate check skips it; PyYAML's own "unhashable key" refusal is what is raised,
    # never ours.
    with pytest.raises(yaml.constructor.ConstructorError) as exc:
        yaml.load("? [1, 2]\n: x\n", Loader=StrictLoader)  # noqa: S506
    assert exc.value.problem == "found unhashable key"


def test_construct_mapping_is_defined_only_in_yamlio() -> None:
    offenders = []
    for path in sorted((_ROOT / "packages").glob("*/src/**/*.py")):
        if path == _YAMLIO:
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            is_def = isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            if is_def and node.name == "construct_mapping":
                offenders.append(str(path.relative_to(_ROOT)))
    assert offenders == []


def test_yamlio_imports_only_stdlib_and_yaml() -> None:
    import sys

    allowed = set(sys.stdlib_module_names) | {"yaml"}
    tree = ast.parse(_YAMLIO.read_text())
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "relative import in fr.yamlio"
            roots.add((node.module or "").split(".")[0])
    assert roots <= allowed, roots - allowed
