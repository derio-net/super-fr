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
