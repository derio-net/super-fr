<!-- fr:journal-schema=4 -->
# Journal: 2026-11-21-ops-echo-only-apply

<!-- fr:journal kind=repro scope=debug id=repro-1 created=2026-11-21T16:23:58+00:00 -->
### repro-1 · repro · mutating op with echo-only apply passes self-review; apply_ops records it applied

frank#1007 (run 2026-11-16-feat-gpu-speech-service-1006): ops premerge-gpu-switcher-image and premerge-speech-image are mutating: true with apply: echo '…docker buildx build --push…'. fr plan self-review passed both. fr ops apply would run the echo (exit 0) and treat the op as applied; deliver's last lines told the operator 'fr pickup --run' rather than 'fr ops gate --run'.

<!-- fr:journal kind=root-cause scope=debug id=rc-1 created=2026-11-21T16:24:00+00:00 -->
### rc-1 · root-cause · no layer asks whether an apply acts

plan_ops._ops_gap_issues (plan_ops.py:1967) refuses only check == TODO; apply_ops (ops/apply.py:316) runs op.apply and trusts exit 0; run_cmd._closeout_handoff_lines (run_cmd.py:408) always names fr pickup --run, never consulting fr.run.closeout.devops_gated, which fr pickup itself uses to pick the DevOps brief.

<!-- fr:journal kind=ruled-out scope=debug id=ro-1 created=2026-11-21T16:24:02+00:00 -->
### ro-1 · ruled-out · defect 2 (tool absent from ops profile) is already fail-closed at runtime

A check whose tool is missing exits 127 under bash -c; engine._check maps NOT_FOUND to CANNOT-VERIFY, never DONE (tests/unit/test_ops_engine.py::test_cannot_verify_on_exit_127), and apply_ops stops on CANNOT-VERIFY. The frank case hid docker behind echo, so it is closed by the print-only fix. An authoring-time capability check needs the profile's tool set declared (#1489 'declared needs'); left to that issue.

<!-- fr:journal kind=finding scope=debug id=f-1 created=2026-11-21T16:30:06+00:00 state=fixed -->
### f-1 · finding [fixed] · print-only apply refused at self-review, never counted applied

fr.ops.lint.print_only (one predicate; heredoc bodies, comments and command substitutions are not commands; any file redirect or other first word acts; unparseable is not judged). plan_ops._ops_print_only_issues errors per op; apply_ops treats the op as a manual step (not run, not recorded). Tests first: tests/unit/test_ops_lint.py (predicate table, test_apply_does_not_count_a_print_only_apply_as_applied, test_self_review_errors_on_a_print_only_apply).

<!-- fr:journal kind=finding scope=debug id=f-2 created=2026-11-21T16:30:08+00:00 state=fixed -->
### f-2 · finding [fixed] · a done entry did not say whether the apply ran

Found by the read-only audit: apply_ops wrote the same 'result: done' for an op already DONE before its apply (nothing ran) and one fr applied, so no journal could show that an apply acted. It now records reason FOUND_DONE or APPLIED_DONE (reason is an existing op body key: no journal shape change). Test: tests/unit/test_ops_lint.py::test_a_done_entry_says_whether_the_apply_ran.

<!-- fr:journal kind=finding scope=debug id=f-3 created=2026-11-21T16:30:10+00:00 state=fixed -->
### f-3 · finding [fixed] · devops-gated deliver hand-off named the post-merge pickup

run_cmd._closeout_handoff_lines now asks fr.run.closeout.devops_gated (the same decision fr pickup makes) and names 'fr ops gate --run <id>'; an error in that read keeps the pickup line, which fr pickup routes to the DevOps brief anyway. Tests: tests/unit/test_ops_devops_brief.py::test_deliver_handoff_names_the_devops_stage_for_a_devops_gated_run and its negative twin. fr-goal SKILL.md sentence updated; mirrors synced.

<!-- fr:journal kind=discovery scope=debug id=d-audit created=2026-11-21T16:30:39+00:00 -->
### d-audit · discovery · audit of recent devops close-outs (read-only): no false DONE from a print-only apply

super-fr: no real ops.yaml, no ops profile; clean. agent-images, kid-laptops: no ops; clean. No cnc-* repos found. frank#1007 (run 2026-11-16-feat-gpu-speech-service-1006): the two print-only ops never reached the stage (no op entries) and their images do not exist on GHCR; the branch head has since rewritten them as real post-merge ops. frank root-agents run 2026-11-14-feat-scope-root-agents-912 (#985/#1004): ops are not print-only and their checks are real, but cutover-move-membership and premerge-namespaces got their done entries at stage 6, after stages 4-5 closed, through the found-done path, so no entry shows the gate applied them (f-2 makes that visible from now on); live state not verifiable from here. frank#992: app-webhooks-permission-revoke has no entry and the live installation still holds repository_hooks: write. frank#949/#955 merged with gate:devops unpassed and no op entries.

<!-- fr:journal kind=review scope=debug id=review-1 created=2026-11-21T16:34:53+00:00 -->
### review-1 · review · independent adversarial review: 3 print_only false-print-only bugs fixed, nits partly fixed

A reviewer that had not seen my reasoning read the diff. Each finding was reproduced before acting. Fixed (tests in tests/unit/test_ops_lint.py): (1) an unquoted substitution beside a separator (`);` lexes as one token) swallowed the rest of the command; (2) a substitution body was never judged, and an assignment-only line made it print-only; (3) a `<<` in quotes, a here-string or arithmetic opened a heredoc that hid later lines; nits: `> 1` is a file, `<>` writes, `for` loops, `command echo`, `/bin/echo`. Kept as conservative (false 'acts', the safe direction): a quoted `">"` reads as a redirect; `case` acts. Parts 2 (done reason) and 3 (hand-off) were found sound.
