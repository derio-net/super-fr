"""The `run` kind's version-3 migration — measured tokens (spec §5.C).

`PhaseAccounting` gaining four token fields is a shape change for the same
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
from fr.run.model import MEASURED_TOKEN_FIELDS, MEASURED_TOKENS_SCHEMA_VERSION, parse_run_state

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


def test_the_run_kind_is_stamped_for_measured_tokens() -> None:
    """The stamp lives in the registry and only there; the model declares only
    which version FIRST carried the fields, which is a different statement."""
    assert artifact_kind("run").current_version >= MEASURED_TOKENS_SCHEMA_VERSION
    assert MEASURED_TOKENS_SCHEMA_VERSION == 3


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


def test_migrating_a_v2_run_file_stamps_it_and_rewrites_no_body(tmp_path: Path) -> None:
    """The four fields are absent-by-default on every v2 cursor, and absent is
    exactly what they mean there ("nobody measured this unit"), so there is
    nothing to translate: the migration moves the stamp and touches no other
    byte of an operator's cursor."""
    path = _run_file(tmp_path)
    before = path.read_text()

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    kind = artifact_kind("run")
    assert kind.read_version(path) == kind.current_version
    after = path.read_text()
    # Derived, not hardcoded: this asserted `schema_version: 3` and broke the
    # moment a later migration moved the kind to 4 — the stamp a full run
    # lands on is `current_version`, whatever that is today.
    assert after.replace(f"schema_version: {kind.current_version}", "schema_version: 2") == before
    state = parse_run_state(after)
    assert state.accounting is not None
    snap = state.accounting["phase/1/code"]
    assert snap.journal_entries == 2
    assert snap.measured_tokens is None, "a migrated cursor must not gain a fake measurement"


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


def _stamped(text: str, version: int) -> str:
    return text.replace("schema_version: 2", f"schema_version: {version}")


def test_a_cursor_carrying_a_full_measurement_is_valid(tmp_path: Path) -> None:
    path = _run_file(tmp_path, _stamped(_V2_RUN, 3) + _MEASURED)

    assert artifact_kind("run").validate(path) == []


@pytest.mark.parametrize("dropped", MEASURED_TOKEN_FIELDS)
def test_a_half_recorded_measurement_is_a_structural_problem(tmp_path: Path, dropped: str) -> None:
    """A measurement is atomic: the reader writes all four or none. Three of
    four is not a smaller honest number — it is a sum that reads as one."""
    partial = "".join(line for line in _MEASURED.splitlines(keepends=True) if dropped not in line)
    path = _run_file(tmp_path, _stamped(_V2_RUN, 3) + partial)

    problems = artifact_kind("run").validate(path)

    assert problems, f"dropping {dropped} went unreported"
    assert any(dropped in problem and "phase/1/code" in problem for problem in problems)


def test_a_cursor_that_carries_measurements_but_declares_an_older_shape_is_reported(
    tmp_path: Path,
) -> None:
    """The stamp is the promise a reader relies on. A cursor with v3 content
    under a v2 stamp would never be migrated again and would raise in any fr
    that believed the stamp."""
    path = _run_file(tmp_path, _V2_RUN + _MEASURED)

    problems = artifact_kind("run").validate(path)

    assert any("schema_version" in problem for problem in problems)


def test_the_validator_still_reports_the_older_problems(tmp_path: Path) -> None:
    """Non-regression: the new checks are additions, not a replacement."""
    liar = _run_file(tmp_path, _V2_RUN.replace("cursor: implement", "cursor: ghost"))

    assert any("ghost" in problem for problem in artifact_kind("run").validate(liar))
