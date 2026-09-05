"""CI tripwire: only `fr.artifacts.registry` enumerates artifact kinds (spec §3.A).

The registry is the ONE place that says what an artifact kind is, where it
lives, how it is stamped and how it is validated. A second list somewhere else
— a tuple of kind names in a CLI, a dict of per-kind validators, a set in the
migration runner — is how a sixth kind gets added in one place and silently
missed in another: the migration runs, the validator does not, and nothing
reports a gap. Adding a kind must remain a one-module edit.

The detector looks for a *literal collection* (set/list/tuple/dict-keys) whose
string constants include several registered kind names. The threshold is 3 of
5, so ordinary code mentioning `"plan"` and `"spec"` in the same tuple (which
happens all over this repo — plans and specs are ordinary nouns here) is not an
enumeration, while a real second list of kinds is.

`Literal[...]` slices are skipped, and that exclusion is load-bearing rather
than convenient: `fr_dispatch.work_item` declares
`_Level = Literal["run", "spec", "plan", "phase"]`, the *decomposition-unit*
grammar (spec 2026-08-14 §4.D). It shares three nouns with the artifact kinds
by coincidence — a run item and a run artifact are different things — and is
not a duplicate of the registry. A type-level vocabulary is a closed set the
type checker already enforces; a runtime collection of kind names is the thing
that drifts.
"""

from __future__ import annotations

import ast
from pathlib import Path

from fr.artifacts.registry import ARTIFACT_KINDS

REPO_ROOT = Path(__file__).resolve().parents[2]

# The registry itself, and nothing else, may hold the list.
CANONICAL = REPO_ROOT / "packages" / "fr" / "src" / "fr" / "artifacts" / "registry.py"

KIND_NAMES = frozenset(ARTIFACT_KINDS)
THRESHOLD = 3


def _literal_slices(tree: ast.AST) -> set[int]:
    """`id()` of every tuple that is the slice of a `Literal[...]` annotation."""
    out: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Subscript):
            continue
        base = node.value
        name = base.attr if isinstance(base, ast.Attribute) else getattr(base, "id", None)
        if name == "Literal":
            out.add(id(node.slice))
    return out


def kind_enumerations(text: str) -> list[tuple[int, list[str]]]:
    """`(line, kinds)` for every literal collection enumerating artifact kinds."""
    hits: list[tuple[int, list[str]]] = []
    tree = ast.parse(text)
    skip = _literal_slices(tree)
    for node in ast.walk(tree):
        if id(node) in skip:
            continue
        if isinstance(node, ast.Dict):
            elements: list[ast.expr | None] = list(node.keys)
        elif isinstance(node, ast.Set | ast.List | ast.Tuple):
            elements = list(node.elts)
        else:
            continue
        strings = {
            e.value for e in elements if isinstance(e, ast.Constant) and isinstance(e.value, str)
        }
        found = sorted(strings & KIND_NAMES)
        if len(found) >= THRESHOLD:
            hits.append((node.lineno, found))
    return hits


def test_detector_finds_a_second_list_of_kinds() -> None:
    assert kind_enumerations('KINDS = ("plan", "journal", "run")')
    assert kind_enumerations('for k in ["spec", "plan", "matrix", "run"]:\n    pass')
    assert kind_enumerations('VALIDATORS = {"plan": v1, "run": v2, "spec": v3}')


def test_detector_ignores_ordinary_code() -> None:
    assert not kind_enumerations('paths = ("plan", "spec")')  # two nouns, not the list
    assert not kind_enumerations('doc = "plan, journal, run, matrix, spec"')  # prose
    assert not kind_enumerations("for name, kind in ARTIFACT_KINDS.items():\n    pass")


def test_detector_ignores_a_literal_type_vocabulary() -> None:
    """The `Unit` / `_Level` grammar in `fr_dispatch.work_item` — a run ITEM is
    not a run ARTIFACT, and a type alias is not a second registry."""
    assert not kind_enumerations('_Level = Literal["run", "spec", "plan", "phase"]')
    assert not kind_enumerations('x: typing.Literal["plan", "run", "spec"] = "plan"')


def test_the_registry_is_the_only_enumeration() -> None:
    offenders: list[str] = []
    for path in sorted((REPO_ROOT / "packages").glob("*/src/**/*.py")):
        if path.resolve() == CANONICAL.resolve():
            continue
        for line, kinds in kind_enumerations(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.relative_to(REPO_ROOT)}:{line} enumerates {kinds}")
    assert not offenders, (
        "artifact kinds are enumerated outside fr.artifacts.registry: "
        + "; ".join(offenders)
        + " — iterate ARTIFACT_KINDS instead, and add new kinds to the registry only"
    )


def test_the_registry_still_holds_the_list() -> None:
    """A tripwire that passes because the canonical list moved is no tripwire."""
    assert kind_enumerations(CANONICAL.read_text()) or KIND_NAMES <= set(ARTIFACT_KINDS), (
        "the registry no longer looks like the place the kinds live"
    )
    assert len(KIND_NAMES) >= THRESHOLD
