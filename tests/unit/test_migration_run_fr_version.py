"""The `run` kind's 9 -> 10 migration: `RunState.fr_version` (spec
2026-10-07-cloud-triage §G, R16; Test Plan 11).

Stamp-only, following 7 -> 8 (`fr.artifacts.run_driver`) and 8 -> 9
(`fr.artifacts.run_bound_model`): an old cursor gets no field, which R17 reads
as "no recorded version". A body that does not read as v9 under the live model
is refused and left byte-identical; a body already wholly v10 (the crash
window between the body and the stamp) lets the runner finish the stamp.
"""

from __future__ import annotations

from pathlib import Path

import fr
from fr.artifacts import MIGRATIONS, run_migrations
from fr.artifacts.registry import ARTIFACT_KINDS, read_version
from fr.artifacts.structure import validate_run
from fr.run.model import load_run_state, parse_run_state

from tests.unit.test_run_cli import _CLI_ONLY_SHAPE, _invoke, _repo, _write_shape

V9 = (
    "schema_version: 9\nrun: r1\nworkflow: fr-goal@1\nbranch: b\n"
    "started: '2026-10-08T00:00:00Z'\ncursor: implement\n"
    "steps:\n"
    "  implement:\n"
    "    state: running\n"
    "    units:\n"
    "      phase/1/implement-phase:\n"
    "        state: done\n"
    "        attempts:\n"
    "        - dispatched: '2026-10-08T00:01:00Z'\n"
    "          agent: a1\n"
    "          agent_type: super-fr:fr-phase-executor\n"
    "          harness: claude-code\n"
    "          model: claude-opus-5\n"
    "          tier: hard\n"
    "          returned: '2026-10-08T00:30:00Z'\n"
    "          outcome: done\n"
)


def _seed(root: Path, text: str) -> Path:
    path = root / "docs" / "superpowers" / "runs" / "r1.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_the_run_kind_is_at_version_ten() -> None:
    assert ARTIFACT_KINDS["run"].current_version == 10


def test_the_hop_is_registered_and_moves_nine_to_ten() -> None:
    chain = MIGRATIONS.chain("run", 9)
    assert [(m.from_version, m.to_version) for m in chain] == [(9, 10)]


def test_a_v9_cursor_is_stamped_ten_and_its_body_is_untouched(tmp_path: Path) -> None:
    assert parse_run_state(V9).steps["implement"].units  # the fixture is a real v9 body
    cursor = _seed(tmp_path, V9)

    report = run_migrations(tmp_path, dry_run=False)

    assert report.failed == (), report.failed
    assert read_version("run", cursor) == 10
    assert cursor.read_text() == V9.replace("schema_version: 9", "schema_version: 10")
    assert parse_run_state(cursor.read_text()).fr_version is None, "an old run records none"


def test_a_cursor_that_does_not_read_as_v9_is_refused_unchanged(tmp_path: Path) -> None:
    broken = V9 + "nonsense_key: 1\n"
    cursor = _seed(tmp_path, broken)

    report = run_migrations(tmp_path, dry_run=False)

    assert [f.path for f in report.failed] == [cursor]
    assert "version-9" in report.failed[0].error
    assert cursor.read_text() == broken


def test_a_body_already_wholly_v10_lets_the_runner_finish_the_stamp(tmp_path: Path) -> None:
    """The crash window: a v10 body (it carries `fr_version`) under a 9 stamp."""
    text = V9 + "fr_version: 5.17.1\n"
    cursor = _seed(tmp_path, text)

    report = run_migrations(tmp_path, dry_run=False)

    assert report.failed == (), report.failed
    assert read_version("run", cursor) == 10
    assert parse_run_state(cursor.read_text()).fr_version == "5.17.1"


def test_a_v10_cursor_passes_the_structure_validator(tmp_path: Path) -> None:
    cursor = _seed(
        tmp_path, V9.replace("schema_version: 9", "schema_version: 10") + "fr_version: 6.0.0\n"
    )
    assert validate_run(cursor) == []


def test_fr_run_start_records_the_running_frs_version(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)

    result = _invoke(repo, shipped, ["run", "start", "cli-only", "--branch", "b", "--run-id", "r1"])

    assert result.exit_code == 0, result.output
    state = load_run_state(repo, "r1")
    assert state.fr_version == fr.__version__
    assert state.schema_version == 10
