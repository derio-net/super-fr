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

<!-- fr:journal kind=discovery scope=plan id=p2-init-guard-inside-lock-try created=2026-07-24T21:03:51 phase=2 -->
### p2-init-guard-inside-lock-try · discovery · Init guard sits inside the lock try/finally; SystemExit(2) escapes both clauses by construction (phase 2)

The guard wraps only `mcp = _construct_mcp_client()` and lives INSIDE main()'s outer `try:` whose `finally:` closes the flock handle, so an init timeout still releases the lock (test re-acquires it after main() returns 1 to pin that). `except (TimeoutError, OSError)` deliberately does not catch SystemExit — SystemExit derives from BaseException, not Exception/OSError — so the I1 missing-binaries loud exit propagates out of main() untouched with code 2 and pushes NO failure metric (an operator install error is not a flaky tick). Both properties are now pinned by tests in tests/integration/test_bridge_resilience.py. reason='mcp_init_error' passes METRICS_REASON_ALIASES (packages/fr-vk/src/fr_vk/runner.py:40) unaliased as the plan predicted — only backend_error/preflight are remapped.

<!-- fr:journal kind=discovery scope=plan id=p2-missing-binaries-test-green-at-red-step created=2026-07-24T21:03:56 phase=2 -->
### p2-missing-binaries-test-green-at-red-step · discovery · test_missing_binaries_still_systemexit2 was GREEN at the red step — it is an invariant guard, not a red test (phase 2)

P2.T1.S2's EXPECT RED produced '1 failed, 11 passed': only test_tick_survives_mcp_init_timeout was red (TimeoutError escaped main() at bridge_cli.py:369). The sibling missing-binaries test passed before the change, as it must — it exists to pin that the new except clause does NOT swallow the pre-existing I1 SystemExit(2), i.e. it would only ever go red on a regression (e.g. someone widening the guard to `except Exception` or `except BaseException`). Anyone re-running the phase's TDD sequence should expect exactly one red, not two.

<!-- fr:journal kind=decision scope=plan id=p2-matrix-flip-notes-record-version created=2026-07-24T21:04:06 phase=2 -->
### p2-matrix-flip-notes-record-version · decision · Matrix flips carry the shipping version in notes, and the three rows split unit/unit/int (phase 2)

All three rows moved not-implemented -> ci: vk-mcp-timeout-survives-slow-ops (levels.unit = tests/unit/test_mcp_client_timeout.py), vk-mcp-post-timeout-correctness (levels.unit = tests/unit/test_mcp_client.py), vk-bridge-init-timeout-graceful (levels.int = tests/integration/test_bridge_resilience.py — integration, not unit, since it drives main() end-to-end). Each row's notes keeps the original incident sentence and appends what shipped and in which version (v3.15.1), so the row still explains the #404 failure mode after the spec is archived. `fr acceptance check` exit 0: 54 rows OK, 41 ci / 13 skipped, zero not-implemented remaining.

<!-- fr:journal kind=finding scope=plan id=rev-timeout-message created=2026-07-24T21:16:57 state=fixed -->
### rev-timeout-message · finding [fixed] · Mid-loop _recv timeout raised remaining-slice message

Reviewer (Minor 1): the common timeout path raised _recv's message reporting the remaining slice, not the awaited id + overall budget. Fixed: _recv_matching catches _recv's TimeoutError and re-raises the terminal message. Pinned by test_empty_queue_timeout_names_awaited_id_and_full_budget.

<!-- fr:journal kind=finding scope=plan id=rev-null-id-error created=2026-07-24T21:16:58 state=fixed -->
### rev-null-id-error · finding [fixed] · id:null JSON-RPC error responses were drained instead of surfaced

Reviewer (Minor 2): per JSON-RPC 2.0 a parse/association failure answers id:null + error; the drain loop discarded it and burned the full budget into TimeoutError. Fixed: fast-path returns null-id error messages so call_tool raises VkMcpError. Pinned by test_null_id_error_response_surfaced.

<!-- fr:journal kind=finding scope=plan id=rev-strict-id-compare created=2026-07-24T21:16:59 state=refuted -->
### rev-strict-id-compare · finding [refuted] · Strict == id comparison could miss a server echoing string ids

Reviewer (Minor 3), refuted/won't-change: JSON-RPC requires the server to echo the id verbatim; VK's serde echoes numbers as numbers. Loosening to str-compare would mask genuine protocol bugs. Reviewer agreed strictness is spec-correct ('a note, not a request').

<!-- fr:journal kind=finding scope=plan id=rev-stale-spec-sentence created=2026-07-24T21:17:00 state=fixed -->
### rev-stale-spec-sentence · finding [fixed] · Spec said _initialize inherits bare _recv() default (stale)

Reviewer (Minor 4): _initialize routes through _recv_matching, not a bare _recv(). Fixed the spec Design §3 sentence; DEFAULT_TIMEOUT constant (Minor 6) now single-sources the policy so the _recv default cannot silently diverge.

<!-- fr:journal kind=finding scope=plan id=rev-oserror-redundant created=2026-07-24T21:17:02 state=refuted -->
### rev-oserror-redundant · finding [refuted] · except (TimeoutError, OSError) tuple is redundant

Reviewer (Minor 5), refuted/kept: TimeoutError has been an OSError subclass since 3.3 so the tuple is expressive-only, but it documents the two intended failure modes at the guard site. Reviewer leaned keep; kept.

<!-- fr:journal kind=finding scope=plan id=rev-magic-180 created=2026-07-24T21:17:03 state=fixed -->
### rev-magic-180 · finding [fixed] · Magic 180.0 repeated across defaults

Reviewer (Minor 6): fixed via module-level DEFAULT_TIMEOUT = 180.0 used by _recv, call_tool, and _initialize; start_workspace keeps its explicit literal as the documented known-slow call.
