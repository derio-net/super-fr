"""Tripwire: no `.fr` path is built outside the configuration space resolver.

Spec 2026-11-19-event-driven-a-la-carte R2, R22, §A: `fr.config.space` is the one module
that decides where repo configuration lives, so a `.fr` path built anywhere else is a
reader that ignores the placement. The scan parses every module under `packages/*/src`
with `ast`, as `test_import_direction.py` does, and collects every path-shaped string
literal naming `.fr` or `.fr/...`: an argument of `Path(...)`, an operand of `/`, an
argument of `open`, `read_text` or `show_at_commit`, an element of a `git show` argument
list, and also a literal bound to a name or used as a default (a named path constant is a
construction too; it belongs in `fr.config.space`). An f-string is one when a literal
piece of it names `.fr` as a path segment (`f"{root}/.fr/ci.yaml"`, `f"{rev}:.fr/ci.yaml"`).
Messages are not constructions: a docstring, and the arguments (f-strings included) of
`print`, the echo helpers, a logger, `warnings.warn`, and an exception constructor are
skipped (review p1-r5: an f-string anywhere else is a path until it is a message's).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC_GLOB = "packages/*/src/**/*.py"

ALLOWED = (
    "packages/fr/src/fr/config/space.py",
    "packages/fr/src/fr/artifacts/paths.py",
)
"""The resolver and the artifact path table: the only modules that may name `.fr`."""

ALLOWED_GLOBS = (
    "packages/fr/src/fr/artifacts/*migration*",
    "packages/fr/src/fr/config/migrate*.py",
)
"""Migrations name the old paths they move files from."""

PATH_SHAPED = re.compile(r"\.fr(/[^\s:]*)?")
"""`.fr` or `.fr/<path>`: no whitespace or colon, so a sentence that starts with a path
(`.fr/ops.yaml settings:`) is a message, and `.fr-isolation` is another name."""

FSTRING_PATH = re.compile(r"(?:^|[/:])\.fr(?:/[^\s:]*)?$")
"""A literal piece of an f-string naming `.fr` as a path segment: at the piece's start or
after `/` or `:` (a `<rev>:` prefix), running to the piece's end (a formatted value or the
string's end follows), so `{root}/.fr/ci.yaml` and `{rev}:.fr/` match and a sentence does
not."""

MESSAGE_CALLS = frozenset(
    {
        "print",
        "echo",
        "secho",
        "warn",
        "warning",
        "error",
        "info",
        "debug",
        "exception",
        "critical",
        "fail",
        "note",
    }
)
"""Calls whose arguments are text for a reader, never a path fr opens."""

MESSAGE_SUFFIXES = ("Error", "Exception", "Refused", "Warning", "Problem", "Issue")
"""An exception constructor (and fr's problem/issue records) carries a message."""


def _call_name(call: ast.Call) -> str:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _is_message_call(call: ast.Call) -> bool:
    name = _call_name(call)
    return name in MESSAGE_CALLS or name.endswith(MESSAGE_SUFFIXES)


def _docstrings(tree: ast.AST) -> set[int]:
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                found.add(id(body[0].value))
        # An attribute docstring: a bare string statement after an assignment.
        for field in ("body", "orelse", "finalbody"):
            stmts = getattr(node, field, None)
            if isinstance(stmts, list):
                for stmt in stmts:
                    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                        found.add(id(stmt.value))
    return found


def constructions(source: str, name: str = "<module>") -> list[tuple[int, str]]:
    """`(line, literal)` for every `.fr` path construction in *source*."""
    tree = ast.parse(source, filename=name)
    parents: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
    skip = _docstrings(tree)
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if id(node) in skip:
            continue
        piece = isinstance(parents.get(id(node)), ast.JoinedStr)
        if not (FSTRING_PATH.search if piece else PATH_SHAPED.fullmatch)(node.value):
            continue
        up = parents.get(id(node))
        message = False
        while up is not None:
            if isinstance(up, ast.Call) and _is_message_call(up):
                message = True
                break
            up = parents.get(id(up))
        if not message:
            found.append((node.lineno, node.value))
    return sorted(found)


def _allowed(rel: str) -> bool:
    return rel in ALLOWED or any(Path(rel).match(g) for g in ALLOWED_GLOBS)


def test_no_fr_path_is_built_outside_the_resolver() -> None:
    offenders: list[str] = []
    for path in sorted(REPO.glob(SRC_GLOB)):
        rel = path.relative_to(REPO).as_posix()
        if _allowed(rel):
            continue
        for line, literal in constructions(path.read_text(), rel):
            offenders.append(f"{rel}:{line}: {literal!r}")
    assert not offenders, (
        "a `.fr` path is built outside fr.config.space (spec 2026-11-19-event-driven-a-la-"
        "carte R2): ask `config_space(root)` (`.dir`, `.file`, `.at_default`, `.at_pair`) "
        "or name the file with `fr.config.space.rel` / a constant there:\n  "
        + "\n  ".join(offenders)
    )


FIXTURE = '''
"""A module naming `.fr/ci.yaml` in its docstring."""
from pathlib import Path

def read(root):
    print(".fr/ci.yaml")
    raise ValueError(".fr/ci.yaml")
    log.info(f"{root}/.fr/ci.yaml")
    return (root / ".fr/ci.yaml").read_text()
'''


def test_the_scan_finds_the_construction_and_skips_the_messages() -> None:
    assert constructions(FIXTURE) == [(9, ".fr/ci.yaml")]


def test_the_scan_sees_each_construction_shape() -> None:
    source = (
        'Path(".fr")\n'
        'open(".fr/a")\n'
        'p.read_text(".fr/b")\n'
        'show_at_commit(root, sha, ".fr/c")\n'
        'git(["show", "HEAD:x", ".fr/d"])\n'
        'X = ".fr/e"\n'
        'def f(source=".fr/f"): ...\n'
        'y = ".fr-isolation"\n'
        'z = ".fr/ops.yaml settings:"\n'
    )
    assert [lit for _, lit in constructions(source)] == [
        ".fr",
        ".fr/a",
        ".fr/b",
        ".fr/c",
        ".fr/d",
        ".fr/e",
        ".fr/f",
    ]


def test_an_f_string_building_a_path_is_a_construction() -> None:
    """Review p1-r5: an f-string is a message only as an argument of a message call."""
    source = (
        'Path(f"{root}/.fr/ci.yaml")\n'
        'git(root, "show", f"{rev}:.fr/ci.yaml")\n'
        'p = f"{root}/.fr/{name}"\n'
        'raise ValueError(f"{root}/.fr/ci.yaml is bad")\n'
        'log.warning(f"read {root}/.fr/ci.yaml")\n'
        'typer.secho(f"{rev}:.fr/ci.yaml")\n'
        'warnings.warn(f"{root}/.fr/ci.yaml")\n'
        'print(f"{root}/.fr")\n'
        'x = f"the product checkout\'s .fr/ under {p}"\n'
    )
    assert [line for line, _ in constructions(source)] == [1, 2, 3]
