"""Batch `isolation-reap-names`: gc must not reap a workspace on a PR that only
shares its branch NAME, and `fr isolation up` must leave consistent state.

- super-fr#844 — a MERGED PR found by branch name that merged BEFORE the
  workspace existed belongs to an earlier use of the name, not this workspace.
- super-fr#553 — a worktree whose checked-out branch drifted from the one fr
  registered is not reaped on the registered branch's PR.
- super-fr#578 — a failed `devcontainer up` leaves a state record that
  `status`/`down` can address.
- super-fr#843 — appending fr's patterns to a shared `info/exclude` that lacks
  a trailing newline must not glue onto its last line.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from fr.isolation.local import (
    IsolationError,
    LocalWorktreeDevcontainerTarget,
    _git_common_dir,
)
from fr.isolation.types import list_states, load_state
from tests.unit.test_isolation import FakeRunner, _gc_env, make_repo_with_origin


def _merged(merged_at: str) -> str:
    return json.dumps({"state": "MERGED", "url": "u", "mergedAt": merged_at})


# ---------- super-fr#844: a PR that merged before the workspace existed ----------


def test_gc_does_not_reap_a_fresh_workspace_on_an_earlier_merged_pr_of_the_same_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The #844 repro: a close-out branch name already used by a merged PR is cut
    # fresh from origin/main. `gh pr view <name>` still answers MERGED — for the
    # OLD PR, which merged before this workspace was created.
    branch = "chore/closeout-x"
    repo, runner, target, up = _gc_env(
        tmp_path, monkeypatch, pr_by_branch={branch: _merged("2020-01-01T00:00:00Z")}
    )
    wt = up(branch)

    (action,) = [a for a in target.gc() if a.branch == branch]

    assert action.verdict != "merged", action
    assert action.action != "reaped", action
    assert wt.is_dir()
    assert load_state(repo, branch) is not None


def test_gc_still_reaps_a_workspace_whose_pr_merged_after_it_was_created(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The control: the PR this workspace produced merges later than its `up`.
    branch = "feat/done"
    repo, runner, target, up = _gc_env(
        tmp_path, monkeypatch, pr_by_branch={branch: _merged("2999-01-01T00:00:00Z")}
    )
    wt = up(branch)

    (action,) = [a for a in target.gc() if a.branch == branch]

    assert action.verdict == "merged" and action.action == "reaped", action
    assert not wt.exists()


def test_gc_asks_gh_for_the_merge_time(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, runner, target, up = _gc_env(tmp_path, monkeypatch, pr_by_branch={})
    up("feat/a")
    target.gc()
    views = [c for c in runner.argv_for("gh") if c[:3] == ["gh", "pr", "view"]]
    assert views and all("mergedAt" in c[c.index("--json") + 1] for c in views)


# ---------- super-fr#553: a drifted workspace is not reaped on the old branch ----------


def test_gc_does_not_reap_a_workspace_whose_checkout_drifted_to_another_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The registered branch's PR merged after `up`, but the worktree now has a
    # DIFFERENT branch checked out, whose work nothing has checked.
    branch = "feat/registered"
    repo, runner, target, up = _gc_env(
        tmp_path, monkeypatch, pr_by_branch={branch: _merged("2999-01-01T00:00:00Z")}
    )
    wt = up(branch)
    subprocess.run(["git", "-C", str(wt), "checkout", "-q", "-b", "fix/other"], check=True)

    (action,) = [a for a in target.gc() if a.branch == branch]

    assert action.action == "skipped", action
    assert "fix/other" in (action.detail or "")
    assert wt.is_dir()


# ---------- super-fr#578: a failed devcontainer up is still addressable ----------


def test_failed_devcontainer_up_leaves_a_state_record_that_down_can_address(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path, ["dev"], default="dev")
    target = LocalWorktreeDevcontainerTarget(repo, runner=FakeRunner(fail_on="devcontainer"))

    with pytest.raises(IsolationError) as exc_info:
        target.up(None, "feat/broken")

    st = load_state(repo, "feat/broken")
    assert st is not None, "a failed up left a worktree with no state record"
    assert st.worktree.is_dir()
    assert "feat/broken" in [s.branch for s in list_states(repo)]
    assert "fr isolation down --branch feat/broken" in str(exc_info.value)

    target.down(st, force=True)
    assert not st.worktree.exists()
    assert load_state(repo, "feat/broken") is None


# ---------- super-fr#843: info/exclude without a trailing newline ----------


def test_up_does_not_glue_patterns_onto_an_exclude_line_without_trailing_newline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path, ["dev"], default="dev")
    exclude = _git_common_dir(repo) / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    exclude.write_text("# operator's own\n*.log")  # hand-edited, no trailing \n

    LocalWorktreeDevcontainerTarget(repo, runner=FakeRunner()).up(None, "feat/x")

    lines = exclude.read_text().splitlines()
    assert "*.log" in lines
    assert ".fr-isolation" in lines
    assert exclude.read_text().endswith("\n")
