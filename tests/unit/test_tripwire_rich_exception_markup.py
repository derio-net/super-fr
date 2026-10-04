"""Tripwire (gh#525): an exception is data, never Rich markup.

Rich reads `[...]` in a printed string as a style tag: a bracketed word in the
data is silently DROPPED, and a `[/red]`-shaped one raises `MarkupError` — so a
command dies with a traceback instead of reporting the error it caught.
`fr plan self-review` did exactly that on the plan parse error it exists to
report. Exception text is the likeliest carrier, because a parse error quotes
the malformed fragment back.

The guard is deliberately narrow (the issue's own warning: a plain grep for
`console.print(f"` over-fires on values that cannot hold brackets). It flags
one shape: inside `except ... as <name>:`, a `*console.print(f"...")` call that
interpolates `<name>` (bare, `str(<name>)`, or with a conversion) while markup
is on. The fix is `escape(str(<name>))` — authored `[red]...[/red]` styling in
the format string stays — or `markup=False` on the call.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = sorted((ROOT / "packages").glob("*/src/**/*.py"))


def _console_print(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "print"
        and isinstance(node.func.value, ast.Name)
        and "console" in node.func.value.id
    )


def _markup_off(call: ast.Call) -> bool:
    return any(
        kw.arg == "markup" and isinstance(kw.value, ast.Constant) and kw.value.value is False
        for kw in call.keywords
    )


def _names_exception(value: ast.expr, bound: str) -> bool:
    if isinstance(value, ast.Name):
        return value.id == bound
    # `str(e)` is the same unescaped text.
    return (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == "str"
        and len(value.args) == 1
        and isinstance(value.args[0], ast.Name)
        and value.args[0].id == bound
    )


def _violations(path: Path, root: Path = ROOT) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    found: list[str] = []
    for handler in ast.walk(tree):
        if not isinstance(handler, ast.ExceptHandler) or handler.name is None:
            continue
        for node in ast.walk(handler):
            if not _console_print(node) or _markup_off(node):  # type: ignore[arg-type]
                continue
            for arg in node.args:  # type: ignore[attr-defined]
                if not isinstance(arg, ast.JoinedStr):
                    continue
                if any(
                    isinstance(part, ast.FormattedValue)
                    and _names_exception(part.value, handler.name)
                    for part in arg.values
                ):
                    found.append(f"{path.relative_to(root)}:{node.lineno}")
    return found


def test_the_scanner_catches_the_shape_and_spares_the_fixes(tmp_path: Path) -> None:
    sample = tmp_path / "sample.py"
    sample.write_text(
        "try:\n    pass\nexcept ValueError as e:\n"
        '    err_console.print(f"[red]bad:[/red] {e}")\n'  # flagged
        '    err_console.print(f"[red]bad:[/red] {str(e)}")\n'  # flagged
        '    err_console.print(f"[red]bad:[/red] {escape(str(e))}")\n'
        '    err_console.print(f"bad: {e}", markup=False)\n'
        '    typer.echo(f"bad: {e}")\n'
    )
    assert _violations(sample, tmp_path) == ["sample.py:4", "sample.py:5"]


def test_no_exception_is_interpolated_into_rich_markup() -> None:
    found = [v for path in SOURCES for v in _violations(path)]
    assert not found, (
        "exception text printed as Rich markup — wrap it in "
        "`rich.markup.escape(str(e))` (keep the authored [red] styling) or pass "
        "`markup=False`:\n  " + "\n  ".join(found)
    )
