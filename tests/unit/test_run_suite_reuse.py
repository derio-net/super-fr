"""`deliver` reuses a verified phase suite log on an unchanged code tree —
spec 2026-09-29-fr-goal-light-path §D (R6).

Task 1 pins the pure helpers in `fr.run.code_tree`: the code tree is
`git ls-tree -r HEAD` without fr's artifact trees (`docs/superpowers/`,
`docs/acceptance/`), so the bookkeeping `resolve` writes between the suite run
and `deliver` never reads as a code change.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from fr.run.code_tree import (
    FR_ARTIFACT_PREFIXES,
    code_tree,
    dirty_code_paths,
    newest_code_mtime,
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout


def _commit_all(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)


def _plain_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    (repo / "src").mkdir()
    (repo / "src" / "x.py").write_text("x = 1\n")
    (repo / "docs" / "superpowers" / "runs").mkdir(parents=True)
    (repo / "docs" / "superpowers" / "runs" / "r1.yaml").write_text("run: r1\n")
    _commit_all(repo, "seed")
    return repo


def _set_mtime(path: Path, at: float) -> None:
    os.utime(path, (at, at))


def test_the_excluded_prefixes_are_fr_artifact_trees() -> None:
    assert FR_ARTIFACT_PREFIXES == ("docs/superpowers/", "docs/acceptance/")


def test_code_tree_is_stable_across_a_bookkeeping_only_commit(tmp_path: Path) -> None:
    repo = _plain_repo(tmp_path)
    before = code_tree(repo)
    (repo / "docs" / "superpowers" / "runs" / "r1.yaml").write_text("run: r1\nstep: x\n")
    (repo / "docs" / "acceptance").mkdir()
    (repo / "docs" / "acceptance" / "matrix.yaml").write_text("rows: []\n")
    _commit_all(repo, "bookkeeping")

    assert code_tree(repo) == before
    assert len(before) == 64


def test_code_tree_changes_with_a_code_commit(tmp_path: Path) -> None:
    repo = _plain_repo(tmp_path)
    before = code_tree(repo)
    (repo / "src" / "x.py").write_text("x = 2\n")
    _commit_all(repo, "code")

    assert code_tree(repo) != before


def test_code_tree_takes_a_revision(tmp_path: Path) -> None:
    repo = _plain_repo(tmp_path)
    seed = _git(repo, "rev-parse", "HEAD").strip()
    before = code_tree(repo)
    (repo / "src" / "x.py").write_text("x = 2\n")
    _commit_all(repo, "code")

    assert code_tree(repo, seed) == before


def test_code_tree_ignores_uncommitted_changes(tmp_path: Path) -> None:
    repo = _plain_repo(tmp_path)
    before = code_tree(repo)
    (repo / "src" / "x.py").write_text("x = 3\n")

    assert code_tree(repo) == before


def test_dirty_code_paths_lists_only_uncommitted_code(tmp_path: Path) -> None:
    repo = _plain_repo(tmp_path)
    assert dirty_code_paths(repo) == []
    (repo / "src" / "x.py").write_text("x = 3\n")
    (repo / "src" / "new.py").write_text("y = 1\n")
    (repo / "docs" / "superpowers" / "runs" / "r1.yaml").write_text("changed\n")
    (repo / "docs" / "superpowers" / "runs" / "r2.yaml").write_text("new\n")

    assert dirty_code_paths(repo) == ["src/new.py", "src/x.py"]


def test_newest_code_mtime_spans_committed_and_uncommitted_changes(tmp_path: Path) -> None:
    repo = _plain_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD").strip()
    (repo / "src" / "y.py").write_text("y = 1\n")
    _commit_all(repo, "code")
    (repo / "src" / "z.py").write_text("z = 1\n")
    _set_mtime(repo / "src" / "x.py", 5_000)  # unchanged since base: not counted
    _set_mtime(repo / "src" / "y.py", 1_000)
    _set_mtime(repo / "src" / "z.py", 2_000)
    _set_mtime(repo / "docs" / "superpowers" / "runs" / "r1.yaml", 9_000)

    assert newest_code_mtime(repo, base) == (2_000.0, "src/z.py")

    _set_mtime(repo / "src" / "y.py", 3_000)
    assert newest_code_mtime(repo, base) == (3_000.0, "src/y.py")


def test_newest_code_mtime_is_none_when_no_code_changed(tmp_path: Path) -> None:
    repo = _plain_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD").strip()
    (repo / "docs" / "superpowers" / "runs" / "r1.yaml").write_text("changed\n")

    assert newest_code_mtime(repo, base) is None


def test_newest_code_mtime_without_a_base_counts_every_code_path(tmp_path: Path) -> None:
    """No merge-base (no remote default branch): fail toward stricter — every
    tracked code path counts, so a log must be newer than all of them."""
    repo = _plain_repo(tmp_path)
    _set_mtime(repo / "src" / "x.py", 4_000)

    assert newest_code_mtime(repo, None) == (4_000.0, "src/x.py")


def test_newest_code_mtime_skips_ignored_paths(tmp_path: Path) -> None:
    """The log itself may sit in the worktree; it is not code it tested."""
    repo = _plain_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD").strip()
    (repo / "suite.log").write_text("ok\n")

    assert newest_code_mtime(repo, base, ignore=[repo / "suite.log"]) is None


# --- Task 2: offered `tests` evidence on a phase unit -------------------------
#
# `code` below is the phase executor's member; it declares NO evidence, the way
# the shipped `implement-phase` declares none but the derived `visual`. `tests`
# is OFFERED evidence there: accepted undeclared, never owed.

import json  # noqa: E402

from fr.run import units  # noqa: E402
from fr.run.model import load_run_state  # noqa: E402

from tests.unit.test_run_cli import (  # noqa: E402
    _invoke,
    _invoke_as_harness,
    _invoke_measurable,
    _repo,
    _squash,
    _started_grouped_with_plan,
    _write_shape,
)
from tests.unit.test_run_evidence import _journal  # noqa: E402
from tests.unit.test_run_evidence_separate_context import _SHAPE, _later, _soon  # noqa: E402
from tests.unit.transcript_sessions import (  # noqa: E402
    AGENT_ID,
    BASH,
    CAPTURED_LOG,
    SUBAGENT,
    copy_of,
    dispatched_at,
    ran_at,
    records,
    write_agent,
)

_CODE = ["run", "resolve", "r1", "--step", "code", "--item", "phase/1", "--state", "done"]


def _at_code(tmp_path: Path, *, root: Path | None = None, session: str = "s-c") -> tuple:
    """`phase/1/code` opened. Returns `(repo, shipped, dispatched)`."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _journal(repo)
    advance = ["run", "advance", "r1"]
    run = (
        _invoke(repo, shipped, advance)
        if root is None
        else _invoke_measurable(repo, shipped, advance, root, session)
    )
    assert run.exit_code == 0, run.output
    attempt = units.last_attempt(load_run_state(repo, "r1"), "phase/1/code")
    assert attempt is not None
    return repo, shipped, attempt.dispatched


def _executor_ran(root: Path, session_id: str, opened: str, log: Path | None) -> None:
    """This session dispatched executor `AGENT_ID` after `opened`; its subagent
    transcript holds the captured `Bash` suite call writing `log` (or no Bash
    call at all when `log` is None). Captured rows, re-keyed only."""
    session = dispatched_at(root, _later(opened), session_id=session_id, usage={})
    rows = copy_of(records(SUBAGENT))
    if log is not None:
        call, result = copy_of(records(BASH))
        call["timestamp"] = _later(opened)
        result["timestamp"] = _soon()
        block = call["message"]["content"][0]
        block["input"]["command"] = block["input"]["command"].replace(CAPTURED_LOG, str(log))
        for row in (call, result):
            row["isSidechain"] = True
            row["agentId"] = AGENT_ID
        rows += [call, result]
    write_agent(session, rows=rows)


def _code_evidence(repo: Path) -> dict[str, str]:
    return units.evidence_of(load_run_state(repo, "r1").steps["implement"], "phase/1/code")


def _tree(repo: Path) -> str:
    from fr.run.code_tree import code_tree

    return code_tree(repo)


def test_a_phase_unit_without_tests_resolves_as_today(tmp_path: Path) -> None:
    repo, shipped, _ = _at_code(tmp_path)

    result = _invoke(repo, shipped, [*_CODE, "--agent", "impl-1"])

    assert result.exit_code == 0, result.output
    assert "tests" not in _code_evidence(repo)


def test_a_log_the_executor_wrote_is_recorded_with_its_tree(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped, opened = _at_code(tmp_path, root=root)
    log = tmp_path / "suite.log"
    log.write_text("4051 passed\n")
    _executor_ran(root, "s-c", opened, log)

    result = _invoke_measurable(
        repo, shipped, [*_CODE, "--agent", AGENT_ID, "--evidence", f"tests={log}"], root, "s-c"
    )

    assert result.exit_code == 0, result.output
    witness = _code_evidence(repo)["tests"]
    shown, _, tree = witness.partition(";tree=")
    assert shown.startswith("suite.log@") and len(shown) == len("suite.log@") + 12
    assert tree == _tree(repo)
    assert "unobserved" not in _code_evidence(repo)


def test_an_inline_unit_is_witnessed_by_the_main_thread(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped, opened = _at_code(tmp_path, root=root)
    log = tmp_path / "suite.log"
    log.write_text("4051 passed\n")
    ran_at(root, _later(opened), session_id="s-c", until=_soon(), log=log)

    result = _invoke_measurable(repo, shipped, [*_CODE, "--evidence", f"tests={log}"], root, "s-c")

    assert result.exit_code == 0, result.output
    assert ";tree=" in _code_evidence(repo)["tests"]


def test_a_log_no_command_of_the_executor_wrote_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped, opened = _at_code(tmp_path, root=root)
    log = tmp_path / "suite.log"
    log.write_text("4051 passed\n")
    _executor_ran(root, "s-c", opened, None)

    result = _invoke_measurable(
        repo, shipped, [*_CODE, "--agent", AGENT_ID, "--evidence", f"tests={log}"], root, "s-c"
    )

    assert result.exit_code == 2, result.output
    assert "no command of the unit's holder wrote it" in _squash(result.output)
    assert load_run_state(repo, "r1").steps["implement"].units["phase/1/code"].state == "running"


def test_an_executor_this_session_never_dispatched_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped, opened = _at_code(tmp_path, root=root)
    log = tmp_path / "suite.log"
    log.write_text("4051 passed\n")
    _executor_ran(root, "s-c", opened, log)

    result = _invoke_measurable(
        repo, shipped, [*_CODE, "--agent", "a-bogus", "--evidence", f"tests={log}"], root, "s-c"
    )

    assert result.exit_code == 2, result.output
    assert "a-bogus" in _squash(result.output)


def test_a_log_older_than_a_changed_code_file_is_refused(tmp_path: Path) -> None:
    repo, shipped, _ = _at_code(tmp_path)
    log = tmp_path / "suite.log"
    log.write_text("4051 passed\n")
    stamp = log.stat().st_mtime
    code = repo / "src" / "late.py"
    code.parent.mkdir(exist_ok=True)
    code.write_text("x = 1\n")
    os.utime(code, (stamp + 10, stamp + 10))  # edited after the suite ran

    result = _invoke(repo, shipped, [*_CODE, "--agent", "impl-1", "--evidence", f"tests={log}"])

    assert result.exit_code == 2, result.output
    out = _squash(result.output)
    assert "stale" in out and "src/late.py" in out


def test_an_opencode_phase_log_is_recorded_unobserved(tmp_path: Path) -> None:
    repo, shipped, _ = _at_code(tmp_path)
    log = tmp_path / "suite.log"
    log.write_text("4051 passed\n")

    result = _invoke_as_harness(
        repo,
        shipped,
        [*_CODE, "--agent", "impl-1", "--evidence", f"tests={log}"],
        {"FR_HARNESS": "opencode"},
    )

    assert result.exit_code == 0, result.output
    evidence = _code_evidence(repo)
    assert ";tree=" in evidence["tests"]
    assert "tests" in evidence["unobserved"].split(",")


def test_a_phase_log_inside_the_records_dir_is_refused(tmp_path: Path) -> None:
    repo, shipped, _ = _at_code(tmp_path)
    records_dir = repo / "docs" / "superpowers" / "runs" / "r1.records"
    records_dir.mkdir(parents=True, exist_ok=True)
    (records_dir / "suite.log").write_text("4051 passed\n")

    result = _invoke(
        repo,
        shipped,
        [
            *_CODE,
            "--agent",
            "impl-1",
            "--evidence",
            "tests=docs/superpowers/runs/r1.records/suite.log",
        ],
    )

    assert result.exit_code == 2, result.output
    assert "records dir" in _squash(result.output)


def test_a_phase_record_may_name_its_suite_log(tmp_path: Path) -> None:
    repo, shipped, _ = _at_code(tmp_path)
    log = tmp_path / "suite.log"
    log.write_text("4051 passed\n")
    record = repo / "docs" / "superpowers" / "runs" / "r1.records" / "code__phase-1.yaml"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(
        json.dumps(
            {
                "schema_version": 4,
                "run": "r1",
                "step": "code",
                "item": "phase/1",
                "outcome": "done",
                "evidence": {"tests": str(log)},
            }
        )
    )

    result = _invoke(
        repo,
        shipped,
        [
            "run",
            "resolve",
            "r1",
            "--step",
            "code",
            "--item",
            "phase/1",
            "--record",
            str(record),
            "--no-advance",
        ],
    )

    assert result.exit_code == 0, result.output
    assert ";tree=" in _code_evidence(repo)["tests"]


def test_other_undeclared_evidence_on_a_phase_unit_is_still_refused(tmp_path: Path) -> None:
    repo, shipped, _ = _at_code(tmp_path)

    result = _invoke(repo, shipped, [*_CODE, "--agent", "impl-1", "--evidence", "review=x"])

    assert result.exit_code == 2, result.output
