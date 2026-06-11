# Bridge dispatch hardening — observability, retry-safety, robustness

**Date:** 2026-06-11
**Status:** Seed spec (not yet approved) — authored from the 2026-05-18 bridge
dispatch rebuild-gap audit follow-ups. Intended to be one-shot with `/fr-goal`.
**Source audit:** `docs/superpowers/implemented/audits/2026-05-18-bridge-dispatch-rebuild-gap.md`
**Target repo:** derio-net/super-fr (package: `fr-vk`)

## Problem

The v2 bridge dispatch chain works end-to-end (since vk 2.2.11), but the
rebuild-gap audit closed with six "What we'd do differently" items. Five are
still open as of 2026-06-11 and each is a latent failure mode that cost real
debugging time during the original incident. They share a theme: the bridge is
correct on the happy path but **opaque and non-transactional when a single MCP
call fails mid-dispatch**, and it hardcodes assumptions that hold for today's
repos but not tomorrow's.

All file references below were verified against the current tree on 2026-06-11.

## Requirements

Five independent hardening changes. They are cohesive (all in `fr-vk`'s bridge
+ dispatch path) and should land as one PR with a regression test per item.

### 1. Log per-phase failure strings, not just summary counts

**Today:** `packages/fr-vk/src/fr_vk/bridge_cli.py` (~line 457–463) logs only
`synced=N errors=M skipped=K` per plan. The `TickResult.failures: tuple[str, ...]`
field (`fr-dispatch` `__init__.py`) is computed but never logged. Every
diagnosis in the original incident required reproducing the bug manually
because the cron log discarded the failure reason.

**Change:** in the per-plan loop, after the summary line, emit one
`logger.warning("[bridge]   %s: failure: %s", slug, f)` for each `f in
result.failures`. Keep the summary line.

**Acceptance:** a tick with ≥1 failure logs each failure string at WARNING;
a clean tick logs none. Test by asserting on captured log records.

### 2. Real-wire contract fixture for the MCP client double

**Today:** `tests/integration/test_bridge_dispatch_response_shape.py` has a
hand-written `_RealShapeMcp` double that encodes VK's real envelopes
(`create_issue → {"issue_id"}`, `start_workspace → {"workspace_id"}`,
`update_issue → {"issue": {...}}`) and enforces VK's validation rules. This is
good but **drift-prone**: it is asserted by hand, not pinned to a recorded real
response. The original root-cause bug was exactly a fake (`FakeMcpClient`) that
had silently drifted from VK's wire shape, masking five mismatches.

**Change:** record one real VK MCP response per dispatch-path method
(`list_repos`, `create_issue`, `update_issue`, `start_workspace`,
`link_workspace_issue`) as fixture JSON under
`tests/integration/fixtures/vk_wire/`. Add a contract test asserting that both
`FakeMcpClient` and `_RealShapeMcp` return shapes whose **keys** match the
fixture for each method. The recording can be captured via a small throwaway
script against the live bridge pod (document it in the test module docstring);
commit only the sanitized JSON (no card IDs that leak operator data — replace
UUIDs with `00000000-...` placeholders preserving shape).

**Acceptance:** the contract test fails if any fake method's return keys diverge
from the fixture. Out of scope: a full `vcr.py` HTTP-replay harness — key-shape
assertions against committed fixtures are sufficient.

### 3. Transactional dispatch — roll back a half-created card

**Today:** `packages/fr-vk/src/fr_vk/dispatch.py` `dispatch_phase` (~line
202–293) calls `create_issue` → `update_issue` → `start_workspace` →
`link_workspace_issue` with no rollback. If `start_workspace` raises after the
card was created, the card is stranded; the next tick's title-dedup sees it,
skips dispatch via the shortcut path, and stamps `vk-synced` — masking the
failure permanently (observed as "card in To do / In Progress, no workspace").

**Change:** wrap the post-`create_issue` steps so that on failure of
`update_issue`, `start_workspace`, or `link_workspace_issue`, the just-created
card is deleted (`mcp.delete_issue(card_id)`) before the failure propagates to
`TickResult.failures`. The next tick then gets a clean retry instead of a
dedup-shortcut + spurious `vk-synced`. Guard the cleanup itself (log if the
rollback delete also fails; do not mask the original error).

**Acceptance:** a test where `start_workspace` raises asserts `delete_issue` was
called with the created card's id and no `vk-synced` stamp was applied; the
failure string still reaches `TickResult.failures`.

### 4. Resolve the base branch per repo (drop hardcoded `main`)

**Today:** `dispatch.py` (~line 280) passes `branch="main"` to
`start_workspace`. `McpWorkspaceRepoInput.branch` is the **base** branch VK
forks off, so any target repo whose default is `master`/`trunk`/other breaks at
dispatch time.

**Change:** resolve the target repo's default branch once per dispatch (cache
per repo within a tick). Prefer `gh repo view <owner/name> --json
defaultBranchRef -q .defaultBranchRef.name`; fall back to `main` only if the
lookup fails, and log a warning when falling back. Thread the resolved branch
into `start_workspace`.

**Acceptance:** a test stubs the default-branch lookup to return `master` and
asserts `start_workspace` receives `branch="master"`; a lookup failure falls
back to `main` with a warning.

### 5. Verify and validate the card↔workspace link

**Today:** `dispatch.py` (~line 285) calls `mcp.link_workspace_issue(ws_id,
card_id)` and discards the response — unlike `create_issue`/`start_workspace`,
it never passes through `_expect_id`. The audit flagged that post-dispatch
`get_issue` reported `linked_workspaces: None`, leaving it unknown whether the
link is real or just unsurfaced.

**Change:** (a) validate the `link_workspace_issue` response shape the same way
as the other calls (read VK's rust source / a live probe to confirm the success
envelope; assert on it). (b) Add an integration assertion — against the
real-shape double — that after a successful dispatch the card reports its linked
workspace (or document, with evidence, that VK simply does not surface the link
on the list endpoints and the explicit `link_workspace_issue` call is the
authoritative linkage).

**Acceptance:** `link_workspace_issue`'s response is validated, not discarded; a
regression test pins its expected envelope shape.

## Non-goals

- Re-architecting the dispatch state machine. These are point fixes.
- Migrating away from the cron-tick model.

## Testing & verification

- One failing-first test per requirement, in the existing `fr-vk` test layout.
- After implementation: `uv run pytest` (full suite green), `ruff`, `mypy` clean.
- Bump the lockstep version (`scripts/bump-version.py`) and update `CHANGELOG.md`.
- Live verification (optional, operator-gated): deploy to the bridge pod and
  watch one cron tick produce a clean dispatch with the new failure logging.

## References

- Audit: `docs/superpowers/implemented/audits/2026-05-18-bridge-dispatch-rebuild-gap.md`
  (§"What we'd do differently").
- Bridge code: `packages/fr-vk/src/fr_vk/{bridge.py,bridge_cli.py,dispatch.py}`.
- Wire-shape ground truth: `~/repos/vibe-kanban/crates/mcp/src/task_server/tools/`.
