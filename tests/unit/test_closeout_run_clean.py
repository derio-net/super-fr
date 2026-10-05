"""Close-out runs clean — batch `closeout-run` (super-fr#811, #824, #825, #826).

Four independent defects that each left a close-out dirty or wrong. They were
found together, in take 10 of the talk run (#817):

- #811: `fr pickup --run` in a base clone that has not pulled the merge yet
  said "no run state" with no hint, and `fr status` reported "nothing owed"
  against `origin/<default>` while reading the stale working tree;
- #824: the devcontainer CLI's `devcontainer-lock.json` left every fr
  workspace dirty, so `fr isolation down` refused;
- #825: the close-out brief brought up a housekeeping workspace and never
  took it down;
- #826: the committed `scripts/validate-plans.sh` wrapper exec'd a Claude Code
  marketplace path, which does not exist on an OpenCode- or Hermes-only host.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from fr.commands import status_cmd
from fr.isolation.local import LocalWorktreeDevcontainerTarget
from fr.plan_validator_wrapper import WRAPPER_TEXT
from fr.run.closeout import branch_closeout_brief, closeout_brief
from fr.run.model import RunState, StepRecord
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient
from tests.unit.test_isolation import FakeRunner, make_repo
from tests.unit.test_merge_evidence import (
    _add_remote,
    _commit,
    _git,
    _init,
    _publish,
    _write_plan,
    stub_fetch,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS_REL = Path("docs") / "superpowers" / "runs"


# --- #811: an unpulled base clone --------------------------------------------


@pytest.fixture
def fetched(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    return stub_fetch(monkeypatch)


def _unpulled_clone(tmp_path: Path) -> Path:
    """A clone whose `origin/main` carries a merged feature (a plan plus its
    run file) that the working tree has not pulled: HEAD is strictly behind
    the remote-tracking ref, exactly the base clone of a fresh close-out
    session right after the PR merged."""
    repo = _init(tmp_path / "r")
    _add_remote(repo, tmp_path / "o.git")
    _publish(repo)
    _write_plan(repo, "2026-09-29-feature", [("agentic", True)])
    run_file = repo / RUNS_REL / "r1.yaml"
    run_file.parent.mkdir(parents=True, exist_ok=True)
    run_file.write_text("run: r1\n")
    _commit(repo, "the merged feature")
    _publish(repo)
    _git(repo, "reset", "-q", "--hard", "HEAD~1")
    return repo


def _invoke(monkeypatch: pytest.MonkeyPatch, repo: Path, argv: list[str]):
    monkeypatch.setattr(status_cmd, "_make_gh_client", lambda: FakeGhClient())
    monkeypatch.chdir(repo)
    monkeypatch.setenv("VK_REPO_ROOT", str(repo))
    return CliRunner().invoke(app, argv)


def _flat(result) -> str:
    return " ".join(((result.output or "") + " " + (result.stderr or "")).split())


def test_pickup_run_in_an_unpulled_clone_says_the_run_is_on_the_remote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fetched: list[str]
) -> None:
    repo = _unpulled_clone(tmp_path)

    result = _invoke(monkeypatch, repo, ["pickup", "--run", "r1"])

    assert result.exit_code == 2, result.output
    out = _flat(result)
    assert "origin/main" in out, out
    assert "git pull" in out, out
    assert "fr has no record" not in out, out
    # The close-out session runs right after the merge, before any fetch:
    # pickup fetches first, or the remote-tracking ref is as stale as the tree.
    assert fetched == ["origin"]


def test_pickup_run_that_exists_nowhere_still_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fetched: list[str]
) -> None:
    repo = _unpulled_clone(tmp_path)

    result = _invoke(monkeypatch, repo, ["pickup", "--run", "nope"])

    assert result.exit_code == 2
    out = _flat(result)
    assert "git pull" not in out, out
    assert "nope" in out


def test_status_sweep_in_an_unpulled_clone_says_its_answer_is_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fetched: list[str]
) -> None:
    repo = _unpulled_clone(tmp_path)

    result = _invoke(monkeypatch, repo, ["status"])

    assert result.exit_code == 0, result.output
    out = _flat(result)
    assert "behind origin/main" in out, out
    assert "git pull" in out, out


def test_status_sweep_json_reports_how_far_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fetched: list[str]
) -> None:
    repo = _unpulled_clone(tmp_path)

    result = _invoke(monkeypatch, repo, ["status", "--format", "json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["behind_ref"] == 1


def test_status_sweep_on_an_up_to_date_clone_prints_no_staleness_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fetched: list[str]
) -> None:
    repo = _unpulled_clone(tmp_path)
    _git(repo, "merge", "-q", "--ff-only", "origin/main")

    text = _invoke(monkeypatch, repo, ["status"])
    data = _invoke(monkeypatch, repo, ["status", "--format", "json"])

    assert "behind" not in _flat(text)
    assert json.loads(data.output)["behind_ref"] is None


def test_status_sweep_on_a_branch_ahead_of_the_ref_prints_no_staleness_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fetched: list[str]
) -> None:
    """A feature branch that diverged from the ref is not "behind": its own
    work is the point, and a pull is not the fix."""
    repo = _unpulled_clone(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feat/y")
    (repo / "y.txt").write_text("y\n")
    _commit(repo, "branch work")

    result = _invoke(monkeypatch, repo, ["status"])

    assert "behind" not in _flat(result)


# --- #824: devcontainer-lock.json -------------------------------------------


def test_up_git_excludes_the_devcontainer_lock_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The devcontainer CLI writes `.devcontainer/<profile>/devcontainer-lock
    .json` on `up`. fr owns that tooling, so the file must never make the
    workspace dirty (and so never make `down` refuse)."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path, ["dev"], default="dev")
    target = LocalWorktreeDevcontainerTarget(repo, runner=FakeRunner())
    target.up(profile=None, branch="feat/x")

    # info/exclude is shared by every worktree of the repo, so the base clone
    # answers for the workspace too.
    (repo / ".devcontainer" / "dev" / "devcontainer-lock.json").write_text("{}\n")
    porcelain = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "devcontainer-lock.json" not in porcelain, porcelain


def test_the_lock_file_exclude_is_anchored_and_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path, ["dev"], default="dev")
    target = LocalWorktreeDevcontainerTarget(repo, runner=FakeRunner())
    st = target.up(profile=None, branch="feat/x")
    target._write_isolation_marker(st.worktree, "feat/x")

    lines = (repo / ".git" / "info" / "exclude").read_text().splitlines()
    assert lines.count("/.devcontainer/*/devcontainer-lock.json") == 1
    # A lock file somewhere else in the repo is the repo's own business.
    (repo / "other").mkdir()
    (repo / "other" / "devcontainer-lock.json").write_text("{}\n")
    porcelain = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=all"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "other/devcontainer-lock.json" in porcelain


# --- #825: the housekeeping workspace ----------------------------------------


def _run_state(*, plan: bool) -> RunState:
    steps = {"deliver": StepRecord(state="done", emitted={"pr": "https://example.com/pr/1"})}
    if plan:
        steps["plan"] = StepRecord(
            state="done", emitted={"plan": "docs/superpowers/plans/2026-09-29-feature"}
        )
    return RunState(
        run="r1",
        workflow="fr-goal@1",
        branch="feat/x",
        started="2026-09-29T00:00:00Z",
        cursor="deliver",
        steps=steps,
    )


@pytest.mark.parametrize(
    ("brief", "housekeeping"),
    [
        (
            lambda root: closeout_brief(root, _run_state(plan=True)),
            "chore/archive-2026-09-29-feature",
        ),
        (lambda root: closeout_brief(root, _run_state(plan=False)), "chore/closeout-r1"),
        (lambda root: branch_closeout_brief(root, "feat/x"), "chore/closeout-feat-x"),
    ],
    ids=["run-with-plan", "run-without-plan", "branch"],
)
def test_the_brief_takes_down_the_housekeeping_workspace_it_brought_up(
    tmp_path: Path, brief, housekeeping: str
) -> None:
    out = brief(tmp_path)

    i_up = out.index(f"fr isolation up --branch {housekeeping}")
    i_pr = out.index("open the housekeeping PR")
    i_down = out.index(f"fr isolation down --branch {housekeeping}")
    assert i_up < i_pr < i_down
    # ...and only once that PR has merged: `down` refuses unlanded work.
    down_line = out[i_down : out.index("\n", i_down) if "\n" in out[i_down:] else None]
    assert "merged" in down_line, down_line


# --- #826: a harness-neutral validator wrapper -------------------------------


def _stub(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/usr/bin/env bash\n{body}\n")
    path.chmod(0o755)
    return path


def _run_wrapper(tmp_path: Path, path_dirs: list[Path]) -> subprocess.CompletedProcess[str]:
    wrapper = _stub(tmp_path / "repo" / "scripts" / "validate-plans.sh", "")
    wrapper.write_text(WRAPPER_TEXT)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = {
        "HOME": str(home),
        "PATH": os.pathsep.join([*map(str, path_dirs), "/usr/bin", "/bin"]),
    }
    return subprocess.run(
        [str(wrapper), "a.md"], env=env, capture_output=True, text=True, check=False
    )


def test_the_wrapper_delegates_to_the_installed_fr_on_any_harness(tmp_path: Path) -> None:
    """No Claude Code marketplace under $HOME at all — an OpenCode-only host."""
    log = tmp_path / "fr.log"
    _stub(tmp_path / "bin" / "fr", f'echo "$*" >> {log}')

    done = _run_wrapper(tmp_path, [tmp_path / "bin"])

    assert done.returncode == 0, done.stderr
    assert log.read_text().splitlines()[-1] == "validate plans a.md"


def test_the_wrapper_falls_back_to_the_marketplace_validator_for_an_older_fr(
    tmp_path: Path,
) -> None:
    """An `fr` that predates `fr validate plans` must not break a Claude Code
    host whose marketplace copy still works."""
    _stub(tmp_path / "bin" / "fr", "exit 2")
    log = tmp_path / "market.log"
    _stub(
        tmp_path
        / "home/.claude/plugins/marketplaces/derio-net--super-fr/scripts/validate-plans.sh",
        f'echo "$*" >> {log}',
    )

    done = _run_wrapper(tmp_path, [tmp_path / "bin"])

    assert done.returncode == 0, done.stderr
    assert log.read_text().splitlines() == ["a.md"]


def test_the_wrapper_names_the_fix_when_no_validator_is_installed(tmp_path: Path) -> None:
    done = _run_wrapper(tmp_path, [])

    assert done.returncode == 127
    assert "no super-fr plan validator found" in done.stderr, done.stderr


def _plan_md(root: Path, name: str, body: str) -> Path:
    path = root / "docs" / "superpowers" / "plans" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return path


def test_fr_validate_plans_runs_the_bundled_validator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    good = _plan_md(tmp_path, "2026-09-29-good.md", "# Good\n\n**Status:** draft\n")
    bad = _plan_md(tmp_path, "not-dated.md", "# Bad\n")
    monkeypatch.chdir(tmp_path)

    ok = CliRunner().invoke(app, ["validate", "plans", str(good)])
    ko = CliRunner().invoke(app, ["validate", "plans", str(bad)])

    assert ok.exit_code == 0, ok.output
    assert ko.exit_code == 1, ko.output
    assert "malformed filename" in _flat(ko)


def test_the_bundled_validator_is_byte_identical_to_the_shipped_script() -> None:
    """`scripts/validate-plans.sh` stays: every committed wrapper in the fleet
    still execs the marketplace copy. The two must not drift."""
    bundled = REPO_ROOT / "packages/fr/src/fr/data/validate-plans.sh"
    assert bundled.read_bytes() == (REPO_ROOT / "scripts/validate-plans.sh").read_bytes()
