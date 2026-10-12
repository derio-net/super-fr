# Journal: 2026-10-11-fr-small-fixes

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-12T15:09:26+00:00 input=true -->
### operator-brief · discovery · Batch fr-small-fixes dispatch brief (verbatim)

/fr-goal fr small fixes: tracker close state, models errors, skill column count

Batch `fr-small-fixes` of derio-net/super-fr: 4 issues, delivered as ONE pull request.

## super-fr#1102: tracker/github.py:114 passes state='closed' in lower case; both clients accept only OPEN/CLOSED
`packages/fr/src/fr/tracker/github.py:114` still `edit_issue_state(repo, number, state="closed")`; both clients accept only OPEN/CLOSED, so moving a tracker item to done raises.

## super-fr#1057: fr models check: dead-binding reason keeps trailing ')]))' from the wrapped provider error
`packages/fr/src/fr/bindings/probe.py:49` `_NOT_FOUND` still `[^"\\\n]*`, so the displayed reason keeps `)]))`. Cosmetic; verdict correct.

## super-fr#1055: corrupt models.yaml crashes fr run start after save
Corrupt `models.yaml` raises from `load_models` (`packages/fr/src/fr/models.py:56`) before any guard. Loud, pre-existing.

## super-fr#1066: the fr-triage skill says 'six lifecycle columns'; the board has seven
Skill and both mirrors (`.opencode/skills/fr-triage/SKILL.md:101`) still say six lifecycle columns; `kanban.py:62-72` `COLUMN_TITLES` has seven (Partial added by gh#985).

## Why these belong together
Four small independent fixes; #1102 makes every tracker close raise.

## Delivery rules
- Work on branch `feat/batch-fr-small-fixes`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#1102
  Closes derio-net/super-fr#1057
  Closes derio-net/super-fr#1055
  Closes derio-net/super-fr#1066
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

Coordinator rule (relayed mid-session): targeted tests only locally; any full or large suite through `bash ~/.cache/fr/coord/testslot.sh -- <cmd>`; prefer CI (`tests: ci`); never mark the PR ready, never merge.

<!-- fr:journal kind=decision scope=spec id=d1-models-error-scope created=2026-10-12T15:09:26+00:00 -->
### d1-models-error-scope · decision · #1055 reaches every models.yaml reader

Operator chose: load_models wraps YAML parse errors in ModelsError naming the file; `fr run start` warns after the save and exits 0; advance, resolve's chained advance and `fr models …` refuse with one `fr: <path>: …` line, exit 2. Not taken: guard run start only; treat a corrupt file as empty. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d2-board-columns-tripwire created=2026-10-12T15:09:26+00:00 -->
### d2-board-columns-tripwire · decision · #1066 names the columns and adds a tripwire, defensively

Operator chose name + tripwire, adding: the columns may change (another issue is in flight), so program defensively. Verified: #1107 adds two columns (nine) and #1151 renames the skill paragraph's lead. So the skill lists titles without a count, the docstring names neither, and the test reads COLUMN_TITLES live, finds the paragraph by content, and refuses a stated count (spec §D). decider: operator.

<!-- fr:journal kind=decision scope=spec id=d3-strict-fake created=2026-10-12T15:09:26+00:00 -->
### d3-strict-fake · decision · #1102 fixes the call site and makes FakeGhClient strict

Operator chose: state="CLOSED" at the call site, and FakeGhClient.edit_issue_state raises ValueError on anything but OPEN/CLOSED, like the real clients. Not taken: call site only; case-normalising the real clients. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d4-probe-trim created=2026-10-12T15:09:26+00:00 -->
### d4-probe-trim · decision · #1057 strips trailing brackets rather than narrowing the regex

Operator chose: keep the regex, rstrip a trailing run of `)`/`]`/whitespace, so a parenthesis inside the provider's own message survives. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d5-light-shape-verification-none created=2026-10-12T15:09:26+00:00 -->
### d5-light-shape-verification-none · decision · Light path, one agentic phase; verification none, tests: ci

Operator chose fr-goal-light with one agentic phase, `## Verification` = `strategy: none` with a reason per row, and the full suite proven by CI on the PR (`tests: ci`). decider: operator.

<!-- fr:journal kind=finding scope=spec id=spr-r1 created=2026-10-12T15:16:39+00:00 state=open review_scope=in -->
### spr-r1 · finding [open] (reviewer: in scope) · R6/§C: catching ModelsError at fr run resolve's entry hides that the record was already applied

target: spec. run_cmd.py:6688-6699 applies and commits the record, then _advance_after_record (6702-6735, contract: a failure here must say the record is applied) runs _advance_chain, whose first act (5470) is _orchestrator_model_notice → load_models. A handler at resolve's entry would print only `fr: <path>: …` and invite a re-apply.

<!-- fr:journal kind=finding scope=spec id=spr-r2 created=2026-10-12T15:16:39+00:00 state=open review_scope=in -->
### spr-r2 · finding [open] (reviewer: in scope) · R6's resolve-chained-advance clause has no test in the plan or the Verification row

target: plan. P1.T3.S3 covered start, advance and fr models only; the Verification row named no resolve.

<!-- fr:journal kind=finding scope=spec id=spr-r3 created=2026-10-12T15:16:39+00:00 state=open review_scope=in -->
### spr-r3 · finding [open] (reviewer: in scope) · R6 says every reader refuses, but triage batch dispatch/drive read models.yaml and are not covered

target: spec. triage_batch_cmd.py:941-953 _orchestrator calls load_models uncaught; decision d1 named only run start, advance, resolve's chained advance and fr models.

<!-- fr:journal kind=finding scope=spec id=spr-r4 created=2026-10-12T15:16:39+00:00 state=open review_scope=in -->
### spr-r4 · finding [open] (reviewer: in scope) · R5/R6 stated unconditionally, but no models.yaml is read when no harness is detected

target: spec. run_cmd.py:3609-3610 (_resolved_model returns None before load_models with no harness), 3437-3438, 3454-3458. An executor could read R5 as requiring a new unconditional load.

<!-- fr:journal kind=review scope=spec id=spec-plan-review-1 created=2026-10-12T15:16:39+00:00 -->
### spec-plan-review-1 · review · spec+plan review: 4 findings (spr-r1, spr-r2, spr-r3, spr-r4 in scope, none out)

Independent fr-spec-reviewer (opus) checked decisions d1–d5 against the spec, every named file/helper/test against the codebase (file:line for each), the plan against R1–R7 (each built by a task, TDD shape, no member issue as tracking_issue, rows linked, commands real) and the spec's internal consistency. Verified the strict fake breaks only test_tracker.py:341, which T1 rewrites.

<!-- fr:journal kind=finding scope=spec id=spr-r1-resolved created=2026-10-12T15:16:39+00:00 state=fixed resolves=spr-r1 -->
### spr-r1-resolved · finding [fixed] · resolves spr-r1: R6/§C: catching ModelsError at fr run resolve's entry hides that the record was already applied

Spec R6 and §C now catch the error inside _advance_after_record and print `record applied; the advance after it was refused: fr: <path>: …`, exit 2. Plan P1.T3.S4 says the same and forbids a handler at resolve's entry.

<!-- fr:journal kind=finding scope=spec id=spr-r2-resolved created=2026-10-12T15:16:39+00:00 state=fixed resolves=spr-r2 -->
### spr-r2-resolved · finding [fixed] · resolves spr-r2: R6's resolve-chained-advance clause has no test in the plan or the Verification row

Plan P1.T3.S3 adds (d) resolve --record on a done record: applied, exit 2, no traceback, the 'record applied' line. It also adds (e) no harness → no read. The Verification row now names resolve --record.

<!-- fr:journal kind=finding scope=spec id=spr-r3-resolved created=2026-10-12T15:16:39+00:00 state=fixed resolves=spr-r3 -->
### spr-r3-resolved · finding [fixed] · resolves spr-r3: R6 says every reader refuses, but triage batch dispatch/drive read models.yaml and are not covered

R6 narrowed to the commands d1 names. Triage batch dispatch/drive is listed under Non-goals for the operator to revisit at PR review, and the plan says to leave it untouched.

<!-- fr:journal kind=finding scope=spec id=spr-r4-resolved created=2026-10-12T15:16:39+00:00 state=fixed resolves=spr-r4 -->
### spr-r4-resolved · finding [fixed] · resolves spr-r4: R5/R6 stated unconditionally, but no models.yaml is read when no harness is detected

R5/R6 qualified: they apply when a harness is detected and the command reads the config; with no harness nothing is read and behaviour is unchanged. §C says no new load is added; plan test (e) pins it.
