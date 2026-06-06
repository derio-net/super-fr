"""Integration tests for `fr.bridge.cli.main()`.

These exercise the daemon-level wiring with real git checkouts (E4)
and a monkeypatched MCP/gh surface — proving the loop drives
`discover_plans` against the head-of-main, not the stale tip.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


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


def test_tick_pulls_managed_repos_before_discover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:  # E4
    """Local checkout must be pulled to head-of-main before plans are
    walked — otherwise plans newly added on `origin/main` go silently
    undispatched."""
    clone = _init_bare_with_clone(tmp_path)
    repos_dir = clone.parent

    monkeypatch.setenv("VK_BRIDGE_REPOS", str(clone))
    monkeypatch.setenv("VK_BRIDGE_LOCK_PATH", str(tmp_path / "vk-bridge.lock"))
    # `discover_plans` looks up `${VK_REPOS_DIR}/<name>` — the cli sets
    # this per-iteration to the clone's parent so the lookup resolves
    # to our clone. Pre-set it for clarity.
    monkeypatch.setenv("VK_REPOS_DIR", str(repos_dir))

    from fr.bridge import cli as bridge_cli

    monkeypatch.setattr(bridge_cli, "_SEEN_PLANS_PATH", tmp_path / "_seen_plans.json")
    # `clone.name` is "foo" → owner/name "example/foo" matches the
    # _meta.yaml target_repo above.
    monkeypatch.setattr(
        bridge_cli, "_repo_owner_name", lambda repo_path: f"example/{repo_path.name}"
    )

    # Spy on `_pull_managed_repo` so the ordering assertion (pull
    # before discover) is testable without needing a fully-valid plan
    # fixture in the freshly-pushed commit.
    pull_order: list[str] = []
    real_pull = bridge_cli._pull_managed_repo

    def spy_pull(repo_path: Path) -> None:
        real_pull(repo_path)
        pull_order.append("pull")

    monkeypatch.setattr(bridge_cli, "_pull_managed_repo", spy_pull)

    def spy_discover(repo: str, gh: Any) -> list[Any]:
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

    monkeypatch.setattr(bridge_cli, "RealGhClient", lambda: _StubGh())

    monkeypatch.setattr(bridge_cli._metrics, "push_heartbeat", lambda: None)
    monkeypatch.setattr(bridge_cli._metrics, "push_failure_total", lambda *, reason: None)

    rc = bridge_cli.main([])
    assert rc == 0

    # Auto-pull ran (the new plan dir now exists on the local checkout)
    new_plan_dir = clone / "docs" / "superpowers" / "plans" / "new-plan"
    assert new_plan_dir.is_dir(), (
        "auto-pull did not advance the local checkout; "
        f"expected {new_plan_dir} to exist after main()"
    )
    # Order: pull must precede discover_plans
    assert pull_order == ["pull", "discover"], (
        f"expected pull before discover_plans, got {pull_order!r}"
    )


def test_tick_logs_configured_repos_count_discovered_plans_and_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Regression guard for the 2026-05-18 silent-tick incident.

    Pre-fix the bridge ran a complete tick with zero per-plan output —
    just "[bridge] - vX.Y.Z - <ts> - tick" + "fr.bridge: tick complete"
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
    monkeypatch.setenv("VK_REPOS_DIR", str(repos_dir))

    from fr.bridge import TickResult
    from fr.bridge import cli as bridge_cli

    monkeypatch.setattr(bridge_cli, "_SEEN_PLANS_PATH", tmp_path / "_seen_plans.json")
    monkeypatch.setattr(
        bridge_cli, "_repo_owner_name", lambda repo_path: f"example/{repo_path.name}"
    )
    monkeypatch.setattr(bridge_cli, "_pull_managed_repo", lambda repo_path: None)

    # Stub one fake plan with a slug we'll check in the log.
    class _StubPlan:
        def __init__(self, slug: str) -> None:
            self.dir = tmp_path / slug

    monkeypatch.setattr(
        bridge_cli, "discover_plans", lambda repo, gh: [_StubPlan("fake-plan-slug")]
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
    monkeypatch.setattr(bridge_cli, "RealGhClient", lambda: object())
    monkeypatch.setattr(bridge_cli._metrics, "push_heartbeat", lambda: None)
    monkeypatch.setattr(bridge_cli._metrics, "push_failure_total", lambda *, reason: None)
    monkeypatch.setattr(bridge_cli, "_pr_state_tick", lambda mcp, state: None)
    monkeypatch.setattr(bridge_cli, "reap_orphans", lambda mcp: None)

    with caplog.at_level("INFO", logger="fr.bridge.cli"):
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

    from fr.bridge import cli as bridge_cli

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
    monkeypatch.setattr(bridge_cli, "RealGhClient", lambda: object())
    monkeypatch.setattr(bridge_cli._metrics, "push_heartbeat", lambda: None)
    monkeypatch.setattr(bridge_cli._metrics, "push_failure_total", lambda *, reason: None)
    monkeypatch.setattr(bridge_cli, "_pr_state_tick", lambda mcp, state: None)
    monkeypatch.setattr(bridge_cli, "reap_orphans", lambda mcp: None)

    with caplog.at_level("WARNING", logger="fr.bridge.cli"):
        rc = bridge_cli.main([])

    assert rc == 0
    log_text = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "could not resolve owner/name from git remote" in log_text, log_text
