"""`fr.run.legacy` — the frozen v4 reader, and the tripwire that keeps it frozen.

Spec §4.F, "the legacy reader — a flaw this spec's first draft had". Every run
migration so far parses the file it is about to stamp with the LIVE model, and
that was sound only because every change was additive: the live model stayed a
superset of every old shape. The 4 -> 5 rewrite REMOVES `items`, `dispatch` and
`accounting` from an `extra="forbid"` model, so a v2 cursor carrying `items`
would stop parsing and the chain `2 -> 3 -> 4 -> 5` would refuse every old
cursor at its FIRST hop — stranding exactly the files the framework exists to
carry.

So the prior shape is frozen here, and the proof that the freeze is worth
anything is that it reads every captured cursor, v1 through v4.
"""

from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import pytest
from fr.run import legacy
from fr.run.model import RunStateError

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "run_cursors"


def _captured() -> list[Path]:
    # v1-v4 only: the frozen reader (and the 4 -> 5 rewrite) are defined over
    # the shapes BEFORE `units`; `v5/` feeds the 5 -> 6 hop instead.
    found = sorted(FIXTURES.glob("v[1-4]/*.yaml"))
    assert found, "no captured cursors — the glob is wrong, not the fixtures"
    return found


# ------------------------------------------------- it reads what fr wrote


@pytest.mark.parametrize("path", _captured(), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_the_frozen_reader_parses_every_captured_cursor(path: Path) -> None:
    state = legacy.parse_run_state_v4(path.read_text())
    assert state.run
    assert state.cursor in state.steps


def test_a_v1_cursor_has_no_stamp_at_all_and_still_reads_as_version_one() -> None:
    """`v1` means the key did not exist, not `schema_version: 1`."""
    text = (FIXTURES / "v1" / "2026-09-09-feat-issue-464.yaml").read_text()
    assert "schema_version" not in text
    assert legacy.parse_run_state_v4(text).schema_version == 1


def test_it_reads_all_three_maps_a_v4_cursor_can_carry() -> None:
    state = legacy.parse_run_state_v4(
        (FIXTURES / "v4" / "2026-09-20-feat-phase-holder-identity.yaml").read_text()
    )
    implement = state.steps["implement"]
    assert implement.items["phase/1/implement-phase"] == "done"
    assert implement.dispatch["phase/3/implement-phase"][0].agent == "a5dbd5f0e9bdf3362"
    assert state.accounting["phase/1/implement-phase"].handoff_chars > 0
    # …and a flat `kind: agent` step's unit, which lives only in `dispatch`
    assert state.steps["deliver"].items is None
    assert list(state.steps["deliver"].dispatch) == ["step/deliver"]


def test_it_reads_the_manual_marker_gh496_writes() -> None:
    state = legacy.parse_run_state_v4(
        (FIXTURES / "v4" / "2026-09-20-fix-fr-run-cursor-cluster.yaml").read_text()
    )
    assert state.steps["implement"].items["phase/7"] == "manual"


def test_it_refuses_what_it_cannot_read_as_one_exception_type() -> None:
    with pytest.raises(RunStateError):
        legacy.parse_run_state_v4("steps: [not, a, mapping]")
    with pytest.raises(RunStateError):
        legacy.parse_run_state_v4("- a\n- b\n")
    with pytest.raises(RunStateError):
        legacy.parse_run_state_v4("run: x\n  bad: indent\n")


def test_it_refuses_a_key_no_version_up_to_four_ever_had() -> None:
    """Still `extra="forbid"`: a superset of v1-v4 is not a superset of
    everything. An unrecognised key is a bug report, not data to drop."""
    text = (FIXTURES / "v4" / "2026-09-20-fix-fr-run-cursor-cluster.yaml").read_text()
    with pytest.raises(RunStateError):
        legacy.parse_run_state_v4(text + "\nunits: {}\n")


# --------------------------------------------------- and it stays frozen


FROZEN_CLASSES = ("DispatchRecordV4", "StepRecordV4", "PhaseAccountingV4", "RunStateV4")
FROZEN_CLASSES_V6 = (
    "ContextEstimateV6",
    "MeasuredTokensV6",
    "MainSessionUsageV6",
    "AttemptV6",
    "UnitRecordV6",
    "StepRecordV6",
    "RunStateV6",
)


def test_the_frozen_classes_are_exactly_these_four() -> None:
    """A fifth frozen class means the v4 shape grew one, which is impossible:
    v4 is history. It means somebody edited the reader."""
    declared = tuple(
        name for name, obj in vars(legacy).items() if inspect.isclass(obj) and name.endswith("V4")
    )
    assert sorted(declared) == sorted(FROZEN_CLASSES)


def test_the_frozen_v6_classes_are_exactly_these() -> None:
    """The v5/v6 shape, frozen when run 6 -> 7 removed `estimate`, `measured`
    and `main_session` (spec 2026-09-25-lean-cost-aware-process §5.B.4)."""
    declared = tuple(
        name for name, obj in vars(legacy).items() if inspect.isclass(obj) and name.endswith("V6")
    )
    assert sorted(declared) == sorted(FROZEN_CLASSES_V6)


def test_the_frozen_v6_reader_has_not_been_edited() -> None:
    drifted = {
        name
        for name in FROZEN_CLASSES_V6
        if hashlib.sha256(inspect.getsource(getattr(legacy, name)).encode()).hexdigest()
        != legacy.FROZEN_CLASS_SHA256[name]
    }
    assert not drifted, f"{sorted(drifted)} changed; freeze a `…V7` beside them instead"


@pytest.mark.parametrize(
    "path",
    sorted(FIXTURES.glob("v[56]/*.yaml")),
    ids=lambda p: f"{p.parent.name}/{p.name}",
)
def test_the_frozen_v6_reader_parses_every_captured_v5_and_v6_cursor(path: Path) -> None:
    state = legacy.parse_run_state_v6(path.read_text())
    assert state.cursor in state.steps


def test_the_frozen_reader_has_not_been_edited() -> None:
    """The tripwire. `fr/run/legacy.py`'s models are a CAPTURE of a shape that
    shipped, not code under maintenance: a v4 cursor on someone's branch is
    already written, and editing the reader changes what fr believes those
    bytes mean. A removal from THIS shape freezes a `…V5` beside it; it never
    edits this one.
    """
    drifted = {
        name: hashlib.sha256(inspect.getsource(getattr(legacy, name)).encode()).hexdigest()
        for name in FROZEN_CLASSES
        if hashlib.sha256(inspect.getsource(getattr(legacy, name)).encode()).hexdigest()
        != legacy.FROZEN_CLASS_SHA256[name]
    }
    assert not drifted, (
        f"{sorted(drifted)} changed. `fr.run.legacy` is FROZEN — it is how fr reads "
        "run cursors that are already written, on branches nobody has merged. If the "
        "shape must change, freeze the NEW one as a `…V5` beside it and leave this "
        f"alone. Recorded hashes: {legacy.FROZEN_CLASS_SHA256}; actual: {drifted}"
    )


def test_the_frozen_vocabularies_are_pinned_too() -> None:
    """The `Literal`s are inlined rather than imported from `fr.run.model` for
    exactly this reason: the live vocabularies may grow, and a frozen reader
    that followed them would stop being a reader of v4."""
    assert legacy.STEP_STATES_V4 == ("pending", "running", "done", "failed", "blocked")
    assert legacy.DISPATCH_OUTCOMES_V4 == ("done", "failed", "abandoned")
    assert legacy.ANSWERED_BY_V4 == ("operator", "agent")
