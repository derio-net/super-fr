# fr_vk MCP client: 180s timeouts + response-id correlation + init tolerance

**Slug:** 2026-07-24-vk-mcp-timeout-permit-leak
**Issue:** https://github.com/derio-net/super-fr/issues/404
**Status:** draft

## Problem

On 2026-07-24 (frank secure-agent-pod), vk-local's executor pool wedged:
`vibekanban_active_executions` pinned at max (4) with 10 queued executions and
zero live executor processes — only defunct zombies, and 10 `execution_processes`
rows stuck `status='running'`.

Mechanism: `fr_vk/_mcp_client.py`'s `_recv` defaults to `timeout=30.0`. Heavy VK
ops routinely exceed 30 s under load. On a client-side timeout the server-side
request future is dropped, cancelling `Child::wait().await` — the child completes
but is never reaped, the DB row stays `running`, and the
`VK_MAX_CONCURRENT_EXECUTIONS` semaphore permit is never released. Leaks are
cumulative and terminal: once `active == max` on dead executions, every later
spawn queues forever.

The traceback (`TimeoutError: No response from MCP server within 30.0s`) fired
from fr v3.14.0's bridge tick at 2026-07-24 08:58 UTC; that tick also died
during `_construct_mcp_client()` init. This client backs **every** fr→VK
dispatch path (`fr apply --to vk` included), not just the supercronic bridge.

Exploration found a third defect the issue implies but doesn't name: `_recv`
pops the next queued message without matching the JSON-RPC response `id`. After
any tolerated timeout, the late response stays queued and is misattributed to
the **next** call — off-by-one responses for the rest of the client's life
(e.g. `update_issue` receiving `create_issue`'s payload, breaking
`_extract_simple_id` / `_expect_id`). "Tolerate `TimeoutError` and continue"
is only safe with id correlation.

## Current state (verified against `main` @ 094502b)

- `_recv(timeout=30.0)` — `packages/fr-vk/src/fr_vk/_mcp_client.py:79`.
- `_initialize` calls `_recv()` bare → the MCP handshake gets the 30 s default
  (`_mcp_client.py:101`). Under load (or an `npx -y vibe-kanban@latest` cold
  download) this times out and the exception propagates out of
  `bridge_cli.main` (`bridge_cli.py:369` is not guarded) — whole tick dies
  with a traceback and **no failure metric**.
- `call_tool(..., timeout=30.0)` — `_mcp_client.py:114`; only `start_workspace`
  opts up to 180 s (`_mcp_client.py:210`, since v3.0.0).
- `tests/unit/test_mcp_client_timeout.py` pins the old design ("cheap calls
  fail fast at 30 s; only start_workspace opts up") — deliberately overridden
  by issue #404 + operator Q&A.
- Per-plan / per-card loops in `bridge_cli.py`, `fr_dispatch.tick`,
  `pr_state.py`, `workspaces.py` already wrap backend calls in broad
  `except Exception`, which catches `TimeoutError` — per-call tolerance
  already exists everywhere except client construction.

## Design

Three changes, all in `packages/fr-vk` (plus tests):

### 1. Uniform 180 s default (operator decision qa-timeout-policy)

- `_recv` default `30.0` → `180.0`.
- `call_tool` default `30.0` → `180.0`; rewrite its docstring (the fail-fast
  rationale is retired by #404 — a 30 s deadline under load *causes* the
  wedge it was meant to surface).
- `start_workspace` keeps its explicit `timeout=180.0` (now equal to the
  default, retained as documentation of the known-slow call).
- No env knob (operator declined the override option).
- Explicit `timeout=` on `call_tool` still wins — unchanged.

### 2. Response-id correlation in `call_tool` (operator decision qa-id-correlation)

`call_tool` (and `_initialize`) must receive **the response whose `id` matches
the request it just sent**, within an overall deadline:

- Loop on `_recv` with the remaining deadline (monotonic clock) until a
  message with `id == msg_id` arrives; raise `TimeoutError` when the budget
  is exhausted.
- Discard with a `logger.warning` any message whose `id` != expected: stale
  responses from previously timed-out calls, and server-initiated
  notifications/requests (no `id` or unknown `id`). Ids are allocated
  monotonically from `self._msg_id`, so a mismatch is always stale/foreign,
  never "not yet sent".
- This makes the client safe to keep using after a tolerated timeout —
  required for the bridge's existing per-call `except Exception` posture to
  be correct.

### 3. Bridge init tolerance (issue fix 2)

- Wrap `_construct_mcp_client()` in `bridge_cli.main` so `TimeoutError` (and
  `OSError`-family spawn failures) log one clear line, push
  `_metrics.push_failure_total(reason="mcp_init_error")`, and `return 1` —
  graceful exit instead of an unhandled traceback; the lock still releases
  via the existing `finally`. The loud-exit for *missing binaries* (I1,
  `SystemExit(2)`) is unchanged.
- The 180 s default from change 1 already gives init the longer deadline the
  issue asks for (`_initialize`'s bare `_recv()` inherits it).
- No new per-issue wrapping needed elsewhere: audit confirmed every MCP call
  site in the tick/sweeps is already inside a per-item `except Exception`
  boundary. A regression test pins the init path.

## Out of scope

- Upstream vibe-kanban reaper fix (global child registry) — tracked in the
  fork, lower priority.
- Frank-side mitigations (concurrency cap 4→8, runbook) — already shipped in
  frank.
- `close()` hardening (kill-after-terminate) — untouched.

## Tests

- Rewrite `tests/unit/test_mcp_client_timeout.py`: pin the 180 s default for
  `_recv`/`call_tool`/wrappers; keep the explicit-override-wins case.
- New unit tests (`test_mcp_client.py` or the timeout module): stale response
  with a lower `id` is discarded and the matching one returned; a
  notification (no `id`) is skipped; deadline exhaustion while draining
  mismatches raises `TimeoutError`.
- New integration test (`tests/integration/test_bridge_resilience.py` or
  `test_bridge_cli.py`): `VkMcpClient` construction raising `TimeoutError`
  → `main()` returns 1, pushes `mcp_init_error` failure metric, no traceback
  propagation.

## Version

Patch bump (CLI/engine fix): 3.15.0 → 3.15.1 via `scripts/bump-version.py patch`.

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| 2026-07-24-vk-mcp-timeout-permit-leak | `derio-net/super-fr` | `2026-07-24-vk-mcp-timeout-permit-leak` | — |

## Test Plan

Post-merge, operator-driven (decision qa-test-plan):

1. Upgrade fr on the kali container of frank's secure-agent-pod to the tagged
   release (v3.15.1).
2. Watch `fr-bridge.log` across several supercronic ticks: no
   `TimeoutError: No response from MCP server` tracebacks; ticks complete
   with the summary line.
3. Verify `vibekanban_active_executions` matches live executor processes
   (no phantom `running` rows accumulating) and `vibekanban_queued_executions`
   drains as slots free.
