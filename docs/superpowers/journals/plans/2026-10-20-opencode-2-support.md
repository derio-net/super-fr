<!-- fr:journal-schema=2 -->
# Journal: 2026-10-20-opencode-2-support

<!-- fr:journal kind=decision scope=plan id=five-phases created=2026-10-20T05:45:16+00:00 -->
### five-phases · decision · Five phases — restore, enforce, status line, readers, published surfaces

Phase 1 restores the plugin on V2 (entrypoint, edit gate, pin, idle, claim,
session-id export) and carries the run's one measured premise: V2's
`ShellCreateBefore` has no session id, so `FR_OPENCODE_SESSION_ID` is
correlated from the `shell` tool call's `execute.before`. The stated
failure outcome is "export nothing", never a guess.

Phase 2 adds the pipeline sentinel, the whole-command shell gate (porting
the bash entrypoint's decision, held to it by a verdict table captured by
running the script) and the merged-PR push guard, then the nag and
bind/unbind.

Phase 3 lands the TUI status line and its delivery/registration, risk
first: a TUI entrypoint OpenCode will not load without consumer-side peer
packages is a real possibility, and the phase records which mechanism
shipped.

Phase 4 moves both store readers (`fr.run.observed` and `fr.usage`) onto
`session_v2`/`session_message` behind an explicit version probe, so an
OpenCode 1.x session is refused by name instead of reading as empty.

Phase 5 closes the loop: parity rows, the matrix and its three reports, the
canonical rule and both mirrors, the explainer and the `bump: major`
fragment.

Every `opencode-2-*` row is linked to the phase that implements it; phase 5
records their evidence as bookkeeping. `fr plan self-review` passes with
the split and tier decisions recorded in the spec journal.
