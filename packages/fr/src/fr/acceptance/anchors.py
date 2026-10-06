"""Name anchors into Python — the one definition of what a `.py` fragment means.

A ref's fragment into a Python file names a test the way pytest's node id does,
after the file: `tests/x.py#test_y`, `tests/x.py#TestX::test_y`. It never pins a
line (gh#531). A line is the least stable property of a test: every line added
above it moves it, nothing noticed when it did, and the reports went on linking
readers into the middle of an unrelated test. A name either still resolves or
`fr acceptance check` says it does not.

unittest spells the same identity with dots (`TestX.test_y`), and collects any
`unittest.TestCase` subclass whatever its name (gh#965, gh#893). `::` stays the
canonical form the repair writes; `.` resolves too, since no identifier holds one.

So:
- `line_anchor_error` refuses a new `#L<n>` into a `.py` file at authoring
  (pure — no filesystem);
- `node_line` resolves a name to its current `def`/`class` line, for `check`
  (does it exist?) and the ad-hoc report (link to where it is today);
- `enclosing_node` names the test a line sits in, for the matrix repair that
  converts line anchors recorded before this rule
  (`fr.artifacts.matrix_anchors`).

Resolution is by `ast`, never by importing the test module: `check` must not
execute a repository's code.
"""

from __future__ import annotations

import ast
import re

from fr.acceptance.model import split_ref

LINE_ANCHOR_RE = re.compile(r"^L\d+(?:-L?\d+)?$")
NODE_SEP = "::"
_PART_SEP = re.compile(r"::|\.")

_Def = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef


def is_python(path: str) -> bool:
    return path.endswith(".py")


def line_anchor_error(ref: str) -> str | None:
    """Why `ref` must not be written, or None when it may (pure)."""
    _, path, frag = split_ref(ref)
    if not (is_python(path) and LINE_ANCHOR_RE.match(frag)):
        return None
    return (
        f"line anchor into Python: {ref} — a line moves whenever code is added above "
        f"it, silently (gh#531); anchor on the test's name instead "
        f"(`#test_name`, or `#TestClass{NODE_SEP}test_name`)"
    )


def _parse(source: str) -> ast.Module | None:
    try:
        return ast.parse(source)
    except (SyntaxError, ValueError):
        return None


def _defs(body: list[ast.stmt]) -> list[_Def]:
    return [n for n in body if isinstance(n, _Def)]


def node_line(source: str, node: str) -> int | None:
    """The `def`/`class` line of `node` (`name`, `Class::name` or unittest's
    `Class.name`), or None.

    Only module-level names and names inside module-level classes (at any class
    nesting) are reachable — what a pytest node id can name. A function nested
    inside a function is not a test.
    """
    tree = _parse(source)
    if tree is None or not node:
        return None
    body: list[ast.stmt] = tree.body
    found: _Def | None = None
    for part in _PART_SEP.split(node):
        found = next((d for d in _defs(body) if d.name == part), None)
        if found is None:
            return None
        body = found.body if isinstance(found, ast.ClassDef) else []
    return found.lineno if found is not None else None


def _enclosing_defs(tree: ast.Module, line: int) -> list[_Def]:
    """The module-level def/class whose span holds `line`, then each class-nested
    one inside it — the chain a node id names."""
    path: list[_Def] = []
    body: list[ast.stmt] = tree.body
    while True:
        hit = next((d for d in _defs(body) if _start(d) <= line <= (d.end_lineno or 0)), None)
        if hit is None:
            break
        path.append(hit)
        if not isinstance(hit, ast.ClassDef):
            break
        body = hit.body
    return path


def enclosing_node(source: str, line: int) -> str | None:
    """The node (`name` / `Class::name`) whose span holds `line` — decorators
    included — or None for a line outside every module-level def/class."""
    tree = _parse(source)
    if tree is None:
        return None
    return NODE_SEP.join(d.name for d in _enclosing_defs(tree, line)) or None


def is_test_node(node: str, testcases: frozenset[str] = frozenset()) -> bool:
    """Whether pytest would collect `node`: every enclosing class a test class,
    the last part `test*` (or a test class). A test class is named `Test*` or is
    one of `testcases`, the `unittest.TestCase` subclasses pytest collects
    whatever their name (gh#893). A line anchor that sits in a helper slid off
    its test; naming the helper would certify the slide."""

    def test_class(name: str) -> bool:
        return name.startswith("Test") or name in testcases

    *classes, last = node.split(NODE_SEP)
    return all(test_class(c) for c in classes) and (
        last.startswith("test") or (not classes and test_class(last))
    )


def _base_names(cls: ast.ClassDef) -> list[str]:
    return [
        b.id if isinstance(b, ast.Name) else b.attr
        for b in cls.bases
        if isinstance(b, ast.Name | ast.Attribute)
    ]


def subclasses_testcase(cls: ast.ClassDef, tree: ast.Module) -> bool:
    """Whether `cls` subclasses a `*TestCase` (`unittest.TestCase`,
    `IsolatedAsyncioTestCase`, ...) — directly, or through a class defined at
    this module's top level, which is where a base name resolves. A base
    imported from another module is not followed: resolution reads the file, it
    never imports it. A plain mixin whose own name ends in `TestCase` counts."""
    module = {c.name: c for c in tree.body if isinstance(c, ast.ClassDef)}
    seen: set[str] = set()
    todo = [cls]
    while todo:
        for base in _base_names(todo.pop()):
            if base.endswith("TestCase"):
                return True
            if base in module and base not in seen:
                seen.add(base)
                todo.append(module[base])
    return False


def collected_node_at(source: str, line: int) -> str | None:
    """`enclosing_node`, kept only when it names a test."""
    tree = _parse(source)
    if tree is None:
        return None
    defs = _enclosing_defs(tree, line)
    if not defs:
        return None
    testcases = frozenset(
        d.name for d in defs if isinstance(d, ast.ClassDef) and subclasses_testcase(d, tree)
    )
    name = NODE_SEP.join(d.name for d in defs)
    return name if is_test_node(name, testcases) else None


def _start(d: _Def) -> int:
    return min([d.lineno, *(dec.lineno for dec in d.decorator_list)])


def line_of(ref_frag: str) -> int | None:
    """The first line a `L<n>[-L<m>]` fragment names, or None."""
    m = LINE_ANCHOR_RE.match(ref_frag)
    return int(ref_frag[1:].split("-")[0]) if m else None
