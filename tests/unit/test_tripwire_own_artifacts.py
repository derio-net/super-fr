"""Tripwire: every test module that resolves this checkout's root carries the
`own_artifacts` mark (spec 2026-11-24-ci-economy R19, R20, Design §D).

`--fr-scope` selects `own_artifacts` tests when a changed path lies under `docs/`,
`.fr/` or `.changes/`, or is a root-level `*.md` or `.test_durations`. A module that
reads the checkout without the mark is invisible to that rule, so a docs-only change
would skip it. `root_readers` parses each module with `ast` and flags one with no mark
that does any of:

- names the shared root constant: `REPO_ROOT` or one of its aliases in `tests/`
  (`ROOT_ALIASES`), or asks for conftest's `repo_root` fixture;
- computes `Path(__file__)…parents[…]` (or `.parent` chains) far enough up to reach
  the checkout root from where the module sits;
- imports a `tests/` helper module that exposes the root: a name of the helper whose
  definition resolves the root, directly or through the helper's own imports.

What it cannot see: a test that reaches the checkout only through a subprocess whose
working directory it does not pass (the child inherits pytest's cwd, the checkout),
a root found at run time (`Path.cwd()`, `git rev-parse --show-toplevel`, a package's
`__file__`), and a fixture other than `repo_root` that hands the root over.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path, PurePosixPath

import pytest

pytestmark = pytest.mark.own_artifacts

ROOT = Path(__file__).resolve().parents[2]

# The names `tests/` gives the checkout root (searched 2026-11-24).
ROOT_ALIASES = frozenset({"REPO_ROOT", "ROOT", "REPO", "_REPO", "_ROOT", "_REPO_ROOT"})
ROOT_FIXTURE = "repo_root"
MARK = "own_artifacts"


def _climbs(node: ast.expr, env: Mapping[str, int]) -> int | None:
    """How many directories above `__file__` an expression stands, else None."""
    if isinstance(node, ast.Name):
        if node.id == "__file__":
            return 0
        return env.get(node.id)
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name) and func.id in {"Path", "PurePath", "PurePosixPath", "str"}:
            return _climbs(node.args[0], env) if node.args else None
        if isinstance(func, ast.Attribute):
            if func.attr in {"resolve", "absolute"}:
                return _climbs(func.value, env)
            if func.attr in {"abspath", "realpath"} and node.args:
                return _climbs(node.args[0], env)
            if func.attr == "dirname" and node.args:
                inner = _climbs(node.args[0], env)
                return None if inner is None else inner + 1
        return None
    if isinstance(node, ast.Attribute) and node.attr == "parent":
        inner = _climbs(node.value, env)
        return None if inner is None else inner + 1
    if isinstance(node, ast.Attribute) and node.attr == "parents":
        # `X.parents` stands one above X: `parents[k]` adds k more, and a name
        # holding `X.parents` keeps that count through the env.
        inner = _climbs(node.value, env)
        return None if inner is None else inner + 1
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.slice, ast.Constant)
        and isinstance(node.slice.value, int)
        and node.slice.value >= 0  # parents[-1] is the filesystem root, not the checkout
    ):
        inner = _climbs(node.value, env)
        return None if inner is None else inner + node.slice.value
    return None


def _module_of(path: str) -> str:
    parts = list(PurePosixPath(path).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _is_marked(tree: ast.Module) -> bool:
    """The module-level `pytestmark` carries the mark. A mark on one test or class
    keeps only that item under `--fr-scope`, so it does not cover the module."""
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            targets, value = stmt.targets, stmt.value
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            targets, value = [stmt.target], stmt.value
        else:
            continue
        if not any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in targets):
            continue
        if any(
            isinstance(n, ast.Attribute)
            and n.attr == MARK
            and isinstance(n.value, ast.Attribute)
            and n.value.attr == "mark"
            for n in ast.walk(value)
        ):
            return True
    return False


def _bound_names(tree: ast.Module) -> set[str]:
    """Every name the module binds: assignments, imports, defs, parameters, loops."""
    bound: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            bound.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(n.name)
        elif isinstance(n, ast.arg):
            bound.add(n.arg)
        elif isinstance(n, ast.alias):
            bound.add((n.asname or n.name).split(".")[0])
    return bound


class _Module:
    """What one parsed module says about the root, computed once."""

    def __init__(self, path: str, tree: ast.Module) -> None:
        self.path = path
        self.tree = tree
        depth = len(PurePosixPath(path).parts)  # climbs from __file__ to the root
        dotted = _module_of(path)
        is_init = PurePosixPath(path).name == "__init__.py"
        self.package = dotted if is_init else dotted.rpartition(".")[0]
        self.marked = _is_marked(tree)
        self.imports = self._imports()
        env = self._env()
        self.climbs_to_root = any(
            (c := _climbs(n, env)) is not None and c >= depth
            for n in ast.walk(tree)
            if isinstance(n, ast.expr)
        )
        self.names_alias = self._names_alias()
        # Top-level names: the names each definition reads, and whether it climbs.
        self.tops: dict[str, tuple[frozenset[str], bool]] = {}
        for stmt in tree.body:
            names: list[str] = []
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names = [stmt.name]
            elif isinstance(stmt, ast.Assign):
                names = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                names = [stmt.target.id]
            if not names:
                continue
            reads = frozenset(n.id for n in ast.walk(stmt) if isinstance(n, ast.Name))
            climbs = any(
                (c := _climbs(n, env)) is not None and c >= depth
                for n in ast.walk(stmt)
                if isinstance(n, ast.expr)
            )
            for name in names:
                self.tops[name] = (reads, climbs)

    def _env(self) -> dict[str, int]:
        env: dict[str, int] = {}
        assigns = sorted(
            (n for n in ast.walk(self.tree) if isinstance(n, (ast.Assign, ast.AnnAssign))),
            key=lambda n: (n.lineno, n.col_offset),
        )
        for node in assigns:
            if node.value is None:
                continue
            value = _climbs(node.value, env)
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and value is not None:
                    env[target.id] = value
        return env

    def _names_alias(self) -> bool:
        """The root constant named without being bound here (a star import), or
        conftest's `repo_root` fixture asked for by a test. An alias the module binds
        is judged by what it is bound to: `REPO = "org/repo"` is no root."""
        bound = _bound_names(self.tree)
        if any(
            isinstance(n, ast.Name) and n.id in ROOT_ALIASES and n.id not in bound
            for n in ast.walk(self.tree)
        ):
            return True
        functions = [
            n for n in ast.walk(self.tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        if any(f.name == ROOT_FIXTURE for f in functions):
            return False  # the module's own `repo_root` fixture shadows conftest's
        return any(
            f.name.startswith("test")
            and any(a.arg == ROOT_FIXTURE for a in f.args.args + f.args.kwonlyargs)
            for f in functions
        )

    def _imports(self) -> list[tuple[str, tuple[str, ...] | None]]:
        """`(module, names)` per import of a `tests` module; None names the whole module."""
        found: list[tuple[str, tuple[str, ...] | None]] = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                found += [(a.name, None) for a in node.names if a.name.startswith("tests")]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base = self.package.split(".")
                    base = base[: len(base) - (node.level - 1)]
                    module = ".".join(base + ([node.module] if node.module else []))
                else:
                    module = node.module or ""
                if not module.startswith("tests"):
                    continue
                names = tuple(a.name for a in node.names)
                found.append((module, names))
                # `from tests.unit import helper` imports a module, not a name.
                found += [(f"{module}.{n}", None) for n in names]
        return found

    def reads_root_via(self, exposed: Mapping[str, frozenset[str]]) -> bool:
        return any(
            bool(exposed.get(module))
            if names is None
            else bool(set(names) & exposed.get(module, frozenset()))
            for module, names in self.imports
        )

    def root_names(self, exposed: Mapping[str, frozenset[str]]) -> frozenset[str]:
        """Top-level names whose definition resolves the root, given what the
        helpers it imports expose."""
        roots = {name for name, (_, climbs) in self.tops.items() if climbs}
        for module, names in self.imports:
            if names is not None:
                roots |= set(names) & exposed.get(module, frozenset())
        changed = True
        while changed:  # a name defined over a root name is a root name
            changed = False
            for name, (reads, _) in self.tops.items():
                if name not in roots and reads & roots:
                    roots.add(name)
                    changed = True
        return frozenset(roots)


def root_readers(sources: Mapping[str, str]) -> list[str]:
    """The test modules (`tests/**/test_*.py`) that resolve the checkout root and
    carry no `own_artifacts` mark, sorted. `sources` maps each repo-relative path
    under `tests/` to its source; helpers are resolved within it."""
    mods = {
        _module_of(path): _Module(path, ast.parse(src, filename=path))
        for path, src in sources.items()
    }
    exposed: dict[str, frozenset[str]] = {}
    for _ in range(len(mods) + 1):  # fixpoint over helper-of-helper imports
        before = dict(exposed)
        exposed = {name: mod.root_names(exposed) for name, mod in mods.items()}
        if exposed == before:
            break
    return sorted(
        mod.path
        for mod in mods.values()
        if PurePosixPath(mod.path).name.startswith("test_")
        and not mod.marked
        and (mod.names_alias or mod.climbs_to_root or mod.reads_root_via(exposed))
    )


# --- the pure function, over fixture sources ---------------------------------

UNMARKED = "import pytest\n\n"
MARKED = "import pytest\n\npytestmark = pytest.mark.own_artifacts\n\n"


def test_a_module_naming_the_root_constant_is_flagged() -> None:
    conftest = "from pathlib import Path\n\nREPO_ROOT = Path(__file__).parent.parent\n"
    src = UNMARKED + "from tests.conftest import REPO_ROOT\n\ndef test_x():\n    assert REPO_ROOT\n"
    sources = {"tests/conftest.py": conftest, "tests/unit/test_a.py": src}
    assert root_readers(sources) == ["tests/unit/test_a.py"]


@pytest.mark.parametrize("alias", sorted(ROOT_ALIASES))
def test_every_alias_of_the_root_constant_is_flagged(alias: str) -> None:
    src = UNMARKED + f"from tests.conftest import *\n\ndef test_x():\n    assert {alias}\n"
    assert root_readers({"tests/unit/test_a.py": src}) == ["tests/unit/test_a.py"]


def test_an_alias_bound_to_something_else_is_not_flagged() -> None:
    src = UNMARKED + 'REPO = "example-org/demo"\n\ndef test_x():\n    assert REPO\n'
    assert root_readers({"tests/unit/test_a.py": src}) == []


def test_an_alias_imported_from_a_helper_that_binds_it_to_a_slug_is_not_flagged() -> None:
    helper = 'REPO = "example-org/demo"\n'
    user = UNMARKED + "from tests.unit.test_b import REPO\n\ndef test_x():\n    assert REPO\n"
    sources = {"tests/unit/test_b.py": helper, "tests/unit/test_a.py": user}
    assert root_readers(sources) == []


def test_asking_for_the_repo_root_fixture_is_flagged() -> None:
    src = UNMARKED + "def test_x(repo_root):\n    assert repo_root\n"
    assert root_readers({"tests/unit/test_a.py": src}) == ["tests/unit/test_a.py"]


def test_a_module_with_its_own_repo_root_fixture_is_not_flagged() -> None:
    src = (
        UNMARKED
        + "@pytest.fixture\ndef repo_root(tmp_path):\n    return tmp_path\n\n"
        + "def test_x(repo_root):\n    assert repo_root\n"
    )
    assert root_readers({"tests/unit/test_a.py": src}) == []


@pytest.mark.parametrize(
    "expr",
    [
        "Path(__file__).resolve().parents[2]",
        "Path(__file__).parents[3]",
        "Path(__file__).parent.parent.parent",
        "Path(__file__).resolve().parent.parent.parent / 'docs'",
    ],
)
def test_climbing_from_file_to_the_root_is_flagged(expr: str) -> None:
    src = (
        UNMARKED + f"from pathlib import Path\n\nHERE = {expr}\n\ndef test_x():\n    assert HERE\n"
    )
    assert root_readers({"tests/unit/test_a.py": src}) == ["tests/unit/test_a.py"]


def test_climbing_in_two_steps_is_flagged() -> None:
    src = (
        UNMARKED
        + "from pathlib import Path\n\nHERE = Path(__file__).resolve().parent\n"
        + "TOP = HERE.parents[1]\n\ndef test_x():\n    assert TOP\n"
    )
    assert root_readers({"tests/unit/test_a.py": src}) == ["tests/unit/test_a.py"]


def test_climbing_only_to_the_tests_fixtures_is_not_flagged() -> None:
    src = (
        UNMARKED
        + "from pathlib import Path\n\n"
        + "FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures'\n"
        + "def test_x():\n    assert FIXTURES\n"
    )
    assert root_readers({"tests/unit/test_a.py": src}) == []


def test_importing_a_helper_that_exposes_the_root_is_flagged() -> None:
    helper = (
        "from pathlib import Path\n\nTOP = Path(__file__).resolve().parents[2]\n\n"
        "def load_skill(name):\n    return (TOP / name).read_text()\n\n"
        "def unrelated():\n    return 1\n"
    )
    user = (
        UNMARKED
        + "from tests.unit.skills_helper import load_skill\n\ndef test_x():\n    load_skill('a')\n"
    )
    other = (
        UNMARKED
        + "from tests.unit.skills_helper import unrelated\n\ndef test_x():\n    unrelated()\n"
    )
    sources = {
        "tests/unit/skills_helper.py": helper,
        "tests/unit/test_user.py": user,
        "tests/unit/test_other.py": other,
    }
    assert root_readers(sources) == ["tests/unit/test_user.py"]


def test_a_helper_of_a_helper_is_followed() -> None:
    inner = "from pathlib import Path\n\nTOP = Path(__file__).parents[2]\n"
    outer = "from .inner import TOP\n\nDOCS = TOP / 'docs'\n"
    user = UNMARKED + "from tests.unit.outer import DOCS\n\ndef test_x():\n    assert DOCS\n"
    sources = {
        "tests/unit/inner.py": inner,
        "tests/unit/outer.py": outer,
        "tests/unit/test_user.py": user,
    }
    assert root_readers(sources) == ["tests/unit/test_user.py"]


def test_a_marked_module_is_not_flagged() -> None:
    src = MARKED + "from tests.conftest import REPO_ROOT\n\ndef test_x():\n    assert REPO_ROOT\n"
    assert root_readers({"tests/unit/test_a.py": src}) == []


def test_a_mark_inside_a_pytestmark_list_counts() -> None:
    src = (
        UNMARKED
        + "pytestmark = [pytest.mark.slow, pytest.mark.own_artifacts]\n\n"
        + "def test_x():\n    assert REPO_ROOT\n"
    )
    assert root_readers({"tests/unit/test_a.py": src}) == []


def test_a_mark_on_one_test_does_not_cover_the_module() -> None:
    # --fr-scope keeps only the marked item; test_y would be skipped silently.
    src = (
        UNMARKED
        + "from pathlib import Path\n\nTOP = Path(__file__).parents[2]\n\n"
        + "@pytest.mark.own_artifacts\ndef test_x():\n    assert TOP\n\n"
        + "def test_y():\n    assert TOP\n"
    )
    assert root_readers({"tests/unit/test_a.py": src}) == ["tests/unit/test_a.py"]


def test_a_name_holding_parents_then_indexed_is_flagged() -> None:
    src = (
        UNMARKED
        + "from pathlib import Path\n\nP = Path(__file__).resolve().parents\n"
        + "TOP = P[2]\n\ndef test_x():\n    assert TOP\n"
    )
    assert root_readers({"tests/unit/test_a.py": src}) == ["tests/unit/test_a.py"]


def test_a_module_that_reads_nothing_of_the_checkout_is_not_flagged() -> None:
    src = UNMARKED + "def test_x(tmp_path):\n    assert tmp_path\n"
    assert root_readers({"tests/unit/test_a.py": src}) == []


def test_helpers_themselves_are_never_flagged() -> None:
    helper = "from pathlib import Path\n\nTOP = Path(__file__).parents[2]\n"
    assert root_readers({"tests/unit/helper.py": helper, "tests/conftest.py": helper}) == []


# --- this repo ------------------------------------------------------------------


def test_every_test_module_that_resolves_the_root_is_marked() -> None:
    sources = {
        p.relative_to(ROOT).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted((ROOT / "tests").rglob("*.py"))
        if "__pycache__" not in p.parts
    }
    flagged = root_readers(sources)
    assert flagged == [], (
        f"{len(flagged)} test module(s) resolve this checkout's root without the "
        "`own_artifacts` mark; add `pytestmark = pytest.mark.own_artifacts` "
        "(merged into an existing pytestmark):\n" + "\n".join(flagged)
    )
