"""The briefs and dispatch records refuse, warn and build as they did before the move (spec
2026-11-27-run-verdict R9).

Each refusal path of the brief cluster, each warning printed on the way, and the brief dict one
flat step and one grouped member build, is driven with faked inputs and printed through
`run_cmd`'s adapters (`_refusals`, `_say`) onto a recording console (colour on, so a lost
`style` shows), then compared byte for byte, with its exit code and returned value, against the
capture in `tests/fixtures/run_verdict/brief/`. The capture was taken once from `run_cmd`'s own
functions before the move; it is never regenerated from the code under test.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer
from fr.commands import run_cmd
from fr.git import GitRefusal
from fr.run.model import Attempt, StepRecord
from fr.workflow.model import Step
from rich.console import Console

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/run_verdict/brief"
ROOT: Any = object()


def recording_console() -> Console:
    return Console(
        file=StringIO(), width=80, force_terminal=True, color_system="standard", highlight=False
    )


def _patch(mp: pytest.MonkeyPatch, dotted: str, value: object) -> None:
    module, _, attr = dotted.rpartition(".")
    import importlib

    mp.setattr(importlib.import_module(module), attr, value)


def _raising(exc: BaseException) -> Callable[..., Any]:
    def fn(*_a: object, **_k: object) -> Any:
        raise exc

    return fn


def _attempt(**kw: Any) -> Attempt:
    return Attempt(dispatched="2026-01-01T00:00:00Z", **kw)


def _held(attempt: Attempt, key: str = "phase/1/implement") -> StepRecord:
    from fr.run import units

    return units.with_attempt_appended(StepRecord(state="running"), key, attempt)


STATE: Any = SimpleNamespace(
    run="r1", workflow="fr-goal@1", branch="feat/x", issue=7, steps={}, cursor="plan"
)
STEP_STATE: Any = SimpleNamespace(run="r1", workflow="fr-goal@1", branch="feat/x", issue=None)
FLAT = Step(id="plan", kind="agent", skill="fr-plan", emits=("plan",), tier="standard")
TESTED = Step(id="deliver", kind="agent", evidence=("tests",))
GROUP = Step(
    id="implement",
    kind="agent",
    tier="from_phase",
    for_each="phase",
    steps=(Step(id="implement-phase", kind="agent", agent="super-fr:fr-phase-executor", emits=()),),
)
MEMBER = GROUP.steps[0]


@dataclass(frozen=True)
class Case:
    """One path: how to fake its inputs, which function, and how to call it.

    `repo_root` is the keyword the moved function takes in place of `resolve_repo_root()`;
    `warn` says it takes the command's warning printer; `ROOT` in `args` stands for the
    repository root the function already took as an argument.
    """

    name: str
    fn: str
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)
    setup: Callable[[pytest.MonkeyPatch, Path], None] | None = None
    repo_root: bool = False
    warn: bool = False


def _env(mp: pytest.MonkeyPatch, tmp: Path) -> None:
    """No harness, no models file: a brief the host cannot colour."""
    for name in list(__import__("os").environ):
        if name.startswith(("CLAUDE", "OPENCODE", "HERMES", "FR_HARNESS")):
            mp.delenv(name, raising=False)
    mp.setenv("HOME", str(tmp))
    mp.setenv("XDG_CONFIG_HOME", str(tmp / "cfg"))


def _brief_inputs(mp: pytest.MonkeyPatch, tmp: Path) -> None:
    _env(mp, tmp)
    mp.setenv("FR_HARNESS", "claude-code")
    settings = SimpleNamespace(
        settings=SimpleNamespace(
            git=SimpleNamespace(
                commit=SimpleNamespace(
                    with_issue="{type}({scope}): {summary} (#{issue})",
                    without_issue="{type}({scope}): {summary}",
                )
            )
        )
    )
    _patch(mp, "fr.settings.load_settings", lambda _root: settings)
    _patch(
        mp,
        "fr.record.template.record_brief",
        lambda *_a, **_k: SimpleNamespace(as_dict=lambda: {"path": "RECORD", "template": "t"}),
    )
    _patch(mp, "fr.run.ci_evidence.declared_tests_mode", lambda _root: "ci")
    _patch(mp, "fr.run.ci_evidence.declared_fast_tier", lambda _root: "pytest {base} -q")
    _patch(mp, "fr.git.remote_default_ref", lambda _root: "origin/main")


def _tests_refused(mp: pytest.MonkeyPatch, _tmp: Path) -> None:
    from fr.run.ci_evidence import CiEvidenceRefused

    _patch(
        mp,
        "fr.run.ci_evidence.declared_tests_mode",
        _raising(CiEvidenceRefused("tests: nope is not a mode")),
    )


def _no_base(reason: object) -> Callable[[pytest.MonkeyPatch, Path], None]:
    def setup(mp: pytest.MonkeyPatch, _tmp: Path) -> None:
        _patch(mp, "fr.run.ci_evidence.declared_tests_mode", lambda _root: "ci")
        _patch(mp, "fr.run.ci_evidence.declared_fast_tier", lambda _root: "run {base}")
        _patch(mp, "fr.git.remote_default_ref", lambda _root: reason)

    return setup


def _fast_tier_ok(mp: pytest.MonkeyPatch, _tmp: Path) -> None:
    _patch(mp, "fr.run.ci_evidence.declared_tests_mode", lambda _root: "ci")
    _patch(mp, "fr.run.ci_evidence.declared_fast_tier", lambda _root: "run  {base}   -q")
    _patch(mp, "fr.git.remote_default_ref", lambda _root: "origin/main")


def _lens_error(mp: pytest.MonkeyPatch, _tmp: Path) -> None:
    from fr.lenses.model import LensError

    _patch(
        mp,
        "fr.lenses.accumulate.lens_set",
        _raising(LensError("rule [x] needs lens y, which is not effective")),
    )


def _telemetry(mp: pytest.MonkeyPatch, _tmp: Path) -> None:
    _patch(mp, "fr.run.telemetry.subagent_model", lambda *_a, **_k: "claude-opus-5")
    _patch(mp, "fr.run.telemetry.dispatched_from_this_session", lambda *_a, **_k: False)


def _other_session(mp: pytest.MonkeyPatch, _tmp: Path) -> None:
    _patch(mp, "fr.run.telemetry.dispatched_from_this_session", lambda *_a, **_k: False)


def _preflight(messages: list[str]) -> Callable[[pytest.MonkeyPatch, Path], None]:
    def setup(mp: pytest.MonkeyPatch, _tmp: Path) -> None:
        _patch(mp, "fr.parser.parse", lambda _path: object())
        _patch(
            mp,
            "fr.plan_review._manual_placement_issues",
            lambda _plan: [SimpleNamespace(severity="error", message=m) for m in messages],
        )

    return setup


PLANNED: Any = SimpleNamespace(steps={"plan": SimpleNamespace(emitted={"plan": "p"})})
OPEN = _attempt(
    agent="a1", agent_type="super-fr:fr-phase-executor", harness="claude-code", session="s-9"
)
CLAIMED_STATE: Any = SimpleNamespace(steps={"implement": _held(OPEN)})


def _cases() -> list[Case]:
    return [
        Case(
            "render_template-unresolved",
            "render_template",
            ("echo {{ artifacts.spec }}", {"run.id": "r1"}),
            {"quote": True},
        ),
        Case(
            "template_context-emitted",
            "template_context",
            (
                SimpleNamespace(
                    run="r1", branch="b", steps={"s": SimpleNamespace(emitted={"a": "x"})}
                ),
            ),
        ),
        Case("tests_brief-ci-refused", "tests_brief", (ROOT, TESTED), setup=_tests_refused),
        Case(
            "tests_brief-no-base-refusal",
            "tests_brief",
            (ROOT, TESTED),
            setup=_no_base(GitRefusal("several remotes")),
        ),
        Case(
            "tests_brief-no-base-empty",
            "tests_brief",
            (ROOT, TESTED),
            setup=_no_base(""),
        ),
        Case("tests_brief-fast-tier", "tests_brief", (ROOT, TESTED), setup=_fast_tier_ok),
        Case(
            "lens_set_or_refuse-lens-error",
            "lens_set_or_refuse",
            ("lens-review", ROOT, STATE),
            setup=_lens_error,
        ),
        Case(
            "lens_review_brief-lens-error",
            "lens_review_brief",
            (Step(id="lens-review", kind="agent", evidence=("lenses",)), STATE),
            setup=_lens_error,
            repo_root=True,
        ),
        Case(
            "claimed_identity-other-agent",
            "claimed_identity",
            (OPEN, "phase/1/implement"),
            {"agent": "a2", "harness": None, "model": None},
            warn=True,
        ),
        Case(
            "merge_claim-differing-identity-warns",
            "merge_claim",
            (OPEN, "phase/1/implement"),
            {"agent": "a1", "harness": "opencode", "model": "m2", "agent_type": None},
            warn=True,
        ),
        Case(
            "close_on_resolve-other-agent",
            "close_on_resolve",
            (CLAIMED_STATE, "implement", "phase/1/implement", "done"),
            {"agent": "a2", "harness": None, "model": None},
            warn=True,
        ),
        Case(
            "observed_model-mismatch-warns",
            "observed_model",
            (_attempt(agent="a1", agent_type="t", bound="claude-sonnet-5-5"), "phase/1/implement"),
            setup=_telemetry,
            warn=True,
        ),
        Case(
            "manual_placement_preflight-refused",
            "manual_placement_preflight",
            (ROOT, PLANNED, "implement"),
            setup=_preflight(["phase 2 is manual and outstanding", "phase 3 follows it"]),
        ),
        Case(
            "manual_placement_preflight-clean",
            "manual_placement_preflight",
            (ROOT, PLANNED, "implement"),
            setup=_preflight([]),
        ),
        Case(
            "already_running_refusal-held",
            "already_running_refusal",
            ("implement", "phase/1/implement", None, "r1", "implement-phase", "phase/1", OPEN),
            setup=_other_session,
        ),
        Case(
            "already_running_refusal-running",
            "already_running_refusal",
            ("plan", "plan", "2026-01-01T00:00:00Z", "r1", "plan", None),
        ),
        Case(
            "nothing_running_refusal",
            "nothing_running_refusal",
            ("implement", " in implement-phase", "r1"),
        ),
        Case("resolve_hint-member", "resolve_hint", ("r1", "implement-phase", "phase/1")),
        Case("resolve_hint-flat", "resolve_hint", ("r1", "plan", None, "failed")),
        Case(
            "build_brief-flat",
            "build_brief",
            (FLAT, STATE),
            setup=_brief_inputs,
            repo_root=True,
        ),
        Case(
            "build_brief-flat-tests",
            "build_brief",
            (Step(id="deliver", kind="agent", evidence=("tests", "settle")), STEP_STATE),
            setup=_brief_inputs,
            repo_root=True,
        ),
        Case(
            "build_member_brief-grouped",
            "build_member_brief",
            (MEMBER, GROUP, "phase/1", STATE, "standard"),
            {"harness": "claude-code"},
            setup=_brief_inputs,
            repo_root=True,
        ),
    ]


CASES = _cases()


def _jsonable(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def run_case(
    mp: pytest.MonkeyPatch, case: Case, tmp: Path, call: Callable[[Callable[..., Any]], object]
) -> tuple[str, int, str]:
    """`(stderr, exit code, returned value as JSON)` of one call, on a fresh recording console."""
    console = recording_console()
    mp.setattr(run_cmd, "err_console", console)
    if case.setup is not None:
        case.setup(mp, tmp)
    result: object = None
    try:
        result = call(None)  # type: ignore[arg-type]
        code = 0
    except typer.Exit as e:
        code = e.exit_code
    except Exception as e:  # noqa: BLE001 — a raised error is part of what is captured
        result = f"raised {type(e).__name__}: {e}"
        code = 0
    file = console.file
    assert isinstance(file, StringIO)
    shown = json.dumps(_jsonable(result), indent=2, sort_keys=True, default=str)
    return file.getvalue(), code, shown + "\n"


def _exit_codes() -> dict[str, int]:
    loaded: dict[str, int] = json.loads((FIXTURES / "exit-codes.json").read_text(encoding="utf-8"))
    return loaded


def test_every_case_has_a_capture() -> None:
    assert sorted(_exit_codes()) == sorted(c.name for c in CASES)


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_the_moved_briefs_print_and_return_the_captured_bytes(
    case: Case, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from fr.run import brief
    from fr.run.evidence import lenses

    module = lenses if case.fn == "lens_set_or_refuse" else brief

    def call(_: object) -> object:
        fn = getattr(module, case.fn)
        kwargs = dict(case.kwargs)
        if case.repo_root:
            kwargs["repo_root"] = tmp_path
        if case.warn:
            kwargs["warn"] = run_cmd._say
        args = [tmp_path if a is ROOT else a for a in case.args]
        with run_cmd._refusals():
            return fn(*args, **kwargs)

    stderr, code, shown = run_case(monkeypatch, case, tmp_path, call)
    assert stderr == (FIXTURES / f"{case.name}.txt").read_text(encoding="utf-8")
    assert code == _exit_codes()[case.name]
    assert shown == (FIXTURES / f"{case.name}.json").read_text(encoding="utf-8")
