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

    closed: list[tuple[str, str]] = []
    out = reconcile_done_issues(mcp, seen=set(), close_gh_issue=lambda r, n: closed.append((r, n)))

    assert closed == [("derio-net/runs-fr", "5")]
    assert out == {"derio-net/runs-fr#5"}


def test_seen_set_bounds_reclose():
    from fr_vk.pr_state import reconcile_done_issues

    mcp = FakeMcpClient()
    _prime(mcp, "c1", status="Done", title="gh#5: [derio-net/runs-fr]")

    closed: list[tuple[str, str]] = []
    out = reconcile_done_issues(
        mcp, seen={"derio-net/runs-fr#5"}, close_gh_issue=lambda r, n: closed.append((r, n))
    )

    assert closed == []  # already handled — no gh call
    assert out == {"derio-net/runs-fr#5"}


def test_title_without_repo_is_skipped():
    from fr_vk.pr_state import reconcile_done_issues

    mcp = FakeMcpClient()
    _prime(mcp, "c1", status="Done", title="gh#5: no repo here")

    closed: list[tuple[str, str]] = []
    out = reconcile_done_issues(mcp, seen=set(), close_gh_issue=lambda r, n: closed.append((r, n)))

    assert closed == []
    assert out == set()


def test_non_done_card_is_ignored():
    from fr_vk.pr_state import reconcile_done_issues

    mcp = FakeMcpClient()
    _prime(mcp, "c1", status="In review", title="gh#5: [derio-net/runs-fr]")

    closed: list[tuple[str, str]] = []
    reconcile_done_issues(mcp, seen=set(), close_gh_issue=lambda r, n: closed.append((r, n)))

    assert closed == []


def test_list_issues_failure_returns_seen_unchanged():
    from fr_vk.pr_state import reconcile_done_issues

    class _BoomMcp:
        def list_issues(self, **kw: Any) -> Any:
            raise RuntimeError("mcp down")

    seen = {"a/b#1"}
    out = reconcile_done_issues(_BoomMcp(), seen=seen, close_gh_issue=lambda r, n: None)
    assert out == {"a/b#1"}  # unchanged, no raise


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

    closed: list[tuple[str, str]] = []
    closer = lambda r, n: closed.append((r, n))  # noqa: E731

    seen = reconcile_done_issues(mcp, seen=set(), close_gh_issue=closer)
    assert closed == [("derio-net/runs-fr", "7")]

    # Second tick — seen carries over → no re-close.
    reconcile_done_issues(mcp, seen=seen, close_gh_issue=closer)
    assert closed == [("derio-net/runs-fr", "7")]  # still just the one
