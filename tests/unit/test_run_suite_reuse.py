"""`deliver` reuses a verified phase suite log on an unchanged code tree —
spec 2026-09-29-fr-goal-light-path §D (R6).

Task 1 pins the pure helpers in `fr.run.code_tree`: the code tree is
`git ls-tree -r HEAD` without fr's artifact trees (`docs/superpowers/`,
`docs/acceptance/`), so the bookkeeping `resolve` writes between the suite run
and `deliver` never reads as a code change.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from fr.run import units
from fr.run.code_tree import (
    FR_ARTIFACT_PREFIXES,
    code_tree,
    dirty_code_paths,
    newest_code_mtime,
)
from fr.run.model import load_run_state

from tests.unit.test_run_cli import (
    _invoke,
    _invoke_as_harness,
    _invoke_measurable,
    _repo,
    _squash,
    _started_grouped_with_plan,
    _write_shape,
)
from tests.unit.test_run_evidence import _journal
from tests.unit.test_run_evidence_separate_context import _SHAPE, _deliver, _later, _review, _soon
from tests.unit.transcript_sessions import (
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


def test_the_isolation_marker_is_never_code(tmp_path: Path) -> None:
    repo = _plain_repo(tmp_path)
    (repo / ".fr-isolation").write_text("{}\n")

    assert dirty_code_paths(repo) == []


def test_dirty_code_paths_lists_only_uncommitted_code(tmp_path: Path) -> None:
    repo = _plain_repo(tmp_path)
    assert dirty_code_paths(repo) == []
    (repo / "src" / "x.py").write_text("x = 3\n")
    (repo / "src" / "new.py").write_text("y = 1\n")
    (repo / "docs" / "superpowers" / "runs" / "r1.yaml").write_text("changed\n")
    (repo / "docs" / "superpowers" / "runs" / "r2.yaml").write_text("new\n")

    assert dirty_code_paths(repo) == ["src/new.py", "src/x.py"]


def _settle(repo: Path, at: float) -> None:
    """Every file and directory in the checkout (not `.git`) stamped `at` — so
    a test states each mtime rather than racing the clock."""
    for path in [repo, *repo.rglob("*")]:
        if ".git" in path.relative_to(repo).parts:
            continue
        os.utime(path, (at, at), follow_symlinks=False)


_LOG_AT = 2_000.0
"""When the suite log was written, in every freshness test below."""


def test_newest_code_mtime_is_the_newest_tracked_code_path_or_directory(
    tmp_path: Path,
) -> None:
    """The normal case: nothing touched since the suite ran, so every tracked
    code path and the directories holding them predate the log."""
    repo = _plain_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD").strip()
    _settle(repo, 1_000)
    _set_mtime(repo / "src" / "x.py", 1_500)
    _set_mtime(repo / "docs" / "superpowers" / "runs" / "r1.yaml", 9_000)  # artifact

    newest = newest_code_mtime(repo, base)

    assert newest == (1_500.0, "src/x.py")
    assert newest[0] < _LOG_AT


def test_newest_code_mtime_counts_an_unchanged_tracked_file(tmp_path: Path) -> None:
    """Review r2-2: every TRACKED code path counts, not only the ones that
    differ from the merge-base — an edit restored to the base's bytes is
    still an edit the suite did not run."""
    repo = _plain_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD").strip()
    _settle(repo, 1_000)
    _set_mtime(repo / "src" / "x.py", 5_000)

    assert newest_code_mtime(repo, base) == (5_000.0, "src/x.py")


def test_an_edit_restored_to_the_base_after_the_log_is_seen(tmp_path: Path) -> None:
    repo = _plain_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD").strip()
    _settle(repo, 1_000)
    (repo / "src" / "x.py").write_text("x = 2\n")
    (repo / "src" / "x.py").write_text("x = 1\n")  # the base's bytes again

    newest = newest_code_mtime(repo, base)

    assert newest is not None and newest[0] > _LOG_AT
    assert newest[1] == "src/x.py"


def test_a_rename_after_the_log_is_seen(tmp_path: Path) -> None:
    """A rename keeps the file's own mtime; its directory's moves."""
    repo = _plain_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD").strip()
    _settle(repo, 1_000)
    _git(repo, "mv", "src/x.py", "src/renamed.py")
    _git(repo, "commit", "-qm", "rename")
    assert (repo / "src" / "renamed.py").stat().st_mtime == 1_000

    newest = newest_code_mtime(repo, base)

    assert newest is not None and newest[0] > _LOG_AT
    assert newest[1] == "src/"


def test_a_deletion_after_the_log_is_seen(tmp_path: Path) -> None:
    repo = _plain_repo(tmp_path)
    (repo / "src" / "keep.py").write_text("k = 1\n")
    _commit_all(repo, "keep")
    base = _git(repo, "rev-parse", "HEAD").strip()
    _settle(repo, 1_000)
    _git(repo, "rm", "-q", "src/x.py")
    _git(repo, "commit", "-qm", "delete")

    newest = newest_code_mtime(repo, base)

    assert newest is not None and newest[0] > _LOG_AT
    assert newest[1] == "src/"


def test_a_deletion_that_empties_its_directory_is_seen_on_the_parent(tmp_path: Path) -> None:
    """`git rm` of a directory's last file removes the directory too; the
    nearest surviving ancestor is where the unlink shows."""
    repo = _plain_repo(tmp_path)
    (repo / "pkg").mkdir()
    (repo / "pkg" / "only.py").write_text("o = 1\n")
    _commit_all(repo, "pkg")
    base = _git(repo, "rev-parse", "HEAD").strip()
    _settle(repo, 1_000)
    _git(repo, "rm", "-q", "pkg/only.py")
    _git(repo, "commit", "-qm", "delete")
    assert not (repo / "pkg").exists()

    newest = newest_code_mtime(repo, base)

    assert newest is not None and newest[0] > _LOG_AT
    assert newest[1] == "./"


def test_newest_code_mtime_without_a_base_counts_every_code_path(tmp_path: Path) -> None:
    """No merge-base (no remote default branch): every tracked code path and
    its directory count, exactly as with one."""
    repo = _plain_repo(tmp_path)
    _settle(repo, 1_000)
    _set_mtime(repo / "src" / "x.py", 4_000)

    assert newest_code_mtime(repo, None) == (4_000.0, "src/x.py")


def test_newest_code_mtime_skips_ignored_paths(tmp_path: Path) -> None:
    """The log itself may sit in the worktree; it is not code it tested."""
    repo = _plain_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD").strip()
    (repo / "suite.log").write_text("ok\n")
    _commit_all(repo, "a tracked log")
    _settle(repo, 1_000)
    _set_mtime(repo / "suite.log", 9_000)

    newest = newest_code_mtime(repo, base, ignore=[repo / "suite.log"])

    assert newest is not None and newest[0] == 1_000.0


# --- Task 2: offered `tests` evidence on a phase unit -------------------------
#
# `code` below is the phase executor's member; it declares NO evidence, the way
# the shipped `implement-phase` declares none but the derived `visual`. `tests`
# is OFFERED evidence there: accepted undeclared, never owed.


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
    _commit_all(repo, "late")  # committed: the dirty check (r2-1) is not what refuses
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
    assert (
        "step 'code' declares no evidence, so --evidence review= would record an id "
        "nothing verified" in _squash(result.output)
    )
    assert "tests" not in _code_evidence(repo)


def test_tests_on_a_flat_step_that_does_not_declare_it_is_refused(tmp_path: Path) -> None:
    """`tests` is offered evidence on a PHASE unit only; a flat step that
    declares none still refuses it like any other undeclared name."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _SHAPE)
    _invoke(repo, shipped, ["run", "start", "grouped", "--branch", "b", "--run-id", "r1"])
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    (repo / "docs" / "superpowers" / "plans" / "x").mkdir(parents=True)
    log = tmp_path / "suite.log"
    log.write_text("4051 passed\n")

    result = _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "plan", "--state", "done"]
        + ["--emitted", "plan=docs/superpowers/plans/x", "--evidence", f"tests={log}"],
    )

    assert result.exit_code == 2, result.output
    assert (
        "step 'plan' declares no evidence, so --evidence tests= would record an id "
        "nothing verified" in _squash(result.output)
    )
    assert load_run_state(repo, "r1").steps["plan"].state == "running"


def test_a_dirty_tree_at_phase_resolve_is_refused(tmp_path: Path) -> None:
    """Review r2-1: the witness records HEAD's tree, so a suite run over
    uncommitted code would vouch for a tree it never ran."""
    repo, shipped, _ = _at_code(tmp_path)
    (repo / "seed.md").write_text("edited, not committed\n")
    log = tmp_path / "suite.log"
    log.write_text("4051 passed\n")

    result = _invoke(repo, shipped, [*_CODE, "--agent", "impl-1", "--evidence", f"tests={log}"])

    assert result.exit_code == 2, result.output
    out = _squash(result.output)
    assert "commit your code before recording the suite log" in out.lower()
    assert "seed.md" in out
    assert load_run_state(repo, "r1").steps["implement"].units["phase/1/code"].state == "running"


def test_a_log_inside_the_worktree_is_not_dirty_code(tmp_path: Path) -> None:
    """Review r2-5: the suite's own untracked log is not code, at the phase
    resolve or at `deliver`'s reuse."""
    repo, shipped = _at_deliver_after(tmp_path, log_in_repo=True)
    assert "phase.log" in _git(repo, "status", "--porcelain")
    witness = _code_evidence(repo)["tests"]
    assert witness.startswith("phase.log@")

    result = _deliver(repo, shipped, None, "s-c", "tests=reuse")

    assert result.exit_code == 0, result.output
    assert _deliver_evidence(repo)["tests"] == f"reused:phase/1/code:{witness}"


def test_a_same_named_file_with_other_bytes_is_still_dirty(tmp_path: Path) -> None:
    """The exclusion is the witness's own log — same path AND same bytes."""
    repo, shipped = _at_deliver_after(tmp_path, log_in_repo=True)
    (repo / "phase.log").write_text("rewritten after the phase\n")

    result = _deliver(repo, shipped, None, "s-c", "tests=reuse")

    assert result.exit_code == 2, result.output
    assert "phase.log" in _squash(result.output)


def test_a_rename_committed_after_the_log_is_refused(tmp_path: Path) -> None:
    """Review r2-2: a rename keeps the file's mtime; the directory shows it."""
    repo, shipped, _ = _at_code(tmp_path)
    log = tmp_path / "suite.log"
    log.write_text("4051 passed\n")
    stamp = log.stat().st_mtime
    _git(repo, "mv", "seed.md", "moved.md")
    _git(repo, "commit", "-qm", "rename")
    os.utime(repo, (stamp + 10, stamp + 10))  # the rename happened after the suite ran

    result = _invoke(repo, shipped, [*_CODE, "--agent", "impl-1", "--evidence", f"tests={log}"])

    assert result.exit_code == 2, result.output
    out = _squash(result.output)
    assert "stale" in out and "./" in out


_FAILED_CODE = [*_CODE[:-1], "failed"]


def test_a_failed_resolve_records_no_tree(tmp_path: Path) -> None:
    """Review r2-3: only a `done` phase vouches for its tree."""
    repo, shipped, _ = _at_code(tmp_path)
    log = tmp_path / "suite.log"
    log.write_text("3 failed, 4048 passed\n")

    result = _invoke(
        repo, shipped, [*_FAILED_CODE, "--agent", "impl-1", "--evidence", f"tests={log}"]
    )

    assert result.exit_code == 0, result.output
    witness = _code_evidence(repo)["tests"]
    assert witness.startswith("suite.log@") and ";tree=" not in witness


def test_a_retry_resolved_without_tests_drops_the_prior_witness(tmp_path: Path) -> None:
    repo, shipped, _ = _at_code(tmp_path)
    log = tmp_path / "suite.log"
    log.write_text("3 failed, 4048 passed\n")
    failed = _invoke(
        repo, shipped, [*_FAILED_CODE, "--agent", "impl-1", "--evidence", f"tests={log}"]
    )
    assert failed.exit_code == 0, failed.output
    assert "tests" in _code_evidence(repo)
    retry = _invoke(repo, shipped, ["run", "advance", "r1"])
    assert retry.exit_code == 0, retry.output

    result = _invoke(repo, shipped, [*_CODE, "--agent", "impl-2"])

    assert result.exit_code == 0, result.output
    assert "tests" not in _code_evidence(repo)


def _state_with_code_unit(unit_state: str) -> object:
    from fr.run.model import RunState

    return RunState.model_validate(
        {
            "run": "r1",
            "workflow": "grouped",
            "branch": "b",
            "started": "2026-09-29T00:00:00+00:00",
            "cursor": "implement",
            "steps": {
                "implement": {
                    "state": "running",
                    "units": {
                        "phase/1/code": {
                            "state": unit_state,
                            "attempts": [
                                {
                                    "dispatched": "2026-09-29T01:00:00+00:00",
                                    "returned": "2026-09-29T02:00:00+00:00",
                                    "outcome": "done" if unit_state == "done" else "failed",
                                }
                            ],
                            "evidence": {"tests": "a.log@000000000000;tree=aaa"},
                        }
                    },
                }
            },
        }
    )


def test_a_witness_on_a_unit_that_is_not_done_is_not_reusable() -> None:
    from fr.commands.run_cmd import _latest_tests_witness

    assert _latest_tests_witness(_state_with_code_unit("done")) is not None  # type: ignore[arg-type]
    assert _latest_tests_witness(_state_with_code_unit("failed")) is None  # type: ignore[arg-type]


# --- Task 3: `deliver` `tests: reuse` -----------------------------------------


def _at_deliver_after(
    tmp_path: Path,
    *,
    phase_log: bool = True,
    log_in_repo: bool = False,
    harness_env: dict[str, str | None] | None = None,
) -> tuple:
    """Run to `deliver`, `phase/1/code` resolved with (or without) its own
    suite log — written beside the repo, or untracked inside it, and resolved
    under `harness_env` when given. Returns `(repo, shipped)`."""
    repo, shipped, _ = _at_code(tmp_path)
    code = [*_CODE, "--agent", "impl-1"]
    if phase_log:
        log = (repo if log_in_repo else tmp_path) / "phase.log"
        log.write_text("4051 passed\n")
        code += ["--evidence", f"tests={log}"]
    resolved = (
        _invoke(repo, shipped, code)
        if harness_env is None
        else _invoke_as_harness(repo, shipped, code, harness_env)
    )
    assert resolved.exit_code == 0, resolved.output
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    review = _review(repo, shipped, None, "s-c", "review=rev-p1", "reviewer=r-9")
    assert review.exit_code == 0, review.output
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    return repo, shipped


def _deliver_evidence(repo: Path) -> dict[str, str]:
    return units.evidence_of(load_run_state(repo, "r1").steps["deliver"], "step/deliver")


def test_reuse_passes_on_an_unchanged_code_tree(tmp_path: Path) -> None:
    repo, shipped = _at_deliver_after(tmp_path)
    witness = _code_evidence(repo)["tests"]

    result = _deliver(repo, shipped, None, "s-c", "tests=reuse")

    assert result.exit_code == 0, result.output
    assert _deliver_evidence(repo)["tests"] == f"reused:phase/1/code:{witness}"


def test_reuse_passes_after_a_bookkeeping_only_commit(tmp_path: Path) -> None:
    repo, shipped = _at_deliver_after(tmp_path)
    note = repo / "docs" / "superpowers" / "notes.md"
    note.write_text("bookkeeping\n")
    _commit_all(repo, "chore: bookkeeping")

    result = _deliver(repo, shipped, None, "s-c", "tests=reuse")

    assert result.exit_code == 0, result.output


def test_reuse_is_refused_after_a_code_commit(tmp_path: Path) -> None:
    repo, shipped = _at_deliver_after(tmp_path)
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "fix.py").write_text("x = 2\n")
    _commit_all(repo, "fix: review")

    result = _deliver(repo, shipped, None, "s-c", "tests=reuse")

    assert result.exit_code == 2, result.output
    out = _squash(result.output)
    assert "the code tree changed since phase/1/code (1 path, e.g. src/fix.py)" in out
    assert "run the full suite yourself into a log and name it" in out
    assert load_run_state(repo, "r1").steps["deliver"].state == "running"


def test_reuse_is_refused_while_a_code_path_is_uncommitted(tmp_path: Path) -> None:
    repo, shipped = _at_deliver_after(tmp_path)
    (repo / "seed.md").write_text("edited\n")

    result = _deliver(repo, shipped, None, "s-c", "tests=reuse")

    assert result.exit_code == 2, result.output
    assert "seed.md" in _squash(result.output)


def test_reuse_is_refused_when_no_unit_carries_a_suite_log(tmp_path: Path) -> None:
    repo, shipped = _at_deliver_after(tmp_path, phase_log=False)

    result = _deliver(repo, shipped, None, "s-c", "tests=reuse")

    assert result.exit_code == 2, result.output
    assert "no phase unit recorded a suite log" in _squash(result.output)


def test_reuse_takes_the_most_recently_resolved_witness() -> None:
    from fr.commands.run_cmd import _latest_tests_witness
    from fr.run.model import RunState

    state = RunState.model_validate(
        {
            "run": "r1",
            "workflow": "grouped",
            "branch": "b",
            "started": "2026-09-29T00:00:00+00:00",
            "cursor": "deliver",
            "steps": {
                "implement": {
                    "state": "done",
                    "units": {
                        "phase/1/code": {
                            "state": "done",
                            "attempts": [
                                {
                                    "dispatched": "2026-09-29T01:00:00+00:00",
                                    "returned": "2026-09-29T02:00:00+00:00",
                                    "outcome": "done",
                                }
                            ],
                            "evidence": {"tests": "a.log@000000000000;tree=aaa"},
                        },
                        "phase/1/peer-review": {
                            "state": "done",
                            "attempts": [
                                {
                                    "dispatched": "2026-09-29T03:00:00+00:00",
                                    "returned": "2026-09-29T04:00:00+00:00",
                                    "outcome": "done",
                                }
                            ],
                            "evidence": {"tests": "b.log@111111111111;tree=bbb"},
                        },
                    },
                }
            },
        }
    )

    assert _latest_tests_witness(state) == (
        "phase/1/peer-review",
        "b.log@111111111111;tree=bbb",
    )


def test_the_pr_body_names_the_reused_unit(tmp_path: Path) -> None:
    from fr.record.pr_body import render_pr_body
    from fr.run import units as _units

    repo, shipped = _at_deliver_after(tmp_path)
    state = load_run_state(repo, "r1")
    reused = "reused:phase/1/code:phase.log@0123456789ab;tree=" + "f" * 64
    state = state.model_copy(
        update={
            "steps": {
                **state.steps,
                "deliver": _units.with_evidence(
                    state.steps["deliver"], "step/deliver", {"tests": reused}
                ),
            }
        }
    )

    body = render_pr_body(repo, state)

    assert "## Tests" in body
    assert "reused from `phase/1/code`" in body
    assert "phase.log@0123456789ab" in body
    assert "unverified" not in body  # the source's evidence noted nothing unobserved


def test_deliver_without_tests_is_still_refused_as_missing(tmp_path: Path) -> None:
    repo, shipped = _at_deliver_after(tmp_path)

    result = _deliver(repo, shipped, None, "s-c")

    assert result.exit_code == 2, result.output
    out = _squash(result.output)
    assert "cannot be done without evidence (tests)" in out
    assert load_run_state(repo, "r1").steps["deliver"].state == "running"


def test_reusing_an_unobserved_phase_log_is_itself_unobserved(tmp_path: Path) -> None:
    """Review r2-4: a reuse can be no better verified than its source."""
    from fr.record.pr_body import render_pr_body

    repo, shipped = _at_deliver_after(tmp_path, harness_env={"FR_HARNESS": "opencode"})
    assert "tests" in _code_evidence(repo)["unobserved"].split(",")

    result = _deliver(repo, shipped, None, "s-c", "tests=reuse")

    assert result.exit_code == 0, result.output
    evidence = _deliver_evidence(repo)
    assert evidence["tests"].startswith("reused:phase/1/code:")
    assert "tests" in evidence["unobserved"].split(",")
    assert "unverified" in _squash(result.output)
    body = render_pr_body(repo, load_run_state(repo, "r1"))
    assert "reused from `phase/1/code`" in body and "unverified" in body
