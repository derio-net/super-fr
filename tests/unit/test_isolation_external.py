"""ExternalTarget — adopt a preparer-built containment (spec §A, Type 1).

Mode `external`: another process (a k8s run pod, an attach script) prepared the
container — the checkout, the agent, and the secrets are already inside, and it
signals that by writing the `.fr-isolation` marker itself with `mode="external"`.
fr must RECOGNIZE the containment and adopt it (ensure the feature branch, record
state) rather than isolate a second time. It never owns the checkout or the
container: `down` retires fr state + the marker's branch claim only, never the
preparer's marker file or checkout, and restart/stats refuse outright.

As in the host-worktree suite, every assertion rides a RECORDING runner that
delegates git to the real binary (cheap throwaway repos) and records every argv,
so a stray `docker`/`git worktree remove` is caught structurally.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fr.isolation.external import ExternalTarget
from fr.isolation.local import subprocess_runner
from fr.isolation.types import IsolationError, IsolationState, load_state

from tests.unit.test_isolation import make_repo


class RecordingRunner:
    """Delegates to the real subprocess_runner but records every argv — tests
    assert the exact command sequence AND the ABSENCE of docker / worktree ops."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.captures: list[bool] = []

    def __call__(
        self, argv: list[str], cwd: Path | None = None, check: bool = False, capture: bool = True
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(argv))
        self.captures.append(capture)
        return subprocess_runner(argv, cwd=cwd, check=check, capture=capture)

    def argv_for(self, binary: str) -> list[list[str]]:
        return [c for c in self.calls if c and c[0] == binary]


def _write_marker(
    repo: Path, *, branch: str = "", toplevel: str | None = None, mode: str = "external"
) -> None:
    (repo / ".fr-isolation").write_text(
        json.dumps(
            {
                "toplevel": toplevel if toplevel is not None else str(repo.resolve()),
                "branch": branch,
                "mode": mode,
                "created_at": "2026-07-24T00:00:00+00:00",
            },
            indent=2,
        )
        + "\n"
    )


def _no_docker_or_worktree(runner: RecordingRunner) -> None:
    assert not runner.argv_for("docker"), "external mode must never call docker"
    assert not runner.argv_for("devcontainer"), "external mode must never call devcontainer"
    for c in runner.argv_for("git"):
        assert c[:3] != ["git", "worktree", "remove"], "external mode never removes the checkout"


# ---------- Task 1: marker adoption + validation in up() ----------


def test_up_adopts_marker_saves_state(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)  # primary checkout, NOT a linked worktree
    _write_marker(repo)
    runner = RecordingRunner()

    st = ExternalTarget(repo, runner=runner).up(profile=None, branch="feat/x")

    assert st == IsolationState(
        repo_root=repo.resolve(),
        branch="feat/x",
        worktree=repo.resolve(),
        profile="external",
        created_at=st.created_at,
    )
    assert load_state(repo, "feat/x") == st
    # marker rewritten with the branch filled in, mode preserved
    marker = json.loads((repo / ".fr-isolation").read_text())
    assert marker["branch"] == "feat/x"
    assert marker["mode"] == "external"
    _no_docker_or_worktree(runner)


def test_up_missing_marker_raises_preparer_contract(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)  # no marker written
    with pytest.raises(IsolationError, match="preparer"):
        ExternalTarget(repo, runner=RecordingRunner()).up(profile=None, branch="feat/x")


def test_up_toplevel_mismatch_raises(tmp_path: Path) -> None:
    """A marker copied to the wrong checkout (recorded toplevel != actual)."""
    repo = make_repo(tmp_path)
    _write_marker(repo, toplevel=str(tmp_path / "somewhere-else"))
    with pytest.raises(IsolationError, match="toplevel"):
        ExternalTarget(repo, runner=RecordingRunner()).up(profile=None, branch="feat/x")


def test_up_wrong_mode_raises(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _write_marker(repo, mode="worktree")
    with pytest.raises(IsolationError, match="external"):
        ExternalTarget(repo, runner=RecordingRunner()).up(profile=None, branch="feat/x")


def test_up_profile_ignored_with_note(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = make_repo(tmp_path)
    _write_marker(repo)
    st = ExternalTarget(repo, runner=RecordingRunner()).up(profile="dev", branch="feat/x")
    assert st.profile == "external"  # the passed profile is ignored, not recorded
    assert "ignored" in capsys.readouterr().err.lower()


# ---------- Task 2: ensure requested branch in place ----------


def _head(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_up_new_branch_switch_dash_c(tmp_path: Path) -> None:
    """HEAD on 'main', requested branch absent → git switch -c from current HEAD."""
    repo = make_repo(tmp_path)
    _write_marker(repo)
    runner = RecordingRunner()

    ExternalTarget(repo, runner=runner).up(profile=None, branch="feat/x")

    assert ["git", "switch", "-c", "feat/x"] in runner.argv_for("git")
    assert _head(repo) == "feat/x"
    marker = json.loads((repo / ".fr-isolation").read_text())
    assert marker["branch"] == "feat/x"
    _no_docker_or_worktree(runner)


def test_up_head_already_branch_is_noop_idempotent(tmp_path: Path) -> None:
    """HEAD already on the requested branch → no switch argv, and up is idempotent."""
    repo = make_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "switch", "-c", "feat/x"], check=True)
    _write_marker(repo)
    target = ExternalTarget(repo, runner=(runner := RecordingRunner()))

    target.up(profile=None, branch="feat/x")
    target.up(profile=None, branch="feat/x")  # twice — still a no-op adopt

    assert not any(c[:2] == ["git", "switch"] for c in runner.argv_for("git"))
    assert _head(repo) == "feat/x"


def test_up_existing_branch_switch_no_dash_c(tmp_path: Path) -> None:
    """Branch exists but is not checked out → git switch (no -c)."""
    repo = make_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "branch", "feat/x"], check=True)
    _write_marker(repo)
    runner = RecordingRunner()

    ExternalTarget(repo, runner=runner).up(profile=None, branch="feat/x")

    assert ["git", "switch", "feat/x"] in runner.argv_for("git")
    assert ["git", "switch", "-c", "feat/x"] not in runner.argv_for("git")
    assert _head(repo) == "feat/x"


# ---------- Task 3: exec / down / restart / stats / status ----------


def _upped(tmp_path: Path) -> tuple[Path, RecordingRunner, ExternalTarget, IsolationState]:
    repo = make_repo(tmp_path)
    _write_marker(repo)
    runner = RecordingRunner()
    target = ExternalTarget(repo, runner=runner)
    st = target.up(profile=None, branch="feat/x")
    runner.calls.clear()
    runner.captures.clear()
    return repo, runner, target, st


def test_exec_runs_in_checkout_streams(tmp_path: Path) -> None:
    _, runner, target, st = _upped(tmp_path)
    rc = target.exec(st, ["git", "status", "--porcelain"])
    assert rc == 0
    assert runner.calls[-1] == ["git", "status", "--porcelain"]  # verbatim, no wrapper
    assert runner.captures[-1] is False, "exec must inherit stdio (stream output live)"


def test_exec_returncode_passthrough(tmp_path: Path) -> None:
    _, runner, target, st = _upped(tmp_path)
    assert target.exec(st, ["sh", "-c", "exit 7"]) == 7


def test_down_retires_fr_state_only_leaves_marker_and_checkout(tmp_path: Path) -> None:
    repo, runner, target, st = _upped(tmp_path)
    target.down(st, force=False)

    assert load_state(repo, "feat/x") is None  # fr state file gone
    assert (repo / ".fr-isolation").is_file()  # preparer's marker NOT unlinked
    assert json.loads((repo / ".fr-isolation").read_text())["branch"] == ""  # claim cleared
    assert repo.is_dir() and (repo / "README.md").is_file()  # checkout intact
    _no_docker_or_worktree(runner)


def test_restart_and_stats_refuse(tmp_path: Path) -> None:
    _, _, target, st = _upped(tmp_path)
    with pytest.raises(IsolationError, match="external"):
        target.restart(st)
    with pytest.raises(IsolationError, match="external"):
        target.stats(st)


def test_status_reports_mode_toplevel_branch(tmp_path: Path) -> None:
    repo, _, target, st = _upped(tmp_path)
    s = target.status(st)
    assert s["mode"] == "external"
    assert s["toplevel"] == str(repo.resolve())
    assert s["branch"] == "feat/x"


def test_status_supplies_cli_renderer_keys(tmp_path: Path) -> None:
    """Finding 2a: status carries the keys the shared CLI text renderer reads
    (profile / worktree / pr) so `fr isolation status` never KeyErrors on an
    external workspace."""
    repo, _, target, st = _upped(tmp_path)
    s = target.status(st)
    assert s["profile"] == "external"
    assert s["worktree"] == str(repo.resolve())
    assert s["pr"] is None


# ---------- finding 3: detect() toplevel-resolves the CWD ----------


def test_detect_from_subdirectory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A marker at the checkout toplevel is found even when detect is called
    from a nested subdirectory (git rev-parse --show-toplevel first)."""
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "1")  # evidence for finding 6
    repo = make_repo(tmp_path)
    _write_marker(repo)
    sub = repo / "a" / "b"
    sub.mkdir(parents=True)
    t = ExternalTarget.detect(sub, runner=subprocess_runner)
    assert isinstance(t, ExternalTarget)
    assert t.repo_root == repo.resolve()


def test_detect_not_a_repo_returns_none(tmp_path: Path) -> None:
    """A directory outside any git repo → None (nothing to adopt)."""
    (tmp_path / ".fr-isolation").write_text("{}")  # marker but no git repo
    assert ExternalTarget.detect(tmp_path, runner=subprocess_runner) is None


# ---------- finding 6: detect() requires container evidence ----------


def test_detect_with_container_evidence_returns_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "1")
    repo = make_repo(tmp_path)
    _write_marker(repo)
    assert isinstance(ExternalTarget.detect(repo, runner=subprocess_runner), ExternalTarget)


def test_detect_without_container_evidence_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A forged marker on a bare host is never adopted. Skipped when a
    container-evidence FILE exists on the test host (devcontainer /.dockerenv
    fires unconditionally) — mirrors Phase 3's hook skip-guard."""
    if Path("/.dockerenv").exists() or Path("/run/.containerenv").exists():
        pytest.skip("container evidence file present on host — evidence fires unconditionally")
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "")  # explicitly no evidence
    repo = make_repo(tmp_path)
    _write_marker(repo)
    assert ExternalTarget.detect(repo, runner=subprocess_runner) is None


# ---------- finding 7: corrupt marker → IsolationError, not raw JSONDecodeError ----------


def test_down_with_corrupt_marker_raises_isolationerror(tmp_path: Path) -> None:
    repo, _, target, st = _upped(tmp_path)
    (repo / ".fr-isolation").write_text("{ not valid json")
    with pytest.raises(IsolationError, match="unreadable"):
        target.down(st)


# ---------- finding 8: up() git-excludes the adopted marker ----------


def test_up_git_excludes_marker(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _write_marker(repo)
    ExternalTarget(repo, runner=subprocess_runner).up(profile=None, branch="feat/x")
    exclude = repo / ".git" / "info" / "exclude"
    assert exclude.is_file()
    assert ".fr-isolation" in exclude.read_text().splitlines()


def test_up_git_exclude_idempotent(tmp_path: Path) -> None:
    """A second up (or a repo that already excludes the marker) does not double
    the info/exclude line."""
    repo = make_repo(tmp_path)
    _write_marker(repo)
    t = ExternalTarget(repo, runner=subprocess_runner)
    t.up(profile=None, branch="feat/x")
    t.up(profile=None, branch="feat/x")
    exclude = (repo / ".git" / "info" / "exclude").read_text().splitlines()
    assert exclude.count(".fr-isolation") == 1


# ---------- gc: a structured, non-destructive verdict (#423) ----------


def test_gc_reports_external_ownership_and_mutates_nothing(tmp_path: Path) -> None:
    """gc used to refuse with exit 2 here, which left unattended automation with
    no machine-readable answer in this mode. It now REPORTS: one action naming
    the preparer as cleanup owner, and nothing is touched."""
    repo = make_repo(tmp_path)
    _write_marker(repo)
    runner = RecordingRunner()
    target = ExternalTarget(repo, runner=runner)
    st = target.up(profile=None, branch="feat/x")
    runner.calls.clear()

    (action,) = target.gc()

    assert action.verdict == "external"
    assert action.action == "skipped"
    assert action.worktree == str(repo.resolve())
    assert action.branch == "feat/x"
    assert "preparer" in action.detail
    # nothing reaped: checkout, marker and fr state all survive
    assert repo.is_dir() and (repo / "README.md").is_file()
    assert json.loads((repo / ".fr-isolation").read_text())["mode"] == "external"
    assert load_state(repo, "feat/x") == st
    _no_docker_or_worktree(runner)


def test_gc_dry_run_matches_live_run(tmp_path: Path) -> None:
    """`--dry-run` has nothing to suppress — the verdict is already read-only,
    so both spellings return the same non-destructive report."""
    repo = make_repo(tmp_path)
    _write_marker(repo)
    target = ExternalTarget(repo, runner=RecordingRunner())
    target.up(profile=None, branch="feat/x")
    assert target.gc(dry_run=True) == target.gc(dry_run=False)


def test_gc_without_an_adopted_branch_reports_no_branch(tmp_path: Path) -> None:
    """A prepared container fr has not yet adopted (no `up`) still classifies —
    the marker exists, the branch claim is empty."""
    repo = make_repo(tmp_path)
    _write_marker(repo)
    (action,) = ExternalTarget(repo, runner=RecordingRunner()).gc()
    assert action.verdict == "external" and action.branch is None
