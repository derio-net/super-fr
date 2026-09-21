"""Tripwire: production code reads cost per ATTEMPT, never per unit.

`fr.run.units` still exposes four per-unit cost readers — `estimate_of`,
`measured_of`, `estimated_at`, `accounted_keys`. They answer for a unit's LAST
attempt only. That is a fine seam for tests that want "the cost of the unit I
just dispatched", and it is exactly the shape of the defect the unit-record
work fixed: before it, a redispatch kept an abandoned agent's identity and
discarded its cost, because cost was one number per unit while attempts were a
list (spec `2026-09-20-unit-record-unification-design.md` §1.B).

After phase 4 nothing under `packages/*/src` calls them — status, check,
resolve and claim all iterate attempts. This test keeps it that way: a new
caller in `src` would quietly reintroduce "the unit has one cost", and no
other test would notice, because for a never-redispatched unit the two
readings agree.

The scan carries its own POSITIVE CONTROL. Twice on this branch a
verification silently matched nothing and read as a pass (`git grep -E` has no
`\\b`; a mutation regex that never applied), so a scan that finds nothing is
only trusted here after the same scan has been shown to find something.
"""

from __future__ import annotations

import re
from pathlib import Path

PER_UNIT_COST_READERS = ("estimate_of", "measured_of", "estimated_at", "accounted_keys")
_CALL = re.compile(r"\bunits\.(" + "|".join(PER_UNIT_COST_READERS) + r")\s*\(")

REPO_ROOT = Path(__file__).resolve().parents[2]


def _calls_in(text: str) -> list[str]:
    return [m.group(1) for m in _CALL.finditer(text)]


def test_the_scan_can_actually_find_a_call() -> None:
    """Positive control — if this fails, the tripwire below proves nothing."""
    assert _calls_in("cost = units.estimate_of(state, key)") == ["estimate_of"]
    assert _calls_in("x = units.measured_of (state, key)") == ["measured_of"]
    assert _calls_in("units.last_attempt(record, key)") == []


def test_no_production_module_reads_cost_per_unit() -> None:
    offenders: list[str] = []
    sources = sorted((REPO_ROOT / "packages").glob("*/src/**/*.py"))
    assert sources, "found no production sources — the glob is wrong, not the code clean"
    for path in sources:
        if path.name == "units.py" and path.parent.name == "run":
            continue  # their definitions live here
        for name in _calls_in(path.read_text()):
            offenders.append(f"{path.relative_to(REPO_ROOT)}: units.{name}(…)")
    assert not offenders, (
        "production code must read cost per ATTEMPT (units.attempts / "
        "units.accounted_attempts), never per unit — a per-unit read sees only the "
        "LAST attempt and silently drops an abandoned attempt's cost:\n  " + "\n  ".join(offenders)
    )
