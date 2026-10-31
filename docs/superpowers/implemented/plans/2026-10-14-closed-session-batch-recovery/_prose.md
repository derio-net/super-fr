# Closed-session batch recovery implementation

One agentic phase delivers the single operator ask: an explicit held fresh session
for an already-dispatched batch, without changing its work or lifecycle. The hard
tier is warranted by cross-store allocation/checkpoint concurrency and no-replay
gates. Tasks follow red → green → refactor within the phase. The operator walk is
post-merge at Tester, not an agentic task or a manual implementation phase.

Use the existing optional replacement seam with explicit --recover and durable
source/item allocation intent. Avoid initial dispatch or lifecycle reset. Tests
use fake herdr/forge and disposable local fixtures only. No real paused batch,
triage scope, org driver or hardware is mutated by implementation or validation.
Render/drive unification (#1216) is outside scope.

All pipeline cursor/usage commands run on the host from this workspace with uv run
fr. Tests/builds run through the isolation exec bridge; the coordinator test-slot
wrapper owns heavy-suite concurrency. The final suite runs after the last code
commit into a host-visible log. No nested worktree is created for phase execution.
