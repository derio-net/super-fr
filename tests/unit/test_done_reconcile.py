"""Unit tests for `fr_vk.pr_state.reconcile_done_issues` (#294).

Closes the linked GH Issue of terminal-Done cards (reached by any path —
manual move, VK auto-move, pr_state), bounded by a persisted seen-set so the
per-tick cost self-limits to ~0 once the backlog is reconciled.
"""

from __future__ import annotations

from typing import Any

from tests.unit.fakes import FakeMcpClient


def _prime(
    mcp: FakeMcpClient, cid: str, *, status: str, title: str, url: str | None = None
) -> None:
    mcp.issues[cid] = {
        "id": cid,
        "simple_id": cid[-1],
        "status": status,
        "title": title,
        "latest_pr_url": url,
    }


def test_closes_done_card_issue_from_title():
    from fr_vk.pr_state import reconcile_done_issues

    mcp = FakeMcpClient()
    # No latest_pr_url — proves the close uses the TITLE, not a PR url.
    _prime(mcp, "c1", status="Done", title="gh#5: [derio-net/runs-fr]", url=None)

    closed: list[tuple[str, str, str]] = []
    out = reconcile_done_issues(
        mcp, seen=set(), close_gh_issue=lambda r, n, b: closed.append((r, n, b))
    )

    assert closed == [("derio-net/runs-fr", "5", "github")]
    assert out == {"derio-net/runs-fr#5"}


def test_seen_set_bounds_reclose():
    from fr_vk.pr_state import reconcile_done_issues

    mcp = FakeMcpClient()
    _prime(mcp, "c1", status="Done", title="gh#5: [derio-net/runs-fr]")

    closed: list[tuple[str, str, str]] = []
    out = reconcile_done_issues(
        mcp, seen={"derio-net/runs-fr#5"}, close_gh_issue=lambda r, n, b: closed.append((r, n, b))
    )

    assert closed == []  # already handled — no gh call
    assert out == {"derio-net/runs-fr#5"}


def test_title_without_repo_is_skipped():
    from fr_vk.pr_state import reconcile_done_issues

    mcp = FakeMcpClient()
    _prime(mcp, "c1", status="Done", title="gh#5: no repo here")

    closed: list[tuple[str, str, str]] = []
    out = reconcile_done_issues(
        mcp, seen=set(), close_gh_issue=lambda r, n, b: closed.append((r, n, b))
    )

    assert closed == []
    assert out == set()


def test_non_done_card_is_ignored():
    from fr_vk.pr_state import reconcile_done_issues

    mcp = FakeMcpClient()
    _prime(mcp, "c1", status="In review", title="gh#5: [derio-net/runs-fr]")

    closed: list[tuple[str, str, str]] = []
    reconcile_done_issues(mcp, seen=set(), close_gh_issue=lambda r, n, b: closed.append((r, n, b)))

    assert closed == []


def test_list_issues_failure_returns_seen_unchanged():
    from fr_vk.pr_state import reconcile_done_issues

    class _BoomMcp:
        def list_issues(self, **kw: Any) -> Any:
            raise RuntimeError("mcp down")

    seen = {"a/b#1"}
    out = reconcile_done_issues(_BoomMcp(), seen=seen, close_gh_issue=lambda r, n, b: None)
    assert out == {"a/b#1"}  # unchanged, no raise


def test_caps_closes_per_tick():
    """A large backlog is amortized: at most `max_closes` Issues close per call;
    the rest stay un-`seen` so the next tick continues."""
    from fr_vk.pr_state import reconcile_done_issues

    mcp = FakeMcpClient()
    for i in range(5):
        _prime(mcp, f"c{i}", status="Done", title=f"gh#{i}: [o/r]")

    closed: list[tuple[str, str, str]] = []
    out = reconcile_done_issues(
        mcp, seen=set(), close_gh_issue=lambda r, n, b: closed.append((r, n, b)), max_closes=2
    )

    assert len(closed) == 2  # capped
    assert len(out) == 2  # only the closed keys are recorded; rest retried next tick


def test_threads_project_id_to_list_issues():
    from fr_vk.pr_state import reconcile_done_issues

    seen_kwargs: list[dict] = []

    class _RecMcp:
        def list_issues(self, **kw: Any) -> Any:
            seen_kwargs.append(kw)
            return []

    reconcile_done_issues(
        _RecMcp(), project_id="proj-x", seen=set(), close_gh_issue=lambda r, n, b: None
    )
    assert seen_kwargs and seen_kwargs[0].get("status") == "Done"
    assert seen_kwargs[0].get("project_id") == "proj-x"


def test_preexisting_seen_keys_survive():
    """The returned set is the union of the input seen and newly-closed keys."""
    from fr_vk.pr_state import reconcile_done_issues

    mcp = FakeMcpClient()
    _prime(mcp, "c1", status="Done", title="gh#9: [o/r]")

    out = reconcile_done_issues(mcp, seen={"o/r#1", "o/r#2"}, close_gh_issue=lambda r, n, b: None)
    assert out == {"o/r#1", "o/r#2", "o/r#9"}


def test_e2e_idempotent_across_two_ticks():
    """The whole point: a Done card with an open linked Issue (no Closes
    keyword anywhere) is closed once; a second tick (with the returned seen)
    does not touch it."""
    from fr_vk.pr_state import reconcile_done_issues

    mcp = FakeMcpClient()
    _prime(
        mcp,
        "c1",
        status="Done",
        title="gh#7: [derio-net/runs-fr]",
        url="https://github.com/derio-net/runs-fr/pull/14",
    )

    closed: list[tuple[str, str, str]] = []
    closer = lambda r, n, b: closed.append((r, n, b))  # noqa: E731

    seen = reconcile_done_issues(mcp, seen=set(), close_gh_issue=closer)
    assert closed == [("derio-net/runs-fr", "7", "github")]

    # Second tick — seen carries over → no re-close.
    reconcile_done_issues(mcp, seen=seen, close_gh_issue=closer)
    assert closed == [("derio-net/runs-fr", "7", "github")]  # still just the one
