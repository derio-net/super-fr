# Audit — v2 bridge dispatch rebuild gap

> **Triage status — 2026-06-11: ADDRESSED + follow-ups seeded.** The seven
> wire-shape bugs were fixed (vk 2.2.11) and remain fixed in the current
> `fr-vk` bridge. The five actionable "What we'd do differently" follow-ups are
> all still OPEN as of 2026-06-11 (verified against `packages/fr-vk`): per-phase
> failure-string logging, real-wire contract fixture, transactional card rollback
> on workspace failure, per-repo base-branch resolution, and card↔workspace link
> verification. Seeded as `docs/superpowers/specs/2026-06-11-bridge-dispatch-hardening-design.md`
> (one-shot with `/fr-goal`).


**Date:** 2026-05-18 (single session, 19:30–23:50 CEST / 17:30–21:50 UTC)
**Audience:** future agents/operators touching `vk.bridge.*` or `vk._mcp_client`
**Outcome:** seven structural mismatches between the bridge code and the real
`vibe-kanban-mcp` server fixed across PRs #236–#242, taking the bridge from
"creates 38 spurious GH Issues per double-tick" to "dispatches a working VK
card + workspace + GH `vk-synced` stamp end-to-end" for the first time since
the v2 rebuild merged.

---

## Why this document exists

The v2 bridge rebuild (`spec: docs/superpowers/specs/2026-05-17-v2-bridge-rebuild-design.md`,
delivered in seven Phase-N PRs) shipped a comprehensive test suite that all
passed but **was never exercised against the real `vibe-kanban-mcp`**. Every
assumption tests made about VK's wire shape happened to be wrong — and the
test fakery codified the wrong assumption rather than VK's reality. The bridge
then ran in production for ~24h before any vk-ready phase made it past the
discovery gate, at which point the gap manifested as a 38-issue
mass-dispatch incident on 2026-05-18 18:30–18:48 UTC.

This audit captures the seven bugs, the workflow that surfaced them, and the
patterns worth re-using next time someone integrates with an external service.

---

## Timeline

All times UTC. Bridge cron runs every 2 minutes; each tick is one observation
point.

| Time | What happened |
|------|---------------|
| 18:30 | **Incident wave 1.** PR #194 (`discover_plans` yaml-only filter) over-broadened discovery → bridge picks up every plan with any incomplete phase → 19 spurious `IssueCreate`s land (sfv#196–#214). |
| 18:48 | **Incident wave 2.** PR #215 reverted #194. Bridge runs again, the actual mechanism (in `tick()` → `apply()` → unfiltered `IssueCreate`) still fires for partially-dispatched plans → another 19 spurious creates (sfv#216–#234). |
| 18:55 | Operator stops the cron, closes all 38 issues with explanatory comments. |
| 19:15 | Previous agent writes [`docs/goals/2026-05-18-bridge-apply-skip-issue-create.md`](../../goals/2026-05-18-bridge-apply-skip-issue-create.md) — a complete, agent-actionable brief with TDD discipline, BDD scenarios, code pointers, and a verify-in-pod step. |
| 19:18 | Brief lands as PR #235. |
| 19:30 | This session opens via `/goal` against that brief. Five tasks created; worktree set up from `origin/main`. |
| 19:40 | **PR #236 → v2.2.5** merges. Adds `apply(..., skip_issue_create=True)` and flips the bridge `tick()` callsite. Five BDD scenarios, 444 passing. |
| 19:42 | First v2.2.5 cron tick on agent-images: `synced=0 errors=1 skipped=0` for the v2-bridge-cutover plan. Spurious-creates: zero. Original goal achieved. |
| — | Operator pings: "what's up with the error: `[bridge] 2026-05-17-v2-bridge-cutover: synced=0 errors=1 skipped=0`". |
| 19:45 | Manual `tick(...)` reproduction surfaces: `phase 1: unknown repo 'derio-net/agent-images'`. Probe `mcp.list_repos()` against real VK returns `{'repos': [{'id': 'uuid', 'name': 'agent-images'}, ...]}` — **short names, not owner/name**. `FakeMcpClient.list_repos()` returned `derio-net/X` — the fake matched the bridge's wrong assumption, so all tests passed. |
| 20:04 | **PR #237 → v2.2.6** merges. Three coupled fixes: `is_known_repo` strips `owner/`; `known_repos` returns `{short_name: repo_id}`; `start_workspace.repositories` becomes `[{repo_id, branch}]` (was `["owner/name"]`); `FakeMcpClient` updated to real wire shape. |
| 20:06 | First v2.2.6 cron tick: same `errors=1` on agent-images. Manual repro surfaces VK's actual error envelope: `{success: False, error: 'project_id is required (not available from workspace context)'}`. Reading `vibe-kanban-mcp/.../remote_issues.rs::create_issue` confirms `project_id` is required outside workspace context. |
| 20:19 | **PR #238 → v2.2.7** merges. `vk.bridge.tick()` reads `VK_DERIO_OPS_PROJECT` env, threads through to `dispatch_phase` → `create_issue`. New "unset env" failure path emits per-phase clean failures + `project_id_missing` metric reason. `conftest.py` autouse-sets the env so existing tests aren't disrupted. |
| 20:20 | First v2.2.7 tick: `[bridge] VK_DERIO_OPS_PROJECT unset` — the new clean failure path fires. The K8s manifest injects `VK_DERIO_OPS_PROJECT_ID` (`_ID`-suffixed), but my code (and the legacy bridge inline docs) read the bare name. |
| 20:24 | **PR #239 → v2.2.8** merges. Read `VK_DERIO_OPS_PROJECT_ID` first, fall back to bare name. Regression-guard test pins precedence. |
| 20:26 | First v2.2.8 tick on agent-images: bridge **does** dispatch (gates pass, env resolves). VK card `FFE-193` is created — **but lands in "To do", with no workspace**. Subsequent ticks dedup-hit on the title, skip dispatch, and stamp `vk-synced` via the shortcut path, masking the real failure. Operator notices: "card landed in To do column, until now it was always created in In progress column. Should I delete the VK card and try again?" |
| 20:50 | Diagnosis via shape-introspection: VK's `update_issue` response is `{"issue": {...}}` (wrapped), `create_issue` is `{"issue_id": "<uuid>"}` (not `id`), `start_workspace` is `{"workspace_id": "<uuid>"}` (not `id`). Our `_expect_id` only looks for `"id"` → raises on `create_issue` **after VK already created the card** → `update_issue` never called → card stays "To do" → `start_workspace` never called → no workspace. |
| 21:26 | **PR #240 → v2.2.9** merges. `_expect_id` accepts a `field=` kwarg + wrapped-form fallback; `dispatch_phase` passes `field="issue_id"` / `"workspace_id"`. `FakeMcpClient` updated to return real envelopes so this regression can't ship again. |
| 21:28 | First v2.2.9 tick: card `FFE-194` created **and** updated to "In progress" ✓. But `synced=0 errors=1` again. `start_workspace` is still failing. |
| 21:30 | Manual non-mutating probe (`start_workspace` with a deliberately invalid `repo_id`) surfaces VK's actual rule: `{success: False, error: "Provide 'prompt', or 'issue_id' that has a non-empty title/description."}`. VK refuses workspace creation without a prompt; passing `issue_id=<card_id>` lets VK derive prompt from the linked card's title/description (and auto-link). |
| 21:34 | **PR #241 → v2.2.10** merges. `dispatch_phase` passes `issue_id=card_id` to `start_workspace`. The wire-shape double now enforces VK's prompt rule so any regression here fails the test suite. |
| 21:38 | First v2.2.10 tick: card `FFE-195` created in "In progress" ✓, workspace `57835055-...` created ✓ — then immediately **archived 27s later by `reap_orphans`** with log `workspaces: reaped ... (sid=2026-05-17-v2-bridge-cutover-P1, gh#82, no card)`. |
| 21:42 | Two more bugs uncovered: (a) the previous successful workspace had branch `vk/5783-...` not the requested `vk/gh-82` — manual probe with `branch="vk/gh-82"` returns `400 Bad Request`; rust source confirms `McpWorkspaceRepoInput.branch → WorkspaceRepoInput.target_branch`, i.e. the BASE branch VK forks off (must already exist in target repo). (b) `reap_orphans` parses workspace names as `<sid> -> gh#<n>` and looks up `sid` in `card_status` keyed by VK `simple_id` (`FFE-NNN`); `dispatch_phase` was naming workspaces `{plan_slug}-P{N} -> gh#{N}` — sid never matched → every workspace got reaped on its first tick. |
| 21:47 | **PR #242 → v2.2.11** merges. `branch="main"` (the base, VK auto-generates the fork name). Workspace name uses `simple_id` extracted from `update_issue`'s wrapped response. Wire-shape double now refuses `start_workspace` with a non-`main` branch. |
| 21:50 | First v2.2.11 tick: **`agent-images/2026-05-17-v2-bridge-cutover: synced=1 errors=0 skipped=0`**. Card `FFE-197` in "In progress", workspace `c03f9550-...` named `FFE-197 -> gh#82` on auto-generated branch `vk/c03f-ffe-197-gh-82`, alive after `reap_orphans` ran in the same tick. GH `#82` has `vk-synced`. **End-to-end dispatch chain works for the first time since the v2 rebuild merged.** |

---

## What was broken (the seven gaps)

Every one of these had the same meta-shape: the bridge code made an assumption
about VK's wire that didn't match the deployed server, and the test fakery
encoded the bridge's wrong assumption rather than VK's actual shape. So
"the tests pass" was perfectly compatible with "production is broken."

| # | Bug | Fix |
|---|-----|-----|
| 1 | `tick()` called `apply()` with no filter → `IssueCreate` mutations went through, creating spurious GH issues for every undispatched phase the discovery gate let through. | `apply(..., skip_issue_create=True)` at the bridge callsite. Operator-only via `vk apply --yes`. (PR #236) |
| 2 | `vk.bridge._config.is_known_repo` compared full `owner/name` against VK's `list_repos` response, but VK indexes by SHORT name. Gate refused every dispatch. | `known_repos` returns `{short_name: repo_id}`; `is_known_repo` strips `owner/` before lookup. (PR #237) |
| 3 | `vk._mcp_client.start_workspace` sent `{"repositories": ["owner/name"], "branch": "..."}` (list of strings, top-level branch). VK expects `{"repositories": [{"repo_id": <Uuid>, "branch": <str>}]}` per `task_attempts.rs`. | Resolve short name → `repo_id` via `_config.repo_id_for`; build the correct nested payload. (PR #237) |
| 4 | `create_issue` / `list_issues` require `project_id` when the MCP server isn't running inside a workspace context — the cron is exactly that case. Bridge never threaded one. | Read `VK_DERIO_OPS_PROJECT` env; pass through `tick → dispatch_phase → create_issue` and `tick → dedup → list_issues`. Clean per-phase failure if unset. (PR #238) |
| 5 | The K8s manifest injects `VK_DERIO_OPS_PROJECT_ID` (`_ID`-suffixed); the bridge code (and legacy inline docs) read the bare name. | Read `_ID`-suffixed name first; legacy name as fallback. (PR #239) |
| 6 | `_expect_id(value, op)` only looked for `value["id"]`. VK's `create_issue` returns `{"issue_id": "<uuid>"}`, `start_workspace` returns `{"workspace_id": "<uuid>"}`, `update_issue` returns `{"issue": {...}}` — **none** of which match. Bridge raised AFTER VK had already created the card → cards stranded in "To do" with no workspace. | `_expect_id(value, op, *, field="id")` with per-tool field + wrapped-form fallback + `FakeMcpClient` returns real envelopes. (PR #240) |
| 7a | VK's `start_workspace` requires either `prompt=` or `issue_id=`; bridge passed neither → server-side 400 (`"Provide 'prompt', or 'issue_id' ..."`). | Pass `issue_id=card_id`; VK derives prompt and auto-links. (PR #241) |
| 7b | `McpWorkspaceRepoInput.branch` is the BASE branch VK forks the workspace off, NOT the workspace branch name. Bridge sent `branch="vk/gh-{N}"` → 400 (branch doesn't exist in target repo). | `branch="main"`; VK auto-generates the workspace branch (`vk/<ws-id-prefix>-<name-slug>`). (PR #242) |
| 7c | `dispatch_phase` named workspaces `{plan_slug}-P{N} -> gh#{N}`, but `reap_orphans` parses `<sid> -> gh#<n>` and looks up sid in `card_status` keyed by VK `simple_id`. Mismatch → freshly-spawned workspaces archived ~30s after creation. | Extract `simple_id` from the wrapped `update_issue` response; use as sid prefix. Matches legacy bridge convention. (PR #242) |

---

## Patterns that worked

### Tight TDD loop with wire-shape-faithful doubles

The canonical FakeMcpClient codified the bridge's *intended* shape and let
production bugs pass through. The fix wasn't "more tests" — it was **a
separate test double that refuses anything not matching the real VK server's
schema**.

In `tests/integration/test_bridge_dispatch_response_shape.py` the `_RealShapeMcp`
class is intentionally strict: returns the real envelope keys, refuses
`start_workspace` without `prompt`/`issue_id`, refuses a non-default base
branch. Tests against that double caught the next layer of bugs **before**
deploy on PRs #240–#242. New rule: when the canonical fake has demonstrably
drifted from production, write a wire-shape-faithful counterpart and run the
dispatch chain against both.

### Rust source as ground truth

Every wire-shape question got resolved by reading
`~/repos/vibe-kanban/crates/mcp/src/task_server/tools/` — `remote_issues.rs`,
`task_attempts.rs`, `repos.rs`, `mod.rs`. The Python schemas in our codebase
(`Protocol` definitions, `**kwargs`-laden wrappers) were ambiguous; the rust
schemas (`McpCreateIssueResponse { issue_id: String }`,
`StartWorkspaceResponse { workspace_id: String }`,
`McpWorkspaceRepoInput { repo_id: Uuid, branch: String }`) were definitive.
This was faster than any amount of empirical probing.

### Non-mutating probes against real VK

Several bugs were diagnosed without creating real cards/workspaces by passing
intentionally invalid arguments to the live MCP server and reading the error
envelope. Example: PR #242's `branch="main"` requirement was diagnosed by
calling `start_workspace(branch="vk/gh-82-probe", repo_id="00000000-...")` —
VK refused with the actual error reason in plaintext, no side effects.
Pattern: pass a deliberately invalid required arg, let the server's
validation tell you what's wrong, work backwards.

### Proximity to the production system

The agent ran inside the secure pod that hosts the bridge cron. That meant:

- `vk --version` and `./scripts/install.sh` updated the same binary the cron
  consumed. Deploy = `git pull && install.sh` in the same shell that diagnosed
  the bug.
- `tail -f ~/.willikins-agent/vk-bridge.log` was the live verification surface.
  Each PR's deploy was followed by one or two cron ticks (2-minute interval),
  then either green-light to the next bug or back to the worktree.
- Real `mcp.list_repos()` / `mcp.get_issue(...)` calls revealed VK's actual
  response shapes — no mocking required.
- Cleanups (`mcp.delete_issue(<card_id>)`) happened in the same session as
  the diagnosis.

The IDE's `vk-bridge.log` file open in a side pane while the cron rolled was
the single most productive debugging affordance. Without proximity, this work
would have taken N round-trips between "describe symptom" and "diagnose" — and
each round-trip would have lost context.

### A goal brief as the handoff artifact

The previous agent's
[`docs/goals/2026-05-18-bridge-apply-skip-issue-create.md`](../../goals/2026-05-18-bridge-apply-skip-issue-create.md)
was a model handoff: complete incident timeline, code pointers, TDD discipline,
BDD scenarios, verification steps, version bump instructions. The receiving
agent (this one) could start writing failing tests within minutes of reading
it. **The brief is the unit of transferable context** — better than a thread
of chat, better than a stale spec.

The same pattern continued mid-session: each PR's commit body and PR
description carried enough context to stand alone (incident reference, root
cause, fix shape, test coverage, version bump). Future-me reading
`git log` can reconstruct the session without this audit.

### `/goal` Stop hook persistence

The session covered ~4.5 hours, 7 PRs, ~15 separate sub-decisions. The `/goal`
Stop hook held the agent on task across:

- Diagnosis → fix → deploy → next-failure cycles
- Multiple `tick` waits (each up to 2 minutes)
- One user-confirmation pivot (the dispatch-path rebuild scope decision)
- A "delete the card" handoff to the operator

Without the hook, the agent would have wrapped after PR #236 (the original
goal was met) and the dispatch chain would still be broken. The hook isn't
just "don't stop" — it's "keep being useful past the natural stopping point
when the system is in your face."

### One focused PR per bug

Each gap got its own PR with its own regression-guard test. No batching, no
"while we're in here" refactors. Each PR title described one fact. Each
version bump was one patch. This made the timeline trivially diff-able — and
made it possible for the operator to follow along and intervene at any PR
boundary.

---

## What we'd do differently

### Bridge cli logs summary counts but not failure strings

Every diagnosis in this session required reproducing the bug manually because
the cron log only emits `synced=N errors=M skipped=K` per plan, not the actual
`TickResult.failures` strings. If `cli.py` had logged failures, several of the
sub-bugs (especially #6 and #7a) could have been diagnosed by reading the log
directly instead of running a manual `dispatch_phase`.

**Follow-up:** add `logger.warning("[bridge]   %s: failure: %s", slug, f)`
inside the per-plan loop for each entry in `result.failures`.

### Canonical fakes need a contract test against real wire

`FakeMcpClient.list_repos()` returning `{"name": "derio-net/X"}` was the
single most consequential bug — it masked five separate wire-shape mismatches.
A contract test that exercises the fake against a captured real-VK response
fixture (recorded with a tool like `vcr.py`) would have failed the moment
`FakeMcpClient` drifted from VK's actual shape.

**Follow-up:** record a session of real VK MCP responses, store as fixture
JSON, add a contract test that asserts each fake method's return shape
matches the corresponding fixture.

### Operator-visible symptoms lag the real bug

When `dispatch_phase` partially-succeeds (card created → status updated →
workspace fails), the operator sees "card in In Progress, no workspace" — a
shape that gives no hint of which call broke. Future bridge work should
consider transactional dispatch: don't create a card unless the workspace is
also going to succeed. Or at minimum, on failure, archive the half-created
card so the next tick re-attempts cleanly instead of dedup-shortcutting.

**Follow-up:** evaluate whether `dispatch_phase` should roll back the card on
`start_workspace` failure (delete the card so the next tick gets a clean
retry instead of a dedup hit + spurious `vk-synced` stamp).

### "Hardcoded `main`" is fragile

PR #242 ships `branch="main"` for every dispatch. Repos using `master`,
`trunk`, or feature branches as their default would break. A robust version
would resolve the target_repo's default branch (via `gh repo view --json
defaultBranchRef` or by reading `git symbolic-ref refs/remotes/origin/HEAD`
on the local checkout).

**Follow-up:** resolve the base branch per-repo at dispatch time.

### Card ↔ workspace link is loose

Post-v2.2.11, the dispatch chain works but `get_issue` reports
`linked_workspaces: None` and `list_workspaces` shows `linked_issue: None`,
even though `start_workspace.issue_id` should have auto-linked AND the
explicit `link_workspace_issue` call ran. Need to verify in the VK UI whether
the link is actually present (the fields may just not be surfaced by the
list endpoints), or whether VK's link path is silently broken.

**Follow-up:** verify card↔workspace navigation in the VK UI; if broken,
diagnose the `link_workspace_issue` response shape (likely also wrong
because `_expect_id` isn't called on it).

### The v2 rebuild's "test B2" guard didn't help

The B2 test (`test_no_duplicate_dispatch_implementations` in
`test_bridge_dispatch.py`) enforces that the `create_issue + update_issue +
list_repos + start_workspace + link_workspace_issue` sequence only exists in
one place in `src/`. It correctly enforced the invariant — but the invariant
was about *which calls* fire, not *what payload* they carry. Five of the
seven gaps were about payload shape, which B2 doesn't and can't check.

**Lesson:** call-sequence invariants are necessary but not sufficient.
End-to-end wire-shape assertions are what catches integration drift.

---

## Final state (2026-05-18 23:50 CEST)

- **Bridge version:** `vk 2.2.11`, deployed in `secure-agent-pod` via
  `~/.local/bin/vk` (installed from `~/repos/superpowers-for-vk` via
  `scripts/install.sh`).
- **Cron:** `*/2 * * * *` in `~/.crontab`, re-enabled, supercronic running.
- **Verified working:** `agent-images/2026-05-17-v2-bridge-cutover` (#82) dispatches end-to-end on every cron tick after a clean-state reset (delete VK card + clear `vk-synced` label).
- **Test suite:** 451 passing, 13 skipped, no failures, lint/typecheck clean.
- **PR series merged:** [#236](https://github.com/derio-net/superpowers-for-vk/pull/236), [#237](https://github.com/derio-net/superpowers-for-vk/pull/237), [#238](https://github.com/derio-net/superpowers-for-vk/pull/238), [#239](https://github.com/derio-net/superpowers-for-vk/pull/239), [#240](https://github.com/derio-net/superpowers-for-vk/pull/240), [#241](https://github.com/derio-net/superpowers-for-vk/pull/241), [#242](https://github.com/derio-net/superpowers-for-vk/pull/242).

---

## References

- Original incident brief: [`docs/goals/2026-05-18-bridge-apply-skip-issue-create.md`](../../goals/2026-05-18-bridge-apply-skip-issue-create.md)
- v2 rebuild design: [`docs/superpowers/specs/2026-05-17-v2-bridge-rebuild-design.md`](../specs/2026-05-17-v2-bridge-rebuild-design.md)
- `vibe-kanban-mcp` source (ground truth for wire shapes):
  - `~/repos/vibe-kanban/crates/mcp/src/task_server/tools/remote_issues.rs`
  - `~/repos/vibe-kanban/crates/mcp/src/task_server/tools/task_attempts.rs`
  - `~/repos/vibe-kanban/crates/mcp/src/task_server/tools/repos.rs`
  - `~/repos/vibe-kanban/crates/mcp/src/task_server/tools/mod.rs`
- Bridge log (live during this session): `~/.willikins-agent/vk-bridge.log`
- Closed spurious issues: sfv#196–#214, sfv#216–#234 (38 total, all closed with explanatory comments before the session opened).
