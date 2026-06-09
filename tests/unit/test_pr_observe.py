"""Unit tests for `fr_vk.pr_observe` — the PR-status observer (#290).

Builds the `{card_id: "open"|"merged"}` map that `pr_state.tick` consumes,
resolving each card's `latest_pr_url` to its merge state. The gh fetch is
injectable so these tests never shell out.
"""

from __future__ import annotations

from typing import Any

from tests.unit.fakes import FakeMcpClient


def _prime(mcp: FakeMcpClient, cid: str, *, status: str, url: str | None, title: str = "") -> None:
    mcp.issues[cid] = {
        "id": cid,
        "simple_id": cid[-1],
        "status": status,
        "title": title,
        "latest_pr_url": url,
    }


def test_observe_maps_merged_and_open_skips_no_url():
    from fr_vk.pr_observe import observe_pr_status

    mcp = FakeMcpClient()
    _prime(mcp, "c1", status="In review", url="https://github.com/o/r/pull/13")
    _prime(mcp, "c2", status="In progress", url="https://github.com/o/r/pull/14")
    _prime(mcp, "c3", status="In progress", url=None)  # no PR yet → skipped

    fetched: list[str] = []

    def fake_fetch(url: str) -> str | None:
        fetched.append(url)
        return {
            "https://github.com/o/r/pull/13": "merged",
            "https://github.com/o/r/pull/14": "open",
        }.get(url)

    out = observe_pr_status(mcp, project_id="p", pr_status_fetch=fake_fetch)

    assert out == {"c1": "merged", "c2": "open"}
    # Each card's PR is fetched once (deduped across the two status list calls).
    assert sorted(fetched) == [
        "https://github.com/o/r/pull/13",
        "https://github.com/o/r/pull/14",
    ]


def test_observe_fetches_each_card_once_across_both_status_lists():
    """A card returned under BOTH status lists (a server that doesn't honour
    the filter — like FakeMcpClient) must be PR-fetched exactly once. Pins the
    `seen`-before-fetch ordering invariant."""
    from fr_vk.pr_observe import observe_pr_status

    mcp = FakeMcpClient()
    _prime(mcp, "c1", status="In review", url="https://github.com/o/r/pull/1")

    calls: list[str] = []

    def fetch(url: str) -> str | None:
        calls.append(url)
        return "merged"

    out = observe_pr_status(mcp, pr_status_fetch=fetch)
    assert out == {"c1": "merged"}
    assert calls == ["https://github.com/o/r/pull/1"]  # exactly once, not twice


def test_observe_omits_draft_and_closed():
    from fr_vk.pr_observe import observe_pr_status

    mcp = FakeMcpClient()
    _prime(mcp, "c1", status="In progress", url="https://github.com/o/r/pull/1")  # draft → None
    _prime(mcp, "c2", status="In review", url="https://github.com/o/r/pull/2")  # closed → None

    out = observe_pr_status(mcp, pr_status_fetch=lambda url: None)
    assert out == {}


def test_observe_skips_card_whose_fetch_raises_without_failing_others():
    from fr_vk.pr_observe import observe_pr_status

    mcp = FakeMcpClient()
    _prime(mcp, "c1", status="In review", url="https://github.com/o/r/pull/1")
    _prime(mcp, "c2", status="In review", url="https://github.com/o/r/pull/2")

    def fetch(url: str) -> str | None:
        if url.endswith("/1"):
            raise RuntimeError("gh blew up")
        return "merged"

    out = observe_pr_status(mcp, pr_status_fetch=fetch)
    assert out == {"c2": "merged"}  # c1 skipped, no raise


def test_observe_survives_list_issues_failure():
    from fr_vk.pr_observe import observe_pr_status

    class _BoomMcp:
        def list_issues(self, **kw: Any) -> Any:
            raise RuntimeError("mcp down")

    out = observe_pr_status(_BoomMcp(), pr_status_fetch=lambda url: "merged")
    assert out == {}  # logged + swallowed


# --- default gh PR-status fetcher ---------------------------------------


def _patch_gh(monkeypatch, *, stdout: str, rc: int = 0, raises: Exception | None = None) -> None:
    import fr_vk.pr_observe as po

    class _Res:
        returncode = rc
        stderr = ""

    def fake_run(cmd: Any, **kw: Any) -> Any:
        if raises is not None:
            raise raises
        r = _Res()
        r.stdout = stdout  # type: ignore[attr-defined]
        return r

    monkeypatch.setattr(po.subprocess, "run", fake_run)


def test_default_pr_status_merged(monkeypatch):
    from fr_vk.pr_observe import _default_pr_status_fetch

    _patch_gh(monkeypatch, stdout='{"state": "MERGED", "isDraft": false}')
    assert _default_pr_status_fetch("https://github.com/o/r/pull/1") == "merged"


def test_default_pr_status_open(monkeypatch):
    from fr_vk.pr_observe import _default_pr_status_fetch

    _patch_gh(monkeypatch, stdout='{"state": "OPEN", "isDraft": false}')
    assert _default_pr_status_fetch("https://github.com/o/r/pull/1") == "open"


def test_default_pr_status_draft_is_none(monkeypatch):
    from fr_vk.pr_observe import _default_pr_status_fetch

    _patch_gh(monkeypatch, stdout='{"state": "OPEN", "isDraft": true}')
    assert _default_pr_status_fetch("https://github.com/o/r/pull/1") is None


def test_default_pr_status_closed_unmerged_is_none(monkeypatch):
    from fr_vk.pr_observe import _default_pr_status_fetch

    _patch_gh(monkeypatch, stdout='{"state": "CLOSED", "isDraft": false}')
    assert _default_pr_status_fetch("https://github.com/o/r/pull/1") is None


def test_default_pr_status_subprocess_failure_is_none(monkeypatch):
    from fr_vk.pr_observe import _default_pr_status_fetch

    _patch_gh(monkeypatch, stdout="", rc=1)
    assert _default_pr_status_fetch("https://github.com/o/r/pull/1") is None


def test_default_pr_status_raises_is_none(monkeypatch):
    from fr_vk.pr_observe import _default_pr_status_fetch

    _patch_gh(monkeypatch, stdout="", raises=FileNotFoundError("no gh"))
    assert _default_pr_status_fetch("https://github.com/o/r/pull/1") is None
