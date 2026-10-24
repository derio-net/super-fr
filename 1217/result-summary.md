# Issue 1217 — implementation and verification record

**Code tree:** branch `fix/opencode-v2-recovery-launch`, commit
`559fa99c0779882c30de527c5e99f9af2c120de6`. This commit was pushed by the
coordinator. The worktree was clean when this record was written.

## Change

OpenCode 2.1.4 does not accept root-level `--model`. Managed launches now create
a session through `POST /api/session` with the requested `Model.Ref` and
checkout location, verify the returned model, and start the interactive root
with `--session <id> --auto`. The session ID is persisted in the managed
descriptor and participates in process identity checks. Existing session-less
legacy descriptors retain the previously supported exact model-argument forms.
Initial dispatch, replacement/recovery, and managed restart use the pinned
session path.

## Full-suite status — NOT GREEN

A conservative full-suite run (`uv run pytest -q --no-cov -n 2`) completed on
the pre-compatibility-follow-up tree with **13,463 passed, 136 skipped, and 10
failed** in 4,283 seconds. The failures were reviewed and addressed with focused
regressions; the full suite was **not rerun on this final commit**. Do not
represent the final tree as having a passing full suite.

The earlier `-n auto` run was interrupted by Docker/xdist worker failures at
about 71%; it did not produce a suite result and is not a pass.

### Exact failures and follow-up fixes

1. `tests/integration/test_scenarios.py::test_herdr_opencode_launch` — the
   synthetic runner had no `opencode` executable. The scenario now stubs
   session creation and expects `--session … --auto`.
2. `::test_herdr_opencode_restart` — synthetic pre-session process state used
   legacy `--model` args. Legacy descriptors retain exact old-form recognition;
   the restart scenario supplies a fake API executable and verifies the new
   session launch.
3. `::test_herdr_batch_replace` — replacement source identity did not carry the
   current managed session ID. Replacement now copies the persisted source
   session, and the synthetic scenario models session-based process args.
4. `::test_triage_closed_recovery` — synthetic recovery invoked the real API
   command and asserted the obsolete `--model` launch. It now stubs session
   creation and asserts session attachment.
5. `tests/unit/test_herdr_replacement_observer.py::test_captured_completed_history_has_safe_empty_prompt`
   — legacy captured descriptor had no session ID; fixed by the narrow legacy
   launch-form compatibility branch.
6. `::test_activation_can_observe_a_confirmed_busy_target_without_sending_input`
   — same session-less captured-process compatibility fix.
7. `::test_legacy_source_checkout_is_validated_but_target_must_use_primary`
   — same session-less captured-process compatibility fix.
8. `tests/unit/test_opencode_rendered_readiness.py::test_initial_dispatch_waits_for_rendered_prompt_before_single_submission`
   — synthetic timeline had no API executable and assumed `--model`; it now
   stubs session creation and tracks the pinned session arguments.
9. `::test_managed_restart_waits_for_new_rendered_prompt` — the source process
   used a session-less legacy descriptor; the compatibility branch preserves
   source eligibility before restart creates a fresh pinned session.
10. `::test_replacement_target_waits_for_rendered_prompt` — source identity had
    no session propagation and synthetic session creation was not stubbed; both
    are now covered in the fixture and replacement path.

## Final-tree verification

- mypy: passed for `packages/fr-herdr/src/fr_herdr` (9 source files).
- Focused unit group: **277 passed** with `-n 2`.
- Separate focused installed-scenario run: **27 passed**, including the four
  scenarios above.
- Ruff check and format check: passed for changed Python files.
- `git diff --check`: passed.
- `fr acceptance check`: passed, **561 rows OK** (existing debt warnings remain).
- Change-fragment gate: passed.

## Review and live-test boundary

The final compatibility diff received an independent read-only review with no
findings. The earlier response-envelope question was verified and resolved in
the debug journal against the v2.1.4 protocol and server handler, both of which
specify/return `{data: PublicSessionInfo}`.

No real OpenCode session, fixture session, shared-service restart, or A/B
fixture recovery was performed. The draft PR is explicitly TEST-BLOCKED pending
CI/full-suite evidence; the pending CI result is owned by the operator.
