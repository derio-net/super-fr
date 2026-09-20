"""`fr.run.legacy.v4_to_v5` — the run cursor's first body-rewriting migration.

Spec §4.F. Both prior `run` migrations were stamp-only; this one moves data,
and a body rewrite can half-write in a way a stamp cannot. So it is built as a
**pure dict -> dict function** with no I/O and no clock: everything below runs
it on the CAPTURED cursors of `tests/fixtures/run_cursors/` and on nothing
else, except where a case does not occur in any real file and is stated as
such.

Nothing here wires it up. Phase 2 adds no migration, moves no
`current_version`, and touches no stamp.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.run.legacy import RunMigrationError, v4_to_v5
from fr.run.model import UnitRecord

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "run_cursors"

HOLDER = "v4/2026-09-20-feat-phase-holder-identity.yaml"
CLUSTER = "v4/2026-09-20-fix-fr-run-cursor-cluster.yaml"
INFLIGHT = "v2/2026-09-20-journal-require-reviews-v2.yaml"
MEASURED = "v3/2026-09-20-feat-bounded-executor-handoff.yaml"
SMALLEST = "v1/2026-09-09-feat-issue-464.yaml"


def _captured() -> list[Path]:
    found = sorted(FIXTURES.glob("v*/*.yaml"))
    assert found, "no captured cursors — the glob is wrong, not the fixtures"
    return found


def _load(name: str) -> dict[str, Any]:
    data = yaml.safe_load((FIXTURES / name).read_text())
    assert isinstance(data, dict)
    return data


def _units(out: dict[str, Any], step_id: str) -> dict[str, Any]:
    return out["steps"][step_id].get("units") or {}


# ------------------------------------------------------- items -> unit state


def test_every_item_becomes_a_units_entry_carrying_its_state() -> None:
    before = _load(HOLDER)
    out = v4_to_v5(before)
    units = _units(out, "implement")
    for key, state in before["steps"]["implement"]["items"].items():
        assert units[key]["state"] == state


def test_the_items_map_is_gone_from_every_step() -> None:
    out = v4_to_v5(_load(HOLDER))
    assert all("items" not in record for record in out["steps"].values())


def test_a_manual_marker_keeps_its_state_and_gets_no_attempts() -> None:
    """gh#496's `phase/<n>: manual`. The whole point of the marker is that
    nothing was ever dispatched, so synthesizing an attempt for it would claim
    a dispatch that never happened."""
    out = v4_to_v5(_load(CLUSTER))
    marker = _units(out, "implement")["phase/7"]
    assert marker == {"state": "manual"}


# --------------------------------------------------- dispatch -> attempts


def test_every_dispatch_record_becomes_an_attempt_in_order() -> None:
    before = _load(HOLDER)
    out = v4_to_v5(before)
    units = _units(out, "implement")
    for key, attempts in before["steps"]["implement"]["dispatch"].items():
        got = units[key]["attempts"]
        assert [a["dispatched"] for a in got] == [a["dispatched"] for a in attempts]
        # every field the record carried survives verbatim; only cost is added
        for was, now in zip(attempts, got, strict=True):
            assert {k: v for k, v in now.items() if k not in ("estimate", "measured")} == was


def test_the_dispatch_map_is_gone_from_every_step() -> None:
    out = v4_to_v5(_load(HOLDER))
    assert all("dispatch" not in record for record in out["steps"].values())


def test_a_flat_steps_unit_carries_no_state() -> None:
    """§4.B: `step/<step-id>` has no `state`, because `StepRecord.state` is
    that fact's one home and this spec exists because facts with two homes
    drift. `HOLDER`'s `deliver` step is a captured example."""
    out = v4_to_v5(_load(HOLDER))
    unit = _units(out, "deliver")["step/deliver"]
    assert "state" not in unit
    assert len(unit["attempts"]) == 1


def test_a_running_step_with_no_dispatch_records_no_units_at_all() -> None:
    """The u1 recordless shape, captured: gh#517's in-flight `deliver:
    running` with no dispatch map. There is nothing to convert, so nothing is
    invented — `running` stays the STEP's state and the unit does not exist."""
    out = v4_to_v5(_load(INFLIGHT))
    assert out["steps"]["deliver"]["state"] == "running"
    assert "units" not in out["steps"]["deliver"]


# ----------------------------------------------- accounting -> the attempt


def test_accounting_splits_into_estimate_on_the_last_attempt() -> None:
    before = _load(MEASURED)
    out = v4_to_v5(before)
    for step_id, record in out["steps"].items():
        for key, unit in (record.get("units") or {}).items():
            snapshot = before.get("accounting", {}).get(key)
            if snapshot is None:
                continue
            estimate = unit["attempts"][-1]["estimate"]
            assert estimate["handoff_chars"] == snapshot["handoff_chars"]
            assert estimate["journal_entries"] == snapshot["journal_entries"]
            assert estimate["spec_bytes"] == snapshot["spec_bytes"]
            assert "at" not in estimate  # the attempt's `dispatched` is that moment
            assert step_id  # every accounted unit belongs to a step


def test_a_real_measurement_lands_beside_the_estimate() -> None:
    before = _load(MEASURED)
    out = v4_to_v5(before)
    measured_keys = [
        key for key, snap in before["accounting"].items() if snap.get("input_tokens") is not None
    ]
    assert measured_keys, "this fixture's value is that it carries real measurements"
    for key in measured_keys:
        unit = next(
            (record.get("units") or {})[key]
            for record in out["steps"].values()
            if key in (record.get("units") or {})
        )
        measured = unit["attempts"][-1]["measured"]
        assert measured == {
            name: before["accounting"][key][name]
            for name in (
                "input_tokens",
                "cache_creation_input_tokens",
                "cache_read_input_tokens",
                "output_tokens",
            )
        }


def test_an_unmeasured_unit_gets_no_measured_key_rather_than_zeros() -> None:
    out = v4_to_v5(_load(CLUSTER))
    for unit in _units(out, "implement").values():
        for attempt in unit.get("attempts", []):
            assert "measured" not in attempt


def test_accounting_with_no_dispatch_synthesizes_one_identityless_attempt() -> None:
    """§4.F point 3, and it is the MAJORITY case: `CLUSTER` is a pre-#508
    cursor with accounting and no dispatch map at all. `dispatched` is the
    snapshot's `at` — when fr briefed the unit, and the only fact fr has —
    and nothing else is filled in."""
    before = _load(CLUSTER)
    assert all("dispatch" not in r for r in before["steps"].values())
    out = v4_to_v5(before)
    unit = _units(out, "implement")["phase/1/implement-phase"]
    (attempt,) = unit["attempts"]
    assert attempt["dispatched"] == before["accounting"]["phase/1/implement-phase"]["at"]
    assert set(attempt) == {"dispatched", "estimate"}
    assert attempt["estimate"]["handoff_chars"] == 2369


def test_a_unit_with_a_state_but_neither_cost_nor_dispatch_gets_no_attempt() -> None:
    """Nothing is invented for a unit fr has no record of briefing."""
    before = _load(CLUSTER)
    key = "phase/1/review-phase"
    assert key not in before["accounting"]
    out = v4_to_v5(before)
    assert _units(out, "implement")[key] == {"state": "done"}


def test_the_top_level_accounting_map_is_dropped() -> None:
    for path in _captured():
        out = v4_to_v5(yaml.safe_load(path.read_text()))
        assert "accounting" not in out, path


# ------------------------------------------------------------- refusals


def test_a_partial_measurement_is_refused_and_names_the_missing_fields() -> None:
    """§4.F's first edge. It does not occur in any captured cursor — gh#514's
    validator already calls it invalid — so it is induced by DELETING one
    figure from a captured one, never by authoring a cursor."""
    data = _load(MEASURED)
    key = next(k for k, s in data["accounting"].items() if s.get("input_tokens") is not None)
    del data["accounting"][key]["output_tokens"]
    with pytest.raises(RunMigrationError) as excinfo:
        v4_to_v5(data)
    assert "output_tokens" in str(excinfo.value)
    assert key in str(excinfo.value)


def test_accounting_for_a_unit_no_step_records_is_refused() -> None:
    """A figure with nowhere to go is not dropped to make the file
    convertible. No captured cursor has one — every accounting key in all
    eight is owned by a step — so this too is induced from a capture."""
    data = _load(CLUSTER)
    data["accounting"]["phase/99/implement-phase"] = {"at": "2026-09-20T13:30:36+00:00"}
    with pytest.raises(RunMigrationError) as excinfo:
        v4_to_v5(data)
    assert "phase/99/implement-phase" in str(excinfo.value)


def test_accounting_with_no_at_and_no_attempt_is_refused() -> None:
    """There is neither an attempt to hang the cost on nor a moment to
    synthesize one from."""
    data = _load(CLUSTER)
    del data["accounting"]["phase/1/implement-phase"]["at"]
    with pytest.raises(RunMigrationError) as excinfo:
        v4_to_v5(data)
    assert "phase/1/implement-phase" in str(excinfo.value)


def test_a_refused_cursor_is_left_byte_identical() -> None:
    """§4.F: "a cursor the migration cannot fully convert is left
    byte-identical". The function is pure, so the input it was handed is
    unchanged — there is no half-written state to write out."""
    data = _load(CLUSTER)
    data["accounting"]["phase/99/implement-phase"] = {"at": "2026-09-20T13:30:36+00:00"}
    snapshot = yaml.safe_dump(data, sort_keys=False)
    with pytest.raises(RunMigrationError):
        v4_to_v5(data)
    assert yaml.safe_dump(data, sort_keys=False) == snapshot


def test_the_input_is_never_mutated_on_success_either() -> None:
    data = _load(HOLDER)
    snapshot = yaml.safe_dump(data, sort_keys=False)
    v4_to_v5(data)
    assert yaml.safe_dump(data, sort_keys=False) == snapshot


# ------------------------------------------------- idempotence & coverage


@pytest.mark.parametrize("path", _captured(), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_it_is_idempotent_on_its_own_output(path: Path) -> None:
    once = v4_to_v5(yaml.safe_load(path.read_text()))
    assert v4_to_v5(once) == once


@pytest.mark.parametrize("path", _captured(), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_nothing_is_dropped_and_nothing_invented(path: Path) -> None:
    """The property check (P2.T3.S3): for every unit key in the input, its
    state, its attempt count and every cost figure are recoverable from the
    output — with exactly one documented exception, the synthesized attempt."""
    before = yaml.safe_load(path.read_text())
    after = v4_to_v5(before)

    for step_id, record in before["steps"].items():
        units = (after["steps"][step_id].get("units")) or {}
        for key, state in (record.get("items") or {}).items():
            assert units[key]["state"] == state, (path, key)
        for key, attempts in (record.get("dispatch") or {}).items():
            got = units[key]["attempts"]
            assert len(got) == len(attempts), (path, key)
            for was, now in zip(attempts, got, strict=True):
                # every recorded field survives; only cost is added
                assert {k: v for k, v in now.items() if k not in ("estimate", "measured")} == was

    for key, snapshot in (before.get("accounting") or {}).items():
        unit = next(
            (r.get("units") or {})[key]
            for r in after["steps"].values()
            if key in (r.get("units") or {})
        )
        last = unit["attempts"][-1]
        for name in (
            "journal_entries",
            "journal_lines",
            "handoff_chars",
            "spec_bytes",
            "plan_bytes",
        ):
            assert last["estimate"][name] == snapshot.get(name, 0), (path, key, name)
        if snapshot.get("input_tokens") is not None:
            assert last["measured"]["input_tokens"] == snapshot["input_tokens"], (path, key)


@pytest.mark.parametrize("path", _captured(), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_every_unit_key_in_the_output_was_a_unit_key_in_the_input(path: Path) -> None:
    """The other direction: no unit is conjured. A key in the output came from
    `items`, from `dispatch`, or from nowhere — and nowhere is a bug."""
    before = yaml.safe_load(path.read_text())
    after = v4_to_v5(before)
    for step_id, record in after["steps"].items():
        was = {
            *((before["steps"][step_id].get("items")) or {}),
            *((before["steps"][step_id].get("dispatch")) or {}),
        }
        assert set(record.get("units") or {}) == was, (path, step_id)


def test_a_cursor_with_no_units_at_all_survives_untouched_but_for_accounting() -> None:
    before = _load(SMALLEST)
    after = v4_to_v5(before)
    for step_id, record in before["steps"].items():
        expected = {k: v for k, v in record.items() if k not in ("items", "dispatch")}
        got = {k: v for k, v in after["steps"][step_id].items() if k != "units"}
        assert got == expected


def test_the_stamp_is_not_touched() -> None:
    """The runner writes the stamp; a body rewrite that also stamped would be
    two facts in one function."""
    assert v4_to_v5(_load(HOLDER))["schema_version"] == 4
    assert "schema_version" not in v4_to_v5(_load(SMALLEST))


@pytest.mark.parametrize("path", _captured(), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_every_converted_unit_parses_as_the_v5_model(path: Path) -> None:
    """The output is not merely a differently-shaped dict — every unit it
    produces validates as `UnitRecord`, `Attempt`, `ContextEstimate` and
    `MeasuredTokens`, all `extra="forbid"`.

    `RunState` itself is NOT swapped in phase 2 (nothing is wired), so this
    validates the units directly. Phase 3 replaces it with a whole-cursor
    parse, and that is exactly the assertion that will then have to hold.
    """
    after = v4_to_v5(yaml.safe_load(path.read_text()))
    seen = 0
    for record in after["steps"].values():
        for key, unit in (record.get("units") or {}).items():
            parsed = UnitRecord.model_validate(unit)
            seen += 1
            if key.startswith("step/"):
                assert parsed.state is None, key
            else:
                assert parsed.state is not None, key
            if parsed.state == "manual":
                assert parsed.attempts == (), key
    assert seen or "units" not in str(after), path
