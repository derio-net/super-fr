"""The `run` kind's 10 -> 11 migration: `RunState.issue` and `RunState.pr`
(spec 2026-11-04-repo-feature-settings R12, R14).

Stamp-only, following 9 -> 10 (`fr.artifacts.run_fr_version`): an old cursor
gets neither field, which reads as "no issue recorded" (the without-issue
commit template applies) and "no PR opened through `fr pr create`". A body that
does not read as v10 under the live model is refused and left byte-identical;
a body already wholly v11 (the crash window) lets the runner finish the stamp.
"""

from __future__ import annotations

from pathlib import Path

from fr.artifacts import MIGRATIONS, run_migrations
from fr.artifacts.registry import ARTIFACT_KINDS, read_version
from fr.artifacts.structure import validate_run
from fr.run.model import RunState, load_run_state, parse_run_state

from tests.unit.test_run_cli import _CLI_ONLY_SHAPE, _invoke, _repo, _write_shape

V10 = (
    "schema_version: 10\nrun: r1\nworkflow: fr-goal@1\nbranch: b\n"
    "started: '2026-11-07T00:00:00Z'\ncursor: implement\n"
    "steps:\n"
    "  implement:\n"
    "    state: running\n"
    "    units:\n"
    "      phase/1/implement-phase:\n"
    "        state: done\n"
    "        attempts:\n"
    "        - dispatched: '2026-11-07T00:01:00Z'\n"
    "          agent: a1\n"
    "          agent_type: super-fr:fr-phase-executor\n"
    "          harness: claude-code\n"
    "          model: claude-opus-5\n"
    "          tier: hard\n"
    "          returned: '2026-11-07T00:30:00Z'\n"
    "          outcome: done\n"
    "fr_version: 6.1.0\n"
)


def _seed(root: Path, text: str) -> Path:
    path = root / "docs" / "superpowers" / "runs" / "r1.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_the_run_kind_is_at_version_eleven() -> None:
    assert ARTIFACT_KINDS["run"].current_version == 11


def test_the_hop_is_registered_and_moves_ten_to_eleven() -> None:
    chain = MIGRATIONS.chain("run", 10)
    assert [(m.from_version, m.to_version) for m in chain] == [(10, 11)]


def test_a_v10_cursor_is_stamped_eleven_and_its_body_is_untouched(tmp_path: Path) -> None:
    assert parse_run_state(V10).fr_version == "6.1.0"  # the fixture is a real v10 body
    cursor = _seed(tmp_path, V10)

    report = run_migrations(tmp_path, dry_run=False)

    assert report.failed == (), report.failed
    assert read_version("run", cursor) == 11
    assert cursor.read_text() == V10.replace("schema_version: 10", "schema_version: 11")
    state = parse_run_state(cursor.read_text())
    assert state.issue is None and state.pr is None, "an old run records neither"


def test_a_cursor_that_does_not_read_as_v10_is_refused_byte_identical(tmp_path: Path) -> None:
    broken = V10 + "nonsense_key: 1\n"
    cursor = _seed(tmp_path, broken)

    report = run_migrations(tmp_path, dry_run=False)

    assert [f.path for f in report.failed] == [cursor]
    assert "version-10" in report.failed[0].error
    assert cursor.read_bytes() == broken.encode()


def test_a_body_already_wholly_v11_lets_the_runner_finish_the_stamp(tmp_path: Path) -> None:
    text = V10 + "issue: 123\n"
    cursor = _seed(tmp_path, text)

    report = run_migrations(tmp_path, dry_run=False)

    assert report.failed == (), report.failed
    assert read_version("run", cursor) == 11
    assert parse_run_state(cursor.read_text()).issue == 123


def test_issue_and_pr_round_trip_on_the_model() -> None:
    state = parse_run_state(
        V10.replace("schema_version: 10", "schema_version: 11")
        + "issue: 123\npr: https://example.com/o/r/pull/7\n"
    )
    assert state.issue == 123
    assert state.pr == "https://example.com/o/r/pull/7"
    again = RunState.model_validate(state.model_dump())
    assert again == state


def test_a_v11_cursor_passes_the_structure_validator(tmp_path: Path) -> None:
    cursor = _seed(tmp_path, V10.replace("schema_version: 10", "schema_version: 11") + "issue: 5\n")
    assert validate_run(cursor) == []


def test_fr_run_start_records_the_issue(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)

    result = _invoke(
        repo,
        shipped,
        ["run", "start", "cli-only", "--branch", "b", "--run-id", "r1", "--issue", "123"],
    )

    assert result.exit_code == 0, result.output
    state = load_run_state(repo, "r1")
    assert state.issue == 123
    assert state.schema_version == 11


def test_fr_run_start_without_issue_records_none(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)

    result = _invoke(repo, shipped, ["run", "start", "cli-only", "--branch", "b", "--run-id", "r1"])

    assert result.exit_code == 0, result.output
    assert load_run_state(repo, "r1").issue is None


def test_fr_run_start_refuses_a_non_positive_issue(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE)

    result = _invoke(
        repo,
        shipped,
        ["run", "start", "cli-only", "--branch", "b", "--run-id", "r1", "--issue", "0"],
    )

    assert result.exit_code == 2, result.output
