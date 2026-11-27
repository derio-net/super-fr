"""The lookup cluster refuses and warns as it did before the move (spec 2026-11-27-run-verdict R9).

Each refusal path of `unit_key`, and the drift warning of `resolve_manifest_for_read`, is
driven with faked inputs and printed through `run_cmd`'s adapters (`_refusals`, `_say`) onto a
recording console (colour on, so a lost `style` shows), then compared byte for byte, with its
exit code, against the capture in `tests/fixtures/run_verdict/steps/`. The capture was taken
once from `run_cmd`'s own functions before the move; it is never regenerated from the code
under test.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
import typer
from fr.commands import run_cmd
from rich.console import Console

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/run_verdict/steps"
ROOT = Path("/repo")


def recording_console() -> Console:
    return Console(
        file=StringIO(), width=80, force_terminal=True, color_system="standard", highlight=False
    )


def _member(name: str) -> Any:
    return SimpleNamespace(id=name, steps=[])


MEMBER = _member("implement-phase")
GROUP = SimpleNamespace(id="implement", steps=[MEMBER])
FLAT = _member("plan")
PLANNED: Any = SimpleNamespace(steps={"plan": SimpleNamespace(emitted={"plan": "p"})})
UNPLANNED: Any = SimpleNamespace(steps={})


def _plan_tags(mp: pytest.MonkeyPatch, _module: ModuleType, tags: dict[int, str]) -> None:
    import fr.run.adopt

    mp.setattr(
        fr.run.adopt,
        "parse",
        lambda _path: SimpleNamespace(
            phases=[
                SimpleNamespace(phase=SimpleNamespace(number=n, tag=t)) for n, t in tags.items()
            ]
        ),
    )


def _plan_unparseable(mp: pytest.MonkeyPatch, _module: ModuleType) -> None:
    import fr.parser
    import fr.run.adopt

    def parse(_path: Path) -> object:
        raise fr.parser.PlanSchemaError("phase [1] has no tasks")

    mp.setattr(fr.run.adopt, "parse", parse)


def _drift(mp: pytest.MonkeyPatch, module: ModuleType, *, members: list[str] | None = None) -> None:
    """The shape declares steps a, b (a with member m1); the cursor recorded other ones."""
    declared = SimpleNamespace(
        workflow="tiny",
        schema_version=1,
        steps=[
            SimpleNamespace(id="a", steps=[_member("m1")] if members is not None else []),
            _member("b"),
        ],
    )
    mp.setattr(module, "resolve_workflow", lambda _name, _root: declared)


def _drifted_state(*, same_ids: bool) -> Any:
    steps = {"a": SimpleNamespace(members=["m0"]), "b": SimpleNamespace(members=None)}
    if not same_ids:
        steps = {"a": SimpleNamespace(members=None), "z": SimpleNamespace(members=None)}
    return SimpleNamespace(run="r1", workflow="tiny@1", steps=steps)


@dataclass(frozen=True)
class Case:
    """One path: how to fake its inputs, which function, and its arguments."""

    name: str
    setup: Callable[[pytest.MonkeyPatch, ModuleType], None]
    fn: str
    args: tuple[Any, ...]


def _unit_key_case(name: str, setup: Any, *args: Any) -> Case:
    return Case(f"unit_key-{name}", setup, "unit_key", args)


def _cases() -> list[Case]:
    def agentic_and_manual(mp: pytest.MonkeyPatch, module: ModuleType) -> None:
        _plan_tags(mp, module, {1: "agentic", 2: "manual"})

    def nothing(mp: pytest.MonkeyPatch, module: ModuleType) -> None:
        return None

    return [
        _unit_key_case("member-no-item", nothing, ROOT, PLANNED, MEMBER, GROUP, None),
        _unit_key_case("no-plan-recorded", nothing, ROOT, UNPLANNED, MEMBER, GROUP, "phase/1"),
        _unit_key_case(
            "plan-does-not-parse", _plan_unparseable, ROOT, PLANNED, MEMBER, GROUP, "phase/1"
        ),
        _unit_key_case("manual-phase", agentic_and_manual, ROOT, PLANNED, MEMBER, GROUP, "phase/2"),
        _unit_key_case(
            "not-a-phase-member", agentic_and_manual, ROOT, PLANNED, MEMBER, GROUP, "phase/9"
        ),
        _unit_key_case("group-given-item", nothing, ROOT, PLANNED, GROUP, None, "phase/1"),
        _unit_key_case("non-member-given-item", nothing, ROOT, PLANNED, FLAT, None, "phase/1"),
        Case(
            "resolve_manifest_for_read-step-list-drift",
            lambda mp, m: _drift(mp, m),
            "resolve_manifest_for_read",
            (ROOT, _drifted_state(same_ids=False)),
        ),
        Case(
            "resolve_manifest_for_read-members-drift",
            lambda mp, m: _drift(mp, m, members=["m1"]),
            "resolve_manifest_for_read",
            (ROOT, _drifted_state(same_ids=True)),
        ),
    ]


CASES = _cases()


def run_case(
    mp: pytest.MonkeyPatch,
    case: Case,
    call: Callable[[Callable[..., Any]], object],
    module: ModuleType,
) -> tuple[str, int]:
    """`(stderr, exit code)` of one call, on a fresh recording console."""
    console = recording_console()
    mp.setattr(run_cmd, "err_console", console)
    case.setup(mp, module)
    try:
        call(getattr(module, case.fn))
        code = 0
    except typer.Exit as e:
        code = e.exit_code
    file = console.file
    assert isinstance(file, StringIO)
    return file.getvalue(), code


def _exit_codes() -> dict[str, int]:
    loaded: dict[str, int] = json.loads((FIXTURES / "exit-codes.json").read_text(encoding="utf-8"))
    return loaded


def test_every_case_has_a_capture() -> None:
    assert sorted(_exit_codes()) == sorted(c.name for c in CASES)


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_the_moved_lookup_prints_the_captured_bytes(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fr.run.steps as steps

    def call(fn: Callable[..., Any]) -> object:
        with run_cmd._refusals():
            if case.fn == "resolve_manifest_for_read":
                return fn(*case.args, warn=run_cmd._say)
            return fn(*case.args)

    stderr, code = run_case(monkeypatch, case, call, steps)
    assert stderr == (FIXTURES / f"{case.name}.txt").read_text(encoding="utf-8")
    assert code == _exit_codes()[case.name]
