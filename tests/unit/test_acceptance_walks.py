"""Walk recording and the close command (spec
2026-10-06-verification-strategies §E, R13/R14/R16).

`fr acceptance add`/`set-status` take `--issue`, `--scenario`, `--harness` and
`--verify`; `set-status --walk` appends a walk; once a walk makes a row
walk-verified and no other row holds the issue open, set-status prints the
forge's close and unlabel commands — and nothing under `tracking: none`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.acceptance.model import Matrix, Row, Walk, load_matrix
from fr.acceptance.walks import issues_now_closable, walk_verified

from tests.unit.test_record_apply import _matrix_repo

MATRIX = Path("docs") / "acceptance" / "matrix.yaml"


def _walk(harness: str = "claude-code", outcome: str = "pass") -> Walk:
    return Walk(
        strategy="live",
        harness=harness,
        model="opus",
        outcome=outcome,  # type: ignore[arg-type]
        at="2026-10-06T12:00:00Z",
        evidence="walk.log",
    )


def _row(rid: str, **fields: object) -> Row:
    return Row.model_validate(
        {"id": rid, "capability": "c", "acceptance": "x", "status": "skipped", **fields}
    )


# --- walk_verified -------------------------------------------------------------


def test_a_row_naming_no_harness_is_verified_by_any_passing_walk() -> None:
    assert not walk_verified(_row("a"))
    assert not walk_verified(_row("a", walks=[_walk(outcome="fail")]))
    assert walk_verified(_row("a", walks=[_walk("opencode")]))


def test_a_row_naming_harnesses_needs_a_pass_on_every_one() -> None:
    row = _row("a", harnesses=["claude-code", "opencode"], walks=[_walk("claude-code")])
    assert not walk_verified(row)
    row = _row(
        "a",
        harnesses=["claude-code", "opencode"],
        walks=[_walk("claude-code"), _walk("opencode", "fail"), _walk("opencode")],
    )
    assert walk_verified(row)


# --- issues_now_closable --------------------------------------------------------


def test_an_issue_is_closable_once_no_other_row_holds_it_open(tmp_path: Path) -> None:
    before = _row("a", verify="live", issues=["o/r#1", "o/r#2"])
    after = before.model_copy(update={"walks": (_walk(),)})
    other = _row("b", verify="live", issues=["o/r#2"])  # still waiting for its walk
    pre = _row("c", verify="candidate", issues=["o/r#1"])  # pre-merge: never holds it

    closable = issues_now_closable(Matrix(rows=(after, other, pre)), before, after, tmp_path)

    assert closable == ["o/r#1"]


def test_nothing_is_closable_unless_this_walk_verified_the_row(tmp_path: Path) -> None:
    before = _row("a", verify="live", issues=["o/r#1"], walks=[_walk()])
    after = before.model_copy(update={"walks": (_walk(), _walk())})
    assert issues_now_closable(Matrix(rows=(after,)), before, after, tmp_path) == []

    failed = _row("a", verify="live", issues=["o/r#1"])
    still = failed.model_copy(update={"walks": (_walk(outcome="fail"),)})
    assert issues_now_closable(Matrix(rows=(still,)), failed, still, tmp_path) == []


# --- the CLI ---------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = _matrix_repo(tmp_path)
    monkeypatch.chdir(root)
    return root


def _fr(*args: str):
    from fr.cli import app
    from typer.testing import CliRunner

    return CliRunner().invoke(app, ["acceptance", *args])


def _target(root: Path, rid: str = "target") -> Row:
    return next(r for r in load_matrix(root / MATRIX).rows if r.id == rid)


def _set(*args: str):
    return _fr("set-status", "--id", "target", "--status", "skipped", "--notes", "n", *args)


def test_add_takes_issue_scenario_harness_and_verify(repo: Path) -> None:
    out = _fr(
        "add", "--id", "fresh", "--capability", "Cap", "--acceptance", "X",
        "--status", "not-implemented", "--issue", "o/r#1",
        "--scenario", "tests/scenarios/x.sh", "--harness", "claude-code",
        "--verify", "candidate",
    )  # fmt: skip

    assert out.exit_code == 0, out.output
    row = _target(repo, "fresh")
    assert (row.issues, row.scenario, row.harnesses, row.verify) == (
        ("o/r#1",),
        "tests/scenarios/x.sh",
        ("claude-code",),
        "candidate",
    )


def test_add_refuses_a_malformed_issue(repo: Path) -> None:
    out = _fr(
        "add", "--id", "fresh", "--capability", "Cap", "--acceptance", "X",
        "--status", "not-implemented", "--issue", "#1",
    )  # fmt: skip
    assert out.exit_code == 2
    assert "owner/repo#n" in out.output


def test_set_status_issue_adds_to_the_row(repo: Path) -> None:
    assert _set("--issue", "o/r#1").exit_code == 0
    assert _set("--issue", "o/r#2", "--issue", "o/r#1").exit_code == 0
    assert _target(repo).issues == ("o/r#1", "o/r#2")


def test_set_status_walk_appends_a_walk(repo: Path) -> None:
    out = _set(
        "--walk", "walk.log", "--harness", "claude-code", "--model", "opus", "--strategy", "live"
    )

    assert out.exit_code == 0, out.output
    (walk,) = _target(repo).walks
    assert (walk.strategy, walk.harness, walk.model, walk.outcome, walk.evidence) == (
        "live",
        "claude-code",
        "opus",
        "pass",
        "walk.log",
    )
    assert walk.at.endswith("Z")

    out = _set(
        "--walk", "n", "--harness", "opencode", "--model", "m", "--strategy", "live",
        "--walk-outcome", "fail",
    )  # fmt: skip
    assert out.exit_code == 0, out.output
    assert [w.outcome for w in _target(repo).walks] == ["pass", "fail"]


@pytest.mark.parametrize(
    "missing",
    [
        ["--model", "m", "--strategy", "live"],
        ["--harness", "h", "--strategy", "live"],
        ["--harness", "h", "--model", "m"],
    ],
)
def test_a_walk_missing_harness_model_or_strategy_is_refused(
    repo: Path, missing: list[str]
) -> None:
    before = (repo / MATRIX).read_text()

    out = _set("--walk", "walk.log", *missing)

    assert out.exit_code == 2
    assert (repo / MATRIX).read_text() == before


def test_a_walk_with_an_unknown_strategy_is_refused(repo: Path) -> None:
    out = _set("--walk", "w", "--harness", "h", "--model", "m", "--strategy", "bogus")
    assert out.exit_code == 2


def test_the_walk_that_verifies_the_last_open_row_prints_the_close_commands(repo: Path) -> None:
    assert _set("--issue", "derio-net/demo#7", "--verify", "live").exit_code == 0

    out = _set("--walk", "walk.log", "--harness", "claude-code", "--model", "opus",
               "--strategy", "live")  # fmt: skip

    assert out.exit_code == 0, out.output
    assert "gh issue close 7 --repo derio-net/demo --comment" in out.output
    assert "walk.log" in out.output
    assert "gh issue edit 7 --repo derio-net/demo --remove-label fr:awaiting-live" in out.output


def test_nothing_is_printed_under_tracking_none(repo: Path) -> None:
    profiles = repo / ".devcontainer" / "fr-profiles.yaml"
    profiles.parent.mkdir(exist_ok=True)
    profiles.write_text(
        "schema_version: 2\nprofiles:\n  dev:\n    purpose: x\n"
        "forge: {type: github}\ntracking: {type: none}\n"
    )
    assert _set("--issue", "derio-net/demo#7", "--verify", "live").exit_code == 0

    out = _set("--walk", "walk.log", "--harness", "claude-code", "--model", "opus",
               "--strategy", "live")  # fmt: skip

    assert out.exit_code == 0, out.output
    assert "issue close" not in out.output and "issues close" not in out.output


# --- the forge command table -------------------------------------------------------


def _repo_on(tmp_path: Path, backend: str) -> Path:
    profiles = tmp_path / ".devcontainer" / "fr-profiles.yaml"
    profiles.parent.mkdir(parents=True)
    profiles.write_text(f"backend: {backend}\n")
    return tmp_path


@pytest.mark.parametrize(
    ("backend", "close", "label", "unlabel"),
    [
        (
            "github",
            "gh issue close 3 --repo o/r --comment 'walked: w.log'",
            "gh issue edit 3 --repo o/r --add-label fr:awaiting-live",
            "gh issue edit 3 --repo o/r --remove-label fr:awaiting-live",
        ),
        (
            "gitlab",
            "glab issue close 3 --repo o/r",
            "glab issue update 3 --repo o/r --label fr:awaiting-live",
            "glab issue update 3 --repo o/r --unlabel fr:awaiting-live",
        ),
        (
            "gitea",
            "tea issues close 3 --repo o/r",
            "tea issues edit 3 --repo o/r --add-labels fr:awaiting-live",
            "# tea has no unlabel command: remove the fr:awaiting-live label from o/r#3 by hand",
        ),
    ],
)
def test_the_command_table_renders_every_issue_op_per_backend(
    tmp_path: Path, backend: str, close: str, label: str, unlabel: str
) -> None:
    from fr.hostclient import issue_command

    root = _repo_on(tmp_path, backend)
    assert issue_command(root, "issue-close", ref="o/r#3", comment="walked: w.log") == close
    assert issue_command(root, "issue-label", ref="o/r#3", label="fr:awaiting-live") == label
    assert issue_command(root, "issue-unlabel", ref="o/r#3", label="fr:awaiting-live") == unlabel


def test_every_backend_declares_every_issue_operation() -> None:
    from fr.hostclient import ISSUE_COMMANDS

    ops = {frozenset(table) for table in ISSUE_COMMANDS.values()}
    assert ops == {frozenset({"issue-close", "issue-label", "issue-unlabel"})}
    assert set(ISSUE_COMMANDS) == {"github", "gitlab", "gitea"}
