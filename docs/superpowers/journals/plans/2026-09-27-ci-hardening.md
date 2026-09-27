# Journal: 2026-09-27-ci-hardening

<!-- fr:journal kind=decision scope=plan id=one-agentic-phase created=2026-09-27T14:38:41+00:00 -->
### one-agentic-phase · decision · One agentic phase, tier standard

Change is .github/** + two test files + matrix; no second phase to smoke. No tracking_issue set (brief: members stay batch-owned).

<!-- fr:journal kind=discovery scope=plan id=sha-pins-reresolved-no-drift created=2026-09-27T14:51:16+00:00 phase=1 -->
### sha-pins-reresolved-no-drift · discovery · Every spec §3.A row re-resolved identically via gh api on 2026-09-27 (phase 1)

Re-resolved all 12 rows of spec §3.A through `gh api repos/<o>/<r>/git/ref/tags/<tag>` (dereferencing annotated tag objects via `git/tags/<sha>` to their commit) and confirmed the exact vX.Y.Z version tag dereferences to the same commit. Every commit SHA matched the spec table exactly — no tag had moved, so no unreviewed commit was pinned and no finding was needed.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-09-27T14:51:16+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

acceptance status moves and verification runs only, no code written, so nothing to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-09-27T14:51:16+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

_ci_ok_step's "every other job id" check already reuses _load_ci_workflow directly (other_job_ids = set(jobs) - {"ci-ok"}) rather than a second loader, so there was nothing to consolidate.

<!-- fr:journal kind=finding scope=plan id=tripwire-ignores-yaml-extension created=2026-09-27T14:55:32+00:00 phase=1 state=open review_scope=in -->
### tripwire-ignores-yaml-extension · finding [open] (reviewer: in scope) · Workflows named *.yaml bypass the tripwire (phase 1)

check_pins globbed only *.yml; GitHub runs .yaml too.

<!-- fr:journal kind=finding scope=plan id=flow-style-negative-not-routed-through-the-check created=2026-09-27T14:55:32+00:00 phase=1 state=open review_scope=in -->
### flow-style-negative-not-routed-through-the-check · finding [open] (reviewer: in scope) · Formatting-evasion negatives did not go through check_pins (phase 1)

Flow-style / quoted key / 'uses :' returned [] from check_pins; only a real-repo multiset test caught it, so the negative guarded nothing on its own (spec 3.C: one code path).

<!-- fr:journal kind=finding scope=plan id=version-comment-accepts-four-components created=2026-09-27T14:55:32+00:00 phase=1 state=open review_scope=in -->
### version-comment-accepts-four-components · finding [open] (reviewer: in scope) · vX.Y.Z regex accepted v1.2.3.4 and v1.2.3-rc1 (phase 1)

\b matched before the fourth component.

<!-- fr:journal kind=finding scope=plan id=run-block-uses-line-false-positive created=2026-09-27T14:55:32+00:00 phase=1 state=open review_scope=in -->
### run-block-uses-line-false-positive · finding [open] (reviewer: in scope) · A run: | line starting with uses: was flagged (phase 1)

Text regex matched inside block scalars.

<!-- fr:journal kind=finding scope=plan id=comment-only-evasion-via-block-scalar created=2026-09-27T14:55:32+00:00 phase=1 state=open review_scope=in -->
### comment-only-evasion-via-block-scalar · finding [open] (reviewer: in scope) · A commented decoy in a run block could vouch for an uncommented flow-style pin (phase 1)

Scanned/parsed multisets matched while the real pin had no comment.

<!-- fr:journal kind=review scope=plan id=review-phase-1 created=2026-09-27T14:55:32+00:00 phase=1 -->
### review-phase-1 · review · independent code review of phase 1: 5 findings, all fixed (phase 1)

Dispatched reviewer (opus). Pins (all 12 re-verified via git ls-remote), dependabot.yml, ci-ok job + tests, acceptance rows: no findings. Tripwire: 5 in-scope findings, fixed in 7594c228 by walking the composed YAML node graph (yaml.compose) for jobs.<id>.uses and steps[].uses and reading the version comment from text after the value's end mark; *.yaml globbed; comment regex (?=\s|$). Each fix has a red-first negative through check_pins; 28 tests pass.

<!-- fr:journal kind=finding scope=plan id=tripwire-ignores-yaml-extension-resolved created=2026-09-27T14:55:32+00:00 phase=1 state=fixed resolves=tripwire-ignores-yaml-extension -->
### tripwire-ignores-yaml-extension-resolved · finding [fixed] · resolves tripwire-ignores-yaml-extension: Workflows named *.yaml bypass the tripwire (phase 1)

7594c228: _workflow_files globs *.yml and *.yaml; test_a_yaml_extension_workflow_is_checked_too.

<!-- fr:journal kind=finding scope=plan id=flow-style-negative-not-routed-through-the-check-resolved created=2026-09-27T14:55:32+00:00 phase=1 state=fixed resolves=flow-style-negative-not-routed-through-the-check -->
### flow-style-negative-not-routed-through-the-check-resolved · finding [fixed] · resolves flow-style-negative-not-routed-through-the-check: Formatting-evasion negatives did not go through check_pins (phase 1)

7594c228: check_pins walks composed nodes, so flow-style/quoted/'uses :' are checked directly; three negatives assert check_pins non-empty.

<!-- fr:journal kind=finding scope=plan id=version-comment-accepts-four-components-resolved created=2026-09-27T14:55:32+00:00 phase=1 state=fixed resolves=version-comment-accepts-four-components -->
### version-comment-accepts-four-components-resolved · finding [fixed] · resolves version-comment-accepts-four-components: vX.Y.Z regex accepted v1.2.3.4 and v1.2.3-rc1 (phase 1)

7594c228: (?=\s|$) lookahead; v4.4.0.1 and v4.4.0-rc1 negatives.

<!-- fr:journal kind=finding scope=plan id=run-block-uses-line-false-positive-resolved created=2026-09-27T14:55:32+00:00 phase=1 state=fixed resolves=run-block-uses-line-false-positive -->
### run-block-uses-line-false-positive-resolved · finding [fixed] · resolves run-block-uses-line-false-positive: A run: | line starting with uses: was flagged (phase 1)

7594c228: block scalars are never uses nodes; test_a_uses_line_inside_a_run_block_is_not_a_uses.

<!-- fr:journal kind=finding scope=plan id=comment-only-evasion-via-block-scalar-resolved created=2026-09-27T14:55:32+00:00 phase=1 state=fixed resolves=comment-only-evasion-via-block-scalar -->
### comment-only-evasion-via-block-scalar-resolved · finding [fixed] · resolves comment-only-evasion-via-block-scalar: A commented decoy in a run block could vouch for an uncommented flow-style pin (phase 1)

7594c228: the comment is read after the real node's end mark; decoy test flags x.yml:9.
