"""Tripwire: the looping driver has one error boundary (spec 2026-11-19-batch-train-truth R7).

A `_fail(...)` or a `raise typer.Exit` inside the driver's pass, the loop or its waits ends
the process directly, past the boundary that decides refusal from transient. Earlier fixes
(gh#910, gh#921, gh#998) each moved one such site inside the boundary and the shape stayed;
this test keeps it gone. The loop's deliberate ends leave `_host_loop` as a `LoopEnd`.
"""

from __future__ import annotations

import ast
from pathlib import Path

SOURCE = (
    Path(__file__).resolve().parents[2]
    / "packages"
    / "fr"
    / "src"
    / "fr"
    / "commands"
    / "triage_batch_cmd.py"
)
GUARDED_FUNCTIONS = frozenset(
    {
        "one_pass",
        "_host_loop",
        "wait_out",
        # the loop proper and what its iteration and handler call (p1a-r6)
        "_loop",
        "_wait",
        "_error",
        "_ledger",
        "_ledger_failure",
        "_driver_pass",
        "_stop",
        "_report_read_failure",
        "backoff",
        "pass_exit",
        "_stalled_line",
        "_say",
    }
)
GUARDED_CLASSES = frozenset({"_Driver"})


def _is_exit(node: ast.expr | None) -> bool:
    target = node.func if isinstance(node, ast.Call) else node
    return (
        isinstance(target, ast.Attribute)
        and target.attr == "Exit"
        and isinstance(target.value, ast.Name)
        and target.value.id == "typer"
    )


def _offences(tree: ast.Module) -> list[str]:
    out: list[str] = []
    for top in tree.body:
        name = getattr(top, "name", None)
        if not (
            (isinstance(top, ast.ClassDef) and name in GUARDED_CLASSES)
            or (isinstance(top, ast.FunctionDef) and name in GUARDED_FUNCTIONS)
        ):
            continue
        for node in ast.walk(top):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "_fail"
            ):
                out.append(f"{name}:{node.lineno}: _fail(...)")
            elif isinstance(node, ast.Raise) and _is_exit(node.exc):
                out.append(f"{name}:{node.lineno}: raise typer.Exit")
    return out


def test_no_direct_exit_inside_the_driver_the_loop_or_its_waits() -> None:
    offences = _offences(ast.parse(SOURCE.read_text(encoding="utf-8")))
    assert offences == [], (
        "these end the looping driver past its one boundary; raise DriverRefusal or "
        "TransientPassFailure (fr.triage.drive_errors), or let the error propagate, and "
        "return a LoopEnd from _host_loop:\n" + "\n".join(offences)
    )


def test_the_tripwire_sees_both_shapes() -> None:
    sample = ast.parse(
        "class _Driver:\n"
        "    def a(self):\n"
        "        _fail('x')\n"
        "def wait_out():\n"
        "    raise typer.Exit(code=2)\n"
        "def elsewhere():\n"
        "    _fail('fine here')\n"
    )
    assert _offences(sample) == ["_Driver:3: _fail(...)", "wait_out:5: raise typer.Exit"]


def test_every_guarded_name_is_still_defined() -> None:
    """A rename moves a body out from under the guard silently (p1a-r6): every guarded name
    must be a top-level function or class of the module."""
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    defined = {getattr(top, "name", None) for top in tree.body}
    assert sorted((GUARDED_FUNCTIONS | GUARDED_CLASSES) - defined) == []
