# Journal: 2026-09-08-session-unbind-hook-cancelled

<!-- fr:journal kind=repro scope=debug id=repro-1 created=2026-09-08T14:21:17 -->
### repro-1 · repro · SessionEnd hook fr-session-unbind.sh reported as 'Hook cancelled' on every session end

Operator sees, at the end of every Claude Code session:

    SessionEnd hook [${CLAUDE_PLUGIN_ROOT}/hooks/fr-session-unbind.sh] failed: Hook cancelled

Deterministic repro (Claude Code 2.1.263, macOS):

    claude -p "say ok" --debug hooks 2>&1 | grep -i "hook cancelled"

Fires 1/1. Not cosmetic: `~/.cache/fr/sessions/` held a binding from an
ended session (7ed8847b…, 09:24), i.e. the unbind never completed and
session bindings leak.

<!-- fr:journal kind=ruled-out scope=debug id=ruled-out-nonzero-exit created=2026-09-08T14:21:31 -->
### ruled-out-nonzero-exit · ruled-out · Not a non-zero exit: the script exits 0 on every path

fr-session-unbind.sh is `set -eu` with `|| true` on the one real call and a
literal `exit 0` at the end. "Hook cancelled" is not an exit code at all —
the Claude Code binary produces that exact string only in the `ABORT_ERR`
branch of its hook runner, i.e. the AbortSignal fired while the hook was
still running.

<!-- fr:journal kind=ruled-out scope=debug id=ruled-out-env-timeout created=2026-09-08T14:21:33 -->
### ruled-out-env-timeout · ruled-out · CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS=20000 does not help

The binary reads that env var first in `getSessionEndHookTimeoutMs`, so it
looked like the lever. Setting it to 20000 and re-running the repro still
produced "Hook cancelled". That value feeds the shutdown *failsafe* timer,
not the per-hook abort deadline.

<!-- fr:journal kind=ruled-out scope=debug id=ruled-out-plugin-timeout created=2026-09-08T14:21:52 -->
### ruled-out-plugin-timeout · ruled-out · A `timeout` in the PLUGIN hooks.json does not raise the budget (the obvious fix is a no-op)

Two experiments, both against the real binary:

1. A settings.json-level SessionEnd hook sleeping 2.5s with `"timeout": 15`
   survives — so the `timeout` field IS the budget lever, in general.
2. The same `"timeout": 15` written into the INSTALLED plugin manifest
   (~/.claude/plugins/cache/.../hooks/hooks.json) and re-running the repro:
   still "Hook cancelled".

`getSessionEndHookTimeoutMs` sums over `initialHooksConfig` (settings.json:
user/project/local) plus main-thread agent hooks. Plugin manifests are not in
that set. A plugin therefore CANNOT raise its own SessionEnd budget — shipping
`"timeout": N` in plugins/super-fr/hooks/hooks.json would have looked like a
fix, passed review, and changed nothing.

<!-- fr:journal kind=root-cause scope=debug id=root-cause created=2026-09-08T14:21:53 -->
### root-cause · root-cause · The hook takes ~2.1s; Claude Code aborts SessionEnd hooks at a hard 1500ms floor

Measured budget by bisection with a settings-level sleep hook, Claude Code
2.1.263:

| sleep | cancelled |
|-------|-----------|
| 0.5s  | no  |
| 1.0s  | no  |
| 1.4s  | no  |
| 1.8s  | YES |
| 2.5s  | YES |

Boundary is 1500ms exactly — `SESSION_END_HOOK_TIMEOUT_MS_DEFAULT` (the
`Math.max(1500, …)` floor in `getSessionEndHookTimeoutMs`).

`fr-session-unbind.sh` measures ~2.1s wall on this Mac, essentially all of it
`fr isolation detach` — Python interpreter + CLI import cost, before any work.

So: hook duration (2.1s) > budget (1.5s) -> SIGABRT -> "Hook cancelled", and
`fr isolation detach` is killed mid-flight, leaving the binding on disk.

Because a plugin cannot raise the budget, the hook must simply RETURN inside
1500ms. Since it is transport-only, best-effort, and already swallows every
error, the work belongs in a detached background process: the engine stays
`fr isolation detach`, the transport stops waiting for it.

<!-- fr:journal kind=finding scope=debug id=fix-background-detach created=2026-09-08T14:29:25 state=fixed -->
### fix-background-detach · finding [fixed] · Background the detach so the hook returns in ms; two tests pin both halves

Source change — plugins/super-fr/hooks/fr-session-unbind.sh:

    -fr isolation detach --session "$session_id" >/dev/null 2>&1 || true
    +nohup fr isolation detach --session "$session_id" >/dev/null 2>&1 </dev/null &

The redirections are load-bearing, not tidiness: the harness resolves a hook
only once its stdout AND stderr pipes close, so a child inheriting them would
keep it waiting the full ~2s and the abort would fire anyway.

Verified end to end against Claude Code 2.1.263:
- `claude -p "say ok" --debug hooks` — no "Hook cancelled" (was 1/1 before).
- The stale binding leaked by the 09:24 session was reaped within ~100ms of
  firing the fixed hook, proving the backgrounded detach really completes.
- Three backgrounding constructs (nohup, double-fork, both) were checked to
  survive real session teardown before picking one; `setsid` is absent on
  macOS, so the portable `nohup` form is used.

Tests (tests/unit/test_hooks_session_bind.py), both RED before the change:
- test_returns_inside_the_sessionend_budget_when_fr_is_slow — against a stub fr
  blocking 3s, the hook must return under the 1.5s ceiling.
- test_detach_still_completes_after_the_hook_returns — returning early must not
  become dropping the unbind; the stub log must be empty at return and land
  after. Pins the leak, not just the error message.
The pre-existing synchronous assertion became a race once the call was
backgrounded, so it now polls via a condition-based wait_for_log helper.
