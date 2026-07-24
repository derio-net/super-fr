# fr_vk MCP client timeout / permit-leak fix — plan narrative

Spec: `docs/superpowers/specs/2026-07-24-vk-mcp-timeout-permit-leak-design.md`
(issue #404). One live incident (2026-07-24, frank secure-agent-pod): the 30s
`_recv` default abandoned in-flight VK MCP requests under load; every abandoned
`start_workspace` leaked a `VK_MAX_CONCURRENT_EXECUTIONS` permit server-side
until the executor pool wedged terminally.

Three coordinated changes, two phases:

**Phase 1 — the client** (`packages/fr-vk/src/fr_vk/_mcp_client.py`):
uniform 180s default on `_recv`/`call_tool` (operator decision
qa-timeout-policy — retires the "cheap calls fail fast at 30s" design pinned
by `test_mcp_client_timeout.py`), and JSON-RPC response-id correlation
(decision qa-id-correlation): `call_tool`/`_initialize` drain the receive
queue discarding stale/foreign messages until the matching-id response
arrives within the overall deadline. Correlation is what makes the bridge's
existing per-call `except Exception` tolerance *correct* — without it, a
late response after a tolerated timeout is misattributed to the next call
(off-by-one responses for the client's remaining life).

**Phase 2 — the bridge + release** (`packages/fr-vk/src/fr_vk/bridge_cli.py`):
guard `_construct_mcp_client()` so an init `TimeoutError`/`OSError` logs,
pushes `push_failure_total(reason="mcp_init_error")`, and returns 1 instead
of an unhandled traceback (v3.14.0's second death mode). The I1
missing-binaries `SystemExit(2)` loud-exit is preserved. Then: acceptance
row flips, full CI gates, patch bump 3.15.0 → 3.15.1.

The exploration audit confirmed every other MCP call site in the
tick/sweeps (`fr_dispatch.tick`, `pr_state`, `workspaces`, per-plan loop)
already sits inside a per-item `except Exception` boundary that catches
`TimeoutError` — no new wrapping is needed there.

Out of scope: upstream vibe-kanban reaper fix (fork-tracked), frank-side
mitigations (shipped), `close()` hardening.

Post-merge Test Plan (spec §Test Plan) is operator-driven: upgrade fr on
the kali container, watch fr-bridge.log ticks, verify permits stop leaking.
