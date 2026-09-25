"""`fr run` / `fr usage` execute on the harness host (spec
`2026-09-25-lean-cost-aware-process-design.md` §5.B.6-7).

Two layers, one rule. The bridge (`fr isolation exec`) refuses an inner
`fr run`/`fr usage` in devcontainer mode and prints the exact host-side
command; the in-process check refuses when the operated repo carries a
`target: devcontainer` marker AND container evidence exists (`mode` cannot
discriminate: host-worktree writes `mode: worktree` too, and a host-worktree
pod shows container evidence — p2-r20). Neither refuses host-worktree,
external or a legacy marker without `target`. The
host-side form passes the bash guards. And a transcript gate that cannot
observe records `unobserved` and says so.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from fr.commands import isolation_cmd
from fr.isolation import where
from fr.isolation.types import IsolationState, save_state
from typer.testing import CliRunner

from tests.unit.test_hooks_guard import decision, payload, run_hook, write_sentinel

runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[2]


def _git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    return path


class _FakeTarget:
    def __init__(self) -> None:
        self.ran: list[list[str]] = []

    def exec(self, state: IsolationState, argv: list[str]) -> int:
        self.ran.append(argv)
        return 0


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = _git_repo(tmp_path / "repo")
    target = _FakeTarget()
    monkeypatch.setattr(isolation_cmd, "_target_for", lambda root, state: target)

    def make(mode: str, *, fr_source: bool) -> Path:
        worktree = tmp_path / f"wt-{mode}-{fr_source}"
        worktree.mkdir()
        if fr_source:
            (worktree / "packages" / "fr").mkdir(parents=True)
        save_state(
            IsolationState(
                repo_root=repo,
                branch="b",
                worktree=worktree,
                profile="dev" if mode == "devcontainer" else "host",
                target=mode,  # type: ignore[arg-type]
                created_at="2026-09-25T00:00:00+00:00",
            )
        )
        return worktree

    return repo, target, make


def _exec(repo: Path, *argv: str):
    return runner.invoke(
        app, ["isolation", "exec", "--repo", str(repo), "--branch", "b", "--", *argv]
    )


# --- (a) the bridge ---------------------------------------------------------


def test_exec_refuses_fr_run_in_devcontainer_mode_and_prints_the_host_command(
    workspace,
) -> None:
    repo, target, make = workspace
    worktree = make("devcontainer", fr_source=True)

    result = _exec(repo, "uv", "run", "fr", "run", "resolve", "r", "--step", "x")

    assert result.exit_code == 2, result.output
    assert target.ran == [], "nothing ran inside the container"
    flat = " ".join(result.output.split())
    assert f"cd {worktree} && uv run fr run resolve r --step x" in flat


def test_a_consumer_repo_gets_bare_fr(workspace) -> None:
    repo, _target, make = workspace
    worktree = make("devcontainer", fr_source=False)
    result = _exec(repo, "fr", "usage", "report", "--run", "r")
    assert result.exit_code == 2
    assert f"cd {worktree} && fr usage report --run r" in " ".join(result.output.split())


def test_a_bash_c_string_is_inspected_best_effort(workspace) -> None:
    repo, target, make = workspace
    make("devcontainer", fr_source=False)
    result = _exec(repo, "bash", "-c", "cd /w && fr run status r && echo done")
    assert result.exit_code == 2
    assert "fr run status r" in " ".join(result.output.split())
    assert target.ran == []


def test_other_commands_still_run_inside_the_container(workspace) -> None:
    repo, target, make = workspace
    make("devcontainer", fr_source=False)
    assert _exec(repo, "fr", "plan", "edit", "p").exit_code == 0
    assert _exec(repo, "pytest", "-q").exit_code == 0
    assert len(target.ran) == 2


@pytest.mark.parametrize("mode", ["worktree", "external"])
def test_host_worktree_and_external_are_not_refused(workspace, mode: str) -> None:
    repo, target, make = workspace
    make(mode, fr_source=True)
    result = _exec(repo, "uv", "run", "fr", "run", "status", "r")
    assert result.exit_code == 0, result.output
    assert target.ran == [["uv", "run", "fr", "run", "status", "r"]]


def test_inner_fr_command_recognises_the_invocation_shapes() -> None:
    assert where.inner_fr_command(["fr", "run", "status", "r"]) == ["run", "status", "r"]
    assert where.inner_fr_command(["uv", "run", "fr", "usage", "report"]) == ["usage", "report"]
    assert where.inner_fr_command(["python", "-m", "fr", "run", "cost", "r"]) == [
        "run",
        "cost",
        "r",
    ]
    assert where.inner_fr_command(["sh", "-c", "fr run check r; ls"]) == ["run", "check", "r"]
    assert where.inner_fr_command(["fr", "plan", "edit"]) is None
    assert where.inner_fr_command(["echo", "fr", "run"]) == ["run"]  # best effort, errs strict


# --- (b) the in-process check ------------------------------------------------


def _marker(repo: Path, mode: str, target: str | None = None) -> None:
    data = {"toplevel": str(repo.resolve()), "branch": "b", "mode": mode}
    if target is not None:
        data["target"] = target
    (repo / ".fr-isolation").write_text(json.dumps(data))


def _in_container(monkeypatch: pytest.MonkeyPatch, value: bool = True) -> None:
    monkeypatch.setattr(where, "container_evidence", lambda: value)


def _run_status(repo: Path):
    return runner.invoke(app, ["run", "status", "r"], env={"VK_REPO_ROOT": str(repo)})


def test_fr_run_inside_a_devcontainer_workspace_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _git_repo(tmp_path / "wt")
    (repo / "packages" / "fr").mkdir(parents=True)
    _marker(repo, "worktree", "devcontainer")
    _in_container(monkeypatch)

    result = _run_status(repo)

    assert result.exit_code == 2, result.output
    flat = " ".join(result.output.split())
    assert f"cd {repo.resolve()} && uv run fr run" in flat


def test_fr_usage_is_refused_the_same_way(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _git_repo(tmp_path / "wt")
    _marker(repo, "worktree", "devcontainer")
    _in_container(monkeypatch)
    result = runner.invoke(
        app, ["usage", "report", "--session", "s"], env={"VK_REPO_ROOT": str(repo)}
    )
    assert result.exit_code == 2
    assert "harness host" in " ".join(result.output.split())


def test_a_repo_without_a_marker_inside_a_container_is_not_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _git_repo(tmp_path / "plain")
    _in_container(monkeypatch)
    result = _run_status(repo)
    assert "harness host" not in result.output


def test_external_mode_is_never_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _git_repo(tmp_path / "pod")
    _marker(repo, "external")
    _in_container(monkeypatch)
    assert "harness host" not in _run_status(repo).output


def test_a_devcontainer_marker_on_the_host_is_not_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _git_repo(tmp_path / "wt")
    _marker(repo, "worktree", "devcontainer")
    _in_container(monkeypatch, False)
    assert "harness host" not in _run_status(repo).output


def test_a_host_worktree_pod_with_container_evidence_is_not_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """p2-r20: a host-worktree workspace inside a pod or CI container shows
    container evidence while the harness runs inside it too — `mode: worktree`
    alone cannot tell it from a devcontainer, so the marker's `target` does."""
    repo = _git_repo(tmp_path / "wt")
    _marker(repo, "worktree", "worktree")
    _in_container(monkeypatch)
    assert "harness host" not in _run_status(repo).output


def test_a_legacy_marker_without_target_is_never_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _git_repo(tmp_path / "wt")
    _marker(repo, "worktree")
    _in_container(monkeypatch)
    assert "harness host" not in _run_status(repo).output


# --- (c) the host-side form passes the bash guards --------------------------


def test_the_host_side_form_passes_the_claude_code_bash_guard(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    worktree = tmp_path / "worktrees" / "repo" / "feat__x"
    worktree.mkdir(parents=True)
    sentinels = tmp_path / "sentinels"
    write_sentinel(sentinels, repo)
    env = {"FR_CD_ALLOW_PREFIXES": str(tmp_path / "worktrees")}
    for cmd in (
        f"cd {worktree} && uv run fr run resolve r --step x --state done",
        f"cd {worktree} && fr usage report --run r",
    ):
        assert decision(run_hook(payload(cmd, repo), sentinels, env)) is None, cmd


def test_the_host_side_form_passes_the_hermes_bash_guard(tmp_path: Path) -> None:
    from tests.unit.test_hermes_bash_guard import allowed, fr_repo, linked_worktree
    from tests.unit.test_hermes_bash_guard import payload as hermes_payload
    from tests.unit.test_hermes_bash_guard import run_hook as hermes_hook

    repo = fr_repo(tmp_path)
    wt = linked_worktree(repo)
    assert allowed(hermes_hook(hermes_payload(f"cd {wt} && uv run fr run status r", repo)))


# --- (d) a gate that cannot observe says so and records it ------------------


def test_an_unobservable_gate_records_unobserved_and_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.run import units
    from fr.run.model import load_run_state

    from tests.unit.test_run_evidence_separate_context import _at_deliver, _deliver

    for key in ("FR_HARNESS", "CLAUDECODE", "CLAUDE_PLUGIN_ROOT"):
        monkeypatch.delenv(key, raising=False)
    repo, shipped, _ = _at_deliver(tmp_path)
    review = units.evidence_of(load_run_state(repo, "r1").steps["implement"], "phase/1/peer-review")
    assert review.get("unobserved") == "reviewer", review

    (repo / "fresh.log").write_text("ok\n")
    result = _deliver(repo, shipped, None, "s-d", "tests=fresh.log")

    assert result.exit_code == 0, result.output
    assert "unobserved" in " ".join(result.stderr.split())
    deliver = units.evidence_of(load_run_state(repo, "r1").steps["deliver"], "step/deliver")
    assert deliver.get("unobserved") == "tests", deliver
