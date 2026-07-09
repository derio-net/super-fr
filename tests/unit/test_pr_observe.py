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
#
# The default fetch no longer shells out to `gh` directly (that was the
# fr-vk-bypasses-GhClient sharp edge the multi-backend design fixed —
# see docs/superpowers/specs/
# 2026-07-09-multi-backend-git-host-adapters-design.md §6). Its
# subprocess-level behavior per backend is covered by
# test_real_ghclient.py / test_real_glabclient.py / test_real_teaclient.py's
# TestPrStatusByUrl classes; this module's own tests (below) cover only
# the routing — resolve a client for the URL's host, call
# pr_status_by_url, map state+draft to "open"/"merged"/None.


# --- backend-aware default fetch (multi-backend, #2026-07-09) -----------


class _FakeClient:
    def __init__(self, result: dict | None) -> None:
        self._result = result
        self.urls_seen: list[str] = []

    def pr_status_by_url(self, url: str) -> dict | None:
        self.urls_seen.append(url)
        return self._result


def test_default_pr_status_fetch_routes_through_client_for_backend(monkeypatch):
    """The default fetch resolves a client via
    fr.hostclient.client_for_backend(fr._hosts.backend_for_hostname(...))
    and calls pr_status_by_url — not a raw gh subprocess directly."""
    import fr_vk.pr_observe as po

    fake = _FakeClient({"state": "MERGED", "draft": False})
    monkeypatch.setattr(po.hostclient, "client_for_backend", lambda backend: fake)

    assert po._default_pr_status_fetch("https://gitlab.com/g/p/-/merge_requests/1") == "merged"
    assert fake.urls_seen == ["https://gitlab.com/g/p/-/merge_requests/1"]


def test_default_pr_status_fetch_open_non_draft(monkeypatch):
    import fr_vk.pr_observe as po

    fake = _FakeClient({"state": "OPEN", "draft": False})
    monkeypatch.setattr(po.hostclient, "client_for_backend", lambda backend: fake)
    assert po._default_pr_status_fetch("https://github.com/o/r/pull/1") == "open"


def test_default_pr_status_fetch_draft_is_none(monkeypatch):
    import fr_vk.pr_observe as po

    fake = _FakeClient({"state": "OPEN", "draft": True})
    monkeypatch.setattr(po.hostclient, "client_for_backend", lambda backend: fake)
    assert po._default_pr_status_fetch("https://github.com/o/r/pull/1") is None


def test_default_pr_status_fetch_none_result_is_none(monkeypatch):
    import fr_vk.pr_observe as po

    fake = _FakeClient(None)
    monkeypatch.setattr(po.hostclient, "client_for_backend", lambda backend: fake)
    assert po._default_pr_status_fetch("https://github.com/o/r/pull/1") is None


def test_default_pr_status_fetch_client_raises_is_none(monkeypatch):
    """A client-side exception (network blip, CLI missing) must not
    propagate — matches the old subprocess-based default's fail-soft
    posture."""
    import fr_vk.pr_observe as po

    class _RaisingClient:
        def pr_status_by_url(self, url: str) -> dict | None:
            raise RuntimeError("glab not found")

    monkeypatch.setattr(po.hostclient, "client_for_backend", lambda backend: _RaisingClient())
    assert po._default_pr_status_fetch("https://gitlab.com/g/p/-/merge_requests/1") is None


def test_default_pr_status_fetch_resolves_backend_from_url_hostname(monkeypatch):
    """Different cards on one VK board can point at repos on different
    backends — the fetch must resolve per-URL, not from any ambient
    single-repo context."""
    import fr_vk.pr_observe as po

    seen_backends: list[str] = []

    def fake_client_for_backend(backend: str):
        seen_backends.append(backend)
        return _FakeClient({"state": "OPEN", "draft": False})

    monkeypatch.setattr(po.hostclient, "client_for_backend", fake_client_for_backend)
    po._default_pr_status_fetch("https://github.com/o/r/pull/1")
    po._default_pr_status_fetch("https://gitlab.com/g/p/-/merge_requests/1")
    assert seen_backends == ["github", "gitlab"]
