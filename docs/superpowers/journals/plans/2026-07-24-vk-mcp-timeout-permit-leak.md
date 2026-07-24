# Journal: 2026-07-24-vk-mcp-timeout-permit-leak

<!-- fr:journal kind=review scope=plan id=plan-self-review created=2026-07-24T20:39:51 -->
### plan-self-review · review · Plan self-review passed; phases match spec

fr plan self-review green after fr_version floor bump to >=3.7.0. Phase 1 covers spec design 1+2 (uniform 180s, id correlation) with acceptance rows vk-mcp-timeout-survives-slow-ops + vk-mcp-post-timeout-correctness; phase 2 covers design 3 + gates + patch bump with row vk-bridge-init-timeout-graceful. No manual phases.

<!-- fr:journal kind=discovery scope=plan id=p1-recv-matching-first-attempt-full-budget created=2026-07-24T20:51:44 phase=1 -->
### p1-recv-matching-first-attempt-full-budget · discovery · _recv_matching gives the FIRST attempt the full timeout (spec sketch would have made it timeout-epsilon) (phase 1)

The spec's sketch computes `remaining = deadline - time.monotonic()` at the TOP of every iteration, so the very first `_recv` sees 179.99998..., not 180.0 — the monotonic clock has already advanced between setting the deadline and reading it back. That made P1.T1's `recv_timeouts == [180.0] * 6` assertions unsatisfiable without pytest.approx, which would have weakened the pin the whole file exists for.

Implemented instead: seed `remaining = timeout` before the loop and recompute it only AFTER a discarded message, with the loop condition `while remaining > 0` and the TimeoutError raised on fall-through. Semantics are identical (same overall monotonic deadline, same discard-and-retry) but the first attempt gets exactly the requested budget, so the timeout-policy tests assert exact equality and the recorded-timeout double stays a precise seam.

Consequence for anyone extending the tests: the first entry in _RecordingMcpClient.recv_timeouts per call IS the requested timeout; later entries for the same call are the shrinking remainder.

<!-- fr:journal kind=discovery scope=plan id=p1-existing-fakes-already-id-correct created=2026-07-24T20:52:02 phase=1 -->
### p1-existing-fakes-already-id-correct · discovery · Existing test doubles already sent id-correct responses, so id correlation landed with zero collateral churn (phase 1)

Both pre-existing doubles happened to be id-faithful already: `_FakeVkMcpClient`'s helpers (`_ok`/`_err`) default to msg_id=1 and `_client_with` is always used for a client's FIRST call (id 1), while `_RecordingMcpClient._recv` synthesizes `"id": self._msg_id` — i.e. it echoes whatever id the request just allocated. So routing call_tool through _recv_matching required no edits to any existing test, and the id-correlation tests only had to ADD cases.

The stale-response test therefore has to manufacture the mismatch deliberately: set `client._msg_id = 5` before the call (so the request allocates id 6) and queue a stale id=5 reply ahead of the id=6 one. `_AlwaysMismatchClient` uses id=999 plus a 10ms sleep per attempt so the 0.05s-budget drain test finishes in ~5 iterations instead of spinning thousands of warning logs.

Full suite re-run after the change: 1750 passed, 80 skipped — no other call site depended on _recv's pop-anything behavior or on the 30s default.

<!-- fr:journal kind=decision scope=plan id=p1-skip-request-extraction created=2026-07-24T20:52:04 phase=1 -->
### p1-skip-request-extraction · decision · Skipped P1.T2.S5's optional _request() extraction (marked '-' with note) (phase 1)

call_tool and _initialize share only three lines of scaffolding (increment self._msg_id, _send the envelope, _recv_matching). Their payloads differ (tools/call params vs the protocolVersion/capabilities/clientInfo handshake) and _initialize additionally sends the trailing notifications/initialized. A _request(method, params, timeout) helper would hide the handshake's distinct shape for no meaningful dedup, so the step was ticked with state '-' and that reasoning as its note, per the step's own 'Skip if clean.'
