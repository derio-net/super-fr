"""Gate provenance refuses, warns and returns as it did before the move (spec
2026-11-27-run-verdict R8, R9).

Each refusal and warning path of the provenance cluster (the degradation notice, the gate
flags, the question-round table, the queued gate decision, `gate_provenance` and the missing
emits) is driven with faked inputs through `fr.run.provenance` and `run_cmd`'s adapters
(`_refusals` for a raising function, `_say` as the `warn`) onto a recording console (colour on,
so a lost `style` shows). Its stderr, exit code, returned value, queued gate decisions and
noted unobserved gates are compared byte for byte against the capture in
`tests/fixtures/run_verdict/provenance/`. The capture was taken once from `run_cmd`'s own
functions before the move; it is never regenerated from the code under test.
"""

from __future__ import annotations

import dataclasses
import importlib
import json
import os
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer
from fr.commands import run_cmd
from fr.record.model import QuestionRounds
from fr.run.telemetry import Round
from fr.workflow.model import Step
from rich.console import Console

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/run_verdict/provenance"
AT = "2026-01-01T00:00:00+00:00"
SPEC = "docs/superpowers/specs/s.md"


def recording_console() -> Console:
    return Console(
        file=StringIO(), width=80, force_terminal=True, color_system="standard", highlight=False
    )


def _patch(mp: pytest.MonkeyPatch, dotted: str, value: object) -> None:
    module, _, attr = dotted.rpartition(".")
    mp.setattr(importlib.import_module(module), attr, value)


class Root:
    """The test's repository root, substituted at call time."""


ROOT = Root()


@dataclass(frozen=True)
class Case:
    """One path: how to fake its inputs, which function, and how to call it.

    `raises` says the function refuses by raising `RunRefusal`; `warn` says it takes the
    command's warning printer.
    """

    name: str
    fn: str
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)
    setup: Callable[[pytest.MonkeyPatch, Path], None] | None = None
    raises: bool = False
    warn: bool = False


def _env(mp: pytest.MonkeyPatch, harness: str | None = None) -> None:
    """No harness (or the named one), and nothing of this session in the way."""
    for name in list(os.environ):
        if name.startswith(("CLAUDE", "OPENCODE", "HERMES", "FR_HARNESS")):
            mp.delenv(name, raising=False)
    if harness is not None:
        mp.setenv("FR_HARNESS", harness)


def _rounds(value: list[Round] | None) -> Callable[[pytest.MonkeyPatch, Path], None]:
    def setup(mp: pytest.MonkeyPatch, _tmp: Path) -> None:
        _env(mp)
        _patch(mp, "fr.run.telemetry.answered_rounds_since", lambda _env, _since: value)

    return setup


def _answered(
    value: bool | None, harness: str | None
) -> Callable[[pytest.MonkeyPatch, Path], None]:
    def setup(mp: pytest.MonkeyPatch, _tmp: Path) -> None:
        _env(mp, harness)
        _patch(mp, "fr.run.telemetry.operator_answered_since", lambda _env, _since: value)

    return setup


def _journalled(mp: pytest.MonkeyPatch, tmp: Path) -> None:
    """A spec journal that already holds `gate-no-questions-brainstorm`, body `"first"`."""
    from fr.journal.model import JournalEntry, append_journal_entry, journal_path, spec_journal_slug

    _env(mp)
    slug = spec_journal_slug("s")
    target = journal_path(tmp, "spec", slug)
    target.parent.mkdir(parents=True, exist_ok=True)
    entry = JournalEntry(
        kind="decision",
        scope="spec",
        id="gate-no-questions-brainstorm",
        created=AT,
        title="t",
        body="first",
    )
    append_journal_entry(target, slug, entry)


def _hermes(rounds: list[Round] | None) -> Callable[[pytest.MonkeyPatch, Path], None]:
    def setup(mp: pytest.MonkeyPatch, _tmp: Path) -> None:
        _env(mp, "hermes")
        _patch(mp, "fr.run.telemetry.answered_rounds_since", lambda _env, _since: rounds)

    return setup


RECORD = SimpleNamespace(at=AT)
NO_SPEC = SimpleNamespace(driver="fr-goal", steps={})
STANDALONE = SimpleNamespace(driver="standalone", steps={})
EARLIER_SPEC = SimpleNamespace(
    driver="fr-goal", steps={"brainstorm": SimpleNamespace(emitted={"spec": SPEC})}
)
ONE = [Round(question_texts=("What shall it do?",))]
TWO_ANNOUNCED = [
    Round(question_texts=("What shall it do? a 2nd round may follow",)),
    Round(question_texts=("And how?",)),
]
TWO_PLAIN = [Round(question_texts=("a",)), Round(question_texts=("b",))]
THREE = [Round(question_texts=(t,)) for t in "abc"]
ROUND_TWO = QuestionRounds(rounds=2, trigger="design-risk", reason="the shape was unclear")
ROUND_ONE = QuestionRounds(rounds=1)


def _provenance(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "claimed": None,
        "no_questions": False,
        "reason": None,
        "questions": None,
        "emitted": {"spec": SPEC},
        "state": NO_SPEC,
    }
    base.update(kw)
    return base


def _gp(name: str, setup: Any, **kw: Any) -> Case:
    return Case(
        name, "gate_provenance", (ROOT, "brainstorm", RECORD), _provenance(**kw), setup,
        raises=True, warn=True,
    )  # fmt: skip


def _cases() -> list[Case]:
    return [
        Case(
            "gate_degradation_notice-undetected",
            "gate_degradation_notice",
            setup=_answered(None, None),
        ),
        Case(
            "gate_degradation_notice-observed",
            "gate_degradation_notice",
            setup=_answered(True, "claude-code"),
        ),
        Case(
            "gate_degradation_notice-unreadable",
            "gate_degradation_notice",
            setup=_answered(None, "claude-code"),
        ),
        Case(
            "gate_degradation_notice-opencode",
            "gate_degradation_notice",
            setup=_answered(None, "opencode"),
        ),
        Case(
            "gate_degradation_notice-hermes",
            "gate_degradation_notice",
            setup=_answered(None, "hermes"),
        ),
        Case(
            "gate_degradation_notice-bad-harness",
            "gate_degradation_notice",
            setup=_answered(None, "bogus"),
        ),
        Case("refuse_gate_flags", "refuse_gate_flags", ("brainstorm",), raises=True),
        Case(
            "clears_gate-yes",
            "clears_gate",
            (Step(id="b", kind="agent", gate="operator"), SimpleNamespace(state="blocked"), "done"),
        ),
        Case(
            "clears_gate-declined",
            "clears_gate",
            (
                Step(id="b", kind="agent", gate="operator"),
                SimpleNamespace(state="blocked"),
                "failed",
            ),
        ),
        Case("question_rounds_refusal-agree", "question_rounds_refusal", (ONE, None)),
        Case("question_rounds_refusal-three", "question_rounds_refusal", (THREE, None)),
        Case(
            "question_rounds_refusal-undeclared-two", "question_rounds_refusal", (TWO_PLAIN, None)
        ),
        Case(
            "question_rounds_refusal-declared-two-saw-one",
            "question_rounds_refusal",
            (ONE, ROUND_TWO),
        ),
        Case(
            "question_rounds_refusal-unannounced", "question_rounds_refusal", (TWO_PLAIN, ROUND_TWO)
        ),
        Case(
            "question_rounds_refusal-announced",
            "question_rounds_refusal",
            (TWO_ANNOUNCED, ROUND_TWO),
        ),
        Case(
            "queue_gate_decision-queued",
            "queue_gate_decision",
            (ROOT, SPEC, "gate-no-questions-brainstorm"),
            {"title": "t", "body": "first"},
            setup=lambda mp, _t: _env(mp),
        ),
        Case(
            "queue_gate_decision-same-body",
            "queue_gate_decision",
            (ROOT, SPEC, "gate-no-questions-brainstorm"),
            {"title": "t", "body": "first"},
            setup=_journalled,
        ),
        Case(
            "queue_gate_decision-different-body",
            "queue_gate_decision",
            (ROOT, SPEC, "gate-no-questions-brainstorm"),
            {"title": "t", "body": "second"},
            setup=_journalled,
            raises=True,
        ),
        Case(
            "record_round_two-queued",
            "record_round_two",
            (ROOT, "brainstorm", ROUND_TWO, SPEC),
            setup=lambda mp, _t: _env(mp),
        ),
        Case(
            "record_round_two-default",
            "record_round_two",
            (ROOT, "brainstorm", ROUND_ONE, SPEC),
            setup=lambda mp, _t: _env(mp),
        ),
        Case("observed_gate_rounds-read", "observed_gate_rounds", (RECORD,), setup=_rounds(ONE)),
        Case(
            "observed_gate_rounds-unreadable",
            "observed_gate_rounds",
            (RECORD,),
            setup=_rounds(None),
        ),
        Case(
            "observed_gate_rounds-no-time",
            "observed_gate_rounds",
            (SimpleNamespace(at=None),),
            setup=_rounds(ONE),
        ),
        Case(
            "derive_gate_answer-no-questions",
            "derive_gate_answer",
            (RECORD,),
            {"no_questions": True, "claimed": None},
            _rounds(ONE),
        ),
        Case(
            "derive_gate_answer-observed",
            "derive_gate_answer",
            (RECORD,),
            {"no_questions": False, "claimed": None},
            _rounds(ONE),
        ),
        Case(
            "derive_gate_answer-observed-none",
            "derive_gate_answer",
            (RECORD,),
            {"no_questions": False, "claimed": "agent"},
            _rounds([]),
        ),
        Case(
            "derive_gate_answer-claimed",
            "derive_gate_answer",
            (RECORD,),
            {"no_questions": False, "claimed": "agent"},
            _rounds(None),
        ),
        Case(
            "derive_gate_answer-unclaimed",
            "derive_gate_answer",
            (RECORD,),
            {"no_questions": False, "claimed": None},
            _rounds(None),
        ),
        _gp("gate_provenance-no-questions-no-reason", _rounds(None), no_questions=True),
        _gp(
            "gate_provenance-no-questions-blank-reason",
            _rounds(None),
            no_questions=True,
            reason="  ",
        ),
        _gp(
            "gate_provenance-no-questions-no-spec",
            _rounds(None),
            no_questions=True,
            reason="r",
            emitted={},
        ),
        _gp("gate_provenance-round-two-no-spec", _rounds(ONE), questions=ROUND_TWO, emitted={}),
        _gp("gate_provenance-observed", _rounds(ONE)),
        _gp(
            "gate_provenance-observed-earlier-spec",
            _rounds(TWO_ANNOUNCED),
            questions=ROUND_TWO,
            emitted={},
            state=EARLIER_SPEC,
        ),
        _gp("gate_provenance-observed-standalone", _rounds(TWO_PLAIN), state=STANDALONE),
        _gp("gate_provenance-observed-three-rounds", _rounds(THREE)),
        _gp("gate_provenance-observed-mismatch", _rounds(TWO_PLAIN), questions=ROUND_TWO),
        _gp("gate_provenance-none-answered", _rounds([])),
        _gp(
            "gate_provenance-no-questions",
            _rounds([]),
            no_questions=True,
            reason="the operator had decided",
        ),
        _gp("gate_provenance-unobserved-no-claim", _rounds(None)),
        _gp("gate_provenance-unobserved-claimed", _rounds(None), claimed="operator"),
        _gp("gate_provenance-unobserved-claimed-hermes", _hermes(None), claimed="agent"),
        _gp(
            "gate_provenance-unobserved-round-two",
            _rounds(None),
            claimed="operator",
            questions=ROUND_TWO,
        ),
        _gp(
            "gate_provenance-unobserved-round-one",
            _rounds(None),
            claimed="operator",
            questions=ROUND_ONE,
        ),
        Case(
            "refuse_missing_emits-one",
            "refuse_missing_emits",
            ("brainstorm", ("spec",), {}, None),
            raises=True,
        ),
        Case(
            "refuse_missing_emits-two",
            "refuse_missing_emits",
            ("plan", ("spec", "plan", "journal:plan"), {"spec": "s"}, {}),
            raises=True,
        ),
        Case(
            "refuse_missing_emits-recorded",
            "refuse_missing_emits",
            ("plan", ("spec", "plan"), {"spec": "s"}, {"plan": "p"}),
        ),
    ]


CASES = _cases()


def _resolve(name: str) -> Callable[..., Any]:
    """The function under test."""
    return getattr(importlib.import_module("fr.run.provenance"), name)


def _queue_var() -> ContextVar[Any]:
    """The queue of gate decisions."""
    var: ContextVar[Any] = importlib.import_module("fr.run.provenance").GATE_DECISIONS
    return var


def _jsonable(value: object) -> object:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    return value


def _sub(value: Any, tmp: Path) -> Any:
    return tmp if value is ROOT else value


def run_case(
    mp: pytest.MonkeyPatch, case: Case, tmp: Path, call: Callable[[Any], object]
) -> tuple[str, int, str]:
    """`(stderr, exit code, result as JSON)` of one call, on a fresh recording console."""
    from fr.run.unobserved import take_unobserved

    console = recording_console()
    mp.setattr(run_cmd, "err_console", console)
    take_unobserved()
    _queue_var().set(None)
    if case.setup is not None:
        case.setup(mp, tmp)
    result: object = None
    try:
        result = call(None)
        code = 0
    except typer.Exit as e:
        code = e.exit_code
    except Exception as e:  # noqa: BLE001 — a raised error is part of what is captured
        result = f"raised {type(e).__name__}: {e}"
        code = 0
    queued = [
        [slug, entry.id, entry.title, entry.body, target.name]
        for target, slug, entry in (_queue_var().get() or [])
    ]
    _queue_var().set(None)
    file = console.file
    assert isinstance(file, StringIO)
    shown = json.dumps(
        {"returned": _jsonable(result), "queued": queued, "unobserved": take_unobserved()},
        indent=2,
        sort_keys=True,
        default=str,
    )
    return file.getvalue(), code, shown + "\n"


def _exit_codes() -> dict[str, int]:
    loaded: dict[str, int] = json.loads((FIXTURES / "exit-codes.json").read_text(encoding="utf-8"))
    return loaded


def test_every_case_has_a_capture() -> None:
    assert sorted(_exit_codes()) == sorted(c.name for c in CASES)


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_the_moved_gate_provenance_prints_and_returns_the_captured_bytes(
    case: Case, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def call(_: object) -> object:
        fn = _resolve(case.fn)
        kwargs = {k: _sub(v, tmp_path) for k, v in case.kwargs.items()}
        if case.warn:
            kwargs["warn"] = run_cmd._say
        args = [_sub(a, tmp_path) for a in case.args]
        if case.raises:
            with run_cmd._refusals():
                return fn(*args, **kwargs)
        return fn(*args, **kwargs)

    stderr, code, shown = run_case(monkeypatch, case, tmp_path, call)
    assert stderr == (FIXTURES / f"{case.name}.txt").read_text(encoding="utf-8")
    assert code == _exit_codes()[case.name]
    assert shown == (FIXTURES / f"{case.name}.json").read_text(encoding="utf-8")
