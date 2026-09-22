# Journal: 2026-09-22-triage-open-prs

<!-- fr:journal kind=discovery scope=plan id=c2d9d038123d created=2026-09-22T15:00:25 phase=1 -->
### c2d9d038123d · discovery · no-refactor-because P1.T1 (phase 1)

Test-only red task: writes failing tests and captures fixtures; no production code touched, nothing to refactor.

<!-- fr:journal kind=discovery scope=plan id=41cd022e8f6f created=2026-09-22T15:00:25 phase=2 -->
### 41cd022e8f6f · discovery · no-refactor-because P2.T1 (phase 2)

Test-only red task for anchors; no production code, nothing to refactor.

<!-- fr:journal kind=discovery scope=plan id=1280000d4381 created=2026-09-22T15:00:26 phase=3 -->
### 1280000d4381 · discovery · no-refactor-because P3.T1 (phase 3)

Test-only red task for delivery judgements; no production code, nothing to refactor.

<!-- fr:journal kind=discovery scope=plan id=2deb9936cf45 created=2026-09-22T15:00:26 phase=4 -->
### 2deb9936cf45 · discovery · no-refactor-because P4.T1 (phase 4)

Test-only red task for render; no production code, nothing to refactor.

<!-- fr:journal kind=discovery scope=plan id=6397220f209e created=2026-09-22T13:04:17 phase=1 -->
### 6397220f209e · discovery · open PR collection implemented (phase 1)

Implemented schema 2 facts with open-only PR collection and compact checks/merge/review fields; legacy Forge fakes fall back to filtering the existing all-state response.

<!-- fr:journal kind=discovery scope=plan id=2851dc624279 created=2026-09-22T13:04:19 phase=1 -->
### 2851dc624279 · discovery · no-refactor-because P1.T2 (phase 1)

Collect parsing and schema changes are already factored into small helpers; no further cleanup warranted.

<!-- fr:journal kind=discovery scope=plan id=09ec3e53e671 created=2026-09-22T15:35:16 phase=1 -->
### 09ec3e53e671 · discovery · Phase 1 executor gaps closed inline (phase 1)

Executor left P1.T1.S2 (fixture capture) undone and 7 stale schema-1 tests red. Fixed inline: Facts.schema_ is Literal[2] (strict refuse, not lenient 1|2); updated test_triage_model/collect/check/cli/skeleton to schema 2; captured tests/fixtures/triage/super-fr-open-prs.json live (PR #560, CONFLICTING/DIRTY, whole record); normalized empty reviewDecision to None; SKIPPED/NEUTRAL checks count as pass. All 198 triage tests green, ruff clean.

<!-- fr:journal kind=finding scope=plan id=f1 created=2026-09-22T15:36:05 phase=1 state=open -->
### f1 · finding [open] · Unlinked-PRs dedupe keys on bare number, collides across repos (phase 1)

collect.py linked_numbers is {p.number}: repo A PR #5 linked to an issue suppresses repo B's unlinked PR #5 from Facts.prs. Key must be (repo, number).

<!-- fr:journal kind=finding scope=plan id=f2 created=2026-09-22T15:36:05 phase=1 state=open -->
### f2 · finding [open] · getattr fallback for list_open_prs contradicts the Forge protocol (phase 1)

collect.py uses getattr(forge, 'list_open_prs', None) with silent degrade, but Forge declares it required and GhForge implements it. The fallback only serves two stale test doubles (cli _Forge, skeleton FixtureForge). Remove the fallback and add the method to both doubles so a missing method fails loudly.

<!-- fr:journal kind=review scope=plan id=f050972013a8 created=2026-09-22T15:36:56 phase=1 -->
### f050972013a8 · review · review-phase 1: 2 findings raised, both fixed (phase 1)

Reviewed spec+plan+code for phase 1 (collect open PRs, schema 2). Findings: f1 cross-repo dedupe key, f2 getattr fallback vs Forge protocol. Both fixed with regression tests. No open findings remain.

<!-- fr:journal kind=finding scope=plan id=f1-resolved created=2026-09-22T15:36:57 state=fixed resolves=f1 -->
### f1-resolved · finding [fixed] · resolves f1: Unlinked-PRs dedupe keys on bare number, collides across repos

Dedupe key is now (repo, number); regression test test_same_pr_number_in_two_repos_dedupes_per_repo.

<!-- fr:journal kind=finding scope=plan id=f2-resolved created=2026-09-22T15:36:57 state=fixed resolves=f2 -->
### f2-resolved · finding [fixed] · resolves f2: getattr fallback for list_open_prs contradicts the Forge protocol

Fallback removed; collect calls forge.list_open_prs directly; list_open_prs added to cli and skeleton test doubles.

<!-- fr:journal kind=discovery scope=plan id=db59d201a1f8 created=2026-09-22T13:41:06 phase=2 -->
### db59d201a1f8 · discovery · no-refactor-because P2.T2 (phase 2)

Anchor selection, file reads, and fallback are isolated helpers; no cleanup warranted.

<!-- fr:journal kind=review scope=plan id=0c023df1a038 created=2026-09-22T15:43:03 phase=2 -->
### 0c023df1a038 · review · review-phase 2: no findings (phase 2)

Reviewed spec+plan+code for phase 2 (intent anchors). Anchor order, head-ref fetch with 2000-char cap, spec-meta ref, forge-error degradation all match spec 3.B and Q&A 1. Verified read_file_at_ref live against origin (21KB body). No findings.

<!-- fr:journal kind=discovery scope=plan id=cecea4f371c5 created=2026-09-22T13:45:28 phase=3 -->
### cecea4f371c5 · discovery · no-refactor-because P3.T2 (phase 3)

Optional judgement fields and check classification are direct model extensions; no cleanup warranted.

<!-- fr:journal kind=review scope=plan id=26e1ab768764 created=2026-09-22T15:46:39 phase=3 -->
### 26e1ab768764 · review · review-phase 3: no findings (phase 3)

Reviewed phase 3 (delivery verdicts, unranked-PRs check set). Optional delivery fields keep judgements schema 1 with old files loading; unranked_prs keyed by repo+number grammar; CLI escapes titles. No findings.

<!-- fr:journal kind=discovery scope=plan id=36dc10812b58 created=2026-09-22T15:51:34 phase=4 -->
### 36dc10812b58 · discovery · Phase 4 render implementation (phase 4)

Phase 4 render now puts PRs first with escaped anchor/delivery metadata, CI symbols, verbatim merge_state, collection timestamp, red-CI/conflict chips, and no-script completeness. Render tests: 60 passed; mirror tripwires: 11 passed. Full suite exceeded 120s after 62 tests; minor bump 4.14.4→4.15.0 and acceptance rows moved to ci.

<!-- fr:journal kind=finding scope=plan id=f3 created=2026-09-22T15:55:29 phase=4 state=open -->
### f3 · finding [open] · check prints PRs as owner/repo#n, not the judgement key grammar (phase 4)

CLI prints derio-net/super-fr#564 but judgements.yaml wants super-fr#564 (KEY_RE). Copy-paste from check into judgements fails validation. Print issue_key form like the JSON output does.

<!-- fr:journal kind=review scope=plan id=1cd8627f849d created=2026-09-22T16:44:59 phase=4 -->
### 1cd8627f849d · review · review-phase 4: 1 finding raised, fixed (phase 4)

Reviewed phase 4 (render badges, PRs section, skill + mirrors, minor bump, matrix rows). Findings: f3 CLI printed owner/repo#n instead of judgement-key grammar. Fixed with regression test. Also trimmed SKILL.md to exactly 120 lines (skill validation green) and re-ran both mirror syncs. Live smoke on derio-net/super-fr: 7 issue-less PRs surface with badges, PRs section renders, chips present.

<!-- fr:journal kind=finding scope=plan id=f3-resolved created=2026-09-22T16:44:59 state=fixed resolves=f3 -->
### f3-resolved · finding [fixed] · resolves f3: check prints PRs as owner/repo#n, not the judgement key grammar

check prints issue_key form; regression test test_unranked_prs_print_in_judgement_key_grammar.
