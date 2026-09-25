"""The `run` kind's 5 -> 6 migration and the shape it admits:
`StepRecord.main_session` (spec `2026-09-24-fr-goal-scope-proportion-cost-design.md`
§D).

A new optional field on an `extra="forbid"` model that a released fr reads is
a shape change (`.claude/rules/artifact-versioning.md`), so it ships a stamp
bump, a registered migration and validator support together. The change is
additive, so the hop is stamp-only and rewrites no body — which the captured v5
cursor below proves byte for byte.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.artifacts import ARTIFACT_KINDS, MIGRATIONS, run_migrations
from fr.artifacts.structure import validate_run
from fr.run.legacy import MainSessionUsageV6 as MainSessionUsage
from fr.run.legacy import StepRecordV6 as StepRecord
from fr.run.legacy import parse_run_state_v6
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
V5 = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "run_cursors"
    / "v5"
    / ("2026-09-23-fix-457-uninstall-rules.yaml")
)

USAGE = {
    "input_tokens": 10,
    "cache_creation_input_tokens": 200,
    "cache_read_input_tokens": 3000,
    "output_tokens": 40,
    "turns": 3,
    "sessions": 1,
}


# --- (a) the model --------------------------------------------------------


@pytest.mark.parametrize("missing", sorted(USAGE))
def test_every_figure_but_cost_is_required(missing: str) -> None:
    """Atomic like `MeasuredTokens`: a partial main-session measurement cannot
    be constructed, so "not measured" is the absence of the whole record."""
    with pytest.raises(ValidationError):
        MainSessionUsage(**{k: v for k, v in USAGE.items() if k != missing})


def test_cost_is_optional_and_the_record_is_closed_and_frozen() -> None:
    usage = MainSessionUsage(**USAGE)
    assert usage.cost_usd is None
    with pytest.raises(ValidationError):
        MainSessionUsage(**USAGE, reasoning_tokens=1)
    with pytest.raises(ValidationError):
        usage.turns = 4  # type: ignore[misc]


def test_a_step_record_round_trips_main_session() -> None:
    record = StepRecord(
        state="done", at="2026-09-24T10:00:00+00:00", main_session={**USAGE, "cost_usd": 0.5}
    )
    again = StepRecord.model_validate(record.model_dump(exclude_none=True))
    assert again == record
    assert again.main_session == MainSessionUsage(**USAGE, cost_usd=0.5)


# --- (c) the migration ----------------------------------------------------


def test_the_five_to_six_hop_is_registered() -> None:
    hops = [m for m in MIGRATIONS.schema_migrations("run") if m.from_version == 5]
    assert [(m.from_version, m.to_version) for m in hops] == [(5, 6)]


def test_a_captured_v5_cursor_migrates_to_six_changing_only_the_stamp(tmp_path: Path) -> None:
    """The 5 -> 6 hop alone is stamp-only: its `fn` leaves the body byte-identical
    (the chain then carries the cursor on to 7, which is `test_migration_run_v7`'s)."""
    path = tmp_path / "docs" / "superpowers" / "runs" / V5.name
    path.parent.mkdir(parents=True)
    before = V5.read_bytes()
    path.write_bytes(before)
    (hop,) = [m for m in MIGRATIONS.schema_migrations("run") if m.from_version == 5]

    assert hop.fn(path) is None
    assert path.read_bytes() == before

    report = run_migrations(tmp_path, dry_run=False)
    assert report.ok, [(f.path.name, f.error) for f in report.failed]
    assert ARTIFACT_KINDS["run"].read_version(path) == ARTIFACT_KINDS["run"].current_version
    assert validate_run(path) == []


def test_an_unreadable_v5_cursor_is_refused_and_left_on_five(tmp_path: Path) -> None:
    path = tmp_path / "docs" / "superpowers" / "runs" / "broken.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("schema_version: 5\nrun: broken\ncursor: a\n")  # missing required fields

    report = run_migrations(tmp_path, dry_run=False)

    assert [f.path for f in report.failed] == [path]
    assert ARTIFACT_KINDS["run"].read_version(path) == 5


# --- (d) the validator ----------------------------------------------------


def _with_main_session(tmp_path: Path, stamp: int) -> Path:
    text = V5.read_text().replace("schema_version: 5\n", f"schema_version: {stamp}\n", 1)
    text = text.replace(
        "  brainstorm:\n    state: done\n",
        "  brainstorm:\n    state: done\n    main_session:\n"
        + "".join(f"      {k}: {v}\n" for k, v in USAGE.items()),
        1,
    )
    path = tmp_path / f"v{stamp}.yaml"
    path.write_text(text)
    assert parse_run_state_v6(text).steps["brainstorm"].main_session is not None
    return path


def test_the_frozen_reader_accepts_main_session_on_a_v6_cursor(tmp_path: Path) -> None:
    parse_run_state_v6(_with_main_session(tmp_path, 6).read_text())


def test_the_validator_rejects_main_session_once_run_7_removed_it(tmp_path: Path) -> None:
    """Run 7 moved `main_session` into the usage file; the live model — and so
    `fr validate artifacts` — no longer knows it."""
    problems = validate_run(_with_main_session(tmp_path, 7))
    assert any("main_session" in p for p in problems), problems
