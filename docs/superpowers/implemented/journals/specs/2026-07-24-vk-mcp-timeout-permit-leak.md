# Journal: 2026-07-24-vk-mcp-timeout-permit-leak

<!-- fr:journal kind=decision scope=spec id=qa-timeout-policy created=2026-07-24T20:33:36 -->
### qa-timeout-policy · decision · Uniform 180s timeout for _recv/call_tool defaults

Operator chose uniform 180s (issue #404's ask) over the earlier fail-fast design pinned by test_mcp_client_timeout.py (cheap calls 30s). No env knob. The fail-fast pin tests are rewritten to pin 180s.

<!-- fr:journal kind=decision scope=spec id=qa-id-correlation created=2026-07-24T20:33:37 -->
### qa-id-correlation · decision · Include JSON-RPC response-id correlation in call_tool

Operator chose to include id matching: call_tool drains the recv queue discarding stale/mismatched responses (id < expected, or notifications without id) until the expected id arrives, within the overall deadline. Makes tolerated TimeoutError safe — without it a late response is misattributed to the next call.

<!-- fr:journal kind=decision scope=spec id=qa-test-plan created=2026-07-24T20:33:38 -->
### qa-test-plan · decision · Post-merge Test Plan: pod upgrade + observe

Operator upgrades fr on the kali container (frank secure-agent-pod), then watches fr-bridge.log across a few ticks: no TimeoutError tracebacks; vibekanban_active_executions matches live executor processes; queued executions drain.

<!-- fr:journal kind=review scope=spec id=spec-self-review created=2026-07-24T20:35:44 -->
### spec-self-review · review · Spec reviewed against Q&A + codebase reality

Verified every file/line the spec names on main@094502b: _mcp_client.py:79/101/114/210, bridge_cli.py:369 unguarded init, existing except-Exception boundaries in tick/pr_state/workspaces, METRICS_REASON_ALIASES pass-through for mcp_init_error, test files exist. All three Q&A decisions encoded. No findings.
