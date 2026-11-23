"""`fr pr settle` through the CLI over a fake forge (spec 2026-11-23-pr-readiness-wait R2-R5,
R11)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fr.cli import app
from fr.gh import GhError
from fr.ghclient import UnsupportedForgeOperation
from typer.testing import CliRunner

from tests.unit.settings_repo import git, land_on_main, make_repo

runner = CliRunner()
REPO = "derio-net/sandbox"
READS = frozenset({"open_pr_for_head", "pr_view", "pr_checks", "required_check_names"})


class Forge:
    """A read-only fake: any method not listed here is a write and fails the test."""

    def __init__(
        self,
        *,
        open_pr: int | None = 7,
        view: dict[str, Any] | None = None,
        checks: list[dict[str, Any]] | None = None,
        required: list[str] | None = None,
        unsupported: str | None = None,
        error: str | None = None,
    ) -> None:
        self.open_pr = open_pr
        self.view = view or {
            "state": "OPEN",
            "head_oid": "c" * 40,
            "base_ref": "main",
            "mergeable": "MERGEABLE",
            "merge_state": "CLEAN",
        }
        self.checks = [{"name": "ci-ok", "bucket": "pass"}] if checks is None else checks
        self.required = required or []
        self.unsupported = unsupported
        self.error = error
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def _call(self, op: str, *args: Any) -> None:
        self.calls.append((op, args))
        if op == self.unsupported:
            raise UnsupportedForgeOperation(op, "glab")
        if op == self.error:
            raise GhError("HTTP 502 bad gateway")

    def open_pr_for_head(self, repo: str, branch: str) -> dict[str, Any] | None:
        self._call("open_pr_for_head", repo, branch)
        if self.open_pr is None:
            return None
        return {"number": self.open_pr, "url": f"https://github.com/{repo}/pull/{self.open_pr}"}

    def pr_view(self, repo: str, number: int) -> dict[str, Any]:
        self._call("pr_view", repo, number)
        return self.view

    def pr_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
        self._call("pr_checks", repo, number)
        return self.checks

    def required_check_names(self, repo: str, base: str) -> list[str]:
        self._call("required_check_names", repo, base)
        return self.required

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"fr pr settle called {name}: it may only read")

    @property
    def ops(self) -> list[str]:
        return [op for op, _ in self.calls]


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = make_repo(tmp_path)
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "ci.yml").write_text("on: pull_request\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "ci")
    git(root, "push", "-q", "origin", "main")
    git(root, "checkout", "-q", "-b", "feat/other")
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    monkeypatch.setattr("fr.commands.pr_cmd.origin_slug", lambda _root: REPO)
    monkeypatch.setattr("fr.commands.push_cmd.branch_runs", lambda _root: [])
    return root


def _run(monkeypatch: pytest.MonkeyPatch, forge: Forge, *args: str) -> Any:
    monkeypatch.setattr("fr.commands.pr_cmd.client_for", lambda _root: forge)
    return runner.invoke(app, ["pr", "settle", "--wait", "0", *args])


def test_a_clean_green_pr_exits_0(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    forge = Forge()
    result = _run(monkeypatch, forge)
    assert result.exit_code == 0, result.output
    assert "conflicts (fix, default): clean" in result.output
    assert "ci (fix, default): green" in result.output
    assert set(forge.ops) <= READS


def test_the_pr_comes_from_the_run_cursor_first(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "fr.commands.push_cmd.branch_runs",
        lambda _root: [SimpleNamespace(pr=f"https://github.com/{REPO}/pull/42")],
    )
    forge = Forge()
    assert _run(monkeypatch, forge).exit_code == 0
    assert "open_pr_for_head" not in forge.ops
    assert ("pr_view", (REPO, 42)) in forge.calls


def test_the_pr_is_found_by_head_without_a_cursor(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge = Forge(open_pr=9)
    assert _run(monkeypatch, forge).exit_code == 0
    assert ("open_pr_for_head", (REPO, "feat/other")) in forge.calls
    assert ("pr_view", (REPO, 9)) in forge.calls


def test_no_open_pr_exits_2(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    result = _run(monkeypatch, Forge(open_pr=None))
    assert result.exit_code == 2
    assert "no open pull request" in result.output


def test_a_recorded_pr_that_is_no_longer_open_exits_2(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "fr.commands.push_cmd.branch_runs",
        lambda _root: [SimpleNamespace(pr=f"https://github.com/{REPO}/pull/42")],
    )
    forge = Forge()
    forge.view = {**forge.view, "state": "MERGED"}
    result = _run(monkeypatch, forge)
    assert result.exit_code == 2
    assert "MERGED" in result.output


@pytest.mark.parametrize(
    "branch",
    [
        "feat/batch-x",
        "fix/batch-x",
        "chore/closeout-2026-11-23-1",
        "chore/closeout-feat-batch-x",
        "chore/triage-state-s-wave-2",
        "chore/ops-p",
    ],
)
@pytest.mark.parametrize("modes", ["fix/fix", "report/off", "off/off"])
def test_a_managed_branch_reads_nothing_and_exits_0(
    repo: Path, monkeypatch: pytest.MonkeyPatch, branch: str, modes: str
) -> None:
    conflicts, ci = modes.split("/")
    git(repo, "checkout", "-q", "main")
    land_on_main(repo, f"git:\n  settle:\n    conflicts: '{conflicts}'\n    ci: '{ci}'\n")
    git(repo, "checkout", "-q", "-b", branch)
    forge = Forge(open_pr=None)
    result = _run(monkeypatch, forge)
    assert result.exit_code == 0, result.output
    assert "managed" in result.output and "wave driver" in result.output
    assert forge.calls == []


@pytest.mark.parametrize(
    "branch", ["chore/archive-p", "chore/closeout-2026-11-23-feat-x", "feat/other"]
)
def test_an_unmanaged_branch_is_settled(
    repo: Path, monkeypatch: pytest.MonkeyPatch, branch: str
) -> None:
    git(repo, "checkout", "-q", "-B", branch)
    forge = Forge()
    assert _run(monkeypatch, forge).exit_code == 0
    assert "pr_view" in forge.ops


@pytest.mark.parametrize("op", ["open_pr_for_head", "pr_view", "pr_checks", "required_check_names"])
def test_an_unsupported_read_is_unsupported_and_exits_0(
    repo: Path, monkeypatch: pytest.MonkeyPatch, op: str
) -> None:
    forge = Forge(open_pr=None if op != "open_pr_for_head" else 7, unsupported=op)
    if op != "open_pr_for_head":
        forge.open_pr = 7
    result = _run(monkeypatch, forge)
    assert result.exit_code == 0, result.output
    assert "unsupported" in result.output and "glab" in result.output


def test_unsupported_discovery_wins_over_the_no_pr_refusal(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge = Forge(open_pr=None, unsupported="open_pr_for_head")
    result = _run(monkeypatch, forge)
    assert result.exit_code == 0
    assert "unsupported" in result.output


@pytest.mark.parametrize("op", ["open_pr_for_head", "pr_view", "pr_checks"])
def test_a_transient_forge_failure_exits_75(
    repo: Path, monkeypatch: pytest.MonkeyPatch, op: str
) -> None:
    result = _run(monkeypatch, Forge(error=op))
    assert result.exit_code == 75, result.output
    assert "502" in result.output


def test_declared_gates_come_first(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (repo / ".fr").mkdir(exist_ok=True)
    (repo / ".fr" / "ci.yaml").write_text("gate_checks: [ci-ok]\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "gates")
    forge = Forge(
        checks=[{"name": "ci-ok", "bucket": "pass"}, {"name": "advisory", "bucket": "fail"}],
        required=["advisory"],
    )
    result = _run(monkeypatch, forge)
    assert result.exit_code == 0, result.output
    assert "required_check_names" not in forge.ops


def test_required_checks_come_next(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    forge = Forge(
        checks=[{"name": "ci-ok", "bucket": "pass"}, {"name": "advisory", "bucket": "fail"}],
        required=["ci-ok"],
    )
    result = _run(monkeypatch, forge)
    assert result.exit_code == 0, result.output
    assert ("required_check_names", (REPO, "main")) in forge.calls


def test_with_no_gate_every_check_is_read_and_nothing_refuses(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge = Forge(
        checks=[{"name": "ci-ok", "bucket": "pass"}, {"name": "advisory", "bucket": "fail"}]
    )
    result = _run(monkeypatch, forge)
    assert result.exit_code == 4, result.output
    assert "advisory" in result.output


def test_ci_none_gives_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path)  # no workflow: `fr services` says ci none
    git(root, "checkout", "-q", "-b", "feat/other")
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    monkeypatch.setattr("fr.commands.pr_cmd.origin_slug", lambda _root: REPO)
    monkeypatch.setattr("fr.commands.push_cmd.branch_runs", lambda _root: [])
    forge = Forge(checks=[])
    result = _run(monkeypatch, forge)
    assert result.exit_code == 0, result.output
    assert "ci (fix, default): none" in result.output
    assert "pr_checks" not in forge.ops


def test_a_conflicting_pr_exits_4(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    forge = Forge(checks=[])
    forge.view = {**forge.view, "mergeable": "CONFLICTING", "merge_state": "DIRTY"}
    result = _run(monkeypatch, forge)
    assert result.exit_code == 4
    assert "conflicting" in result.output and "unrunnable" in result.output
    assert "never rebase" in result.output


def test_a_pending_fix_concern_exits_75_at_the_end_of_the_wait(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _run(monkeypatch, Forge(checks=[{"name": "ci-ok", "bucket": "pending"}]))
    assert result.exit_code == 75


def test_the_repo_setting_decides_the_modes(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    git(repo, "checkout", "-q", "main")
    land_on_main(repo, "git:\n  settle:\n    ci: report\n")
    git(repo, "checkout", "-q", "feat/other")
    result = _run(monkeypatch, Forge(checks=[{"name": "ci-ok", "bucket": "fail"}]))
    assert result.exit_code == 0, result.output
    assert "ci (report, repo): red" in result.output


def test_both_off_reads_nothing(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    git(repo, "checkout", "-q", "main")
    land_on_main(repo, "git:\n  settle:\n    conflicts: 'off'\n    ci: 'off'\n")
    git(repo, "checkout", "-q", "feat/other")
    forge = Forge()
    result = _run(monkeypatch, forge)
    assert result.exit_code == 0, result.output
    assert forge.calls == []


def test_a_wait_above_the_ceiling_is_refused(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fr.commands.pr_cmd.client_for", lambda _root: Forge())
    result = runner.invoke(app, ["pr", "settle", "--wait", "541"])
    assert result.exit_code == 2
    assert "540" in result.output


def test_json_prints_the_verdict(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    result = _run(monkeypatch, Forge(), "--json")
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["conflict_state"] == "clean" and data["ci_state"] == "green"
    assert data["exit_code"] == 0
    assert data["witness"] == f"fix/fix:clean/green@{'c' * 40}"
