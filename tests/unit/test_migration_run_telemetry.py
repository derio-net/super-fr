"""The `run` kind's version-3 migration — measured tokens (spec §5.C).

**Read this file with the 4 -> 5 flip in mind.** It was written when 2 -> 3 was
the newest hop and the accounting snapshot lived in a top-level `accounting`
map; that map is gone from the live model
(`2026-09-20-unit-record-unification-design.md` §4.A). The 2 -> 3 hop itself
is unchanged and still stamp-only — but a v2 cursor now rides the WHOLE chain,
and the last hop rewrites the body, so what is asserted below is where the
snapshot ENDS UP, not that no byte moved.

The accounting snapshot gaining four token fields is a shape change for the same
reason `answered_by` was: `RunState` is `extra="forbid"`-closed, so an fr that
does not know the keys RAISES rather than ignoring them. "Optional and
defaulted" buys nothing against a closed-world reader — the rule's own worked
example is this exact kind, and this file pins all three obligations
`.claude/rules/artifact-versioning.md` attaches: the stamp bump (in
`fr.artifacts.registry` and nowhere else), a REGISTERED migration reached
through the package import, and the structure validator.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from fr.artifacts import MIGRATIONS, artifact_kind, run_migrations
from fr.artifacts.registry import PRE_FRAMEWORK_VERSION
from fr.run import units
from fr.run.legacy import MEASURED_TOKEN_FIELDS_V4, MeasuredTokensV6
from fr.run.model import UNIT_RECORD_SCHEMA_VERSION, parse_run_state
from fr.usage.file import load_usage, usage_path

_V2_RUN = """\
schema_version: 2
run: r1
workflow: fr-goal@1
branch: feat/x
started: '2026-09-20T09:00:00Z'
cursor: implement
steps:
  implement:
    state: running
    items:
      phase/1/code: running
accounting:
  phase/1/code:
    at: '2026-09-20T09:00:01Z'
    journal_entries: 2
    journal_lines: 40
    handoff_chars: 900
    spec_bytes: 200
    plan_bytes: 300
"""

_MEASURED = """\
    input_tokens: 1
    cache_creation_input_tokens: 1000
    cache_read_input_tokens: 20000
    output_tokens: 50
"""


def _run_file(root: Path, text: str = _V2_RUN, stem: str = "r1") -> Path:
    path = root / "docs" / "superpowers" / "runs" / f"{stem}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_the_four_figures_are_the_same_four_on_both_sides_of_the_flip() -> None:
    """What "a measurement" consists of is stated twice on purpose — frozen in
    the v4 legacy reader, and in the frozen v5/v6 `MeasuredTokensV6` — and the
    two must agree or the 4 -> 5 rewrite would carry a figure the next hop refuses."""
    assert set(MEASURED_TOKEN_FIELDS_V4) == set(MeasuredTokensV6.model_fields)


def test_the_chain_reaches_the_current_version_from_both_older_versions() -> None:
    kind = artifact_kind("run")
    for start in (PRE_FRAMEWORK_VERSION, 2):
        chain = MIGRATIONS.chain("run", start)
        assert chain, f"no registered migration moves a version-{start} run file"
        assert chain[-1].to_version == kind.current_version


def test_registration_rides_the_package_import_not_the_callers_memory() -> None:
    """A migration nobody imports never runs."""
    code = "import fr.artifacts as a;print(a.MIGRATIONS.chain('run', 2)[-1].to_version)"
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert out == str(artifact_kind("run").current_version)


def test_migrating_a_v2_run_file_carries_its_snapshot_onto_an_attempt(tmp_path: Path) -> None:
    """2 -> 3 itself translates nothing: the four fields are absent-by-default
    on every v2 cursor, and absent is exactly what they mean there ("nobody
    measured this unit"). The chain's LAST hop then moves the snapshot onto
    the unit — and must still not invent a measurement on the way."""
    path = _run_file(tmp_path)

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    kind = artifact_kind("run")
    assert kind.read_version(path) == kind.current_version
    state = parse_run_state(path.read_text())
    assert units.unit_state(state.steps["implement"], "phase/1/code") == "running"
    # run 7 moved the snapshot into the usage file — and still no measurement
    usage = load_usage(usage_path(tmp_path, "r1"))
    assert usage is not None
    (entry,) = usage.captures[0].sessions
    assert entry.briefs == {"phase/1/code": 900}
    assert entry.models == {}, "a migrated cursor must not gain a fake measurement"


def test_migrating_is_idempotent(tmp_path: Path) -> None:
    path = _run_file(tmp_path)
    run_migrations(tmp_path, dry_run=False)
    once = path.read_text()

    report = run_migrations(tmp_path, dry_run=False)

    assert report.applied == ()
    assert path.read_text() == once


def test_a_run_file_that_is_not_run_state_is_reported_never_stamped(tmp_path: Path) -> None:
    """Same one real decision as the v1->v2 migration, and the same answer:
    a cursor fr cannot read is not certified as a shape it never understood."""
    broken = _run_file(tmp_path, "schema_version: 2\nrun: r2\ncursor: a\n", stem="r2")
    healthy = _run_file(tmp_path)

    report = run_migrations(tmp_path, dry_run=False)

    assert [f.path for f in report.failed] == [broken]
    assert yaml.safe_load(broken.read_text()).get("schema_version") == 2
    assert artifact_kind("run").read_version(healthy) == artifact_kind("run").current_version


# --- the structure validator, obligation 3 -------------------------------
#
# The validator reads the LIVE shape only. What it said about a v3 cursor's
# `accounting` map is now said in two other places, both stronger: a partial
# measurement cannot be REPRESENTED (`MeasuredTokens` requires all four), and a
# v4 file carrying one is refused by the migration and left byte-identical.


def _stamped(text: str, version: int) -> str:
    return text.replace("schema_version: 2", f"schema_version: {version}")


def _migrated(root: Path, text: str) -> Path:
    path = _run_file(root, text)
    report = run_migrations(root, dry_run=False)
    assert report.ok, report.failed
    return path


def test_a_cursor_carrying_a_full_measurement_migrates_and_is_valid(tmp_path: Path) -> None:
    path = _migrated(tmp_path, _stamped(_V2_RUN, 3) + _MEASURED)

    assert artifact_kind("run").validate(path) == []
    usage = load_usage(usage_path(tmp_path, "r1"))
    assert usage is not None
    (figures,) = usage.captures[0].sessions[0].models.values()
    assert (figures.input, figures.cache_write, figures.cache_read, figures.output) == (
        1,
        1000,
        20000,
        50,
    )


@pytest.mark.parametrize("dropped", MEASURED_TOKEN_FIELDS_V4)
def test_a_half_recorded_measurement_never_reaches_the_new_shape(
    tmp_path: Path, dropped: str
) -> None:
    """A measurement is atomic: the reader writes all four or none. Three of
    four is not a smaller honest number — it is a sum that reads as one. The
    migration refuses it BY NAME and leaves the cursor exactly as it was."""
    partial = "".join(line for line in _MEASURED.splitlines(keepends=True) if dropped not in line)
    path = _run_file(tmp_path, _stamped(_V2_RUN, 4) + partial)
    before = path.read_bytes()

    report = run_migrations(tmp_path, dry_run=False)

    assert [f.path for f in report.failed] == [path], f"dropping {dropped} went unreported"
    assert dropped in report.failed[0].error and "phase/1/code" in report.failed[0].error
    assert path.read_bytes() == before


@pytest.mark.parametrize("dropped", MEASURED_TOKEN_FIELDS_V4)
def test_a_partial_measurement_cannot_be_written_in_the_new_shape_either(dropped: str) -> None:
    figures = {name: 1 for name in MEASURED_TOKEN_FIELDS_V4 if name != dropped}
    with pytest.raises(ValueError, match=dropped):
        MeasuredTokensV6(**figures)


def test_a_cursor_in_the_new_shape_that_declares_an_older_one_is_reported(
    tmp_path: Path,
) -> None:
    """The stamp is the promise a reader relies on. A v5 body under a v4 stamp
    — what the 4 -> 5 migration's crash window leaves — raises in any fr that
    believes the stamp, so the validator says so rather than letting the file
    pass as merely "stale"."""
    path = _migrated(tmp_path, _V2_RUN)
    current = artifact_kind("run").current_version
    path.write_text(
        path.read_text().replace(
            f"schema_version: {current}", f"schema_version: {UNIT_RECORD_SCHEMA_VERSION - 1}"
        )
    )

    from fr.artifacts.structure import validate_run

    assert any("schema_version" in problem for problem in validate_run(path))


def test_the_validator_still_reports_the_older_problems(tmp_path: Path) -> None:
    """Non-regression: the new checks are additions, not a replacement."""
    liar = _migrated(tmp_path, _V2_RUN)
    liar.write_text(liar.read_text().replace("cursor: implement", "cursor: ghost"))

    assert any("ghost" in problem for problem in artifact_kind("run").validate(liar))
