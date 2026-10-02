"""Name anchors into Python — the one definition of what a `.py` fragment means.

A ref's fragment into a Python file names a test the way pytest's node id does,
after the file: `tests/x.py#test_y`, `tests/x.py#TestX::test_y`. It never pins a
line (gh#531). A line is the least stable property of a test: every line added
above it moves it, nothing noticed when it did, and the reports went on linking
readers into the middle of an unrelated test. A name either still resolves or
`fr acceptance check` says it does not.

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
    """The `def`/`class` line of `node` (`name` or `Class::name`), or None.

    Only module-level names and names inside module-level classes (at any class
    nesting) are reachable — what a pytest node id can name. A function nested
    inside a function is not a test.
    """
    tree = _parse(source)
    if tree is None or not node:
        return None
    body: list[ast.stmt] = tree.body
    found: _Def | None = None
    for part in node.split(NODE_SEP):
        found = next((d for d in _defs(body) if d.name == part), None)
        if found is None:
            return None
        body = found.body if isinstance(found, ast.ClassDef) else []
    return found.lineno if found is not None else None


def enclosing_node(source: str, line: int) -> str | None:
    """The node (`name` / `Class::name`) whose span holds `line` — decorators
    included — or None for a line outside every module-level def/class."""
    tree = _parse(source)
    if tree is None:
        return None
    path: list[str] = []
    body: list[ast.stmt] = tree.body
    while True:
        hit = next((d for d in _defs(body) if _start(d) <= line <= (d.end_lineno or 0)), None)
        if hit is None:
            break
        path.append(hit.name)
        if not isinstance(hit, ast.ClassDef):
            break
        body = hit.body
    return NODE_SEP.join(path) or None


def is_test_node(node: str) -> bool:
    """Whether pytest would collect `node`: every enclosing class `Test*`, the
    last part `test*` (or a `Test*` class). A line anchor that sits in a
    helper slid off its test; naming the helper would certify the slide."""
    *classes, last = node.split(NODE_SEP)
    return all(c.startswith("Test") for c in classes) and (
        last.startswith("test") or (not classes and last.startswith("Test"))
    )


def collected_node_at(source: str, line: int) -> str | None:
    """`enclosing_node`, kept only when it names a test."""
    name = enclosing_node(source, line)
    return name if name is not None and is_test_node(name) else None


def _start(d: _Def) -> int:
    return min([d.lineno, *(dec.lineno for dec in d.decorator_list)])


def line_of(ref_frag: str) -> int | None:
    """The first line a `L<n>[-L<m>]` fragment names, or None."""
    m = LINE_ANCHOR_RE.match(ref_frag)
    return int(ref_frag[1:].split("-")[0]) if m else None
