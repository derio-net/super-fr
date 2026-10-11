# Drive resilience — implementation plan

One agentic phase for the batch `driver-resilience` (super-fr#1127, #1134, #1135). The three asks are
small and touch adjacent code (the drive command, the privacy guard, the REST client), about 450 lines
in all, so a single reviewer holds them. Splitting would add two executor and reviewer round trips for
no review benefit.

Order inside the phase, smallest risk first:

1. **§C — free-plan rulesets 403** (`real_ghrestclient.required_check_names`). Self-contained.
2. **§B — unreadable visibility retries in loop mode.** `VisibilityUnreadable(PrivacyError)` and the
   `ForgeReadError(code=2)` mapping in `take_lease`/`save_pass`, which reuses the loop's existing skip-and-retry
   policy. `_host_loop` honours `restart_to` on a skipped pass (spec-review sr-1).
3. **§A — the single-pass guard.** `--single-pass`, `SinglePass` passed through `build_driver`, and the
   refusal after planning. Existing dispatching `--once --yes` host tests gain `--single-pass`. Then the
   fr-triage skill sentence and both mirror syncs.

Verification is unit tests only (spec `## Verification`: `strategy: none`). The rows move to `ci` in the
final task.
