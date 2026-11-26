<!-- fr:journal-schema=4 -->
# Journal: 2026-11-25-wave-plan-file-overlap

<!-- fr:journal kind=discovery scope=spec id=brief-1577 created=2026-11-25T13:12:29+00:00 input=true -->
### brief-1577 · discovery · Operator brief: derio-net/super-fr#1577

Goal as typed: derio-net/super-fr#1577 — Wave planning: flag batches whose plans touch the same files before they conflict at merge. Read the issue and its triage judgement (refs/heads/fr-triage/s-f7ea4061, judgements.yaml) for context. Deliver one PR as fr-goal does; do not merge it (the operator's wave driver merges). Stay clear of the live batches for #1578 and #1581.

Issue title: Wave planning: flag batches whose plans touch the same files before they conflict at merge

Issue body:
## Problem
Conflicts between batches of one wave are discovered only at merge time, when the second PR to touch a file conflicts. Each one costs a hand-back, a session cycle, a full suite, a push and a fresh approval (2026-11-19: #1550 twice, #1551 twice).
## Proposal
When the plans of a wave's batches exist, the driver (or `fr triage batch` planning) compares the files each plan says it will touch. Batches that overlap on a non-generated path are flagged: merge them into one batch, or order one after the other with `--after` / a later wave. Generated mirrors (the repo's `mirrors:`) are not overlap, since they are regenerated. The check is advisory at wave planning and visible on the Batches page.
Related: the merge-queue issue https://github.com/derio-net/super-fr/issues/1576.

Triage judgement: tier 3, theme triage-drive, cx M, severity med, kind feature; "Flag batches whose plans touch the same files at wave planning, before they conflict at merge." Note: Feature group Merge flow; designed with #1576.

<!-- fr:journal kind=decision scope=spec id=q-source created=2026-11-25T13:12:29+00:00 decided_by=operator -->
### q-source · decision · Compare plan files only

Operator: compare each batch plan's phase `files:`, read at its branch head; the PR-diff forecast stays as it is. decider: operator

<!-- fr:journal kind=decision scope=spec id=q-globs created=2026-11-25T13:12:29+00:00 decided_by=operator -->
### q-globs · decision · Glob against literal only

Operator: literal-literal and glob-matches-literal count; two globs never overlap. decider: operator

<!-- fr:journal kind=decision scope=spec id=q-pairs created=2026-11-25T13:12:29+00:00 decided_by=operator -->
### q-pairs · decision · Any two unmerged batches not linked by after

Operator: compare every pair of unmerged batches whose plans exist and are not in one after-chain, whatever their wave. decider: operator

<!-- fr:journal kind=decision scope=spec id=q-surfaces created=2026-11-25T13:12:29+00:00 decided_by=operator -->
### q-surfaces · decision · Batches page and fr triage check

Operator: surface on the Batches page cards and as a `plan overlap` set in `fr triage check`; no driver warning, no new command. decider: operator

<!-- fr:journal kind=decision scope=spec id=q-collision created=2026-11-25T13:12:29+00:00 decided_by=operator -->
### q-collision · decision · New module, thin hook into kanban

Operator: logic in a new fr/triage/plan_overlap.py; kanban.py/kanban_render.py get one field and one line; model.py untouched (no schema change). decider: operator

<!-- fr:journal kind=decision scope=spec id=q-verify created=2026-11-25T13:12:29+00:00 decided_by=operator -->
### q-verify · decision · CI unit tests only

Operator: rows verify none, CI unit tests over fixture plans and batches; no walk owed. decider: operator

<!-- fr:journal kind=decision scope=spec id=q-gate created=2026-11-25T13:12:29+00:00 decided_by=operator -->
### q-gate · decision · Gate developer, no hold

Operator: gate developer; nothing held after merge. decider: operator

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-11-25T13:17:35+00:00 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · The run cursor has no `artifacts.plan` key; the plan folder is in `steps.<step>.emitted.plan`

check: codebase. run/model.py:278,317 and a real cursor (2026-11-24-feat-ci-economy.yaml:34-38) hold the plan at steps.plan.emitted.plan. The spec's reader would find no plan in any real cursor.

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-11-25T13:17:35+00:00 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · PlanSource cannot tell no-ref from no-cursor

check: consistency. gitseam.py:960-966 list_dir returns [] for a missing ref, so R2's separate reasons are untestable with list_dir/show alone.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-11-25T13:17:35+00:00 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · Unknown batch repo and a clone with no origin have no stated reason

check: consistency. batch.py:108-113 batch_repo may return None; gitseam.py:651-655 origin_repo raises without an origin; unstated they crash fr triage check, which must exit 0.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-11-25T13:17:35+00:00 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · The driver's board reads cwd, but the driver works through --checkout clones

check: codebase. triage_batch_cmd.py:3961-3990 and :5822-5836: group/org scopes would show every repo but the cwd's as not compared.

<!-- fr:journal kind=finding scope=spec id=s5 created=2026-11-25T13:17:35+00:00 state=open review_scope=in -->
### s5 · finding [open] (reviewer: in scope) · build_board's overlap input and the board's unread display are undefined

check: consistency. kanban.py:804-815; triage_kanban_cmd.py:424-436 notes. Type of overlaps= and where unread reasons show were unstated.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-25T13:17:35+00:00 -->
### spec-review-1 · review · independent spec review: 5 findings

Dispatched fr-spec-reviewer reviewed spec and journal against the 7 decisions and the codebase; 5 findings (s1-s5), all in scope, all fixed in the spec. Every other named helper was verified with file:line (last_dispatch, dependency_state, with_forecast, planned_merge_order, read_cursor, KIND_DIRS, toplevel, Checkout.origin_repo/show/list_dir, TriageConfig.generated, VersionBlock.files, Facts.config_for, PhaseHeader.files, Card, build_board, write_board, check_command, batch edit --wave/--after). Suggested lenses: errors, tests.

<!-- fr:journal kind=lens scope=spec id=lens-errors-1 created=2026-11-25T13:17:35+00:00 lens=errors step=spec-review -->
### lens-errors-1 · lens · The not-compared path must turn every git and YAML failure into a reason inside a command that always exits 0

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-25T13:17:35+00:00 lens=tests step=spec-review -->
### lens-tests-1 · lens · The reader's fixtures must match the real cursor and phase-file shapes

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-11-25T13:17:35+00:00 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: The run cursor has no `artifacts.plan` key; the plan folder is in `steps.<step>.emitted.plan`

Background, R1 and Design A now read the plan folder from the `plan` value of any step's `emitted` mapping; the quiet/stealth case is named; the Test Plan fixture uses the real cursor shape.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-11-25T13:17:35+00:00 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: PlanSource cannot tell no-ref from no-cursor

PlanSource gains exists_at(ref, path), which Checkout has (gitseam.py:944); the reader checks the ref first, so `no ref origin/<branch>` is its own reason.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-11-25T13:17:35+00:00 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: Unknown batch repo and a clone with no origin have no stated reason

R2 names `repo of batch unknown` (batch_repo None); R9 names `no clone here` for a cwd outside a clone or without origin; source_for_clones turns GitError into that reason; both are in the Test Plan.

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-11-25T13:17:35+00:00 state=fixed resolves=s4 -->
### s4-resolved · finding [fixed] · resolves s4: The driver's board reads cwd, but the driver works through --checkout clones

write_board takes an optional checkouts map; the driver's _write_board passes checkout_paths (one line, inside the module budget: 8223 of 8225); R9 states the driver's board reads its own clones.

<!-- fr:journal kind=finding scope=spec id=s5-resolved created=2026-11-25T13:17:35+00:00 state=fixed resolves=s5 -->
### s5-resolved · finding [fixed] · resolves s5: build_board's overlap input and the board's unread display are undefined

build_board takes overlaps: Mapping[str, tuple[str, ...]] from card_lines(report); each not-compared batch is one page note; R7's Test Plan line covers it.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-25T13:17:37+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  plan-overlap-board: none
  plan-overlap-check: none
row_kinds:
  plan-overlap-board: none
  plan-overlap-check: none
run_gate: developer
run_kind: none
```

<!-- fr:journal kind=discovery scope=spec id=test-plan-step-1 created=2026-11-26T12:56:50+00:00 -->
### test-plan-step-1 · discovery · Test Plan step 1: ran

Step: pre-merge — CI: `tests/unit/test_triage_plan_overlap.py` covers the reader over the real cursor shape (`steps.plan.emitted.plan`) and real phase files (cursor found, plan read, and every R2 and R9 reason: unknown repo, no ref, no cursor, no recorded plan, unreadable file, no clone, no clone of the repo), the overlap rule (literal, glob against literal, glob against glob not counted, `generated:` and `version.files` ignored), `after` chains in both directions and through a third batch, cross-wave pairs, and R9's clone rule (row `plan-overlap-check`).

Evidence: CI green on PR #1694 (ci-ok); re-run 2026-11-26 on merged main ff14a97ae (contains f753a8413): tests/unit/test_triage_plan_overlap.py 41 passed

<!-- fr:journal kind=discovery scope=spec id=test-plan-step-2 created=2026-11-26T12:56:51+00:00 -->
### test-plan-step-2 · discovery · Test Plan step 2: ran

Step: pre-merge — CI: `fr triage check` text and `--json` output with overlaps and unread batches, exit 0 (row `plan-overlap-check`).

Evidence: CI green on PR #1694 (ci-ok); re-run 2026-11-26 on merged main ff14a97ae: the fr triage check plan overlap tests in tests/unit/test_triage_check.py, 5 passed (text, --json, exit 0 when unread, when the read raises, and through a real clone)

<!-- fr:journal kind=discovery scope=spec id=test-plan-step-3 created=2026-11-26T12:56:53+00:00 -->
### test-plan-step-3 · discovery · Test Plan step 3: ran

Step: pre-merge — CI: the board model and render show the overlap on both cards and a note per not-compared batch, and `write_board` with a `checkouts` map reads through those clones (row `plan-overlap-board`).

Evidence: CI green on PR #1694 (ci-ok); re-run 2026-11-26 on merged main ff14a97ae: the board overlap tests in test_triage_kanban, test_triage_kanban_render and test_triage_kanban_cmd, 6 passed (both cards, a note per unread batch, write_board checkouts, the driver's checkout map)
