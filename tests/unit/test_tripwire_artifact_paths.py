"""CI tripwire: only `fr.artifacts.paths` spells an artifact directory (spec 2026-11-04 R1).

R1: "One path resolver, keyed by kind and placement, produces every artifact path. ... A
tripwire refuses a hardcoded artifact path outside it." A literal `docs/superpowers/...`
or `docs/acceptance/...` anywhere else is a path that does not move with the placement.

Caught: a string constant that is not a docstring (f-string parts included) and holds
`docs/superpowers` or `docs/acceptance` or is the bare `"superpowers"` (so a `.name ==
"superpowers"` comparison, or a `"docs" / x` built elsewhere, cannot walk to the root by name;
only a `KIND_DIRS[...]` or `kind_dir(...)` key is exempt). A bare `"acceptance"` is NOT
flagged: it is a feature, section and CLI key in ~75 places, which would need a large
allowlist. Also caught: any
join that puts `docs` straight before `superpowers` or `acceptance` — a `/` chain (also
`root / "docs" / "superpowers/plans"`), `Path("docs") / ...`, `Path("docs", ...)`,
`.joinpath("docs", ...)`, any call's positional arguments, and a tuple or list of
segments. Docstrings and comments are prose, not paths.

`PENDING` lists the modules still allowed a literal. It is empty: plan 3's phase 2 moved
every caller onto the resolver. It may only shrink: an entry with no violation left fails,
so a future exemption is named here, with its reason, and removed with its fix.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RESOLVER = "fr/artifacts/paths.py"
_NEEDLES = ("docs/superpowers", "docs/acceptance")
_SEGMENTS = ("superpowers", "acceptance")

# Modules (relative to their package's `src/`) still allowed a literal. Empty by design.
PENDING: tuple[str, ...] = ()


def _docstring_ids(tree: ast.AST) -> set[int]:
    """Every bare string-expression statement: module, class and function docstrings,
    and the attribute docstrings that follow an assignment."""
    return {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }


def _is_str(node: ast.AST, value: str | None = None) -> bool:
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and (value is None or node.value == value)
    )


_PATH_CALLS = frozenset({"Path", "PurePath", "PurePosixPath", "PosixPath"})


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _segments(node: ast.AST) -> list[str | None]:
    """The path segments *node* spells, `None` for any segment not known statically.

    A string splits on `/`; a `/`-join, a `Path(...)` and a `.joinpath(...)` concatenate
    their parts. Anything else is one unknown segment."""
    if _is_str(node):
        assert isinstance(node, ast.Constant)
        return [part for part in node.value.split("/") if part] or [None]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _segments(node.left) + _segments(node.right)
    joined = _static_str(node)
    if joined is not None:  # `"docs" + "/" + "superpowers"`
        return _segments(ast.Constant(value=joined))
    if isinstance(node, ast.Call):
        name = _call_name(node)
        if (
            name == "join"
            and isinstance(node.func, ast.Attribute)
            and _is_str(node.func.value, "/")
            and len(node.args) == 1
            and isinstance(node.args[0], (ast.Tuple, ast.List))
        ):  # `"/".join(["docs", "superpowers"])`
            return [seg for elt in node.args[0].elts for seg in _segments(elt)]
        if name == "joinpath" and isinstance(node.func, ast.Attribute):
            return _segments(node.func.value) + _arg_segments(node)
        if name in _PATH_CALLS:
            return _arg_segments(node)
    return [None]


def _arg_segments(node: ast.Call) -> list[str | None]:
    return [seg for arg in node.args for seg in _segments(arg)]


def _static_str(node: ast.AST) -> str | None:
    """The string *node* spells when it is built only from constants joined by `+`."""
    if _is_str(node):
        assert isinstance(node, ast.Constant)
        return str(node.value)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _static_str(node.left), _static_str(node.right)
        return None if left is None or right is None else left + right
    return None


# A bare `"superpowers"` is the artifact root's own name: a kind-dir lookup key
# (`KIND_DIRS["superpowers"]`, `kind_dir("superpowers", ...)`) is the one legitimate use.
_KEY_CALLS = frozenset({"kind_dir", "shell_name"})


def _key_ids(tree: ast.AST) -> set[int]:
    """Ids of the string constants that are kind-table keys, not path segments."""
    out: set[int] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == "KIND_DIRS"
        ):
            out.add(id(node.slice))
        elif isinstance(node, ast.Call) and _call_name(node) in _KEY_CALLS and node.args:
            out.add(id(node.args[0]))
        elif isinstance(node, ast.Call) and _call_name(node) == "below" and len(node.args) > 1:
            out.add(id(node.args[1]))  # `below(root, kind)`
    return out


def _artifact_join(segments: list[str | None]) -> str | None:
    """`"docs" / <segment>` when *segments* hold `docs` then an artifact segment."""
    for here, after in zip(segments, segments[1:]):
        if here == "docs" and after in _SEGMENTS:
            return f'"docs" / {after!r}'
    return None


def violations(source: str) -> list[tuple[int, str]]:
    """`(line, what)` for every artifact-path literal in *source*, one per line.

    Caught: a string constant that is not a docstring, and any join that puts `docs`
    before an artifact segment: a `/` chain, `Path(...)`, `.joinpath(...)`, any call's
    positional arguments (`os.path.join`) and a tuple or list of segments."""
    tree = ast.parse(source)
    docs = _docstring_ids(tree)
    keys = _key_ids(tree)
    found: dict[int, str] = {}
    for node in ast.walk(tree):
        what: str | None = None
        if _is_str(node) and id(node) not in docs:
            assert isinstance(node, ast.Constant)
            if any(n in node.value for n in _NEEDLES) or (
                node.value == "superpowers" and id(node) not in keys
            ):
                what = repr(node.value)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.Add)):
            what = _artifact_join(_segments(node))
        elif isinstance(node, ast.Call):
            what = _artifact_join(_segments(node)) or _artifact_join(_arg_segments(node))
        elif isinstance(node, (ast.Tuple, ast.List)):
            what = _artifact_join([seg for elt in node.elts for seg in _segments(elt)])
        if what is not None:
            found.setdefault(getattr(node, "lineno", 0), what)
    return sorted(found.items())


def _modules() -> dict[str, Path]:
    out: dict[str, Path] = {}
    for src in sorted(REPO_ROOT.glob("packages/*/src")):
        for path in sorted(src.rglob("*.py")):
            out[path.relative_to(src).as_posix()] = path
    return out


def _violating() -> dict[str, list[tuple[int, str]]]:
    out = {}
    for rel, path in _modules().items():
        if rel == RESOLVER:
            continue
        found = violations(path.read_text())
        if found:
            out[rel] = found
    return out


def test_no_artifact_path_literal_outside_the_resolver() -> None:
    offenders = {rel: v for rel, v in _violating().items() if rel not in PENDING}
    assert not offenders, (
        "artifact paths spelled outside fr.artifacts.paths (use kind_dir / KIND_DIRS):\n"
        + "\n".join(f"  {rel}:{line} {what}" for rel, v in offenders.items() for line, what in v)
    )


def test_pending_only_shrinks() -> None:
    violating = _violating()
    stale = [rel for rel in PENDING if rel not in violating]
    assert not stale, f"no literal left in these PENDING modules; remove them: {stale}"
    modules = _modules()
    assert all(rel in modules for rel in PENDING)
    assert list(PENDING) == sorted(set(PENDING)), "keep PENDING sorted and unique"


def test_the_resolver_itself_holds_the_literals() -> None:
    assert violations(_modules()[RESOLVER].read_text())


_PLANTED = '''
"""Module docstring naming docs/superpowers/plans is prose."""
from pathlib import Path

# a comment naming docs/acceptance/features is prose too
X = "docs/superpowers/runs"
Y = Path("/r") / "docs" / "acceptance" / "features"


def f(root):
    """docs/superpowers/specs in a docstring is fine."""
    return root / "docs" / "superpowers"


Z = f"{1}docs/acceptance/{2}"
'''


def test_the_detector_finds_both_forms_and_skips_prose() -> None:
    lines = [line for line, _ in violations(_PLANTED)]
    assert lines == [6, 7, 12, 15]


_PLANTED_OTHER_FORMS = """
from pathlib import Path
import os

A = Path("docs") / "superpowers"
B = Path("docs", "superpowers")
C = root.joinpath("docs", "superpowers")
D = ("docs", "superpowers", "plans")
E = ["docs", "acceptance"]
F = root / "docs" / "superpowers/plans"
G = os.path.join(root, "docs", "acceptance")
H = Path(root, "docs") / "acceptance" / "features"
"""


def test_the_detector_finds_every_other_join_form() -> None:
    lines = [line for line, _ in violations(_PLANTED_OTHER_FORMS)]
    assert lines == [5, 6, 7, 8, 9, 10, 11, 12]


def test_a_docs_join_not_followed_by_an_artifact_segment_is_fine() -> None:
    assert violations('P = root / "docs" / "explainers"\nQ = "docs/reference/cli.md"\n') == []
    assert violations('T = ("docs", "explainers")\nU = Path("docs", "reference")\n') == []


_PLANTED_NEW_FORMS = """
from fr.artifacts.paths import KIND_DIRS, kind_dir

OK1 = KIND_DIRS["superpowers"]
OK2 = kind_dir("superpowers", space)
A = "docs" + "/superpowers"
B = "docs/" + "super" + "powers"
C = "/".join(["docs", "superpowers"])
D = "/".join(("docs", "acceptance"))
E = p.name == "superpowers"
F = os.path.join(root, "docs", "superpowers")
G = parts[i] == "superpowers"
"""


def test_the_detector_finds_concatenation_joins_and_a_bare_superpowers() -> None:
    lines = [line for line, _ in violations(_PLANTED_NEW_FORMS)]
    # B spells no whole `docs/superpowers` constant: only its joined static string does.
    assert lines == [6, 7, 8, 9, 10, 11, 12]


# --- a placement-bound directory joined to a raw root (review p3-r1) ---------------------
#
# R1: "every caller asks the resolver for the ROOT as well as the layout". Phase 2 left
# `repo_root / RUNS_REL`-style joins, which under quiet write into the product checkout.
# Caught: a `/` whose right side is `KIND_DIRS[<kind>]` (or `Path(...)` of it, or a module
# constant built from one, in any module) for a placement-bound kind, and whose left side
# is not the resolver's answer: a call to one of `_ROOT_CALLS`, or a name bound from one
# (assigned, or iterated over) in the same module. Repo configuration kinds
# (`fr.artifacts.paths.REPO_CONFIG_KINDS`) are read from the product checkout everywhere.
# A root that is ALREADY an artifact root by construction (an exported tree, the root an
# artifact's own path names) says so with `paths.below(root, kind)`.

_ROOT_CALLS = frozenset({"artifact_root", "feature_root", "feature_roots", "search_roots"})


def _kind_keys(node: ast.AST) -> set[str]:
    return {
        n.slice.value
        for n in ast.walk(node)
        if isinstance(n, ast.Subscript)
        and (
            (isinstance(n.value, ast.Name) and n.value.id == "KIND_DIRS")
            or (isinstance(n.value, ast.Attribute) and n.value.attr == "KIND_DIRS")
        )
        and isinstance(n.slice, ast.Constant)
        and isinstance(n.slice.value, str)
    }


def _bound_kinds(keys: set[str]) -> bool:
    from fr.artifacts.paths import REPO_CONFIG_KINDS

    return any(k not in REPO_CONFIG_KINDS for k in keys)


def _bound_constants(trees: dict[str, ast.Module]) -> set[str]:
    """Module-level names, in any module, assigned a placement-bound `KIND_DIRS` path."""
    names: set[str] = set()
    for tree in trees.values():
        for node in tree.body:
            value = node.value if isinstance(node, (ast.Assign, ast.AnnAssign)) else None
            if value is None or not _bound_kinds(_kind_keys(value)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names |= {t.id for t in targets if isinstance(t, ast.Name)}
    return names


def _resolved_names(tree: ast.AST) -> set[str]:
    """Names bound from a resolver call in *tree*: `x = artifact_root(...)`, `for x in
    feature_roots(...)`, a comprehension over one."""

    def from_resolver(value: ast.AST | None) -> bool:
        return isinstance(value, ast.Call) and _call_name(value) in _ROOT_CALLS

    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and from_resolver(node.value):
            out |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        elif isinstance(node, (ast.For, ast.comprehension)) and from_resolver(node.iter):
            if isinstance(node.target, ast.Name):
                out.add(node.target.id)
    return out


def _right_is_bound(node: ast.AST, constants: set[str]) -> bool:
    if isinstance(node, ast.Name):
        return node.id in constants
    if isinstance(node, ast.Attribute):
        return node.attr in constants
    if isinstance(node, ast.Call) and _call_name(node) in _PATH_CALLS and len(node.args) == 1:
        return _right_is_bound(node.args[0], constants)
    return _bound_kinds(_kind_keys(node)) and isinstance(node, ast.Subscript)


def raw_root_joins(source: str, constants: set[str]) -> list[tuple[int, str]]:
    tree = ast.parse(source)
    resolved = _resolved_names(tree)
    found = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)):
            continue
        if not _right_is_bound(node.right, constants):
            continue
        left = node.left
        if isinstance(left, ast.Call) and _call_name(left) in _ROOT_CALLS:
            continue
        if isinstance(left, ast.Name) and left.id in resolved:
            continue
        found.append((node.lineno, f"{ast.unparse(left)} / {ast.unparse(node.right)}"))
    return sorted(set(found))


def _raw_root_offenders() -> dict[str, list[tuple[int, str]]]:
    trees = {rel: ast.parse(path.read_text()) for rel, path in _modules().items()}
    constants = _bound_constants(trees)
    out = {}
    for rel, path in _modules().items():
        if rel == RESOLVER:
            continue
        found = raw_root_joins(path.read_text(), constants)
        if found:
            out[rel] = found
    return out


def test_no_placement_bound_directory_is_joined_to_a_raw_root() -> None:
    offenders = _raw_root_offenders()
    assert not offenders, (
        "a placement-bound artifact directory joined to a raw root (ask the resolver: "
        "artifact_root(root) / X, feature_roots(...), or paths.below(root, kind) for a root "
        "that already is one):\n"
        + "\n".join(f"  {rel}:{line} {what}" for rel, v in offenders.items() for line, what in v)
    )


_PLANTED_JOINS = """
from pathlib import Path
from fr.artifacts.paths import KIND_DIRS, artifact_root, feature_roots

RUNS_REL = Path(KIND_DIRS["run"])
WORKFLOWS_REL = Path(KIND_DIRS["workflow"])


def f(repo_root):
    a = repo_root / RUNS_REL
    b = artifact_root(repo_root) / RUNS_REL
    base = artifact_root(repo_root)
    c = base / RUNS_REL
    d = repo_root / WORKFLOWS_REL
    e = repo_root / KIND_DIRS["plan"]
    for froot in feature_roots(space):
        g = froot / KIND_DIRS["plan"]
    h = Path(repo_root) / Path(KIND_DIRS["spec"])
"""


def test_the_join_detector_finds_raw_roots_and_spares_the_resolver() -> None:
    constants = _bound_constants({"m": ast.parse(_PLANTED_JOINS)})
    assert constants == {"RUNS_REL"}
    lines = [line for line, _ in raw_root_joins(_PLANTED_JOINS, constants)]
    assert lines == [10, 15, 18]
