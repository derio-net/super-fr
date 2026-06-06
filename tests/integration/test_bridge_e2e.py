"""End-to-end acceptance tests for `fr_dispatch.tick`.

Each test composes the full pipeline — observe → render → diff → apply →
per-phase dispatch — against a tmp_path plan + FakeGhClient + FakeMcpClient.
The docstrings repeat the Given/When/Then from the v2-bridge-rebuild spec
(F1, F4, F5, H7) so `pytest -v` reads like a BDD report.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from fr_vk.runner import VkRunner

from tests.unit.fakes import FakeGhClient, FakeMcpClient


def _write_minimal_plan(plan_dir: Path, *, target_repo: str, phases: list[dict[str, Any]]) -> None:
    """Materialise a v2 plan-folder for an integration test.

    Each `phases` entry is a dict with keys:
      number, title, tag, depends_on, tracking_issue (optional),
      completion_at (optional → marks the phase complete),
      completion_note (optional → required for manual completion).

    Step state defaults to unticked. The single-step shape keeps the
    fixture compact; tests inspect projection, not step-level deltas.
    """
    plan_dir.mkdir(parents=True, exist_ok=True)
    meta = textwrap.dedent(
        f"""\
        schema_version: 2
        plan: e2e-fixture
        target_repo: {target_repo}
        vk_version: ">=2.0.0,<3.0.0"
        created: "2026-05-18"
        """
    )
    (plan_dir / "_meta.yaml").write_text(meta)

    for p in phases:
        n = p["number"]
        tag = p.get("tag", "agentic")
        deps = p.get("depends_on", [])
        deps_yaml = "[" + ", ".join(str(d) for d in deps) + "]"
        tracking = p.get("tracking_issue")
        tracking_yaml = f'"{tracking}"' if tracking else "null"
        completion_at = p.get("completion_at")
        at_yaml = f'"{completion_at}"' if completion_at else "null"
        completion_note = p.get("completion_note")
        note_yaml = f'"{completion_note}"' if completion_note else "null"
        body = textwrap.dedent(
            f"""\
            schema_version: 2
            phase:
              number: {n}
              title: {p["title"]}
              tag: {tag}
              depends_on: {deps_yaml}
              tracking_issue: {tracking_yaml}
            tasks:
              - number: 1
                title: t
                steps:
                  - id: P{n}.T1.S1
                    text: s
            state:
              steps:
                P{n}.T1.S1: {{ state: " ", ticked_at: null, note: null }}
              completion: {{ at: {at_yaml}, note: {note_yaml}, observed_prs: [] }}
            """
        )
        (plan_dir / f"{n:02d}.yaml").write_text(body)


def _preload_repo_labels(gh: FakeGhClient, repo: str) -> None:
    """Pre-register the full managed-label vocabulary so the FakeGhClient
    accepts edit_issue_labels even before apply()'s RepoLabelEnsure runs.

    The real bridge always runs ensure_labels first; tests that want to
    skip that detail (here we focus on projection, not the ensure step)
    pre-load and assert separately.
    """
    gh.repo_labels.setdefault(repo, set()).update(
        {
            "fr:ready",
            "fr:blocked",
            "fr:synced",
            "in-progress",
            "pr-ready",
            "manual",
            "plan:e2e-fixture",
            "phase:1",
            "phase:2",
            "phase:3",
            "phase:4",
        }
    )


# ── F1: Full tick produces same end-state as legacy bridge for a fixture ──


def test_tick_end_state_matches_legacy_for_fixture(tmp_path: Path) -> None:
    """
    GIVEN a fixture multi-phase plan with mixed depends_on shape
    AND   a FakeMcpClient + FakeGhClient pre-loaded with the dispatched Issues
    WHEN  fr_dispatch.tick() runs one tick
    THEN  the resulting label state on every Issue matches the documented
          expectation:
          - root phases (depends_on=[]) → vk-ready + vk-synced
          - blocked phases (deps not done) → vk-blocked (no vk-ready, no vk-synced)
          - completed phases → no lifecycle label, state CLOSED
          - manual phases → manual label
    AND   the resulting workspace count == count of root phases just synced
    """
    from fr import parse
    from fr_dispatch import tick

    repo = "derio-net/superpowers-for-vk"
    plan_dir = tmp_path / "plan"
    _write_minimal_plan(
        plan_dir,
        target_repo=repo,
        phases=[
            # Phase 1: root, NOT complete, agentic → will get dispatched
            {
                "number": 1,
                "title": "Root ready",
                "tag": "agentic",
                "depends_on": [],
                "tracking_issue": f"https://github.com/{repo}/issues/100",
            },
            # Phase 2: depends on 4 (manual incomplete) → blocked
            {
                "number": 2,
                "title": "Depends on manual",
                "tag": "agentic",
                "depends_on": [4],
                "tracking_issue": f"https://github.com/{repo}/issues/200",
            },
            # Phase 3: agentic, already complete (closed)
            {
                "number": 3,
                "title": "Completed",
                "tag": "agentic",
                "depends_on": [],
                "tracking_issue": f"https://github.com/{repo}/issues/300",
                "completion_at": "2026-05-17T10:00:00Z",
            },
            # Phase 4: manual, not complete → manual label
            {
                "number": 4,
                "title": "Manual phase",
                "tag": "manual",
                "depends_on": [],
                "tracking_issue": f"https://github.com/{repo}/issues/400",
            },
        ],
    )
    plan = parse(plan_dir)

    gh = FakeGhClient()
    _preload_repo_labels(gh, repo)
    # Phase 1: not synced yet, has stale phase label
    gh.add_issue(repo, 100, state="OPEN", labels={"fr:ready", "phase:1", "plan:e2e-fixture"})
    # Phase 2: blocked — queued (runner marker survives) but the
    # lifecycle label drifted off; the tick must restore fr:blocked.
    gh.add_issue(repo, 200, state="OPEN", labels={"runner:vk", "phase:2", "plan:e2e-fixture"})
    # Phase 3: agentic complete — closed + merged PR observed
    gh.add_issue(
        repo,
        300,
        state="CLOSED",
        labels={"phase:3", "plan:e2e-fixture"},
        linked_prs=[
            {"url": f"https://github.com/{repo}/pull/301", "state": "CLOSED", "merged": True}
        ],
    )
    # Phase 4: manual — gets `manual` label projected
    gh.add_issue(repo, 400, state="OPEN", labels={"phase:4", "plan:e2e-fixture"})

    mcp = FakeMcpClient()
    result = tick(plan, gh, VkRunner(mcp))

    # End-state assertions per the spec's projection rules.
    p1_labels = gh.issues[(repo, 100)].labels
    assert "fr:ready" in p1_labels
    assert "fr:synced" in p1_labels

    p2_labels = gh.issues[(repo, 200)].labels
    assert "fr:blocked" in p2_labels
    assert "fr:ready" not in p2_labels
    assert "fr:synced" not in p2_labels

    p3 = gh.issues[(repo, 300)]
    assert p3.state == "CLOSED"
    lifecycle_labels = {
        "fr:ready",
        "fr:blocked",
        "fr:in-progress",
        "fr:pr-ready",
        "fr:ready",
        "fr:blocked",
        "in-progress",
        "pr-ready",
        "manual",
    }
    assert not (p3.labels & lifecycle_labels), (
        f"completed phase should carry no lifecycle label, got: {p3.labels & lifecycle_labels}"
    )

    p4_labels = gh.issues[(repo, 400)].labels
    assert "manual" in p4_labels

    # Workspace count == root phases just synced. Phase 1 is the only
    # root-and-not-complete phase, so exactly one workspace should exist.
    assert result.synced == 1, f"expected synced=1 got {result.synced} (failures={result.failures})"
    workspaces = [c for c in mcp.calls if c[0] == "start_workspace"]
    assert len(workspaces) == 1
    # VK indexes by short name; the bridge resolves derio-net/superpowers-for-vk
    # → "superpowers-for-vk" → the matching uuid from list_repos.
    assert workspaces[0][1]["repo_id"] == "uuid-superpowers-for-vk"


# ── F4: Idempotency — re-running tick yields no further mutations ──────


def test_tick_is_idempotent(tmp_path: Path) -> None:
    """
    GIVEN a plan in a steady-state (all phases dispatched, labels match
          renderer projection)
    WHEN  fr_dispatch.tick() runs once
    AND   fr_dispatch.tick() runs again immediately after
    THEN  the second run made no MCP mutations
    AND   the second run made no GH label changes
    AND   the second run made no GH Issue state changes
    """
    from fr import parse
    from fr_dispatch import tick

    repo = "derio-net/superpowers-for-vk"
    plan_dir = tmp_path / "plan"
    _write_minimal_plan(
        plan_dir,
        target_repo=repo,
        phases=[
            {
                "number": 1,
                "title": "Single phase",
                "tag": "agentic",
                "depends_on": [],
                "tracking_issue": f"https://github.com/{repo}/issues/42",
            },
        ],
    )
    plan = parse(plan_dir)

    gh = FakeGhClient()
    _preload_repo_labels(gh, repo)
    gh.add_issue(repo, 42, state="OPEN", labels={"fr:ready", "phase:1", "plan:e2e-fixture"})
    mcp = FakeMcpClient()

    # Tick 1: brings the plan to steady state (vk-synced applied + body update)
    tick(plan, gh, VkRunner(mcp))

    # Snapshot post-first-tick state.
    gh_calls_after_first = list(gh.calls)
    mcp_calls_after_first = list(mcp.calls)
    issue_after_first = (
        gh.issues[(repo, 42)].state,
        frozenset(gh.issues[(repo, 42)].labels),
        gh.issues[(repo, 42)].body,
    )

    # Tick 2: should be a no-op.
    tick(plan, gh, VkRunner(mcp))

    # The 2nd tick may issue read-only MCP calls (list_workspaces,
    # list_issues, list_repos) for slot/dedup/config — those are not
    # mutations. The mutation-shaped calls must NOT have grown.
    mutation_methods = {
        "create_issue",
        "update_issue",
        "start_workspace",
        "link_workspace_issue",
    }
    new_mcp = mcp.calls[len(mcp_calls_after_first) :]
    new_mcp_mutations = [c for c in new_mcp if c[0] in mutation_methods]
    assert new_mcp_mutations == [], f"second tick produced MCP mutations: {new_mcp_mutations}"

    # No new per-issue GH mutations (label/state/body). `ensure_labels` is
    # idempotent label-vocabulary maintenance, not an issue mutation —
    # `apply()` re-emits it every tick by design. The spec's idempotency
    # contract scopes "no GH label changes / no GH Issue state changes"
    # to per-issue diffs.
    new_gh = [
        c
        for c in gh.calls[len(gh_calls_after_first) :]
        if c[0] in {"edit_issue_labels", "edit_issue_state", "edit_issue_body", "create_issue"}
    ]
    assert new_gh == [], f"second tick produced per-issue GH mutations: {new_gh}"

    # End state of the Issue must be byte-for-byte identical.
    assert (
        gh.issues[(repo, 42)].state,
        frozenset(gh.issues[(repo, 42)].labels),
        gh.issues[(repo, 42)].body,
    ) == issue_after_first


# ── F5: Legacy body-text-driven dispatch retired ──────────────────────


def test_standalone_fr_ready_issue_without_plan_is_ignored(tmp_path: Path) -> None:
    """
    GIVEN a vk-ready GitHub Issue that is NOT backed by any v2 plan
          (manual `gh issue create --label vk-ready` outside the plan workflow)
    AND   no plan in any managed repo references it as tracking_issue
    WHEN  fr_dispatch.tick() runs
    THEN  no MCP calls were made for this Issue
    AND   no labels were changed on this Issue
    (Legacy bridge would have parsed the body and dispatched; new bridge ignores.)

    Verifies the structural property in `fr_dispatch.tick`: the loop iterates
    phases of DISCOVERED plans only. A free-floating vk-ready Issue with no
    plan reference simply isn't in the iteration set — there's no code
    path that falls back to listing gh Issues by label for dispatch.
    """
    from fr import parse
    from fr_dispatch import tick

    repo = "derio-net/superpowers-for-vk"

    # Build a single-phase plan with NO tracking_issue → not dispatched yet.
    plan_dir = tmp_path / "plan"
    _write_minimal_plan(
        plan_dir,
        target_repo=repo,
        phases=[
            {
                "number": 1,
                "title": "Undispatched phase",
                "tag": "agentic",
                "depends_on": [],
                # No tracking_issue at all
            },
        ],
    )
    plan = parse(plan_dir)

    gh = FakeGhClient()
    _preload_repo_labels(gh, repo)
    # Free-floating vk-ready Issue — NOT referenced by the plan above.
    gh.add_issue(repo, 9999, state="OPEN", labels={"fr:ready"}, body="manually filed")
    snapshot_labels = frozenset(gh.issues[(repo, 9999)].labels)
    snapshot_state = gh.issues[(repo, 9999)].state
    snapshot_body = gh.issues[(repo, 9999)].body

    mcp = FakeMcpClient()
    tick(plan, gh, VkRunner(mcp))

    # No MCP calls referenced the orphan Issue.
    orphan_token = "9999"
    for name, args in mcp.calls:
        for value in args.values():
            assert orphan_token not in str(value), (
                f"MCP call {name!r} touched orphan issue 9999: {args}"
            )

    # The orphan Issue is untouched on the gh side.
    for name, args in gh.calls:
        if args.get("repo") == repo and args.get("number") == 9999:
            raise AssertionError(f"gh call {name} touched orphan 9999: {args}")

    assert frozenset(gh.issues[(repo, 9999)].labels) == snapshot_labels
    assert gh.issues[(repo, 9999)].state == snapshot_state
    assert gh.issues[(repo, 9999)].body == snapshot_body


# ── H7: Cross-repo bridge tick — vk-synced lands on tracking-issue repo ──


def test_cross_repo_phase_dispatches_to_correct_repo(tmp_path: Path) -> None:
    """
    GIVEN a plan with target_repo='derio-net/foo' and a phase with
          tracking_issue='https://github.com/derio-net/bar/issues/100'
    WHEN  fr_dispatch.tick() runs
    THEN  fr_dispatch.dispatch is called with workspace branch repo='derio-net/bar'
    AND   the vk-synced label is added on derio-net/bar#100 (NOT derio-net/foo)
    AND   the workspace name follows '<simple_id> -> gh#100' convention
    """
    from fr import parse
    from fr_dispatch import tick

    target_repo = "derio-net/foo"
    foreign_repo = "derio-net/bar"

    plan_dir = tmp_path / "plan"
    _write_minimal_plan(
        plan_dir,
        target_repo=target_repo,
        phases=[
            {
                "number": 1,
                "title": "Foreign-dispatched",
                "tag": "agentic",
                "depends_on": [],
                "tracking_issue": f"https://github.com/{foreign_repo}/issues/100",
            },
        ],
    )
    plan = parse(plan_dir)

    gh = FakeGhClient()
    # The bridge ensures labels on the foreign repo first; pre-seed both
    # repos' label vocab so edits succeed deterministically.
    for repo in (target_repo, foreign_repo):
        gh.repo_labels.setdefault(repo, set()).update(
            {
                "fr:ready",
                "fr:blocked",
                "fr:synced",
                "in-progress",
                "pr-ready",
                "manual",
                "plan:e2e-fixture",
                "phase:1",
            }
        )
    gh.add_issue(
        foreign_repo, 100, state="OPEN", labels={"fr:ready", "phase:1", "plan:e2e-fixture"}
    )

    # Advertise both repos in VK's registry (short names, with ids) so
    # `fr_dispatch.config.is_known_repo` accepts the dispatch and
    # `repo_id_for` returns the canonical Uuid. VK indexes by short name
    # only — no `owner/`.
    mcp = FakeMcpClient()
    mcp._repos = [
        {"id": "uuid-foo", "name": "foo"},
        {"id": "uuid-bar", "name": "bar"},
    ]
    result = tick(plan, gh, VkRunner(mcp))

    assert result.synced == 1, f"expected synced=1 got {result.synced} ({result.failures})"

    # The workspace went to the FOREIGN repo, not target_repo. After the
    # 2026-05-18 wire-shape fix, this means start_workspace was called
    # with repo_id pointing at `bar`, not `foo`.
    ws_calls = [c for c in mcp.calls if c[0] == "start_workspace"]
    assert len(ws_calls) == 1
    args = ws_calls[0][1]
    assert args["repo_id"] == "uuid-bar", (
        f"workspace dispatched to wrong repo: repo_id={args['repo_id']!r} (want 'uuid-bar')"
    )

    # Workspace name follows the canonical `<plan>-P<n> -> gh#<n>` convention.
    assert "-> gh#100" in args["name"]

    # vk-synced landed on the FOREIGN issue.
    foreign_labels = gh.issues[(foreign_repo, 100)].labels
    assert "fr:synced" in foreign_labels

    # And the target_repo got no per-issue mutation for issue 100 (it has
    # no issue 100 at all — the assertion guards against a future regression
    # that dual-stamps).
    target_calls = [
        c
        for c in gh.calls
        if c[0] in {"edit_issue_labels", "edit_issue_state", "edit_issue_body"}
        and c[1].get("repo") == target_repo
    ]
    for name, args in target_calls:
        # The target_repo's only legit per-issue mutations are for phases
        # whose tracking_issue lives there. Our plan has none such, so any
        # mutation here would be a routing bug.
        raise AssertionError(f"unexpected target_repo per-issue mutation: {name} {args}")
