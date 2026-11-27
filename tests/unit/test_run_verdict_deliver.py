"""The deliver gates refuse and warn as they did before the move (spec 2026-11-27-run-verdict R9).

Each refusal path of the gate cluster, and each warning printed on the way, is driven with
faked inputs and printed through `run_cmd`'s adapters (`_refusals`, `_say`) onto a recording
console (colour on, so a lost `style` shows), then compared byte for byte, with its exit code,
against the capture in `tests/fixtures/run_verdict/deliver/`. The capture was taken once from
`run_cmd`'s own functions before the move; it is never regenerated from the code under test.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
import typer
from fr.commands import run_cmd
from rich.console import Console

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/run_verdict/deliver"
ROOT = Path("/repo")
# a name the moved module spells without run_cmd's leading underscore
_ALIASES = {"narrow_answered_by": "_answered_by_or_exit"}


def recording_console() -> Console:
    return Console(
        file=StringIO(), width=80, force_terminal=True, color_system="standard", highlight=False
    )


def sym(module: ModuleType, name: str) -> str:
    """The attribute of `module` that holds `name` (run_cmd's is underscored)."""
    if hasattr(module, name):
        return name
    return _ALIASES.get(name, f"_{name}")


def _patch(mp: pytest.MonkeyPatch, dotted: str, value: object) -> None:
    module, _, attr = dotted.rpartition(".")
    import importlib

    mp.setattr(importlib.import_module(module), attr, value)


STATE: Any = SimpleNamespace(run="r1", branch="feat/x", pr=None, steps={})
ASK_STATE: Any = SimpleNamespace(run="r1", branch="feat/x", pr="https://example.com/o/r/pull/7")


def _settings(*, pr: str = "auto", pr_body: str = "full") -> Any:
    return SimpleNamespace(
        settings=SimpleNamespace(git=SimpleNamespace(pr=pr), forge=SimpleNamespace(pr_body=pr_body))
    )


def _raising(exc: BaseException) -> Callable[..., Any]:
    def fn(*_a: object, **_k: object) -> Any:
        raise exc

    return fn


@dataclass(frozen=True)
class Case:
    """One path: how to fake its inputs, which function, and its arguments."""

    name: str
    fn: str
    setup: Callable[[pytest.MonkeyPatch, ModuleType, Path], None]
    args: Callable[[Path], tuple[Any, ...]]
    kwargs: dict[str, Any] = field(default_factory=dict)
    witness: Any = None


_ROOT_STATE = {"warn_ops_gap", "warn_label_sync", "deliver_exit_guard"}


def _nothing(mp: pytest.MonkeyPatch, module: ModuleType, tmp: Path) -> None:
    return None


def _case(name: str, fn: str, setup: Any = _nothing, args: Any = None, **kw: Any) -> Case:
    default = (lambda tmp: (ROOT, STATE)) if fn in _ROOT_STATE else (lambda tmp: ())
    return Case(f"{fn}-{name}", fn, setup, args or default, **kw)


# -- ops gap / label sync / exit guard ------------------------------------------------------


def _ops_gap(mp: pytest.MonkeyPatch, *, heading: bool) -> None:
    from fr.spec import TestPlanHeading, TestPlanHeadingError

    _patch(mp, "fr.requirements.run_spec", lambda _s: "docs/s.md")
    _patch(mp, "fr.verification.exit.run_plan_dir", lambda *_a: None)
    _patch(mp, "fr.verification.exit.run_exit", lambda *_a: SimpleNamespace(gates=()))
    if heading:
        _patch(
            mp,
            "fr.ops.gap.ops_gap",
            _raising(TestPlanHeadingError(TestPlanHeading(3, "## Test plan", False), "docs/s.md")),
        )
    else:
        _patch(mp, "fr.ops.gap.ops_gap", lambda *_a: ["gap"])
        _patch(mp, "fr.ops.gap.gap_message", lambda gap, *, has_plan: f"ops gap {gap} {has_plan}")


def _label_outcome(mp: pytest.MonkeyPatch, outcome: object) -> None:
    def sync(*_a: object) -> object:
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    _patch(mp, "fr.verification.labels.sync_exit_labels", sync)


def _outcome(**kw: Any) -> Any:
    return SimpleNamespace(**{"unknown": False, "warning": None, "off": None, **kw})


def _label_cases() -> list[Case]:
    from fr.verification import labels

    def with_outcome(outcome: Any) -> Any:
        return lambda mp, m, t: _label_outcome(mp, outcome)

    sync_args = lambda t: (ROOT, STATE, None, "r1")  # noqa: E731
    return [
        _case("heading-error", "warn_ops_gap", lambda mp, m, t: _ops_gap(mp, heading=True)),
        _case("gap-message", "warn_ops_gap", lambda mp, m, t: _ops_gap(mp, heading=False)),
        _case(
            "sync-failed",
            "warn_label_sync",
            with_outcome(RuntimeError("forge down")),
        ),
        _case("outcome-warning", "warn_label_sync", with_outcome(_outcome(warning="mapped"))),
        _case(
            "lowered",
            "deliver_exit_guard",
            lambda mp, m, t: _patch(
                mp, "fr.verification.baseline.unaccounted_lowerings", lambda *_a: ["a: x", "b: y"]
            ),
        ),
        _case(
            "forge-undeterminable",
            "deliver_label_sync",
            with_outcome(labels.ForgeUndeterminable("no origin remote")),
            sync_args,
        ),
        _case(
            "sync-error",
            "deliver_label_sync",
            with_outcome(labels.LabelSyncError("forge said no")),
            sync_args,
        ),
        _case("unknown", "deliver_label_sync", with_outcome(_outcome(unknown=True)), sync_args),
        _case(
            "unknown-warning",
            "deliver_label_sync",
            with_outcome(_outcome(unknown=True, warning="cannot read")),
            sync_args,
        ),
        _case(
            "warning-and-off",
            "deliver_label_sync",
            with_outcome(_outcome(warning="mapped", off="verification:x")),
            sync_args,
        ),
    ]


# -- the PR gates ----------------------------------------------------------------------------


def _ask(mp: pytest.MonkeyPatch, module: ModuleType, tmp: Path) -> None:
    _patch(mp, "fr.settings.load_settings", lambda _r: _settings(pr="ask"))


class _Client:
    def __init__(self, live: str | BaseException) -> None:
        self.live = live

    def pr_body(self, ref: str, *, cwd: Path) -> str:
        if isinstance(self.live, BaseException):
            raise self.live
        return self.live


def _pr_gate(
    *,
    live: str | BaseException = "",
    pr_body: str = "full",
    shape: str | None = None,
    render: str | BaseException = "rendered",
    markers: list[str] | None = None,
) -> Callable[[pytest.MonkeyPatch, ModuleType, Path], None]:
    def setup(mp: pytest.MonkeyPatch, module: ModuleType, tmp: Path) -> None:
        _patch(mp, "fr.shape.deliver_shape_refusal", lambda *_a: shape)
        _patch(mp, "fr.settings.load_settings", lambda _r: _settings(pr_body=pr_body))
        _patch(mp, "fr.record.model.records_dir", lambda _r, _run: tmp / "recs")
        _patch(mp, "fr.record.pr_body.durable_pr_body_path", lambda _r, _run: tmp / "kept.md")
        _patch(
            mp,
            "fr.record.pr_body.render_pr_body",
            _raising(render) if isinstance(render, BaseException) else (lambda *_a: render),
        )
        _patch(mp, "fr.record.pr_body.fr_markers", lambda _live: markers or [])
        _patch(mp, "fr.hostclient.client_for", lambda _r: _Client(live))
        _patch(mp, "fr.hostclient.FORGE_ERRORS", (OSError,))
        _patch(mp, "fr.hostclient.pr_command", lambda *_a, **_k: "EDIT-PR")
        mp.setattr(module, sym(module, "refuse_unclosed_owed"), lambda *_a: None)
        mp.setattr(module, sym(module, "refuse_premature_closes"), lambda *_a: None)

    return setup


def _all_sections() -> str:
    from fr.record.pr_body import REQUIRED_SECTIONS

    return "\n".join(REQUIRED_SECTIONS) + "\n"


def _pr_gate_cases() -> list[Case]:
    args = lambda t: (t, STATE, "https://example.com/o/r/pull/3")  # noqa: E731
    return [
        _case("ask-no-pr", "deliver_pr_ask_gate", _ask, lambda t: (ROOT, STATE, None)),
        _case(
            "ask-other-pr",
            "deliver_pr_ask_gate",
            _ask,
            lambda t: (ROOT, ASK_STATE, "https://example.com/o/r/pull/9"),
        ),
        _case("no-shape", "deliver_pr_gate", _pr_gate(shape="the shape file is missing"), args),
        _case(
            "render-refused",
            "deliver_pr_gate",
            _pr_gate(render=_PrBodyRefused()),
            args,
        ),
        _case("cannot-read-pr", "deliver_pr_gate", _pr_gate(live=OSError("HTTP 404")), args),
        _case(
            "minimal-marker",
            "deliver_pr_gate",
            _pr_gate(live="body", pr_body="minimal", markers=["<!-- a -->", "<!-- b -->"]),
            args,
        ),
        _case("missing-sections", "deliver_pr_gate", _pr_gate(live="no sections here"), args),
        _case(
            "shared-keyword",
            "deliver_pr_gate",
            _pr_gate(live=_all_sections() + "Closes #1 and #2\n"),
            args,
        ),
        _case("minimal-note", "deliver_pr_gate", _pr_gate(live="plain", pr_body="minimal"), args),
    ]


def _PrBodyRefused() -> BaseException:  # noqa: N802 — a constructor named for its class
    from fr.record.pr_body import PrBodyRefused

    return PrBodyRefused("the shape section cannot be rendered")


# -- owed, premature closes, journals ----------------------------------------------------------


def _owed(
    *,
    discharged: Any = ("o/r#5",),
    held: Any = frozenset(),
) -> Callable[[pytest.MonkeyPatch, ModuleType, Path], None]:
    def setup(mp: pytest.MonkeyPatch, module: ModuleType, tmp: Path) -> None:
        from fr.record import pr_body

        _patch(mp, "fr.owed_refs.discharge_travels", lambda _r: True)
        _patch(mp, "fr._hosts.origin_hostname", lambda _r: "example.com")
        _patch(mp, "fr.hostclient.pr_command", lambda *_a, **_k: "EDIT-PR")
        _patch(
            mp,
            "fr.record.pr_body.discharged_owed",
            _raising(discharged)
            if isinstance(discharged, BaseException)
            else (lambda _r: [SimpleNamespace(ref=ref) for ref in discharged]),
        )
        _patch(
            mp,
            "fr.record.pr_body.run_held_issues",
            _raising(held) if isinstance(held, BaseException) else (lambda *_a: held),
        )
        assert pr_body  # the patched module is the one the gate reads

    return setup


def _premature(*, matrix: Any, found: Any = ()) -> Callable[..., None]:
    def setup(mp: pytest.MonkeyPatch, module: ModuleType, tmp: Path) -> None:
        _patch(mp, "fr.record.pr_body.run_narrowings", lambda *_a: [])
        _patch(
            mp,
            "fr.acceptance.fold.load_effective",
            _raising(matrix) if isinstance(matrix, BaseException) else (lambda _r: matrix),
        )
        _patch(mp, "fr.acceptance.check.resolve_identity", lambda *_a: ("o", "r"))
        _patch(mp, "fr.requirements.run_spec", lambda _s: None)
        _patch(mp, "fr.verification.exit.run_exit", _raising(RuntimeError("unreadable")))
        _patch(mp, "fr.record.pr_body.holds_open_for_run", lambda *_a: frozenset())
        _patch(mp, "fr.record.pr_body.premature_closes", lambda *_a, **_k: list(found))

    return setup


def _journals_unreadable(mp: pytest.MonkeyPatch, module: ModuleType, tmp: Path) -> None:
    from fr.record.pr_body import UnreadableJournalError

    _patch(mp, "fr.record.pr_body.run_narrowings", _raising(UnreadableJournalError("a.yaml: bad")))
    _patch(mp, "fr.acceptance.fold.load_effective", lambda _r: SimpleNamespace(rows=[]))


def _owed_cases() -> list[Case]:
    from fr.acceptance.model import AcceptanceError
    from fr.record.pr_body import UnreadableDischargeError

    args = lambda t: (ROOT, STATE, "closes nothing", "1", "body.md")  # noqa: E731
    closes = SimpleNamespace(
        line="Closes #7",
        ref="o/r#7",
        rows=["r-1"],
        decisions=["d-1"],
        tracks=["t-1"],
        fix="Refs o/r#7",
    )
    matrix = SimpleNamespace(rows=[SimpleNamespace(issues=["o/r#7"])])
    return [
        _case(
            "discharge-unreadable",
            "refuse_unclosed_owed",
            _owed(discharged=UnreadableDischargeError("a journal is torn")),
            args,
        ),
        _case(
            "holds-unreadable",
            "refuse_unclosed_owed",
            _owed(held=AcceptanceError("matrix is torn")),
            args,
        ),
        _case("not-closed", "refuse_unclosed_owed", _owed(), args),
        _case(
            "matrix-unreadable",
            "refuse_premature_closes",
            _premature(matrix=AcceptanceError("fold is torn")),
            lambda t: (ROOT, STATE, "Closes #7\n"),
        ),
        _case(
            "closes-held-issue",
            "refuse_premature_closes",
            _premature(matrix=matrix, found=[closes]),
            lambda t: (ROOT, STATE, "Closes #7\n"),
        ),
        _case(
            "journal-unreadable",
            "refuse_premature_closes",
            _journals_unreadable,
            lambda t: (ROOT, STATE, "x"),
        ),
    ]


# -- placement, acceptance, leftovers --------------------------------------------------------


def _drift(mp: pytest.MonkeyPatch, module: ModuleType, tmp: Path) -> None:
    from fr.placement.drift import DriftError

    _patch(
        mp, "fr.placement.drift.refuse", _raising(DriftError("branch is on the wrong placement"))
    )


def _amendments(mp: pytest.MonkeyPatch, module: ModuleType, tmp: Path) -> None:
    _patch(mp, "fr.settings.disabled", lambda *_a: False)
    _patch(
        mp,
        "fr.acceptance.amend.branch_refusals",
        lambda _r: SimpleNamespace(
            warnings=["fetch skipped"], errors=["edited in place: r-1"], stale=["r-2 is stale"]
        ),
    )


def _leftovers(mp: pytest.MonkeyPatch, module: ModuleType, tmp: Path) -> None:
    from fr.record.pr_body import Leftover

    _patch(mp, "fr.verification.exit.run_exit", _raising(RuntimeError("unreadable")))
    _patch(
        mp,
        "fr.record.pr_body.unaccounted",
        lambda *_a: [
            Leftover("row", "r-1", "owed", "fr acceptance set-status --id r-1"),
            Leftover("finding", "f-1", "out of scope", "fr journal resolve f-1"),
        ],
    )


_CLEANUPS: list[Callable[[], None]] = []


def _held_rows(mp: pytest.MonkeyPatch, module: ModuleType, tmp: Path) -> None:
    _leftovers(mp, module, tmp)
    holder = getattr(module, sym(module, "RECORD_ROWS"))
    token = holder.set(("rec.yaml", {"r-1": "walked"}))
    _CLEANUPS.append(lambda: holder.reset(token))


# -- local stamps ------------------------------------------------------------------------------


def _fragment(
    mp: pytest.MonkeyPatch,
    module: ModuleType,
    tmp: Path,
    *,
    parse: Any = None,
    matrix: Any = None,
    paths: list[str] | None = None,
    blobs: Any = None,
) -> None:
    folder = tmp / "docs/acceptance/features"
    folder.mkdir(parents=True)
    (folder / "spec.yaml").write_text("rows: []\n", encoding="utf-8")
    mp.setattr(module, "artifact_root", lambda _r: tmp)
    _patch(mp, "fr.settings.disabled", lambda *_a: False)
    row = SimpleNamespace(id="r-1", status="local", notes="n")
    fragment = SimpleNamespace(amendments=[], rows=[row])
    _patch(
        mp,
        "fr.acceptance.fragment.parse_fragment",
        _raising(parse) if isinstance(parse, BaseException) else (lambda *_a, **_k: fragment),
    )
    current = SimpleNamespace(matrix=SimpleNamespace(rows=[row]), revisions={}, pending=[])
    _patch(
        mp,
        "fr.acceptance.fold.effective",
        _raising(matrix) if isinstance(matrix, BaseException) else (lambda _r: current),
    )
    _patch(mp, "fr.acceptance.local.level_ref_paths", lambda _r: paths or [])
    _patch(mp, "fr.acceptance.local.head_blobs", lambda *_a: blobs)


def _local_cases() -> list[Case]:
    from fr.acceptance.model import AcceptanceError

    args = lambda t: (t, "spec", "suite.log")  # noqa: E731

    def frag(**kw: Any) -> Any:
        return lambda mp, m, t: _fragment(mp, m, t, **kw)

    return [
        _case(
            "fragment-unreadable",
            "local_stamp_plan",
            frag(parse=AcceptanceError("not yaml")),
            args,
        ),
        _case(
            "matrix-unreadable", "local_stamp_plan", frag(matrix=AcceptanceError("fold torn")), args
        ),
        _case("no-witness", "local_stamp_plan", frag(), args, witness="tests is ci"),
        _case(
            "head-unreadable",
            "local_stamp_plan",
            frag(blobs=None),
            args,
            witness=("suite.log@0123456789ab", "feed"),
        ),
        _case(
            "no-test-path",
            "local_stamp_plan",
            frag(blobs={}),
            args,
            witness=("suite.log@0123456789ab", "feed"),
        ),
        _case(
            "not-committed",
            "local_stamp_plan",
            frag(blobs={"other.py": "abc"}, paths=["t.py"]),
            args,
            witness=("suite.log@0123456789ab", "feed"),
        ),
    ]


# -- the small ones ----------------------------------------------------------------------------


def _small_cases() -> list[Case]:
    from fr.record.pr_body import UnreadableJournalError

    return [
        _case(
            "no-rounds-trigger", "questions_from_flags", args=lambda t: (None, "design-risk", None)
        ),
        _case("no-rounds-reason", "questions_from_flags", args=lambda t: (None, None, "why")),
        _case("round-two-unexplained", "questions_from_flags", args=lambda t: (2, None, None)),
        _case("not-a-provenance", "narrow_answered_by", args=lambda t: ("robot",)),
        _case(
            "unreadable",
            "gate_journals",
            args=lambda t: (_raising(UnreadableJournalError("b.yaml: torn")),),
        ),
        _case("drifted", "deliver_placement_gate", _drift, lambda t: (ROOT,)),
        _case(
            "stale-and-warning",
            "deliver_acceptance_gate",
            _amendments,
            lambda t: (ROOT,),
        ),
        _case("unaccounted", "deliver_leftovers_gate", _leftovers, lambda t: (ROOT, STATE)),
        _case("record-wins", "deliver_leftovers_gate", _held_rows, lambda t: (ROOT, STATE)),
    ]


def _cases() -> list[Case]:
    return [
        *_small_cases(),
        *_label_cases(),
        *_pr_gate_cases(),
        *_owed_cases(),
        *_local_cases(),
    ]


CASES = _cases()


def run_case(
    mp: pytest.MonkeyPatch,
    case: Case,
    tmp: Path,
    call: Callable[[Callable[..., Any], tuple[Any, ...]], object],
    module: ModuleType,
) -> tuple[str, int]:
    """`(stderr, exit code)` of one call, on a fresh recording console."""
    console = recording_console()
    mp.setattr(run_cmd, "err_console", console)
    case.setup(mp, module, tmp)
    try:
        call(getattr(module, sym(module, case.fn)), case.args(tmp))
        code = 0
    except typer.Exit as e:
        code = e.exit_code
    finally:
        while _CLEANUPS:
            _CLEANUPS.pop()()
    file = console.file
    assert isinstance(file, StringIO)
    return file.getvalue(), code


def _exit_codes() -> dict[str, int]:
    loaded: dict[str, int] = json.loads((FIXTURES / "exit-codes.json").read_text(encoding="utf-8"))
    return loaded


def test_every_case_has_a_capture() -> None:
    assert sorted(_exit_codes()) == sorted(c.name for c in CASES)


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_the_moved_gates_print_the_captured_bytes(
    case: Case, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import fr.run.deliver as deliver

    def call(fn: Callable[..., Any], args: tuple[Any, ...]) -> object:
        extra: dict[str, Any] = {}
        if case.fn in {
            "warn_ops_gap",
            "warn_label_sync",
            "deliver_label_sync",
            "deliver_pr_gate",
        }:
            extra["warn"] = run_cmd._say
        if case.fn == "deliver_label_sync":
            extra["resume_hint"] = run_cmd._resolve_hint("r1", "deliver", None)
        if case.fn == "local_stamp_plan":
            extra["today"] = "2026-11-14"
            extra["witness"] = lambda _r, _t: case.witness
        with run_cmd._refusals():
            return fn(*args, **extra)

    stderr, code = run_case(monkeypatch, case, tmp_path, call, deliver)
    assert stderr == (FIXTURES / f"{case.name}.txt").read_text(encoding="utf-8")
    assert code == _exit_codes()[case.name]


def test_the_record_rows_holder_keeps_its_context_var_name() -> None:
    import fr.run.deliver as deliver

    assert deliver.RECORD_ROWS.name == "fr_record_rows"


def test_repo_relative_takes_the_root_it_is_given(tmp_path: Path) -> None:
    import fr.run.deliver as deliver

    assert deliver.repo_relative(tmp_path, str(tmp_path / "a/b.md")) == "a/b.md"
    assert deliver.repo_relative(tmp_path, "docs/x.md") == "docs/x.md"
    assert deliver.repo_relative(tmp_path, "/elsewhere/x.md") == "/elsewhere/x.md"
