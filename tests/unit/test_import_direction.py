"""Package boundary enforcement (super-fr split, B2 style).

Imports are read from the syntax tree (`ast`), not matched by pattern. Dynamic
imports and entry-point loading are not judged.

Dependency direction is the architecture: `fr` imports neither sibling;
`fr_dispatch` never imports an adapter (adapters plug in via the Runner
protocol / entry points). A violation here is a design regression, not
a style nit — the whole point of the split is that the base ships
without the dispatch stack and the framework ships without any adapter.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

PACKAGES = Path(__file__).resolve().parents[2] / "packages"


def _imports_of(package_dir: Path) -> dict[Path, set[str]]:
    """Root module of every import in every file under `package_dir`."""
    out: dict[Path, set[str]] = {}
    for py in package_dir.rglob("*.py"):
        package = ".".join(py.relative_to(package_dir.parent).parent.parts)
        nodes = _import_nodes(py.read_text(), package)
        out[py] = {module.split(".")[0] for module, _names, _pos in nodes if module}
    return out


# The sanctioned soft points (spec §Architecture; 2026-09-25-triage-batches
# §3.C): `fr apply --to` and `fr triage batch dispatch` import fr_dispatch
# behind an importlib.util.find_spec guard. No other fr module may.
_SOFT_POINTS = ("apply_cmd.py", "triage_batch_cmd.py", "triage_kanban_cmd.py")
_SOFT_TARGET = "fr_dispatch"

# Every workspace package but `fr` itself, read from disk (gh#643): a hand
# list missed `fr_cncd`, and would miss the next package the same way.
_SIBLINGS = frozenset(p.parent.name for p in PACKAGES.glob("*/src/*/__init__.py")) - {"fr"}


def _sibling_offenders(src_root: Path) -> dict[str, set[str]]:
    return {
        str(f): roots & _SIBLINGS
        for f, roots in _imports_of(src_root).items()
        if roots & _SIBLINGS
        and not (
            f.parent.name == "commands"
            and f.name in _SOFT_POINTS
            and roots & _SIBLINGS == {_SOFT_TARGET}
        )
    }


def test_fr_imports_no_siblings() -> None:
    offenders = _sibling_offenders(PACKAGES / "fr" / "src" / "fr")
    assert not offenders, f"fr must not import siblings: {offenders}"


def test_every_sibling_package_is_an_offender(tmp_path: Path) -> None:
    """gh#643: a hand-written banned set missed `fr_cncd`. Every package under
    `packages/*/src/` other than `fr` itself is a sibling, including ones added
    after this test was written."""
    siblings = {p.parent.name for p in PACKAGES.glob("*/src/*/__init__.py")} - {"fr"}
    assert {"fr_claude_cloud", "fr_cncd", "fr_dispatch", "fr_herdr"} <= siblings
    for name in siblings:
        (tmp_path / f"imports_{name}.py").write_text(f"from {name}.x import y\n")
    offenders = _sibling_offenders(tmp_path)
    assert set(offenders) == {str(tmp_path / f"imports_{n}.py") for n in siblings}


def test_a_third_fr_dispatch_import_is_refused(tmp_path: Path) -> None:
    """The soft points are a closed pair: any other module importing
    fr_dispatch, and a soft point importing an adapter, are offenders."""
    commands = tmp_path / "commands"
    commands.mkdir()
    in_def = "def f():\n    from fr_dispatch.registry import x\n"
    (commands / "triage_batch_cmd.py").write_text(in_def)
    (commands / "other_cmd.py").write_text(in_def)
    (commands / "apply_cmd.py").write_text("def f():\n    import fr_cncd\n")
    offenders = _sibling_offenders(tmp_path)
    assert set(offenders) == {str(commands / "other_cmd.py"), str(commands / "apply_cmd.py")}


def test_soft_points_are_guarded() -> None:
    """Each sanctioned import must stay behind find_spec — never module-level —
    and carry the same install message."""
    for name in _SOFT_POINTS:
        src = (PACKAGES / "fr" / "src" / "fr" / "commands" / name).read_text()
        assert not _soft_point_violations(src), name


def test_fr_dispatch_never_imports_fr_cncd() -> None:
    offenders = {
        str(f): roots & {"fr_cncd"}
        for f, roots in _imports_of(PACKAGES / "fr-dispatch" / "src" / "fr_dispatch").items()
        if "fr_cncd" in roots
    }
    assert not offenders, f"fr_dispatch must not import the adapter: {offenders}"


_ADAPTERS = ("fr_cncd", "fr_herdr", "fr_claude_cloud")


def test_adapters_never_import_each_other() -> None:
    """The runner adapters are peers: each may import the base and the
    framework, never a sibling adapter."""
    offenders = {}
    for adapter in _ADAPTERS:
        src = PACKAGES / adapter.replace("_", "-") / "src" / adapter
        assert (src / "__init__.py").is_file(), src
        for f, roots in _imports_of(src).items():
            hit = roots & (set(_ADAPTERS) - {adapter})
            if hit:
                offenders[str(f)] = hit
    assert not offenders, f"an adapter must not import a sibling adapter: {offenders}"


def test_fr_dispatch_carries_no_vk_vocabulary() -> None:
    """The framework carries no VK vocabulary: no MCP client types, no
    VibeKanban wire shapes, no willikins metric names."""
    banned = re.compile(r"VkMcpClient|vibe-kanban|willikins|project_id|VK_[A-Z]", re.I)
    offenders = []
    for py in (PACKAGES / "fr-dispatch" / "src" / "fr_dispatch").rglob("*.py"):
        for n, line in enumerate(py.read_text().splitlines(), 1):
            if banned.search(line):
                offenders.append(f"{py.name}:{n}: {line.strip()}")
    assert not offenders, "VK vocabulary leaked into fr_dispatch:\n" + "\n".join(offenders)


def test_fr_dispatch_never_imports_fr_herdr() -> None:
    offenders = {
        str(f): roots & {"fr_herdr"}
        for f, roots in _imports_of(PACKAGES / "fr-dispatch" / "src" / "fr_dispatch").items()
        if "fr_herdr" in roots
    }
    assert not offenders, f"fr_dispatch must not import the adapter: {offenders}"


def _imports_fr_triage(source: str) -> bool:
    """True when `source` imports `fr.triage` (or `from fr import triage`)."""
    return any(
        module == "fr.triage"
        or module.startswith("fr.triage.")
        or (module == "fr" and "triage" in names)
        for module, names, _position in _import_nodes(source)
    )


def test_fr_herdr_never_imports_fr_triage() -> None:
    """Spec §3.C: `fr-herdr` never imports `fr.triage` — a runner takes a
    WorkItem, never triage state. `_imports_of` keeps only the root `fr`,
    so this reads the dotted module."""
    offenders = [
        str(py)
        for py in (PACKAGES / "fr-herdr" / "src" / "fr_herdr").rglob("*.py")
        if _imports_fr_triage(py.read_text())
    ]
    assert not offenders, f"fr_herdr must not import fr.triage: {offenders}"


def test_fr_claude_cloud_never_imports_fr_triage() -> None:
    """Cloud-triage §F: `fr-claude-cloud` is a runner like herdr: it takes a WorkItem
    and the scope's state directory, never triage state through `fr.triage`."""
    src = PACKAGES / "fr-claude-cloud" / "src" / "fr_claude_cloud"
    assert (src / "__init__.py").is_file()
    offenders = [str(py) for py in src.rglob("*.py") if _imports_fr_triage(py.read_text())]
    assert not offenders, f"fr_claude_cloud must not import fr.triage: {offenders}"


def test_fr_never_imports_fr_claude_cloud() -> None:
    """`fr` reaches the cloud runner only through `fr.triage.driver.Mailbox` and the
    registry, never by import (no soft point names it either)."""
    offenders = {
        str(f): roots & {"fr_claude_cloud"}
        for f, roots in _imports_of(PACKAGES / "fr" / "src" / "fr").items()
        if "fr_claude_cloud" in roots
    }
    assert not offenders, f"fr must not import the cloud runner: {offenders}"


def test_fr_dispatch_never_imports_fr_claude_cloud() -> None:
    offenders = {
        str(f): roots & {"fr_claude_cloud"}
        for f, roots in _imports_of(PACKAGES / "fr-dispatch" / "src" / "fr_dispatch").items()
        if "fr_claude_cloud" in roots
    }
    assert not offenders, f"fr_dispatch must not import the adapter: {offenders}"


def test_fr_herdr_tripwire_catches_a_triage_import(tmp_path: Path) -> None:
    """The pattern above must actually fire, or the guard is decorative."""
    assert _imports_fr_triage("from fr.triage.model import Batch\n")
    assert _imports_fr_triage("import fr.triage\n")
    assert _imports_fr_triage("from fr import triage\n")
    assert _imports_fr_triage("import os, fr.triage\n")
    assert not _imports_fr_triage("from fr.triaged import x\n")


def test_board_status_equals_session_status() -> None:
    """`fr.triage.kanban` may not import `fr_dispatch`, so it keeps its own copy of
    the vocabulary; this is what stops the two drifting."""
    from typing import get_args

    from fr.triage.kanban import BoardStatus
    from fr_dispatch.protocols import SessionStatus

    assert get_args(BoardStatus) == get_args(SessionStatus)


# --- the syntax-tree reader (G01) -------------------------------------------


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_call_name(node.value)}.{node.attr}"
    return ""


def _is_type_checking(test: ast.expr) -> bool:
    return _call_name(test) in {"TYPE_CHECKING", "typing.TYPE_CHECKING"}


def _import_nodes(
    source: str, package: str | None = None
) -> list[tuple[str, tuple[str, ...], str]]:
    """Every import in `source` as `(dotted module, imported names, position)`.

    Position is `function` (inside any def or lambda), `type_checking` (in the body
    of `if TYPE_CHECKING:` outside a function) or `module`. Reads the syntax tree, so
    a comma list, an alias, a nested import and a multi-line import are all seen.
    A `SyntaxError` is not caught: an unparseable file must fail the guard, not pass
    it. Dynamic imports (`importlib.import_module`) and entry-point loading are not
    judged: nothing here can see them.
    """
    found: list[tuple[str, tuple[str, ...], str]] = []
    parts = package.split(".") if package else []

    def visit(node: ast.AST, position: str) -> None:
        if isinstance(node, ast.Import):
            found.extend((a.name, (), position) for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                keep = parts[: len(parts) - (node.level - 1)]
                module = ".".join([*keep, *([module] if module else [])])
            found.append((module, tuple(a.name for a in node.names), position))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            position = "function"
        for field, value in ast.iter_fields(node):
            children = value if isinstance(value, list) else [value]
            for child in children:
                if not isinstance(child, ast.AST):
                    continue
                inner = position
                if (
                    isinstance(node, ast.If)
                    and field == "body"
                    and position == "module"
                    and _is_type_checking(node.test)
                ):
                    inner = "type_checking"
                visit(child, inner)

    visit(ast.parse(source), "module")
    return found


def _soft_point_violations(source: str) -> list[str]:
    """Why `source` is not a well-formed soft point for `fr_dispatch`."""
    problems = [
        f"{module} imported at {position} level"
        for module, _names, position in _import_nodes(source)
        if module.split(".")[0] == _SOFT_TARGET and position == "module"
    ]
    guarded = any(
        isinstance(n, ast.Call)
        and _call_name(n.func) == "importlib.util.find_spec"
        and n.args
        and isinstance(n.args[0], ast.Constant)
        and n.args[0].value == _SOFT_TARGET
        for n in ast.walk(ast.parse(source))
    )
    if not guarded:
        problems.append('no importlib.util.find_spec("fr_dispatch") call')
    if "uv tool install --with fr-dispatch fr" not in source:
        problems.append("install message missing")
    return problems


_GUARD = (
    "import importlib.util\n"
    'importlib.util.find_spec("fr_dispatch")\n'
    '"uv tool install --with fr-dispatch fr"\n'
)


def test_import_nodes_read_every_spelling() -> None:
    def mods(src: str) -> list[str]:
        return [m for m, _n, _p in _import_nodes(src)]

    assert mods("import os, fr_cncd\n") == ["os", "fr_cncd"]
    assert mods("import fr_cncd as c\n") == ["fr_cncd"]
    assert mods("from fr_cncd import x\n") == ["fr_cncd"]
    assert mods("def f():\n    import fr_cncd\n") == ["fr_cncd"]
    assert mods("try:\n    import fr_cncd\nexcept ImportError:\n    pass\n") == ["fr_cncd"]
    assert mods("import os, fr.triage\n") == ["os", "fr.triage"]
    assert _import_nodes("from fr import triage\n") == [("fr", ("triage",), "module")]
    assert mods("from . import x\n") == [""]
    assert _import_nodes("from . import x\n", package="fr.triage") == [
        ("fr.triage", ("x",), "module")
    ]


def test_import_nodes_do_not_swallow_a_syntax_error() -> None:
    import pytest

    with pytest.raises(SyntaxError):
        _import_nodes("    import x\n")


def test_soft_point_violations_fire_on_planted_sources() -> None:
    assert _soft_point_violations(_GUARD + "from fr_dispatch import x\n")
    assert _soft_point_violations(
        _GUARD + "try:\n    from fr_dispatch import x\nexcept ImportError:\n    x = None\n"
    )
    assert _soft_point_violations(_GUARD + "if SOMETHING:\n    from fr_dispatch import x\n")
    assert _soft_point_violations('"uv tool install --with fr-dispatch fr"\n')  # no find_spec
    assert not _soft_point_violations(_GUARD + "def f():\n    from fr_dispatch import x\n")
    assert not _soft_point_violations(
        _GUARD
        + "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from fr_dispatch import x\n"
    )


def test_cloud_status_is_the_protocol_type() -> None:
    """The cloud adapter's status IS the dispatch protocol's: one vocabulary, so the
    mailbox can never hand back a status the protocol does not name."""
    from fr_claude_cloud.mailbox import FrStatus
    from fr_dispatch.protocols import SessionStatus

    assert FrStatus is SessionStatus
    # `typing` caches equal Literals, so identity also holds for a second literal
    # written with the same values. The source must assign the protocol's name.
    import fr_claude_cloud.mailbox as mailbox

    assert _alias_target(Path(mailbox.__file__).read_text(), "FrStatus") == "SessionStatus"


def _alias_target(source: str, name: str) -> str | None:
    """The bare name a module-level `name = <Name>` assigns, else None."""
    for node in ast.parse(source).body:
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
        if any(isinstance(t, ast.Name) and t.id == name for t in targets):
            value = node.value
            return value.id if isinstance(value, ast.Name) else None
    return None


def test_a_redeclared_status_literal_is_reported() -> None:
    """The planted case: a separate literal with the protocol's own values."""
    assert _alias_target('FrStatus = Literal["running", "done"]\n', "FrStatus") is None
    assert _alias_target("FrStatus = SessionStatus\n", "FrStatus") == "SessionStatus"
