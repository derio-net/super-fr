# Journal: 2026-09-26-usage-unavailable-when-no-session

<!-- fr:journal kind=decision scope=plan id=one-phase-plan created=2026-09-26T15:06:48 -->
### one-phase-plan · decision · Single agentic standard-tier phase

Per operator: one phase, debugging-first (red tests, then fix, then refactor/gates and matrix/fragment bookkeeping).

<!-- fr:journal kind=decision scope=plan id=placeholder-after-merge created=2026-09-26T15:46:43 phase=1 -->
### placeholder-after-merge · decision · Placeholder written after the merge (phase 1)

capture() builds the no-session-found placeholder only when the merged list is empty, and _merge drops any earlier placeholder, so real sessions always win and repeated empty captures keep exactly one. Reason is kept verbatim in _KEPT_REASONS (NO_SESSION_FOUND).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-09-26T15:46:43 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

RED-only task: it adds failing tests and no production code, so there was nothing to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-09-26T15:46:43 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

The change is a three-line filter in _merge plus one fallback after it; nothing duplicated to extract.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-09-26T15:50:41 phase=1 state=open review_scope=out -->
### p1-r1 · finding [open] (reviewer: out of scope) · placeholder harness falls back to 'unknown' when detection fails (phase 1)

Spec accepts it; the reason text is harness-neutral. Pre-existing harness_now behaviour, not caused by this change.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-09-26T15:50:41 phase=1 state=open review_scope=out -->
### p1-r2 · finding [open] (reviewer: out of scope) · redundant FR_HOSTNAME monkeypatch in last new test (phase 1)

Harmless duplicate of the env override passed to capture; cosmetic.

<!-- fr:journal kind=review scope=plan id=p1-review created=2026-09-26T15:50:41 phase=1 -->
### p1-review · review · phase 1 review: no in-scope findings (phase 1)

Independent reviewer read the diff against spec/plan: _merge + post-merge placeholder correct and never-raising, require_sessions path unchanged, NO_SESSION_FOUND in closed vocabulary, telemetry.py untouched, no schema change, tests fail without the fix. Two out-of-scope nits filed (p1-r1, p1-r2).

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-09-26T15:50:41 phase=1 state=open resolves=p1-r1 out_of_scope=true -->
### p1-r1-resolved · finding [out-of-scope] · resolves p1-r1: placeholder harness falls back to 'unknown' when detection fails (phase 1)

Pre-existing harness_now fallback; not caused by this change.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-09-26T15:50:41 phase=1 state=open resolves=p1-r2 out_of_scope=true -->
### p1-r2-resolved · finding [out-of-scope] · resolves p1-r2: redundant FR_HOSTNAME monkeypatch in last new test (phase 1)

Cosmetic redundancy in a test; not a defect in this change.

<!-- fr:journal kind=finding scope=plan id=cr1 created=2026-09-26T23:37:02 phase=1 state=open review_scope=in -->
### cr1 · finding [open] (reviewer: in scope) · backfill writes sessions: [] for a cursor naming no session (phase 1)

backfill.py::_entries returned [] with no sessions and no cursor figures; same #636 defect by a second writer, and backfill never revisits a run.

<!-- fr:journal kind=finding scope=plan id=cr2 created=2026-09-26T23:37:03 phase=1 state=open review_scope=in -->
### cr2 · finding [open] (reviewer: in scope) · change fragment summary is not valid YAML (phase 1)

Unquoted plain scalar containing ': ' made yaml.safe_load raise; scripts/changes.py accepted it, other tools would not.

<!-- fr:journal kind=finding scope=plan id=cr3 created=2026-09-26T23:37:04 phase=1 state=open review_scope=in -->
### cr3 · finding [open] (reviewer: in scope) · matrix row at ci covers fr run cost only via summarize(), not the CLI (phase 1)

Test Plan item 2 names the CLI output; add a CLI-level assertion.

<!-- fr:journal kind=finding scope=plan id=cr4 created=2026-09-26T23:37:04 phase=1 state=open review_scope=out -->
### cr4 · finding [open] (reviewer: out of scope) · existing sessions: [] usage files stay as they are (phase 1)

e.g. implemented/usage/2026-09-26-fix-models-opencode-noop-505.yaml. Archived artifacts are frozen history; they already render as a dash, never 0.
