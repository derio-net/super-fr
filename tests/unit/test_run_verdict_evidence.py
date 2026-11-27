"""The evidence verifiers refuse, warn and return as they did before the move (spec
2026-11-27-run-verdict R7, R9).

Each refusal path of every function of the evidence cluster (bar `_verified_evidence`, which
stays in `run_cmd`), each warning printed on the way and each unobserved gate noted, is driven
with faked inputs through `fr.run.evidence` and `run_cmd`'s adapters (`_settle` for a verdict,
`_refusals` for a raising function, `_say` as the `warn`) onto a recording console (colour on,
so a lost `style` shows). Its stderr, exit code, returned value and noted gates are compared
byte for byte against the capture in `tests/fixtures/run_verdict/evidence/`. The capture was
taken once from `run_cmd`'s own functions before the move; it is never regenerated from the
code under test. Inputs are faked where the function looks them up (its lazy imports' source
modules), and `_patch` follows a faked function into every evidence module that imported it.

`test_two_derived_refusals_print_the_summary_line` pins gh#768's summary line through
`fr run resolve`, against a capture taken from the same resolve before the move.
"""

from __future__ import annotations

import datetime as dt
import importlib
import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer
from fr.commands import run_cmd
from fr.journal.model import JournalEntry
from fr.run.model import Attempt, StepRecord
from fr.workflow.model import Step
from rich.console import Console

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/run_verdict/evidence"
OPENED = "2026-01-01T00:00:00+00:00"
LATER = "2026-01-02T00:00:00+00:00"
PHASE_KEY = "phase/1/review-phase"
DELIVER = "step/deliver"
_REBIND_PREFIXES: tuple[str, ...] = ("fr.run.evidence.",)
"""The modules `_patch` follows a faked name into, by the identity of what they imported."""


def recording_console() -> Console:
    return Console(
        file=StringIO(), width=80, force_terminal=True, color_system="standard", highlight=False
    )


def _patch(mp: pytest.MonkeyPatch, dotted: str, value: object) -> None:
    """Fake `dotted` at its source, and wherever an evidence module imported it by name."""
    module, _, attr = dotted.rpartition(".")
    source = importlib.import_module(module)
    original = getattr(source, attr)
    mp.setattr(source, attr, value)
    for name, loaded in list(sys.modules.items()):
        if loaded is None or loaded is source or not name.startswith(_REBIND_PREFIXES):
            continue
        for held, obj in list(vars(loaded).items()):
            if obj is original:
                mp.setattr(loaded, held, value)


def _raising(exc: BaseException) -> Callable[..., Any]:
    def fn(*_a: object, **_k: object) -> Any:
        raise exc

    return fn


@dataclass(frozen=True)
class T:
    """An evidence target, built at call time (`TARGET`): `scope`, `phase`, `feature`."""

    scope: str
    phase: int | None
    feature: bool = False


def _target_class() -> Any:
    return importlib.import_module("fr.run.evidence.target").EvidenceTarget


TARGET: Callable[[], Any] = _target_class


class Root:
    """The test's repository root, substituted at call time."""


ROOT = Root()


@dataclass(frozen=True)
class Case:
    """One path: how to fake its inputs, which function, and how to call it.

    `kind` is how the moved function reports: `verdict` (a `Verdict`, settled), `raises`
    (a `RunRefusal`, through `_refusals()`), or `plain` (a value, or an error of its own).
    `warn` says it takes the command's warning printer.
    """

    name: str
    module: str
    fn: str
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)
    setup: Callable[[pytest.MonkeyPatch, Path], None] | None = None
    kind: str = "plain"
    warn: bool = False


# --- inputs ------------------------------------------------------------------------------


def _entry(**kw: Any) -> JournalEntry:
    base: dict[str, Any] = {"scope": "plan", "created": OPENED, "title": "t"}
    base.update(kw)
    return JournalEntry(**base)


def _state(**steps: Any) -> Any:
    return SimpleNamespace(run="r1", steps=steps, base_branch=None)


PLANNED = _state(plan=SimpleNamespace(emitted={"plan": "docs/superpowers/plans/p"}, units=None))
SPECCED = _state(brainstorm=SimpleNamespace(emitted={"spec": "docs/superpowers/specs/s.md"}))
EMPTY = _state()


def _implemented(agent: str = "impl-1") -> Any:
    from fr.run import units

    record = units.with_attempt_appended(
        StepRecord(state="done"),
        "phase/1/implement-phase",
        Attempt(dispatched=OPENED, agent=agent, agent_type="super-fr:fr-phase-executor"),
    )
    return _state(implement=record)


def _dispatch(agent: str, agent_type: str | None = "reviewer", returned: str | None = None) -> Any:
    from fr.run.observed import ChildDispatch

    return ChildDispatch(agent, agent_type, dt.datetime(2026, 1, 1, 1, tzinfo=dt.UTC), returned)


@dataclass
class _View:
    found: list[Any]
    session: str = "s-1"
    children: dict[str, Any] = field(default_factory=dict)

    def dispatches(self, _start: object) -> list[Any]:
        return self.found

    def child(self, holder: str) -> Any:
        return self.children.get(holder, False)


def _session(view: _View | None) -> Callable[[pytest.MonkeyPatch, Path], None]:
    def setup(mp: pytest.MonkeyPatch, _tmp: Path) -> None:
        _patch(mp, "fr.run.observed.observed_session", lambda _env: view)
        _patch(mp, "fr.run.observed.why_unobservable", lambda _h, _env, what: f"no {what} here")

    return setup


def _findings(*rows: str) -> str:
    return "done.\n```review-findings\n" + "\n".join(rows) + "\n```\n"


def _lens_block(lens: str, *files: str) -> str:
    return f"```review-lens\nlens: {lens}\nexamined: {', '.join(files)}\n```\n"


def _lenses(*ids: str, changed: tuple[str, ...] | None = ("src/a.py", "src/b.py")) -> Any:
    from fr.lenses.accumulate import LensEntry, LensSet
    from fr.lenses.model import Lens

    return LensSet(
        lenses=tuple(LensEntry(i, rule=("src/**",), file="src/a.py") for i in ids),
        changed=changed,
        definitions={i: Lens(id=i, title=f"{i} title", brief=f"look at {i}") for i in ids},
    )


def _files(tmp: Path, **files: str) -> None:
    for rel, text in files.items():
        path = tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _plan_dir(mp: pytest.MonkeyPatch, tmp: Path) -> None:
    (tmp / "docs/superpowers/plans/p").mkdir(parents=True)


def _journal(scope_dir: str, slug: str, text: str) -> Callable[[pytest.MonkeyPatch, Path], None]:
    def setup(_mp: pytest.MonkeyPatch, tmp: Path) -> None:
        _files(tmp, **{f"docs/superpowers/journals/{scope_dir}/{slug}.md": text})

    return setup


def _harness(name: str | None) -> Callable[[pytest.MonkeyPatch, Path], None]:
    def setup(mp: pytest.MonkeyPatch, _tmp: Path) -> None:
        for var in list(os.environ):
            if var.startswith(("CLAUDE", "OPENCODE", "HERMES", "FR_HARNESS")):
                mp.delenv(var, raising=False)
        if name is not None:
            mp.setenv("FR_HARNESS", name)

    return setup


def _chain(*setups: Callable[[pytest.MonkeyPatch, Path], None]) -> Callable[..., None]:
    def setup(mp: pytest.MonkeyPatch, tmp: Path) -> None:
        for one in setups:
            one(mp, tmp)

    return setup


# --- suite logs ----------------------------------------------------------------------------

LOG = "suite.log"
_MTIME = dt.datetime(2026, 1, 1, 12, tzinfo=dt.UTC)


def _log(text: str = "12 passed\nexit=0\n", *, when: dt.datetime = _MTIME) -> Callable[..., None]:
    def setup(_mp: pytest.MonkeyPatch, tmp: Path) -> None:
        path = tmp / LOG
        path.write_text(text, encoding="utf-8")
        os.utime(path, (when.timestamp(), when.timestamp()))

    return setup


def _wrote(first: object, earlier: object = None) -> Callable[..., None]:
    """`orchestrator_wrote_since`: `first` for the unit's window, `earlier` from 1970."""

    def setup(mp: pytest.MonkeyPatch, _tmp: Path) -> None:
        def wrote(_env: object, _path: object, since: str) -> object:
            return earlier if since.startswith("1970") else first

        _patch(mp, "fr.run.telemetry.orchestrator_wrote_since", wrote)

    return setup


def _code(
    *,
    newest: object = None,
    dirty: tuple[str, ...] = (),
    tree: str = "tree-1",
    error: str | None = None,
    since: list[str] | None = None,
) -> Callable[..., None]:
    from fr.git import GitUnavailableError

    def setup(mp: pytest.MonkeyPatch, tmp: Path) -> None:
        def newest_mtime(*_a: object, **_k: object) -> object:
            if error is not None:
                raise GitUnavailableError(error)
            if newest == "after":
                return ((tmp / LOG).stat().st_mtime + 100, "src/changed.py")
            return newest

        def code_tree(_root: object) -> str:
            if error is not None:
                raise GitUnavailableError(error)
            return tree

        _patch(mp, "fr.run.code_tree.newest_code_mtime", newest_mtime)
        _patch(mp, "fr.run.code_tree.default_merge_base", lambda _root: "base-sha")
        _patch(mp, "fr.run.code_tree.dirty_code_paths", lambda _root: list(dirty))
        _patch(mp, "fr.run.code_tree.code_tree", code_tree)
        _patch(mp, "fr.run.code_tree.code_paths_since_tree", lambda _root, _tree: since)

    return setup


_AROUND = [(_MTIME - dt.timedelta(minutes=1), _MTIME + dt.timedelta(minutes=1))]
_ELSEWHEN = [(_MTIME - dt.timedelta(hours=3), _MTIME - dt.timedelta(hours=2))]
_BEFORE_OPEN = [(_MTIME - dt.timedelta(minutes=1), dt.datetime(2026, 1, 2, tzinfo=dt.UTC))]


def _holder(found: object) -> Callable[..., None]:
    """The holder's session for a phase log: `found` is its `wrote_windows`, or False."""

    def setup(mp: pytest.MonkeyPatch, _tmp: Path) -> None:
        child = (
            False
            if found is False
            else SimpleNamespace(session="child-1", wrote_windows=lambda _path, _start: found)
        )
        view = _View([], children={"exec-1": child})
        _patch(mp, "fr.run.observed.observed_session", lambda _env: view)

    return setup


def _reused_state(*, unobserved: bool = False) -> Any:
    evidence = {"tests": "suite.log@abcdef012345;tree=tree-1"}
    if unobserved:
        evidence["unobserved"] = "tests"
    unit = SimpleNamespace(
        evidence=evidence, state="done", attempts=[SimpleNamespace(returned=OPENED)]
    )
    return _state(implement=SimpleNamespace(state="done", units={"phase/1/implement-phase": unit}))


# --- walks ---------------------------------------------------------------------------------


def _walk_inputs(
    *,
    spec: str | None = "docs/superpowers/specs/s.md",
    rows: tuple[Any, ...] = (),
    error: Any = None,
) -> Callable[..., None]:
    from fr.verification.walk import WalkOwed

    def setup(mp: pytest.MonkeyPatch, _tmp: Path) -> None:
        if error is not None:
            _patch(mp, "fr.verification.rows.run_verification", _raising(error))
            return
        _patch(mp, "fr.verification.rows.run_verification", lambda _root, _state: (spec, None))
        _patch(mp, "fr.requirements.load_spec_matrix", lambda _root, _spec: (None, "spec:s"))
        _patch(mp, "fr.verification.walk.walk_owed", lambda *_a: WalkOwed(rows=rows))

    return setup


def _row(rid: str, scenario: str | None = None) -> Any:
    return SimpleNamespace(id=rid, scenario=scenario)


def _owed(*rows: Any) -> Any:
    from fr.verification.walk import WalkOwed

    return WalkOwed(rows=rows)


def _walk_log(mp: pytest.MonkeyPatch, tmp: Path, *, link: bool = False) -> None:
    mp.setenv("HOME", str(tmp / "home"))
    directory = tmp / "home/.cache/fr/walks/r1"
    directory.mkdir(parents=True)
    (directory / "walk.log").write_text("walk log\n", encoding="utf-8")
    os.utime(directory / "walk.log", (_MTIME.timestamp(), _MTIME.timestamp()))
    if link:
        (tmp / "link.log").symlink_to(directory / "walk.log")


def _walk_checks(problems: list[str], ran: object) -> Callable[..., None]:
    def setup(mp: pytest.MonkeyPatch, tmp: Path) -> None:
        _walk_log(mp, tmp)
        _patch(
            mp, "fr.verification.walk.parse_walk_log", lambda _text: SimpleNamespace(strategy="s")
        )
        _patch(mp, "fr.verification.walk.check_walk_log", lambda *_a, **_k: list(problems))
        _patch(mp, "fr.verification.resolve.strategy_identity", lambda *_a: "sid")
        _patch(mp, "fr.run.telemetry.orchestrator_ran_since", lambda *_a: ran)
        _patch(mp, "fr.run.observed.why_unobservable", lambda _h, _env, what: f"no {what} here")

    return setup


def _walk_path(tmp: Path) -> str:
    return str(tmp / "home/.cache/fr/walks/r1/walk.log")


class WalkLog:
    """The walk log's absolute path, substituted at call time."""


WALK_LOG = WalkLog()


# --- forge / ci ----------------------------------------------------------------------------


def _ci(result: object) -> Callable[..., None]:
    def setup(mp: pytest.MonkeyPatch, _tmp: Path) -> None:
        fake = _raising(result) if isinstance(result, BaseException) else (lambda _root: result)
        _patch(mp, "fr.run.ci_evidence.verify_ci", fake)

    return setup


def _ci_cases() -> list[Case]:
    from fr.gh import GhError
    from fr.ghclient import HostRefusedError
    from fr.run.ci_evidence import CiEvidenceRefused, CiPending

    forge = GhError("HTTP 502 bad gateway")
    forge.stderr = "gateway [timeout]"  # type: ignore[attr-defined]
    return [
        Case(
            "ci_tests_witness-not-done",
            "ci",
            "ci_tests_witness",
            (DELIVER, ROOT),
            {"done": False},
            kind="verdict",
        ),
        Case(
            "ci_tests_witness-ok",
            "ci",
            "ci_tests_witness",
            (DELIVER, ROOT),
            {"done": True},
            setup=_ci("ci:sha@tree"),
            kind="verdict",
        ),
        Case(
            "ci_tests_witness-host-refused",
            "ci",
            "ci_tests_witness",
            (DELIVER, ROOT),
            {"done": True},
            setup=_ci(HostRefusedError("host [x] not logged in")),
            kind="verdict",
        ),
        Case(
            "ci_tests_witness-forge-error",
            "ci",
            "ci_tests_witness",
            (DELIVER, ROOT),
            {"done": True},
            setup=_ci(forge),
            kind="verdict",
        ),
        Case(
            "ci_tests_witness-pending",
            "ci",
            "ci_tests_witness",
            (DELIVER, ROOT),
            {"done": True},
            setup=_ci(CiPending("abc123", "ci-ok [pending]")),
            kind="verdict",
        ),
        Case(
            "ci_tests_witness-refused",
            "ci",
            "ci_tests_witness",
            (DELIVER, ROOT),
            {"done": True},
            setup=_ci(CiEvidenceRefused("tests: ci — gate [x] failed")),
            kind="verdict",
        ),
    ]


# --- visual / single phase / historical ----------------------------------------------------


def _visual(*, refused: list[str] | None = None, unobserved: bool = False) -> Callable[..., None]:
    from fr.run.visual import VisualRefusedError

    def setup(mp: pytest.MonkeyPatch, _tmp: Path) -> None:
        if refused is not None:
            _patch(mp, "fr.run.visual.owed_for_unit", _raising(VisualRefusedError(refused)))
        else:
            _patch(mp, "fr.run.visual.owed_for_unit", lambda *_a, **_k: ["row-1"])
        derived = SimpleNamespace(
            unobserved=unobserved, why="no transcript [here]", witness="visual@1"
        )
        _patch(mp, "fr.run.visual.derive_visual", lambda *_a, **_k: derived)
        _patch(mp, "fr.run.visual.role_for", lambda *_a: "executor")

    return setup


def _tags(result: object) -> Callable[..., None]:
    def setup(mp: pytest.MonkeyPatch, _tmp: Path) -> None:
        fake = _raising(result) if isinstance(result, BaseException) else (lambda *_a: result)
        _patch(mp, "fr.run.adopt.plan_phase_tags", fake)

    return setup


def _historical(
    *, refused: list[str] | None = None, refusal: str | None = None
) -> Callable[..., None]:
    from fr.run.visual import VisualRefusedError

    def setup(mp: pytest.MonkeyPatch, _tmp: Path) -> None:
        if refused is not None:
            _patch(mp, "fr.run.visual.owed_for_unit", _raising(VisualRefusedError(refused)))
        else:
            _patch(mp, "fr.run.visual.owed_for_unit", lambda *_a, **_k: [])
        _patch(mp, "fr.run.historical.historical_review_refusal", lambda *_a, **_k: refusal)

    return setup


VISUAL_STEP = Step(id="implement-phase", kind="agent", evidence=("visual",))
REVIEW = _entry(kind="review", id="r-p1", phase=1)


def _all_cases() -> list[Case]:  # noqa: PLR0915 — one table of every path
    from fr.run.adopt import AdoptError
    from fr.verification.spec_section import SectionError

    spec_review = Step(id="spec-review", kind="agent", evidence=("review", "findings"))
    deliver = Step(id="deliver", kind="agent", evidence=("tests", "proportionality"))
    plan_step = Step(id="plan", kind="agent", emits=("plan",))
    silent = Step(id="plan", kind="agent", emits=())
    no_evidence = Step(id="plan", kind="agent")
    f_open = _entry(kind="finding", id="p1-r1", state="open", phase=1, review_scope="in")
    f_fixed = _entry(kind="finding", id="p1-r2", state="fixed", phase=1, review_scope="out")
    s_open = _entry(kind="finding", id="s-r1", state="open", scope="spec")
    oos = [
        _entry(kind="finding", id="p1-r3", state="open", phase=1),
        _entry(
            kind="finding", id="p1-r3-a", resolves="p1-r3", state="open", out_of_scope=True, phase=1
        ),
        _entry(kind="finding", id="p1-r3-b", resolves="p1-r3", state="fixed", phase=1),
    ]
    spec_rev_old = _entry(
        kind="review", id="sr-1", scope="spec", created="2025-12-01T00:00:00+00:00"
    )
    spec_rev = _entry(kind="review", id="sr-2", scope="spec", created=LATER)
    spec_disc = _entry(kind="discovery", id="sd-1", scope="spec")
    l_sec = _entry(kind="finding", id="l-security-r1", state="open", review_scope="in")
    sec = _lenses("security")
    two = _lenses("security", "tests")
    lens_review = T("plan", None, True)
    phase = T("plan", 1)
    spec = T("spec", None)
    view_ok = _View([_dispatch("rev-1")])
    good_journal = (
        "<!-- fr:journal kind=review scope=plan id=r-p1 "
        "created=2026-01-01T00:00:00+00:00 phase=1 -->\n"
        "### r-p1 · review · reviewed\n\nclean\n"
    )
    return [
        # emitted
        Case("parse_emitted-no-equals", "emitted", "parse_emitted", (["plan"], ROOT)),
        Case("parse_emitted-empty-name", "emitted", "parse_emitted", (["=x"], ROOT)),
        Case("parse_emitted-empty-value", "emitted", "parse_emitted", (["plan= "], ROOT)),
        Case("parse_emitted-twice", "emitted", "parse_emitted", (["pr=a", "pr=b"], ROOT)),
        Case("parse_emitted-undeclared", "emitted", "parse_emitted", (["pr=u"], ROOT, plan_step)),
        Case(
            "parse_emitted-undeclared-nothing", "emitted", "parse_emitted", (["pr=u"], ROOT, silent)
        ),
        Case("parse_emitted-outside", "emitted", "parse_emitted", (["plan=/nowhere/p"], ROOT)),
        Case(
            "parse_emitted-missing",
            "emitted",
            "parse_emitted",
            (["plan=docs/superpowers/plans/nope"], ROOT),
        ),
        Case(
            "parse_emitted-ok",
            "emitted",
            "parse_emitted",
            (["pr=https://x.example/1", "plan=docs/superpowers/plans/p"], ROOT),
            setup=_plan_dir,
        ),
        # target: evidence parsing
        Case("parse_evidence-no-equals", "target", "parse_evidence", (["review"], spec_review)),
        Case("parse_evidence-empty-name", "target", "parse_evidence", (["=x"], spec_review)),
        Case("parse_evidence-empty-value", "target", "parse_evidence", (["review= "], spec_review)),
        Case(
            "parse_evidence-twice",
            "target",
            "parse_evidence",
            (["review=a", "review=b"], spec_review),
        ),
        Case(
            "parse_evidence-offered",
            "target",
            "parse_evidence",
            (["tests=x.log"], spec_review),
            {"phase_unit": True},
        ),
        Case(
            "parse_evidence-declares-none", "target", "parse_evidence", (["review=a"], no_evidence)
        ),
        Case("parse_evidence-undeclared", "target", "parse_evidence", (["tests=a"], spec_review)),
        Case(
            "parse_evidence-derived", "target", "parse_evidence", (["proportionality=a"], deliver)
        ),
        # journals
        Case("plan_journal_entries-no-plan", "journals", "plan_journal_entries", (ROOT, EMPTY)),
        Case("plan_journal_entries-missing", "journals", "plan_journal_entries", (ROOT, PLANNED)),
        Case(
            "plan_journal_entries-unreadable",
            "journals",
            "plan_journal_entries",
            (ROOT, PLANNED),
            setup=_journal(
                "plans", "p", "<!-- fr:journal kind=nope scope=plan id=x created=2026 -->\n### x\n"
            ),
        ),
        Case(
            "plan_journal_entries-ok",
            "journals",
            "plan_journal_entries",
            (ROOT, PLANNED),
            setup=_journal("plans", "p", good_journal),
        ),
        Case(
            "review_journal_entries-feature-missing",
            "journals",
            "review_journal_entries",
            (ROOT, PLANNED, lens_review),
        ),
        Case(
            "review_journal_entries-spec-none",
            "journals",
            "review_journal_entries",
            (ROOT, EMPTY, spec),
        ),
        Case(
            "review_journal_entries-spec-missing",
            "journals",
            "review_journal_entries",
            (ROOT, SPECCED, spec),
        ),
        Case(
            "review_journal_entries-debug-none",
            "journals",
            "review_journal_entries",
            (ROOT, EMPTY, T("debug", None)),
        ),
        # journals: the review entry
        Case(
            "verify_review_entry-not-found",
            "journals",
            "verify_review_entry",
            (PHASE_KEY, "r-x"),
            {"slug": "p", "entries": [REVIEW], "target": phase, "since": OPENED},
            kind="raises",
        ),
        Case(
            "verify_review_entry-not-found-feature",
            "journals",
            "verify_review_entry",
            ("step/lens-review", "r-x"),
            {"slug": "p", "entries": [], "target": lens_review, "since": OPENED},
            kind="raises",
        ),
        Case(
            "verify_review_entry-other-phase",
            "journals",
            "verify_review_entry",
            (PHASE_KEY, "p1-r1"),
            {
                "slug": "p",
                "entries": [_entry(kind="finding", id="p1-r1", state="open", phase=2)],
                "target": phase,
                "since": OPENED,
            },
            kind="raises",
        ),
        Case(
            "verify_review_entry-no-phase",
            "journals",
            "verify_review_entry",
            (PHASE_KEY, "d1"),
            {
                "slug": "p",
                "entries": [_entry(kind="discovery", id="d1")],
                "target": phase,
                "since": OPENED,
            },
            kind="raises",
        ),
        Case(
            "verify_review_entry-phase-ok",
            "journals",
            "verify_review_entry",
            (PHASE_KEY, "r-p1"),
            {"slug": "p", "entries": [REVIEW], "target": phase, "since": OPENED},
            kind="raises",
        ),
        Case(
            "verify_review_entry-feature-phased",
            "journals",
            "verify_review_entry",
            ("step/lens-review", "r-p1"),
            {"slug": "p", "entries": [REVIEW], "target": lens_review, "since": OPENED},
            kind="raises",
        ),
        Case(
            "verify_review_entry-feature-kind",
            "journals",
            "verify_review_entry",
            ("step/lens-review", "d1"),
            {
                "slug": "p",
                "entries": [_entry(kind="discovery", id="d1")],
                "target": lens_review,
                "since": OPENED,
            },
            kind="raises",
        ),
        Case(
            "verify_review_entry-spec-kind",
            "journals",
            "verify_review_entry",
            ("step/spec-review", "sd-1"),
            {"slug": "s", "entries": [spec_disc], "target": spec, "since": OPENED},
            kind="raises",
        ),
        Case(
            "verify_review_entry-spec-before",
            "journals",
            "verify_review_entry",
            ("step/spec-review", "sr-1"),
            {"slug": "s", "entries": [spec_rev_old], "target": spec, "since": OPENED},
            kind="raises",
        ),
        Case(
            "verify_review_entry-feature-before",
            "journals",
            "verify_review_entry",
            ("step/lens-review", "sr-1"),
            {
                "slug": "p",
                "entries": [spec_rev_old.model_copy(update={"scope": "plan"})],
                "target": lens_review,
                "since": OPENED,
            },
            kind="raises",
        ),
        Case(
            "verify_review_entry-spec-no-since",
            "journals",
            "verify_review_entry",
            ("step/spec-review", "sr-2"),
            {"slug": "s", "entries": [spec_rev], "target": spec, "since": None},
            kind="raises",
        ),
        Case(
            "verify_review_entry-spec-ok",
            "journals",
            "verify_review_entry",
            ("step/spec-review", "sr-2"),
            {"slug": "s", "entries": [spec_rev], "target": spec, "since": OPENED},
            kind="raises",
        ),
        # journals: closed findings
        Case(
            "closed_findings_witness-unauthorized",
            "journals",
            "closed_findings_witness",
            (PHASE_KEY, "p", oos, phase),
            kind="verdict",
        ),
        Case(
            "closed_findings_witness-open-phase",
            "journals",
            "closed_findings_witness",
            (PHASE_KEY, "p", [f_open, f_fixed], phase),
            kind="verdict",
        ),
        Case(
            "closed_findings_witness-open-spec",
            "journals",
            "closed_findings_witness",
            ("step/spec-review", "s", [s_open], spec),
            kind="verdict",
        ),
        Case(
            "closed_findings_witness-open-feature",
            "journals",
            "closed_findings_witness",
            ("step/lens-review", "p", [f_open, l_sec], lens_review),
            kind="verdict",
        ),
        Case(
            "closed_findings_witness-ok",
            "journals",
            "closed_findings_witness",
            (PHASE_KEY, "p", [f_fixed], phase),
            kind="verdict",
        ),
        # review: historical
        Case(
            "refuse_unboundable_historical-flat",
            "review",
            "refuse_unboundable_historical",
            ("step/spec-review", spec, {"reviewer": "historical"}),
            kind="raises",
        ),
        Case(
            "refuse_unboundable_historical-no-review",
            "review",
            "refuse_unboundable_historical",
            (PHASE_KEY, phase, {"reviewer": "historical"}),
            kind="raises",
        ),
        Case(
            "refuse_unboundable_historical-ok",
            "review",
            "refuse_unboundable_historical",
            (PHASE_KEY, phase, {"reviewer": "historical", "review": "r-p1"}),
            kind="raises",
        ),
        Case(
            "verify_historical_bound-visual",
            "review",
            "verify_historical_bound",
            (PHASE_KEY, ROOT, PLANNED),
            {"target": phase, "entry_id": "r-p1", "entries": [REVIEW]},
            setup=_historical(refused=["visual: cannot tell [x]", "row r-1 owes shots"]),
            kind="raises",
        ),
        Case(
            "verify_historical_bound-refused",
            "review",
            "verify_historical_bound",
            (PHASE_KEY, ROOT, PLANNED),
            {"target": phase, "entry_id": "r-p1", "entries": [REVIEW]},
            setup=_historical(refusal="the review [predates] the phase"),
            kind="raises",
        ),
        Case(
            "verify_historical_bound-ok",
            "review",
            "verify_historical_bound",
            (PHASE_KEY, ROOT, PLANNED),
            {"target": phase, "entry_id": "r-p1", "entries": [REVIEW]},
            setup=_historical(),
            kind="raises",
        ),
        # review: the reviewer
        Case(
            "verify_reviewer-implementer",
            "review",
            "verify_reviewer",
            (PHASE_KEY, "impl-1", _implemented()),
            {"target": phase, "opened": OPENED},
            setup=_session(view_ok),
            kind="raises",
            warn=True,
        ),
        Case(
            "verify_reviewer-executor",
            "review",
            "verify_reviewer",
            (PHASE_KEY, "rev-1", EMPTY),
            {"target": phase, "opened": OPENED},
            setup=_session(_View([_dispatch("rev-1", "super-fr:fr-phase-executor")])),
            kind="raises",
            warn=True,
        ),
        Case(
            "verify_reviewer-other-agent",
            "review",
            "verify_reviewer",
            ("step/spec-review", "rev-1", EMPTY),
            {"target": spec, "opened": OPENED, "expected_agent": "super-fr:fr-spec-reviewer"},
            setup=_session(_View([_dispatch("rev-1", "general-purpose")])),
            kind="raises",
            warn=True,
        ),
        Case(
            "verify_reviewer-not-dispatched",
            "review",
            "verify_reviewer",
            (PHASE_KEY, "rev-9", EMPTY),
            {"target": phase, "opened": OPENED},
            setup=_session(view_ok),
            kind="raises",
            warn=True,
        ),
        Case(
            "verify_reviewer-unobserved",
            "review",
            "verify_reviewer",
            (PHASE_KEY, "rev-1", EMPTY),
            {"target": phase, "opened": OPENED},
            setup=_session(None),
            kind="raises",
            warn=True,
        ),
        Case(
            "verify_reviewer-no-window",
            "review",
            "verify_reviewer",
            (PHASE_KEY, "rev-1", EMPTY),
            {"target": phase, "opened": None},
            setup=_session(view_ok),
            kind="raises",
            warn=True,
        ),
        Case(
            "verify_reviewer-ok",
            "review",
            "verify_reviewer",
            ("step/spec-review", "rev-1", EMPTY),
            {"target": spec, "opened": OPENED, "expected_agent": "super-fr:fr-spec-reviewer"},
            setup=_session(_View([_dispatch("rev-1", "fr-spec-reviewer-hard")])),
            kind="raises",
            warn=True,
        ),
        Case(
            "same_agent-folds",
            "review",
            "same_agent",
            ("fr-spec-reviewer-hard", "super-fr:fr-spec-reviewer"),
        ),
        Case("same_agent-none", "review", "same_agent", (None, "super-fr:fr-spec-reviewer")),
        # review: returned findings
        Case(
            "check_returned_findings-unobserved",
            "review",
            "check_returned_findings",
            (PHASE_KEY, [f_open], 1, OPENED, "rev-1"),
            setup=_session(None),
            kind="raises",
            warn=True,
        ),
        Case(
            "check_returned_findings-not-returned",
            "review",
            "check_returned_findings",
            (PHASE_KEY, [f_open], 1, OPENED, "rev-1"),
            setup=_session(_View([_dispatch("rev-1"), _dispatch("helper")])),
            kind="raises",
            warn=True,
        ),
        Case(
            "check_returned_findings-problems",
            "review",
            "check_returned_findings",
            (PHASE_KEY, [f_open, f_fixed], 1, OPENED, "rev-1"),
            setup=_session(
                _View(
                    [
                        _dispatch("rev-1", returned="no block here"),
                        _dispatch(
                            "rev-2",
                            returned=_findings(
                                "p1-r1 | out | scope [moved]", "p1-r9 | in | not journaled"
                            ),
                        ),
                        _dispatch("rev-3", returned=_findings("p1-r1 | in | twice")),
                        _dispatch("rev-4", returned=_findings("garbage line")),
                        _dispatch("helper", returned="a helper's chat"),
                    ]
                )
            ),
            kind="raises",
            warn=True,
        ),
        Case(
            "check_returned_findings-ok",
            "review",
            "check_returned_findings",
            (PHASE_KEY, [f_open, f_fixed], 1, OPENED, "rev-1"),
            setup=_session(
                _View(
                    [_dispatch("rev-1", returned=_findings("p1-r1 | in | ok", "p1-r2 | out | old"))]
                )
            ),
            kind="raises",
            warn=True,
        ),
        # lenses: reviewers
        Case(
            "verify_lens_reviewers-problems",
            "lenses",
            "verify_lens_reviewers",
            (
                "step/lens-review",
                "security=a1,bogus,security=a2,docs=a3,tests=a1",
                EMPTY,
                _lenses("security", "tests", "errors"),
                ROOT,
            ),
            {"target": lens_review, "opened": OPENED},
            setup=_session(view_ok),
            kind="raises",
            warn=True,
        ),
        Case(
            "verify_lens_reviewers-empty-set",
            "lenses",
            "verify_lens_reviewers",
            ("step/lens-review", "docs=a3", EMPTY, _lenses(), ROOT),
            {"target": lens_review, "opened": OPENED},
            setup=_session(view_ok),
            kind="raises",
            warn=True,
        ),
        Case(
            "verify_lens_reviewers-reviewer-refused",
            "lenses",
            "verify_lens_reviewers",
            ("step/lens-review", "security=rev-9", EMPTY, sec, ROOT),
            {"target": lens_review, "opened": OPENED},
            setup=_session(view_ok),
            kind="raises",
            warn=True,
        ),
        Case(
            "verify_lens_reviewers-unobserved",
            "lenses",
            "verify_lens_reviewers",
            ("step/lens-review", "security=rev-1,tests=rev-2", EMPTY, two, ROOT),
            {"target": lens_review, "opened": OPENED},
            setup=_session(None),
            kind="raises",
            warn=True,
        ),
        Case(
            "owed_on-empty-set",
            "lenses",
            "owed_on",
            (
                Step(id="lens-review", kind="agent", evidence=("review", "reviewer", "lenses")),
                _lenses(),
            ),
        ),
        Case(
            "owed_on-no-set",
            "lenses",
            "owed_on",
            (Step(id="lens-review", kind="agent", evidence=("review", "reviewer", "lenses")), None),
        ),
        # lenses: returns
        Case(
            "lenses_witness-empty",
            "lenses",
            "lenses_witness",
            ("step/lens-review", ROOT, _lenses(), [], None, OPENED),
            kind="verdict",
        ),
        Case(
            "lenses_witness-unobserved",
            "lenses",
            "lenses_witness",
            ("step/lens-review", ROOT, sec, [l_sec], {"security": "rev-1"}, OPENED),
            setup=_session(None),
            kind="verdict",
        ),
        Case(
            "lenses_witness-not-returned",
            "lenses",
            "lenses_witness",
            (
                "step/lens-review",
                ROOT,
                two,
                [l_sec],
                {"security": "rev-1", "tests": "rev-2"},
                OPENED,
            ),
            setup=_session(
                _View(
                    [
                        _dispatch(
                            "rev-1",
                            returned=_lens_block("security", "src/a.py")
                            + _findings("l-security-r1 | in | x"),
                        ),
                        _dispatch("rev-2"),
                    ]
                )
            ),
            kind="verdict",
        ),
        Case(
            "lenses_witness-problems",
            "lenses",
            "lenses_witness",
            (
                "step/lens-review",
                ROOT,
                _lenses("security", "tests", "errors", "docs"),
                [l_sec],
                {"security": "rev-1", "tests": "rev-2", "errors": "rev-3", "docs": "rev-4"},
                OPENED,
            ),
            setup=_session(
                _View(
                    [
                        _dispatch(
                            "rev-1",
                            returned=_lens_block("tests", "src/a.py")
                            + _findings(
                                "l-security-r1 | out | [tag]", "l-security-r7 | in | absent"
                            ),
                        ),
                        _dispatch("rev-2", returned="nothing"),
                        _dispatch(
                            "rev-3",
                            returned=_lens_block("errors", "src/zz.py")
                            + "```review-findings\n```\n",
                        ),
                        _dispatch(
                            "rev-4",
                            returned="```review-lens\nbroken\n```\n"
                            + _findings("p1-r1 | in | wrong id"),
                        ),
                    ]
                )
            ),
            kind="verdict",
        ),
        Case(
            "lenses_witness-warned-then-refused",
            "lenses",
            "lenses_witness",
            (
                "step/lens-review",
                ROOT,
                two,
                [l_sec],
                {"security": "rev-1", "tests": "rev-2"},
                OPENED,
            ),
            setup=_session(
                _View(
                    [
                        _dispatch(
                            "rev-1",
                            returned=_lens_block("tests", "src/a.py")
                            + _findings("l-security-r1 | in | x"),
                        ),
                        _dispatch("rev-2"),
                    ]
                )
            ),
            kind="verdict",
        ),
        Case(
            "lenses_witness-untracked",
            "lenses",
            "lenses_witness",
            (
                "step/lens-review",
                ROOT,
                _lenses("security", changed=None),
                [],
                {"security": "rev-1"},
                OPENED,
            ),
            setup=_chain(
                _session(
                    _View(
                        [
                            _dispatch(
                                "rev-1",
                                returned=_lens_block("security", "src/a.py", "../etc")
                                + _findings("none"),
                            )
                        ]
                    )
                ),
                lambda mp, _t: _patch(
                    mp,
                    "fr.git.git_answer",
                    lambda *_a: SimpleNamespace(returncode=0, stdout="src/a.py\0src/b.py\0"),
                ),
            ),
            kind="verdict",
        ),
        Case(
            "lenses_witness-ok",
            "lenses",
            "lenses_witness",
            (
                "step/lens-review",
                ROOT,
                two,
                [l_sec],
                {"security": "rev-1", "tests": "rev-2"},
                OPENED,
            ),
            setup=_session(
                _View(
                    [
                        _dispatch(
                            "rev-1",
                            returned=_lens_block("security", "src/a.py")
                            + _findings("l-security-r1 | in | x"),
                        ),
                        _dispatch(
                            "rev-2",
                            returned=_lens_block("tests", "src/a.py", "src/b.py")
                            + _findings("none"),
                        ),
                    ]
                )
            ),
            kind="verdict",
        ),
        # walk
        Case(
            "walk_obligation-no-spec",
            "walk",
            "walk_obligation",
            (DELIVER, ROOT, EMPTY),
            setup=_walk_inputs(spec=None),
            kind="raises",
        ),
        Case(
            "walk_obligation-unreadable",
            "walk",
            "walk_obligation",
            (DELIVER, ROOT, EMPTY),
            setup=_walk_inputs(error=SectionError("## Verification: line [3] unreadable")),
            kind="raises",
        ),
        Case(
            "walk_obligation-unscripted",
            "walk",
            "walk_obligation",
            (DELIVER, ROOT, EMPTY),
            setup=_walk_inputs(rows=(_row("r-1"), _row("r-2", "s.sh"), _row("r-3"), _row("r-4"))),
            kind="raises",
        ),
        Case(
            "walk_obligation-ok",
            "walk",
            "walk_obligation",
            (DELIVER, ROOT, EMPTY),
            setup=_walk_inputs(rows=(_row("r-1", "s.sh"),)),
            kind="raises",
        ),
        Case(
            "verify_walk-none-owed",
            "walk",
            "verify_walk",
            (DELIVER, "none", ROOT, EMPTY, _owed(_row("r-1"), _row("r-2"))),
            {"opened": OPENED},
            kind="verdict",
        ),
        Case(
            "verify_walk-none-owed-run",
            "walk",
            "verify_walk",
            (
                DELIVER,
                "none",
                ROOT,
                EMPTY,
                SimpleNamespace(owed=True, rows=(), run_strategy="agent-walk"),
            ),
            {"opened": OPENED},
            kind="verdict",
        ),
        Case(
            "verify_walk-none",
            "walk",
            "verify_walk",
            (DELIVER, "none", ROOT, EMPTY, _owed()),
            {"opened": OPENED},
            kind="verdict",
        ),
        Case(
            "verify_walk-symlink",
            "walk",
            "verify_walk",
            (DELIVER, "link.log", ROOT, EMPTY, _owed()),
            {"opened": OPENED},
            setup=lambda mp, tmp: _walk_log(mp, tmp, link=True),
            kind="verdict",
        ),
        Case(
            "verify_walk-outside",
            "walk",
            "verify_walk",
            (DELIVER, LOG, ROOT, EMPTY, _owed()),
            {"opened": OPENED},
            setup=_chain(_log(), _walk_log),
            kind="verdict",
        ),
        Case(
            "verify_walk-unparseable",
            "walk",
            "verify_walk",
            (DELIVER, WALK_LOG, ROOT, EMPTY, _owed()),
            {"opened": OPENED},
            setup=_walk_log,
            kind="verdict",
        ),
        Case(
            "verify_walk-problems",
            "walk",
            "verify_walk",
            (DELIVER, WALK_LOG, ROOT, EMPTY, _owed()),
            {"opened": OPENED},
            setup=_chain(_walk_checks(["step 2 [failed]"], []), _code(dirty=("src/x.py",))),
            kind="verdict",
        ),
        Case(
            "verify_walk-other-bytes",
            "walk",
            "verify_walk",
            (DELIVER, WALK_LOG, ROOT, EMPTY, _owed()),
            {"opened": OPENED},
            setup=_chain(_walk_checks([], _ELSEWHEN), _code()),
            kind="verdict",
        ),
        Case(
            "verify_walk-predates",
            "walk",
            "verify_walk",
            (DELIVER, WALK_LOG, ROOT, EMPTY, _owed()),
            {"opened": LATER},
            setup=_chain(_walk_checks([], None), _code()),
            kind="verdict",
        ),
        Case(
            "verify_walk-unobserved",
            "walk",
            "verify_walk",
            (DELIVER, WALK_LOG, ROOT, EMPTY, _owed()),
            {"opened": OPENED},
            setup=_chain(_walk_checks([], None), _code()),
            kind="verdict",
        ),
        Case(
            "verify_walk-ok",
            "walk",
            "verify_walk",
            (DELIVER, WALK_LOG, ROOT, EMPTY, _owed()),
            {"opened": OPENED},
            setup=_chain(_walk_checks([], _AROUND), _code()),
            kind="verdict",
        ),
        # suite: reading a log
        Case(
            "read_suite_log-records-dir",
            "suite",
            "read_suite_log",
            (DELIVER, "docs/superpowers/runs/r1.records/suite.log", ROOT),
            kind="raises",
        ),
        Case(
            "read_suite_log-missing",
            "suite",
            "read_suite_log",
            (DELIVER, "absent.log", ROOT),
            kind="raises",
        ),
        Case(
            "read_suite_log-empty",
            "suite",
            "read_suite_log",
            (DELIVER, LOG, ROOT),
            setup=_log(""),
            kind="raises",
        ),
        Case(
            "read_suite_log-advisory",
            "suite",
            "read_suite_log",
            (DELIVER, LOG, ROOT),
            setup=_log(
                "fr-scope: advisory because -m\nfr-scope: advisory — not deliver evidence\n"
            ),
            kind="raises",
        ),
        Case(
            "read_suite_log-ok",
            "suite",
            "read_suite_log",
            (DELIVER, LOG, ROOT),
            setup=_log(),
            kind="raises",
        ),
        # suite: deliver's fresh log
        Case(
            "verify_tests_log-issued-before",
            "suite",
            "verify_tests_log",
            (DELIVER, LOG, ROOT),
            {"opened": "2026-01-01T12:00:30+00:00"},
            setup=_chain(_log(), _wrote([], _BEFORE_OPEN)),
            kind="verdict",
        ),
        Case(
            "verify_tests_log-nobody",
            "suite",
            "verify_tests_log",
            (DELIVER, LOG, ROOT),
            {"opened": OPENED},
            setup=_chain(_log(), _wrote([], [])),
            kind="verdict",
        ),
        Case(
            "verify_tests_log-other-bytes",
            "suite",
            "verify_tests_log",
            (DELIVER, LOG, ROOT),
            {"opened": OPENED},
            setup=_chain(_log(), _wrote(_ELSEWHEN)),
            kind="verdict",
        ),
        Case(
            "verify_tests_log-predates",
            "suite",
            "verify_tests_log",
            (DELIVER, LOG, ROOT),
            {"opened": LATER},
            setup=_chain(_log(), _wrote(None), _harness("hermes")),
            kind="verdict",
        ),
        Case(
            "verify_tests_log-unobserved-stale",
            "suite",
            "verify_tests_log",
            (DELIVER, LOG, ROOT),
            {"opened": OPENED},
            setup=_chain(_log(), _wrote(None), _harness("hermes"), _code(newest="after")),
            kind="verdict",
        ),
        Case(
            "verify_tests_log-unobserved-ok",
            "suite",
            "verify_tests_log",
            (DELIVER, LOG, ROOT),
            {"opened": OPENED},
            setup=_chain(_log(), _wrote(None), _harness("opencode"), _code()),
            kind="verdict",
        ),
        Case(
            "verify_tests_log-no-code-base",
            "suite",
            "verify_tests_log",
            (DELIVER, LOG, ROOT),
            {"opened": OPENED},
            setup=_chain(_log(), _wrote(_AROUND), _code(error="git [missing]")),
            kind="verdict",
        ),
        Case(
            "verify_tests_log-missing",
            "suite",
            "verify_tests_log",
            (DELIVER, "absent.log", ROOT),
            {"opened": OPENED},
            kind="verdict",
        ),
        Case(
            "verify_tests_log-ok",
            "suite",
            "verify_tests_log",
            (DELIVER, LOG, ROOT),
            {"opened": OPENED},
            setup=_chain(_log(), _wrote(_AROUND), _code()),
            kind="verdict",
        ),
        # suite: a phase's own log
        Case(
            "verify_phase_tests_log-no-holder",
            "suite",
            "verify_phase_tests_log",
            ("phase/1/implement-phase", LOG, ROOT),
            {"opened": OPENED, "holder": "exec-9"},
            setup=_chain(_log(), _harness("claude-code"), _holder([])),
            kind="verdict",
        ),
        Case(
            "verify_phase_tests_log-nobody",
            "suite",
            "verify_phase_tests_log",
            ("phase/1/implement-phase", LOG, ROOT),
            {"opened": OPENED, "holder": "exec-1"},
            setup=_chain(_log(), _harness("claude-code"), _holder([])),
            kind="verdict",
        ),
        Case(
            "verify_phase_tests_log-other-bytes",
            "suite",
            "verify_phase_tests_log",
            ("phase/1/implement-phase", LOG, ROOT),
            {"opened": OPENED, "holder": "exec-1"},
            setup=_chain(_log(), _harness("claude-code"), _holder(_ELSEWHEN)),
            kind="verdict",
        ),
        Case(
            "verify_phase_tests_log-unreadable-child",
            "suite",
            "verify_phase_tests_log",
            ("phase/1/implement-phase", LOG, ROOT),
            {"opened": OPENED, "holder": "exec-1", "record_tree": False},
            setup=_chain(_log(), _harness("claude-code"), _holder(None)),
            kind="verdict",
        ),
        Case(
            "verify_phase_tests_log-predates",
            "suite",
            "verify_phase_tests_log",
            ("phase/1/implement-phase", LOG, ROOT),
            {"opened": LATER, "holder": "exec-1"},
            setup=_chain(_log(), _harness("hermes")),
            kind="verdict",
        ),
        Case(
            "verify_phase_tests_log-unobserved-no-tree",
            "suite",
            "verify_phase_tests_log",
            ("phase/1/implement-phase", LOG, ROOT),
            {"opened": OPENED, "holder": "exec-1", "record_tree": False},
            setup=_chain(_log(), _harness("hermes")),
            kind="verdict",
        ),
        Case(
            "verify_phase_tests_log-no-session",
            "suite",
            "verify_phase_tests_log",
            ("phase/1/implement-phase", LOG, ROOT),
            {"opened": OPENED, "holder": None, "record_tree": False},
            setup=_chain(_log(), _harness("claude-code"), _session(None)),
            kind="verdict",
        ),
        Case(
            "verify_phase_tests_log-no-opening",
            "suite",
            "verify_phase_tests_log",
            ("phase/1/implement-phase", LOG, ROOT),
            {"opened": None, "holder": None, "record_tree": False},
            setup=_chain(_log(), _harness("claude-code"), _session(_View([]))),
            kind="verdict",
        ),
        Case(
            "verify_phase_tests_log-git-error",
            "suite",
            "verify_phase_tests_log",
            ("phase/1/implement-phase", LOG, ROOT),
            {"opened": OPENED, "holder": "exec-1"},
            setup=_chain(
                _log(), _harness("claude-code"), _holder(_AROUND), _code(error="git [gone]")
            ),
            kind="verdict",
        ),
        Case(
            "verify_phase_tests_log-dirty",
            "suite",
            "verify_phase_tests_log",
            ("phase/1/implement-phase", LOG, ROOT),
            {"opened": OPENED, "holder": "exec-1"},
            setup=_chain(
                _log(),
                _harness("claude-code"),
                _holder(_AROUND),
                _code(dirty=("src/a.py", "src/b.py")),
            ),
            kind="verdict",
        ),
        Case(
            "verify_phase_tests_log-dirty-one",
            "suite",
            "verify_phase_tests_log",
            ("phase/1/implement-phase", LOG, ROOT),
            {"opened": OPENED, "holder": "exec-1"},
            setup=_chain(
                _log(), _harness("claude-code"), _holder(_AROUND), _code(dirty=("src/a.py",))
            ),
            kind="verdict",
        ),
        Case(
            "verify_phase_tests_log-stale",
            "suite",
            "verify_phase_tests_log",
            ("phase/1/implement-phase", LOG, ROOT),
            {"opened": OPENED, "holder": "exec-1"},
            setup=_chain(_log(), _harness("claude-code"), _holder(_AROUND), _code(newest="after")),
            kind="verdict",
        ),
        Case(
            "verify_phase_tests_log-ok",
            "suite",
            "verify_phase_tests_log",
            ("phase/1/implement-phase", LOG, ROOT),
            {"opened": OPENED, "holder": "exec-1"},
            setup=_chain(_log(), _harness("claude-code"), _holder(_AROUND), _code()),
            kind="verdict",
        ),
        # suite: reuse and local stamps
        Case(
            "reuse_tests_witness-none",
            "suite",
            "reuse_tests_witness",
            (DELIVER, ROOT, EMPTY),
            kind="verdict",
        ),
        Case(
            "reuse_tests_witness-git-error",
            "suite",
            "reuse_tests_witness",
            (DELIVER, ROOT, _reused_state()),
            setup=_code(error="git [gone]"),
            kind="verdict",
        ),
        Case(
            "reuse_tests_witness-changed",
            "suite",
            "reuse_tests_witness",
            (DELIVER, ROOT, _reused_state()),
            setup=_code(tree="tree-2", since=["src/a.py", "src/b.py"]),
            kind="verdict",
        ),
        Case(
            "reuse_tests_witness-changed-one",
            "suite",
            "reuse_tests_witness",
            (DELIVER, ROOT, _reused_state()),
            setup=_code(tree="tree-2", since=["src/a.py"]),
            kind="verdict",
        ),
        Case(
            "reuse_tests_witness-not-in-history",
            "suite",
            "reuse_tests_witness",
            (DELIVER, ROOT, _reused_state()),
            setup=_code(tree="tree-2", since=None),
            kind="verdict",
        ),
        Case(
            "reuse_tests_witness-unobserved",
            "suite",
            "reuse_tests_witness",
            (DELIVER, ROOT, _reused_state(unobserved=True)),
            setup=_code(),
            kind="verdict",
        ),
        Case(
            "reuse_tests_witness-ok",
            "suite",
            "reuse_tests_witness",
            (DELIVER, ROOT, _reused_state()),
            setup=_code(),
            kind="verdict",
        ),
        Case(
            "local_stamp_witness-reused-no-tree",
            "suite",
            "local_stamp_witness",
            (ROOT, "reused:phase/1/implement-phase:suite.log@abcdef012345"),
        ),
        Case(
            "local_stamp_witness-reused",
            "suite",
            "local_stamp_witness",
            (ROOT, "reused:phase/1/implement-phase:suite.log@abcdef012345;tree=tree-1"),
        ),
        Case("local_stamp_witness-none", "suite", "local_stamp_witness", (ROOT, None)),
        Case("local_stamp_witness-ci", "suite", "local_stamp_witness", (ROOT, "ci")),
        Case(
            "local_stamp_witness-git-error",
            "suite",
            "local_stamp_witness",
            (ROOT, "suite.log@abcdef012345"),
            setup=_code(error="git [gone]"),
        ),
        Case(
            "local_stamp_witness-dirty",
            "suite",
            "local_stamp_witness",
            (ROOT, "suite.log@abcdef012345"),
            setup=_code(dirty=("src/a.py", "src/b.py")),
        ),
        Case(
            "local_stamp_witness-ok",
            "suite",
            "local_stamp_witness",
            (ROOT, "suite.log@abcdef012345"),
            setup=_code(),
        ),
        # ci
        *_ci_cases(),
        # derived: single phase and visual
        Case(
            "single_phase_witness-no-plan",
            "derived",
            "single_phase_witness",
            (DELIVER, ROOT, EMPTY, {}),
            kind="verdict",
        ),
        Case(
            "single_phase_witness-unreadable",
            "derived",
            "single_phase_witness",
            (DELIVER, ROOT, EMPTY, {"plan": "docs/p"}),
            setup=_tags(AdoptError("plan docs/p [has no] phases")),
            kind="verdict",
        ),
        Case(
            "single_phase_witness-two",
            "derived",
            "single_phase_witness",
            (DELIVER, ROOT, PLANNED, {}),
            setup=_tags({1: "agentic", 2: "agentic", 3: "manual"}),
            kind="verdict",
        ),
        Case(
            "single_phase_witness-none",
            "derived",
            "single_phase_witness",
            (DELIVER, ROOT, PLANNED, {}),
            setup=_tags({1: "manual"}),
            kind="verdict",
        ),
        Case(
            "single_phase_witness-ok",
            "derived",
            "single_phase_witness",
            (DELIVER, ROOT, PLANNED, {}),
            setup=_tags({1: "manual", 2: "agentic"}),
            kind="verdict",
        ),
        Case(
            "visual_witness-refused",
            "derived",
            "visual_witness",
            ("phase/1/implement-phase", ROOT, PLANNED, VISUAL_STEP),
            {"phase": 1, "entries": None, "holder": "exec-1", "reviewer": None, "since": OPENED},
            setup=_visual(refused=["visual: refused [x]", "row r-1 has no shot"]),
            kind="verdict",
        ),
        Case(
            "visual_witness-unobserved",
            "derived",
            "visual_witness",
            ("phase/1/implement-phase", ROOT, PLANNED, VISUAL_STEP),
            {"phase": 1, "entries": None, "holder": "exec-1", "reviewer": None, "since": OPENED},
            setup=_visual(unobserved=True),
            kind="verdict",
        ),
        Case(
            "visual_witness-ok",
            "derived",
            "visual_witness",
            ("phase/1/implement-phase", ROOT, PLANNED, VISUAL_STEP),
            {"phase": None, "entries": None, "holder": None, "reviewer": None, "since": OPENED},
            setup=_visual(),
            kind="verdict",
        ),
        # owed
        Case(
            "debt_phrase-bare",
            "owed",
            "debt_phrase",
            (StepRecord(state="done"), DELIVER, ("tests",)),
        ),
        Case(
            "unevidenced_units-no-manifest",
            "owed",
            "unevidenced_units",
            (ROOT, EMPTY),
            setup=lambda mp, _t: _patch(
                mp, "fr.run.steps.resolve_manifest_checked_schema", _raising(OSError("gone"))
            ),
        ),
    ]


CASES = _all_cases()


def _resolve(value: object, tmp: Path) -> object:
    if value is ROOT:
        return tmp
    if value is WALK_LOG:
        return _walk_path(tmp)
    if isinstance(value, T):
        return TARGET()(value.scope, value.phase, value.feature)
    if isinstance(value, list):
        return [_resolve(v, tmp) for v in value]
    return value


def _jsonable(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, bytes):
        return value.decode()
    return value


def _normalize(text: str, tmp: Path) -> str:
    for spelled in sorted({str(tmp.resolve()), str(tmp)}, key=len, reverse=True):
        text = text.replace(spelled, "<ROOT>")
    return text


def run_case(
    mp: pytest.MonkeyPatch, case: Case, tmp: Path, call: Callable[[Callable[..., Any]], object]
) -> tuple[str, int, str]:
    """`(stderr, exit code, returned value and noted gates as JSON)` of one call."""
    from fr.run.unobserved import take_unobserved

    console = recording_console()
    mp.setattr(run_cmd, "err_console", console)
    mp.chdir(tmp)
    if case.setup is not None:
        case.setup(mp, tmp)
    take_unobserved()
    result: object = None
    try:
        result = call(None)  # type: ignore[arg-type]
        code = 0
    except typer.Exit as e:
        code = e.exit_code
    except Exception as e:  # noqa: BLE001 — a raised error is part of what is captured
        result = f"raised {type(e).__name__}: {e}"
        code = 0
    noted = take_unobserved()
    file = console.file
    assert isinstance(file, StringIO)
    shown = json.dumps(
        {"returned": _jsonable(result), "unobserved": noted},
        indent=2,
        sort_keys=True,
        default=str,
    )
    return _normalize(file.getvalue(), tmp), code, _normalize(shown, tmp) + "\n"


def _exit_codes() -> dict[str, int]:
    loaded: dict[str, int] = json.loads((FIXTURES / "exit-codes.json").read_text(encoding="utf-8"))
    return loaded


def test_every_case_has_a_capture() -> None:
    assert sorted(_exit_codes()) == sorted(c.name for c in CASES)


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_the_moved_verifiers_print_and_return_the_captured_bytes(
    case: Case, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def call(_: object) -> object:
        fn = getattr(importlib.import_module(f"fr.run.evidence.{case.module}"), case.fn)
        kwargs = {k: _resolve(v, tmp_path) for k, v in case.kwargs.items()}
        if case.warn:
            kwargs["warn"] = run_cmd._say
        args = [_resolve(a, tmp_path) for a in case.args]
        if case.kind == "verdict":
            return run_cmd._settle(fn(*args, **kwargs))
        if case.kind == "raises":
            with run_cmd._refusals():
                return fn(*args, **kwargs)
        return fn(*args, **kwargs)

    stderr, code, shown = run_case(monkeypatch, case, tmp_path, call)
    assert stderr == (FIXTURES / f"{case.name}.txt").read_text(encoding="utf-8")
    assert code == _exit_codes()[case.name]
    assert shown == (FIXTURES / f"{case.name}.json").read_text(encoding="utf-8")


# --- gh#768: two derived refusals through `fr run resolve` ---------------------------------


def two_derived_refusals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, int]:
    """`deliver` resolved with no base for proportionality or docs: `(output, exit code)`."""
    from fr import gh
    from fr.record.pr_body import REQUIRED_SECTIONS

    from tests.unit.record_support import RUN, fr, write_record
    from tests.unit.test_deliver_pr_body import PR, _at_deliver

    body = "\n\n".join(f"{h}\n\nNone." for h in REQUIRED_SECTIONS)
    monkeypatch.setattr(gh, "view_pr_body", lambda ref, *, cwd=None: body)
    root = _at_deliver(tmp_path)
    monkeypatch.setattr(
        "fr.run.evidence.derived.proportionality_base",
        lambda _root: (None, "no base for this test"),
    )
    monkeypatch.setattr("fr.docs.load.load_config", lambda _root: object())
    (root / "suite.log").write_text("n passed\n")
    data = {
        "run": RUN, "step": "deliver", "outcome": "done",
        "emitted": {"pr": PR}, "evidence": {"tests": "suite.log"},
    }  # fmt: skip
    rec = write_record(root, data)
    out = fr(root, ["run", "resolve", RUN, "--step", "deliver", "--record", str(rec)])
    return _normalize(out.output, tmp_path), out.exit_code


@pytest.mark.own_artifacts
def test_two_derived_refusals_print_the_summary_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output, code = two_derived_refusals(tmp_path, monkeypatch)
    assert output == (FIXTURES / "resolve-two-derived-refusals.txt").read_text(encoding="utf-8")
    assert code == 2
    assert "2 derived witnesses failed: proportionality, docs" in output
