"""The derived delivery verifiers print what they printed before the move (spec 2026-11-27-run-verdict R7, R9).

Each refusal path of `proportionality_witness`, `docs_witness` and `witness_base` is driven
with the same faked inputs that drove the pre-move `run_cmd` functions, settled through
`run_cmd`'s adapter onto a recording console (colour on, so a lost `style` shows), and
compared byte for byte, with its exit code, against the capture in
`tests/fixtures/run_verdict/derived/`. The capture was taken once from the code before the
move; it is never regenerated from the code under test.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer
from rich.console import Console

from fr.commands import run_cmd

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/run_verdict/derived"
KEY = "deliver"
ROOT = Path("/repo")


def recording_console() -> Console:
    return Console(
        file=StringIO(), width=80, force_terminal=True, color_system="standard", highlight=False
    )


def _state(*, plan: str | None = "docs/superpowers/plans/p", base_branch: str | None = None) -> Any:
    steps = {"plan": SimpleNamespace(emitted={"plan": plan})} if plan else {}
    return SimpleNamespace(steps=steps, base_branch=base_branch)


@dataclass(frozen=True)
class _Git:
    """`git_answer`, faked: HEAD's branch and which local branches exist."""

    head: str
    branches: tuple[str, ...]

    def __call__(self, _root: Path, *args: str) -> Any:
        if args[:2] == ("rev-parse", "--abbrev-ref"):
            return SimpleNamespace(stdout=f"{self.head}\n", returncode=0)
        if args[:3] == ("rev-parse", "--verify", "--quiet"):
            ok = args[3].removeprefix("refs/heads/") in self.branches
            return SimpleNamespace(stdout="", returncode=0 if ok else 1)
        raise AssertionError(args)


def _no_remote(mp: pytest.MonkeyPatch, git: _Git) -> None:
    import fr.git
    import fr.isolation.types

    def no_state(_root: Path, _branch: str) -> None:
        raise ValueError("no isolation state")

    mp.setattr(fr.git, "remote_default_ref", lambda _root: None)
    mp.setattr(fr.git, "git_answer", git)
    mp.setattr(fr.isolation.types, "load_state", no_state)


def _target(mp: pytest.MonkeyPatch, *, error: str | None = None) -> None:
    import fr.run.target

    def target_ref(_root: Path, branch: str | None) -> str | None:
        if error is not None:
            raise fr.run.target.TargetError(error)
        return f"origin/{branch}"

    mp.setattr(fr.run.target, "target_ref", target_ref)


def _plan_parses(mp: pytest.MonkeyPatch, *, error: str | None = None) -> None:
    import fr.parser

    def parse(_path: Path) -> object:
        if error is not None:
            raise fr.parser.PlanSchemaError(error)
        return object()

    mp.setattr(fr.parser, "parse", parse)


def _no_merge_base(mp: pytest.MonkeyPatch) -> None:
    import fr.proportionality

    text = "no merge-base with [origin/main]: pass --base <ref>\n"
    mp.setattr(
        fr.proportionality,
        "run_report",
        lambda _root, _plan, _base: SimpleNamespace(merge_base=None, text=text),
    )


def _docs(mp: pytest.MonkeyPatch, *, env_error: str | None = None, findings: int = 0) -> None:
    import fr.docs.gate
    import fr.docs.load
    import fr.docs.render

    def load_config(_root: Path) -> object:
        if env_error is not None:
            raise fr.docs.load.DocsEnvError(env_error)
        return object()

    found = [object()] * findings
    mp.setattr(fr.docs.load, "load_config", load_config)
    mp.setattr(fr.docs.load, "merge_base_of", lambda _root, _base: "abc123")
    mp.setattr(
        fr.docs.gate,
        "evaluate",
        lambda _root, _config, _base: SimpleNamespace(findings=found, pages=[]),
    )
    mp.setattr(
        fr.docs.render,
        "findings_text",
        lambda _f: "docs/a.md: [covers] changed, page did not\n  covers: packages/**\n",
    )


@dataclass(frozen=True)
class Case:
    """One refusal path: how to fake its inputs, and the call before and after the move."""

    name: str
    setup: Callable[[pytest.MonkeyPatch], None]
    old: Callable[[], object]
    new: Callable[[], object]


def _new_proportionality(state: Any) -> Callable[[], object]:
    def call() -> object:
        from fr.run.evidence import derived

        return run_cmd._settle(derived.proportionality_witness(KEY, ROOT, state))

    return call


def _new_docs(state: Any, *, announce: bool) -> Callable[[], object]:
    def call() -> object:
        from fr.run.evidence import derived

        return run_cmd._settle(derived.docs_witness(KEY, ROOT, announce=announce, state=state))

    return call


def _new_base(state: Any, name: str, *, announce: bool) -> Callable[[], object]:
    def call() -> object:
        from fr.run.evidence import derived

        with run_cmd._refusals():
            return derived.witness_base(
                KEY, ROOT, name, announce=announce, warn=run_cmd._say, state=state
            )

    return call


def _old(name: str, *args: Any, **kwargs: Any) -> Callable[[], object]:
    return lambda: getattr(run_cmd, name)(*args, **kwargs)


_FALLBACK = _Git(head="feat/x", branches=("main",))
_NOTHING = _Git(head="feat/x", branches=())


def _cases() -> list[Case]:
    no_plan = _state(plan=None)
    targeted = _state(base_branch="main")
    untargeted = _state()
    return [
        Case(
            "proportionality_witness-no-plan",
            lambda mp: None,
            _old("_proportionality_witness", KEY, ROOT, no_plan),
            _new_proportionality(no_plan),
        ),
        Case(
            "proportionality_witness-plan-does-not-parse",
            lambda mp: _plan_parses(mp, error="phase [1] has no tasks"),
            _old("_proportionality_witness", KEY, ROOT, targeted),
            _new_proportionality(targeted),
        ),
        Case(
            "proportionality_witness-no-merge-base",
            lambda mp: (_plan_parses(mp), _target(mp), _no_merge_base(mp)) and None,
            _old("_proportionality_witness", KEY, ROOT, targeted),
            _new_proportionality(targeted),
        ),
        Case(
            "proportionality_witness-fallback-then-no-merge-base",
            lambda mp: (_plan_parses(mp), _no_remote(mp, _FALLBACK), _no_merge_base(mp)) and None,
            _old("_proportionality_witness", KEY, ROOT, untargeted),
            _new_proportionality(untargeted),
        ),
        Case(
            "proportionality_witness-no-base",
            lambda mp: (_plan_parses(mp), _no_remote(mp, _NOTHING)) and None,
            _old("_proportionality_witness", KEY, ROOT, untargeted),
            _new_proportionality(untargeted),
        ),
        Case(
            "docs_witness-env-error",
            lambda mp: _docs(mp, env_error="cannot read .fr/docs.yaml: [bad] key"),
            _old("_docs_witness", KEY, ROOT, announce=True, state=targeted),
            _new_docs(targeted, announce=True),
        ),
        Case(
            "docs_witness-findings",
            lambda mp: (_docs(mp, findings=2), _target(mp)) and None,
            _old("_docs_witness", KEY, ROOT, announce=True, state=targeted),
            _new_docs(targeted, announce=True),
        ),
        Case(
            "docs_witness-fallback-then-findings",
            lambda mp: (_docs(mp, findings=1), _no_remote(mp, _FALLBACK)) and None,
            _old("_docs_witness", KEY, ROOT, announce=True, state=untargeted),
            _new_docs(untargeted, announce=True),
        ),
        Case(
            "docs_witness-target-error",
            lambda mp: (_docs(mp), _target(mp, error="base branch [main] does not resolve"))
            and None,
            _old("_docs_witness", KEY, ROOT, announce=False, state=targeted),
            _new_docs(targeted, announce=False),
        ),
        Case(
            "witness_base-target-error",
            lambda mp: _target(mp, error="base branch [main] does not resolve"),
            _old("_witness_base", KEY, ROOT, "docs", announce=True, state=targeted),
            _new_base(targeted, "docs", announce=True),
        ),
        Case(
            "witness_base-no-base",
            lambda mp: _no_remote(mp, _NOTHING),
            _old("_witness_base", KEY, ROOT, "proportionality", announce=True, state=untargeted),
            _new_base(untargeted, "proportionality", announce=True),
        ),
        Case(
            "witness_base-fallback-announced",
            lambda mp: _no_remote(mp, _FALLBACK),
            _old("_witness_base", KEY, ROOT, "proportionality", announce=True, state=untargeted),
            _new_base(untargeted, "proportionality", announce=True),
        ),
    ]


CASES = _cases()


def run_case(mp: pytest.MonkeyPatch, case: Case, call: Callable[[], object]) -> tuple[str, int]:
    """`(stderr, exit code)` of one call, on a fresh recording console."""
    console = recording_console()
    mp.setattr(run_cmd, "err_console", console)
    case.setup(mp)
    try:
        call()
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
def test_the_moved_verifier_prints_the_captured_bytes(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    stderr, code = run_case(monkeypatch, case, case.new)
    assert stderr == (FIXTURES / f"{case.name}.txt").read_text(encoding="utf-8")
    assert code == _exit_codes()[case.name]
