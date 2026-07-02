"""`fr.parser.parse_strict` — the parity-contract entry point (cncd §3.3).

`parse()` stays lenient for plans in the wild (missing `_prose.md` →
`prose=None`; phase-number gaps tolerated) so the bridge keeps skipping
gracefully. `parse_strict()` layers the two folder-level invariants the
cross-language fixtures corpus enforces on cncd's Go parser:

  - `_prose.md` is mandatory (every fr authoring path writes it), and
  - phase numbers are contiguous 1..N.

Everything else (schema shape, P.T.S ids, state key-set equality,
`extra="forbid"`) is already enforced by the pydantic models via
`parse()`.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

MINIMAL = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
MULTI_PHASE = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"


def test_parse_strict_accepts_valid_folder():
    from fr.parser import parse_strict

    plan = parse_strict(MINIMAL)
    assert plan.meta.plan == "2026-05-09-fixture-minimal"
    assert plan.prose is not None


def test_parse_strict_matches_parse_output():
    """On a valid folder, parse_strict returns exactly what parse returns."""
    from fr.parser import parse, parse_strict

    assert parse_strict(MINIMAL) == parse(MINIMAL)


def test_parse_strict_rejects_missing_prose(tmp_path):
    from fr.parser import PlanSchemaError, parse_strict

    dest = tmp_path / "no_prose"
    shutil.copytree(MINIMAL, dest)
    (dest / "_prose.md").unlink()
    with pytest.raises(PlanSchemaError, match="_prose.md"):
        parse_strict(dest)


def test_parse_strict_rejects_noncontiguous_phases(tmp_path):
    """Phases 1 and 3 with no 2 → strict failure naming the gap."""
    from fr.parser import PlanSchemaError, parse_strict

    dest = tmp_path / "gap"
    shutil.copytree(MINIMAL, dest)
    phase3 = (dest / "01.yaml").read_text().replace("number: 1", "number: 3").replace("P1.", "P3.")
    (dest / "03.yaml").write_text(phase3)
    with pytest.raises(PlanSchemaError, match="contiguous"):
        parse_strict(dest)


def test_parse_strict_rejects_zero_phases(tmp_path):
    """A folder with `_meta.yaml` + `_prose.md` but no phase files is not a
    dispatchable plan — strict mode refuses it."""
    from fr.parser import PlanSchemaError, parse_strict

    dest = tmp_path / "empty"
    shutil.copytree(MINIMAL, dest)
    (dest / "01.yaml").unlink()
    with pytest.raises(PlanSchemaError, match="no phase files"):
        parse_strict(dest)


def test_parse_strict_accepts_multi_phase_gapless_control(tmp_path):
    """Control: contiguous 1..N passes strict. The multi_phase fixture has a
    deliberate 1,2,10 gap, so renumber 10 → 3 to build the gapless copy."""
    from fr.parser import parse_strict

    dest = tmp_path / "gapless"
    shutil.copytree(MULTI_PHASE, dest)
    phase3 = (
        (dest / "10.yaml").read_text().replace("number: 10", "number: 3").replace("P10.", "P3.")
    )
    (dest / "10.yaml").unlink()
    (dest / "03.yaml").write_text(phase3)
    plan = parse_strict(dest)
    assert [p.phase.number for p in plan.phases] == [1, 2, 3]


def test_plain_parse_stays_lenient(tmp_path):
    """Regression guard: parse() must NOT grow the strict checks — the wild
    plans that lack _prose.md or have gaps must keep parsing."""
    from fr.parser import parse

    dest = tmp_path / "lenient"
    shutil.copytree(MINIMAL, dest)
    (dest / "_prose.md").unlink()
    assert parse(dest).prose is None
    # the deliberate 1,2,10 gap fixture parses fine
    assert [p.phase.number for p in parse(MULTI_PHASE).phases] == [1, 2, 10]
