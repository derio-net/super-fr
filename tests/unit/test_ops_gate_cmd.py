"""`fr ops gate` and the pieces it wires (spec 2026-10-22-fr-ops R15): the command's
refusals and preview, `fr ops status --ready`, the ops workspace's rebase, and the
terminal question stage 5 asks."""

from __future__ import annotations

import os
import pty
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import ops_gate_cmd
from fr.run.model import RunState, StepRecord, save_run_state
from typer.testing import CliRunner

from tests.unit.test_ops_cli import PLAN_REL, _git, _repo
from tests.unit.test_ops_gate import FakeForge

runner = CliRunner()


def _with_run(
    root: Path, *, pr: str | None = "https://github.com/derio-net/super-fr/pull/5"
) -> None:
    emitted = {"pr": pr} if pr else {}
    save_run_state(
        root,
        RunState(
            run="run-1",
            workflow="fr-goal@1",
            branch="feat/x",
            started="2026-10-22T00:00:00+00:00",
            cursor="deliver",
            steps={
                "plan": StepRecord(state="done", emitted={"plan": PLAN_REL}),
                "deliver": StepRecord(state="done", emitted=emitted),
            },
        ),
    )
    (root / ".devcontainer").mkdir(exist_ok=True)
    (root / ".devcontainer/fr-profiles.yaml").write_text(
        "profiles:\n  ops: {purpose: operate, secrets: [], ops: true}\ndefault: ops\n"
    )


@pytest.fixture
def gate_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = _repo(tmp_path / "r")
    _with_run(root)
    monkeypatch.chdir(root)
    monkeypatch.setattr(ops_gate_cmd, "_interactive", lambda: True)
    monkeypatch.setattr("fr._hosts.origin_slug", lambda root: "derio-net/super-fr")
    monkeypatch.setattr("fr._hosts.origin_hostname", lambda root: "github.com")
    forge = FakeForge()
    monkeypatch.setattr(ops_gate_cmd, "_forge", lambda url: forge)
    return root


def _gate(*args: str) -> Any:
    return runner.invoke(app, ["ops", "gate", *args])


def test_it_refuses_a_non_interactive_context(gate_repo: Path, monkeypatch) -> None:
    monkeypatch.setattr(ops_gate_cmd, "_interactive", lambda: False)
    result = _gate("--run", "run-1")
    assert result.exit_code == 2
    assert "terminal" in result.output


def test_its_interactivity_is_the_artifact_gates_predicate(monkeypatch) -> None:
    monkeypatch.setattr("fr.artifacts.trigger.is_interactive", lambda: False)
    assert ops_gate_cmd._interactive() is False
    monkeypatch.setattr("fr.artifacts.trigger.is_interactive", lambda: True)
    assert ops_gate_cmd._interactive() is True


def test_without_yes_it_previews_the_eight_stages(gate_repo: Path) -> None:
    result = _gate("--run", "run-1")
    assert result.exit_code == 0, result.output
    for n in range(1, 9):
        assert f" {n}. " in result.output
    assert "PR #5" in result.output and "chore/ops-p" in result.output
    assert "nothing done" in result.output


def test_an_unknown_run_is_refused(gate_repo: Path) -> None:
    result = _gate("--run", "nope")
    assert result.exit_code == 2 and "nope" in result.output


def test_a_run_with_no_pr_is_refused(tmp_path: Path, monkeypatch) -> None:
    root = _repo(tmp_path / "r")
    _with_run(root, pr=None)
    monkeypatch.chdir(root)
    monkeypatch.setattr(ops_gate_cmd, "_interactive", lambda: True)
    result = _gate("--run", "run-1")
    assert result.exit_code == 2 and "PR" in result.output


def test_two_ops_profiles_need_profile(gate_repo: Path) -> None:
    (gate_repo / ".devcontainer/fr-profiles.yaml").write_text(
        "profiles:\n  a: {ops: true}\n  b: {ops: true}\ndefault: a\n"
    )
    result = _gate("--run", "run-1")
    assert result.exit_code == 2 and "--profile" in result.output
    assert _gate("--run", "run-1", "--profile", "b").exit_code == 0


def test_no_ops_profile_is_refused_naming_scaffold(gate_repo: Path) -> None:
    (gate_repo / ".devcontainer/fr-profiles.yaml").write_text("profiles:\n  dev: {}\n")
    result = _gate("--run", "run-1")
    assert result.exit_code == 2 and "fr init scaffold --ops" in result.output


# ------------------------------------------------------------- fr ops status --ready


READY_OPS = """schema_version: 1
ops:
  - {id: pre, summary: s, phase: pre-merge, check: 'true'}
  - {id: live, summary: s, phase: post-merge, check: 'false', ready: 'true'}
  - {id: later, summary: s, phase: post-merge, check: 'false', ready: 'echo not built; exit 1'}
"""


def test_status_ready_reports_each_ready_probe(tmp_path: Path, monkeypatch) -> None:
    root = _repo(tmp_path, READY_OPS)
    monkeypatch.chdir(root)
    result = runner.invoke(app, ["ops", "status", "--plan", PLAN_REL, "--ready"])
    assert result.exit_code == 1, result.output
    assert "READY" in result.stdout and "live" in result.stdout
    assert "NOT READY" in result.stdout and "not built" in result.stdout
    assert "pre" not in result.stdout.split()


def test_status_ready_exits_0_when_every_ready_passes(tmp_path: Path, monkeypatch) -> None:
    root = _repo(tmp_path, READY_OPS.replace("echo not built; exit 1", "true"))
    monkeypatch.chdir(root)
    result = runner.invoke(app, ["ops", "status", "--plan", PLAN_REL, "--ready"])
    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------- the gitseam pieces


def _commit(root: Path, name: str, msg: str) -> str:
    (root / name).write_text(msg)
    _git(root, "add", "-A")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", msg)
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


def test_rebase_onto_replays_only_the_ops_branch_commits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.triage.gitseam import Worktree

    # `git rebase` writes commits: CI runners have no global identity to lend it.
    for var, value in (
        ("GIT_COMMITTER_NAME", "t"),
        ("GIT_COMMITTER_EMAIL", "t@t"),
        ("GIT_AUTHOR_NAME", "t"),
        ("GIT_AUTHOR_EMAIL", "t@t"),
    ):
        monkeypatch.setenv(var, value)

    root = tmp_path / "g"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    base = _commit(root, "a", "base")
    _git(root, "switch", "-q", "-c", "feat")
    pr_head = _commit(root, "f", "feature")
    _git(root, "switch", "-q", "-c", "ops")
    _commit(root, "evidence", "evidence")
    _git(root, "switch", "-q", "main")
    _git(root, "reset", "-q", "--hard", base)
    (root / "f").write_text("feature")  # the squash of the feature
    _commit(root, "f", "feature squashed")
    _git(root, "switch", "-q", "ops")
    Worktree(root).rebase_onto("main", pr_head)
    log = subprocess.run(
        ["git", "-C", str(root), "log", "--format=%s", "main..HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.split("\n")  # fmt: skip
    assert [s for s in log if s] == ["evidence"]


def test_ask_reads_one_line_from_the_terminal() -> None:
    from fr.ops.apply import TtyPrompt

    master, slave = pty.openpty()
    try:
        os.write(master, b"ran it worked\n")
        answer = TtyPrompt(tty=os.ttyname(slave)).ask("step 1?")
        assert answer == "ran it worked"
    finally:
        os.close(master)
        os.close(slave)


def test_confirm_reads_the_answer_from_the_terminal() -> None:
    """p4: `TtyPrompt.confirm` opened the tty in text "r+" mode and read nothing back, so
    every terminal confirmation (apply without --yes, attest, the merge) read as "no"."""
    from fr.ops.apply import TtyPrompt

    for typed, want in ((b"y\n", True), (b"n\n", False)):
        master, slave = pty.openpty()
        try:
            os.write(master, typed)
            assert TtyPrompt(tty=os.ttyname(slave)).confirm("go?") is want
        finally:
            os.close(master)
            os.close(slave)


def test_git_revisions_follow_end_of_options(monkeypatch, tmp_path: Path) -> None:
    """p4-gate-state-host-side: a revision is never read as a git option."""
    from fr.commands.ops_gate_cmd import HostCheckout
    from fr.triage import gitseam

    seen: list[list[str]] = []
    monkeypatch.setattr(gitseam, "git_ok", lambda args, cwd: seen.append(args) or True)
    monkeypatch.setattr(gitseam, "git", lambda args, cwd: seen.append(args) or "")
    gitseam.Worktree(tmp_path).rebase_onto("origin/main", "a" * 40)
    HostCheckout(tmp_path).changed_paths("origin/main", "a" * 40, [".devcontainer/ops"])
    for argv in seen:
        if "a" * 40 in argv:
            assert argv.index("--end-of-options") < argv.index("a" * 40), argv
    assert any(a[0] == "rebase" for a in seen) and any(a[0] == "diff" for a in seen)


def test_changed_paths_are_what_the_pr_changed_not_what_main_gained(tmp_path: Path) -> None:
    """gh#1266: stage 1 asks which pinned paths the PR changes. A profile change that
    merged to the default branch AFTER the PR forked is not the PR's, so the diff is
    from the merge base (`main...head`), never from main's tip (`main head`)."""
    from fr.commands.ops_gate_cmd import HostCheckout

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(tmp_path), "-c", "user.email=t@t", "-c", "user.name=t", *args],
            check=True, capture_output=True, text=True,
        ).stdout.strip()  # fmt: skip

    git("init", "-q", "-b", "main")
    (tmp_path / "README").write_text("seed\n")
    git("add", "-A")
    git("commit", "-qm", "seed")
    git("checkout", "-qb", "feat")
    (tmp_path / "app.py").write_text("x = 1\n")
    git("add", "-A")
    git("commit", "-qm", "the PR's own change")
    head = git("rev-parse", "HEAD")
    git("checkout", "-q", "main")
    (tmp_path / ".devcontainer" / "ops").mkdir(parents=True)
    (tmp_path / ".devcontainer" / "ops" / "devcontainer.json").write_text("{}\n")
    git("add", "-A")
    git("commit", "-qm", "the ops profile, in its own PR")
    pinned = [".devcontainer/ops"]

    host = HostCheckout(tmp_path)
    assert host.changed_paths("main", head, pinned) == []
    # ...yet the PR head's copy is not main's: a workspace cut there would run it.
    assert host.differing_paths("main", head, pinned) == [".devcontainer/ops/devcontainer.json"]
    tip = git("rev-parse", "main")
    assert host.rev_parse("main") == tip
    assert host.differing_paths("main", tip, pinned) == []
    assert host.rev_parse("no-such-branch") is None

    git("checkout", "-q", "feat")
    (tmp_path / ".devcontainer" / "ops").mkdir(parents=True)
    (tmp_path / ".devcontainer" / "ops" / "devcontainer.json").write_text('{"x": 1}\n')
    git("add", "-A")
    git("commit", "-qm", "the PR rewrites the profile")
    head = git("rev-parse", "HEAD")
    assert HostCheckout(tmp_path).changed_paths("main", head, pinned) == [
        ".devcontainer/ops/devcontainer.json"
    ]


def test_the_ops_branch_push_is_leased(monkeypatch, tmp_path: Path) -> None:
    """p4-r11 correction: the first push creates the branch (refusing one that exists);
    every later one is leased on the sha fr last pushed, never a bare --force."""
    from fr.commands.ops_gate_cmd import OpsWorkspace
    from fr.triage import gitseam

    seen: list[list[str]] = []
    exists = [False]
    monkeypatch.setattr(gitseam, "git", lambda args, cwd: seen.append(args) or "")
    monkeypatch.setattr(gitseam, "git_ok", lambda args, cwd: exists[0])
    ws = OpsWorkspace(tmp_path)
    ws.push("chore/ops-p")
    ws.push("chore/ops-p", lease="a" * 40)
    assert seen == [
        ["push", "origin", "HEAD:refs/heads/chore/ops-p"],
        ["push", f"--force-with-lease=refs/heads/chore/ops-p:{'a' * 40}", "origin",
         "HEAD:refs/heads/chore/ops-p"],
    ]  # fmt: skip
    exists[0] = True
    with pytest.raises(gitseam.GitError, match="already has"):
        ws.push("chore/ops-p")


def test_the_host_materialises_the_head_paths_skipping_absent_ones(tmp_path: Path) -> None:
    """spec 2026-11-01-ops-gate-probes R5: the scratch tree stage 1 reads the gap from."""
    import shutil
    import subprocess

    from fr.commands.ops_gate_cmd import HostCheckout

    repo = tmp_path / "repo"
    (repo / "docs/superpowers/plans/p").mkdir(parents=True)
    (repo / "docs/superpowers/plans/p/ops.yaml").write_text("schema_version: 2\nnone: x\n")
    (repo / "docs/superpowers/specs").mkdir(parents=True)
    (repo / "docs/superpowers/specs/s.md").write_text("# S\n")
    (repo / "other.txt").write_text("not asked for\n")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
         "commit", "-qm", "x"],
        check=True,
    )  # fmt: skip
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    (repo / "docs/superpowers/specs/s.md").write_text("# changed after the commit\n")
    out = HostCheckout(repo).materialise(
        head, ["docs/superpowers/specs", "docs/superpowers/plans/p", ".fr"]
    )
    try:
        assert (out / "docs/superpowers/specs/s.md").read_text() == "# S\n"
        assert (out / "docs/superpowers/plans/p/ops.yaml").is_file()
        assert not (out / "other.txt").exists() and not (out / ".fr").exists()
    finally:
        shutil.rmtree(out)
