"""Integration tests for `fr_dispatch.cli.main()`.

These exercise the daemon-level wiring with real git checkouts (E4)
and a monkeypatched MCP/gh surface — proving the loop drives
`discover_plans` against the head-of-main, not the stale tip.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    )


def _init_bare_with_clone(tmp_path: Path) -> Path:
    """Create a bare origin + a stale clone at `<tmp>/repos/foo`.

    The clone starts at the seed commit; origin then advances by one
    commit that adds a plan dir. The clone must `git pull --ff-only`
    before `discover_plans` runs, otherwise the new plan stays
    invisible.

    Returns the local clone path.
    """
    bare = tmp_path / "origin.git"
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()
    clone = repos_dir / "foo"
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(bare)],
        check=True,
        capture_output=True,
    )

    # Seed via a throwaway working tree.
    seed = tmp_path / "_seed"
    seed.mkdir()
    _git(seed, "init", "-b", "main")
    _git(seed, "config", "user.email", "test@example.com")
    _git(seed, "config", "user.name", "test")
    (seed / "README.md").write_text("seed\n")
    _git(seed, "add", "README.md")
    _git(seed, "commit", "-m", "seed")
    _git(seed, "remote", "add", "origin", str(bare))
    _git(seed, "push", "origin", "main")

    subprocess.run(
        ["git", "clone", str(bare), str(clone)],
        check=True,
        capture_output=True,
    )
    _git(clone, "config", "user.email", "test@example.com")
    _git(clone, "config", "user.name", "test")

    # Origin advances: add a plan that isn't on the local clone yet.
    plan_dir = seed / "docs" / "superpowers" / "plans" / "new-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "_meta.yaml").write_text("plan: new-plan\ntarget_repo: example/foo\n")
    (plan_dir / "_prose.md").write_text("# new plan\n")
    _git(seed, "add", ".")
    _git(seed, "commit", "-m", "add plan")
    _git(seed, "push", "origin", "main")

    return clone


def test_tick_syncs_bridge_owned_checkout_before_discover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:  # E4 / #286
    """The bridge clones + syncs its OWN checkout (not the shared one VK
    uses) to head-of-main before plans are walked. Proves the dedicated
    checkout is created under FR_BRIDGE_CHECKOUT_DIR and advanced, and that
    sync precedes discovery."""
    clone = _init_bare_with_clone(tmp_path)  # configured (VK-shared) checkout
    bridge_base = tmp_path / "bridge-co"

    monkeypatch.setenv("VK_BRIDGE_REPOS", str(clone))
    monkeypatch.setenv("VK_BRIDGE_LOCK_PATH", str(tmp_path / "vk-bridge.lock"))
    monkeypatch.setenv("FR_BRIDGE_CHECKOUT_DIR", str(bridge_base))

    from fr_vk import bridge_cli

    monkeypatch.setattr(bridge_cli, "_SEEN_PLANS_PATH", tmp_path / "_seen_plans.json")
    monkeypatch.setattr(
        bridge_cli, "_repo_owner_name", lambda repo_path: f"example/{repo_path.name}"
    )

    # Spy on `_pull_managed_repo` so the ordering assertion (sync before
    # discover) is testable; delegate to the real sync so the bridge
    # checkout actually advances.
    pull_order: list[str] = []
    real_pull = bridge_cli._pull_managed_repo

    def spy_pull(repo_path: Path) -> bool:
        result = real_pull(repo_path)
        pull_order.append("pull")
        return result

    monkeypatch.setattr(bridge_cli, "_pull_managed_repo", spy_pull)

    def spy_discover(repo: str, gh: Any, **kwargs: Any) -> list[Any]:
        pull_order.append("discover")
        return []

    monkeypatch.setattr(bridge_cli, "discover_plans", spy_discover)

    class _StubMcp:
        def list_workspaces(self, **kwargs: Any) -> list[Any]:
            return []

        def list_issues(self, **kwargs: Any) -> list[Any]:
            return []

        def close(self) -> None:
            pass

    monkeypatch.setattr(bridge_cli, "_construct_mcp_client", lambda: _StubMcp())

    class _StubGh:
        def view_issue(self, repo: str, number: int) -> dict[str, Any]:
            return {"state": "OPEN", "labels": [], "assignees": [], "body": ""}

        def list_linked_prs(self, repo: str, issue_number: int) -> list[Any]:
            return []

    monkeypatch.setattr(bridge_cli.hostclient, "client_for", lambda repo_root: _StubGh())

    monkeypatch.setattr(bridge_cli._metrics, "push_heartbeat", lambda: None)
    monkeypatch.setattr(bridge_cli._metrics, "push_failure_total", lambda *, reason: None)
    monkeypatch.setattr(bridge_cli._metrics, "push_repo_desync_total", lambda *, repo: None)

    rc = bridge_cli.main([])
    assert rc == 0

    # The BRIDGE-owned checkout (not the configured clone) was created and
    # advanced to head-of-main.
    bridge_plan_dir = bridge_base / "foo" / "docs" / "superpowers" / "plans" / "new-plan"
    assert bridge_plan_dir.is_dir(), (
        "bridge-owned checkout was not created/advanced; "
        f"expected {bridge_plan_dir} to exist after main()"
    )
    # Order: sync must precede discover_plans
    assert pull_order == ["pull", "discover"], (
        f"expected sync before discover_plans, got {pull_order!r}"
    )


def test_tick_logs_configured_repos_count_discovered_plans_and_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Regression guard for the 2026-05-18 silent-tick incident.

    Pre-fix the bridge ran a complete tick with zero per-plan output —
    just "[bridge] - vX.Y.Z - <ts> - tick" + "fr_dispatch: tick complete"
    bracketing total silence. That made it impossible to diagnose
    no-op ticks ("did the bridge see no repos? no plans? skip all?").

    This test pins the three new log signals:
      1. "configured repos: N found at ..." — proves _configured_repos ran
      2. "<owner>: M discoverable plan(s): ..." — proves discover_plans ran
      3. "  <plan_slug>: synced=A errors=B skipped=C" — per-plan result
      4. "summary: T plan(s) ticked, A synced, B errors, C skipped"
    """
    clone = _init_bare_with_clone(tmp_path)
    repos_dir = clone.parent

    monkeypatch.setenv("VK_BRIDGE_REPOS", str(clone))
    monkeypatch.setenv("VK_BRIDGE_LOCK_PATH", str(tmp_path / "vk-bridge.lock"))
    monkeypatch.setenv("FR_REPOS_DIR", str(repos_dir))

    from fr_dispatch import TickResult
    from fr_vk import bridge_cli

    monkeypatch.setattr(bridge_cli, "_SEEN_PLANS_PATH", tmp_path / "_seen_plans.json")
    monkeypatch.setattr(
        bridge_cli, "_repo_owner_name", lambda repo_path: f"example/{repo_path.name}"
    )
    # Bridge-owned checkout resolves to the clone here (no real clone in CI).
    monkeypatch.setattr(
        bridge_cli, "_ensure_bridge_checkout", lambda configured, name, base=None: clone
    )
    monkeypatch.setattr(bridge_cli, "_pull_managed_repo", lambda repo_path: False)
    monkeypatch.setattr(bridge_cli._metrics, "push_repo_desync_total", lambda *, repo: None)

    # Stub one fake plan with a slug we'll check in the log.
    class _StubPlan:
        # `meta.workflow` / `repo_root` added in Phase 12: the bridge now
        # resolves each plan's own shape before ticking it. `workflow=None`
        # is the pre-Phase-12 plan every existing repo has, and resolves the
        # same default `tick` was already using — so this stub still
        # describes today's behaviour, with one more attribute.
        def __init__(self, slug: str) -> None:
            self.dir = tmp_path / slug
            self.repo_root = tmp_path
            self.meta = SimpleNamespace(plan=slug, workflow=None)

    monkeypatch.setattr(
        bridge_cli, "discover_plans", lambda repo, gh, **kw: [_StubPlan("fake-plan-slug")]
    )
    # Tick returns a non-trivial counter so the per-plan log line is testable.
    monkeypatch.setattr(
        bridge_cli,
        "_tick",
        lambda plan, gh, mcp, **kw: TickResult(synced=2, errors=0, skipped=1, failures=()),
    )

    class _StubMcp:
        def list_workspaces(self, **kwargs: Any) -> list[Any]:
            return []

        def list_issues(self, **kwargs: Any) -> list[Any]:
            return []

        def close(self) -> None:
            pass

    monkeypatch.setattr(bridge_cli, "_construct_mcp_client", lambda: _StubMcp())
    monkeypatch.setattr(bridge_cli.hostclient, "client_for", lambda repo_root: object())
    monkeypatch.setattr(bridge_cli._metrics, "push_heartbeat", lambda: None)
    monkeypatch.setattr(bridge_cli._metrics, "push_failure_total", lambda *, reason: None)
    monkeypatch.setattr(bridge_cli, "_pr_state_tick", lambda mcp, state: None)
    monkeypatch.setattr(bridge_cli, "reap_orphans", lambda mcp: None)

    with caplog.at_level("INFO", logger="fr_vk.bridge_cli"):
        rc = bridge_cli.main([])

    assert rc == 0
    log_text = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "configured repos: 1 found at" in log_text, log_text
    assert "example/foo: 1 discoverable plan(s): fake-plan-slug" in log_text, log_text
    assert "fake-plan-slug: synced=2 errors=0 skipped=1" in log_text, log_text
    assert "summary: 1 plan(s) ticked, 2 synced, 0 errors, 1 skipped" in log_text, log_text


def test_tick_warns_when_owner_name_unresolvable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """If `_repo_owner_name` returns None (e.g., the repo has no GitHub
    remote, or the URL parser can't recognize it), the bridge must log
    a warning instead of silently skipping. Pre-fix this was a per-repo
    `continue` with zero output."""
    clone = _init_bare_with_clone(tmp_path)
    monkeypatch.setenv("VK_BRIDGE_REPOS", str(clone))
    monkeypatch.setenv("VK_BRIDGE_LOCK_PATH", str(tmp_path / "vk-bridge.lock"))

    from fr_vk import bridge_cli

    monkeypatch.setattr(bridge_cli, "_SEEN_PLANS_PATH", tmp_path / "_seen_plans.json")
    monkeypatch.setattr(bridge_cli, "_pull_managed_repo", lambda repo_path: None)
    monkeypatch.setattr(bridge_cli, "_repo_owner_name", lambda repo_path: None)

    class _StubMcp:
        def list_workspaces(self, **kwargs: Any) -> list[Any]:
            return []

        def list_issues(self, **kwargs: Any) -> list[Any]:
            return []

        def close(self) -> None:
            pass

    monkeypatch.setattr(bridge_cli, "_construct_mcp_client", lambda: _StubMcp())
    monkeypatch.setattr(bridge_cli.hostclient, "client_for", lambda repo_root: object())
    monkeypatch.setattr(bridge_cli._metrics, "push_heartbeat", lambda: None)
    monkeypatch.setattr(bridge_cli._metrics, "push_failure_total", lambda *, reason: None)
    monkeypatch.setattr(bridge_cli, "_pr_state_tick", lambda mcp, state: None)
    monkeypatch.setattr(bridge_cli, "reap_orphans", lambda mcp: None)

    with caplog.at_level("WARNING", logger="fr_vk.bridge_cli"):
        rc = bridge_cli.main([])

    assert rc == 0
    log_text = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "could not resolve owner/name from git remote" in log_text, log_text


def _stub_bridge_io(bridge_cli: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub the MCP / gh / metric surface so a tick can run for the
    desync-metric assertions (discovery returns nothing)."""
    monkeypatch.setattr(
        bridge_cli, "_repo_owner_name", lambda repo_path: f"example/{repo_path.name}"
    )
    monkeypatch.setattr(bridge_cli, "discover_plans", lambda repo, gh, **kw: [])

    class _StubMcp:
        def list_workspaces(self, **kwargs: Any) -> list[Any]:
            return []

        def list_issues(self, **kwargs: Any) -> list[Any]:
            return []

        def close(self) -> None:
            pass

    monkeypatch.setattr(bridge_cli, "_construct_mcp_client", lambda: _StubMcp())
    monkeypatch.setattr(bridge_cli.hostclient, "client_for", lambda repo_root: object())
    monkeypatch.setattr(bridge_cli._metrics, "push_heartbeat", lambda: None)
    monkeypatch.setattr(bridge_cli._metrics, "push_failure_total", lambda *, reason: None)
    # Production calls these with a `project_id=` kwarg — match the real
    # signature so the post-loop sweep isn't silently swallowing a TypeError.
    monkeypatch.setattr(bridge_cli, "_pr_state_tick", lambda mcp, state, *, project_id=None: None)
    monkeypatch.setattr(bridge_cli, "reap_orphans", lambda mcp, *, project_id=None: None)


def test_tick_pushes_desync_metric_on_dirty_bridge_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:  # #286
    """A desynced (dirty) bridge checkout is healed AND a
    `repo_desync_total{repo=...}` metric is pushed — no longer silent."""
    clone = _init_bare_with_clone(tmp_path)
    bare = tmp_path / "origin.git"
    bridge_base = tmp_path / "bridge-co"
    bridge_co = bridge_base / "foo"
    # Pre-create the bridge-owned checkout in a DIRTY state (a tracked file
    # removed in the working tree → status is non-empty while HEAD ==
    # origin/main): the #286 signature the metric must surface.
    subprocess.run(["git", "clone", str(bare), str(bridge_co)], check=True, capture_output=True)
    (bridge_co / "README.md").unlink()
    assert _git(bridge_co, "status", "--porcelain").stdout.strip()  # genuinely dirty

    monkeypatch.setenv("VK_BRIDGE_REPOS", str(clone))
    monkeypatch.setenv("VK_BRIDGE_LOCK_PATH", str(tmp_path / "vk-bridge.lock"))
    monkeypatch.setenv("FR_BRIDGE_CHECKOUT_DIR", str(bridge_base))

    from fr_vk import bridge_cli

    monkeypatch.setattr(bridge_cli, "_SEEN_PLANS_PATH", tmp_path / "_seen_plans.json")
    _stub_bridge_io(bridge_cli, monkeypatch)
    desync_repos: list[str] = []
    monkeypatch.setattr(
        bridge_cli._metrics, "push_repo_desync_total", lambda *, repo: desync_repos.append(repo)
    )

    rc = bridge_cli.main([])
    assert rc == 0
    assert desync_repos == ["example/foo"], desync_repos
    # Tree was healed.
    assert _git(bridge_co, "status", "--porcelain").stdout.strip() == ""


def test_tick_clean_bridge_checkout_does_not_push_desync_metric(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:  # #286
    """A clean bridge checkout (normal fast-forward) must NOT push the
    desync metric — it is not a desync."""
    clone = _init_bare_with_clone(tmp_path)
    bare = tmp_path / "origin.git"
    bridge_base = tmp_path / "bridge-co"
    bridge_co = bridge_base / "foo"
    subprocess.run(["git", "clone", str(bare), str(bridge_co)], check=True, capture_output=True)

    monkeypatch.setenv("VK_BRIDGE_REPOS", str(clone))
    monkeypatch.setenv("VK_BRIDGE_LOCK_PATH", str(tmp_path / "vk-bridge.lock"))
    monkeypatch.setenv("FR_BRIDGE_CHECKOUT_DIR", str(bridge_base))

    from fr_vk import bridge_cli

    monkeypatch.setattr(bridge_cli, "_SEEN_PLANS_PATH", tmp_path / "_seen_plans.json")
    _stub_bridge_io(bridge_cli, monkeypatch)
    desync_repos: list[str] = []
    monkeypatch.setattr(
        bridge_cli._metrics, "push_repo_desync_total", lambda *, repo: desync_repos.append(repo)
    )

    rc = bridge_cli.main([])
    assert rc == 0
    assert desync_repos == [], desync_repos


def test_tick_feeds_real_pr_observations_to_pr_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:  # #290
    """The bridge must build a real {card: status} map via observe_pr_status
    and pass it to _pr_state_tick — not the dead `{}` stub."""
    monkeypatch.setenv("VK_BRIDGE_LOCK_PATH", str(tmp_path / "lock"))

    from fr_vk import bridge_cli

    monkeypatch.setattr(bridge_cli, "_SEEN_PLANS_PATH", tmp_path / "seen.json")
    monkeypatch.setattr(bridge_cli, "_configured_repos", lambda: [])  # skip the repo loop

    class _StubMcp:
        def close(self) -> None:
            pass

    monkeypatch.setattr(bridge_cli, "_construct_mcp_client", lambda: _StubMcp())
    monkeypatch.setattr(bridge_cli.hostclient, "client_for", lambda repo_root: object())
    monkeypatch.setattr(bridge_cli._metrics, "push_heartbeat", lambda: None)
    monkeypatch.setattr(bridge_cli, "reap_orphans", lambda mcp, *, project_id=None: None)

    monkeypatch.setattr(
        bridge_cli, "observe_pr_status", lambda mcp, *, project_id=None: {"c1": "merged"}
    )
    captured: list[Any] = []
    monkeypatch.setattr(
        bridge_cli,
        "_pr_state_tick",
        lambda mcp, observations, *, project_id=None: captured.append(observations),
    )

    rc = bridge_cli.main([])
    assert rc == 0
    assert captured == [{"c1": "merged"}], f"pr_state was fed {captured!r}, expected the real map"


def test_tick_reconciles_done_issues_and_persists_seen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:  # #294
    """main() must load the done-closed seen-set, call reconcile_done_issues,
    and persist the returned set."""
    import json as _json

    monkeypatch.setenv("VK_BRIDGE_LOCK_PATH", str(tmp_path / "lock"))

    from fr_vk import bridge_cli

    monkeypatch.setattr(bridge_cli, "_SEEN_PLANS_PATH", tmp_path / "seen.json")
    monkeypatch.setattr(bridge_cli, "_DONE_CLOSED_PATH", tmp_path / "done.json")
    monkeypatch.setattr(bridge_cli, "_configured_repos", lambda: [])

    class _StubMcp:
        def close(self) -> None:
            pass

    monkeypatch.setattr(bridge_cli, "_construct_mcp_client", lambda: _StubMcp())
    monkeypatch.setattr(bridge_cli.hostclient, "client_for", lambda repo_root: object())
    monkeypatch.setattr(bridge_cli._metrics, "push_heartbeat", lambda: None)
    monkeypatch.setattr(bridge_cli, "observe_pr_status", lambda mcp, *, project_id=None: {})
    monkeypatch.setattr(bridge_cli, "_pr_state_tick", lambda *a, **k: None)
    monkeypatch.setattr(bridge_cli, "reap_orphans", lambda mcp, *, project_id=None: 0)

    seen_arg: list[set] = []

    def fake_reconcile(mcp, *, project_id=None, seen=None, close_gh_issue=None):
        seen_arg.append(seen)
        return {"derio-net/runs-fr#5"}

    monkeypatch.setattr(bridge_cli, "reconcile_done_issues", fake_reconcile)

    rc = bridge_cli.main([])
    assert rc == 0
    assert seen_arg, "reconcile_done_issues was not called"
    persisted = _json.loads((tmp_path / "done.json").read_text())
    assert "derio-net/runs-fr#5" in persisted


def test_load_done_closed_warns_on_non_list_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:  # #294 review
    """A present-but-malformed state file (not a list) must not silently
    fall through to empty — it has to be observable."""
    from fr_vk import bridge_cli

    p = tmp_path / "done.json"
    p.write_text("{}")  # a dict, not a list
    monkeypatch.setattr(bridge_cli, "_DONE_CLOSED_PATH", p)

    with caplog.at_level("WARNING", logger="fr_vk.bridge_cli"):
        out = bridge_cli._load_done_closed()

    assert out == set()
    assert any("not a list" in r.getMessage() for r in caplog.records)
