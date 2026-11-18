<!-- fr:journal-schema=4 -->
# Journal: 2026-11-18-consumer-delivery

<!-- fr:journal kind=discovery scope=plan id=p1-bun-flaky-under-load created=2026-11-18T16:03:17+00:00 phase=1 -->
### p1-bun-flaky-under-load · discovery · bun timing tests time out on a loaded host (phase 1)

marker relative-PATH, pin registration and quiet-placement tests failed only while pytest ran in parallel; green alone (host load average above 30).

<!-- fr:journal kind=decision scope=plan id=p1-rule-list-env-var created=2026-11-18T16:03:17+00:00 phase=1 -->
### p1-rule-list-env-var · decision · install.sh hands the rule list to the delivery as FR_OPENCODE_RULES (phase 1)

One space-separated env var keeps the positional contract (install <dir>) that every caller and test uses; the list stays defined once, in CLAUDE_RULES.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-18T16:03:17+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

smoke and change fragment only, no code to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-18T16:03:17+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

docs and acceptance bookkeeping, no code to clean

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-18T16:16:49+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · install.sh's refusal line still says fix cli.json, wrong for the new missing-rule refusal (phase 1)

scripts/install.sh:1024-1025. Fixed: the second line now says fix what the message above names (cli.json, or a missing rule file).

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-18T16:16:49+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · FR_OPENCODE_RULES expanded unquoted (globbing) and rule names not validated (phase 1)

scripts/deliver-opencode-plugin.sh:127,138. Fixed: one `read -r -a` into an array, every name must match ^[A-Za-z0-9._-]+\.md$ and not start with a dot, checked before any write; parametrised refusal test.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-18T16:16:49+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · De-dup by exact text gives two copies of a rule under version skew with opencode.json instructions (phase 1)

packages/fr-opencode-plugin/src/rules.ts:60. Fixed: a part whose `Instructions from: <path>/<file>` header names the same rule file also counts as present; tests for skew and for a same-suffix different file.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-18T16:16:49+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · Unreadable-file test passes as root and does not prove the skip (phase 1)

packages/fr-opencode-plugin/test/rules.test.ts:61-74. Fixed: a readFile seam throws for bad.md; the test asserts exactly ["OK"].

<!-- fr:journal kind=review scope=plan id=review-phase-1 created=2026-11-18T16:16:49+00:00 phase=1 -->
### review-phase-1 · review · phase 1 review: approve with 4 minor in-scope findings, all fixed (phase 1)

Independent reviewer (separate context) checked R1-R7, the three de-dup cases, lookup counts and fallbacks; bun test 320/0 and tsc clean at review. Findings p1-r1..p1-r4 (all in scope, minor) fixed with tests; after the fixes bun test 322/0, tsc clean, 32 pytest pass. Declined-to-judge items were outside the phase (live OpenCode semantics owed to Test Plan 1).

<!-- fr:journal kind=lens scope=plan id=lens-security-1 created=2026-11-18T16:16:49+00:00 phase=1 lens=security step=review-phase -->
### lens-security-1 · lens · the installer copies files named by an env var; check every installer input together (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-18T16:16:49+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: install.sh's refusal line still says fix cli.json, wrong for the new missing-rule refusal (phase 1)

Neutral remedy line in install.sh.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-18T16:16:49+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: FR_OPENCODE_RULES expanded unquoted (globbing) and rule names not validated (phase 1)

Array read plus name validation before any write; refusal tests.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-18T16:16:49+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: De-dup by exact text gives two copies of a rule under version skew with opencode.json instructions (phase 1)

Header-name de-dup in rules.ts with tests.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-18T16:16:49+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: Unreadable-file test passes as root and does not prove the skip (phase 1)

readFile seam; exact assertion.
