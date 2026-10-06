# Journal: 2026-10-06-archive-followups

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-06T17:20:22+00:00 input=true -->
### operator-brief · discovery · Operator brief (verbatim) — batch archive-followups

/fr-goal Archive does its own follow-ups: price closed sessions, retarget matrix refs, offer issues for open ends

Batch `archive-followups` of derio-net/super-fr: 3 issues, delivered as ONE pull request.

## super-fr#930: fr archive: refresh earlier closeouts' unpriced usage sessions automatically
Every archived usage file carries the close-out's own session unpriced; `fr usage backfill` fixes it by hand.

## super-fr#528: fr archive should retarget matrix refs it invalidates — 60 warnings had accumulated across 12 specs
Archive moves specs but neither archive nor `repair_repo` retargets matrix refs; acceptance check retains an archive-twin warning fallback.
Note: Batch after the super-fr#544 safety work: retarget same-repo refs and regenerate reports only after successful archive. take 10 (#817, OpenCode + GitLab, fr 4.35.0): archive left the matrix levels ref to the plan stale, so fr acceptance check failed after closeout.

## super-fr#458: fr archive: offer to open GitHub issues for open ends the run left behind (journal findings, rework items)
Archive moves journals and runs but does not turn remaining open ends into tracker issues.
Note: Product enhancement, not a broken invariant. Reconsider after the deferred journal path has usage evidence.

## Why these belong together
Wave 9 feature 4: close-outs leave these to fix by hand.

## Delivery rules
- Work on branch `feat/batch-archive-followups`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#930
  Closes derio-net/super-fr#528
  Closes derio-net/super-fr#458
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

<!-- fr:journal kind=decision scope=spec id=q1-refresh-when created=2026-10-06T17:20:22+00:00 -->
### q1-refresh-when · decision · Usage refresh runs when an archive moves anything

Operator chose: only invocations that stage moves refresh; a no-op archive leaves the tree clean.

<!-- fr:journal kind=decision scope=spec id=q2-no-status-nag created=2026-10-06T17:20:22+00:00 -->
### q2-no-status-nag · decision · No fr status reminder for unpriced usage

Operator chose: out of scope; the message points at the next fr archive / fr usage backfill.

<!-- fr:journal kind=decision scope=spec id=q3-retarget-all-moved created=2026-10-06T17:20:22+00:00 -->
### q3-retarget-all-moved · decision · Retarget every path archive moved

Operator chose: specs, journals, plan dirs (and files in them), runs, usage — same-repo only, after a successful archive.

<!-- fr:journal kind=decision scope=spec id=q4-plan-ref-stays-error created=2026-10-06T17:20:22+00:00 -->
### q4-plan-ref-stays-error · decision · Stale plan ref stays an error; twin warning reworded

Operator chose: no plan archive twin; the spec/journal twin warning says a ref survived an archive fr did not perform.

<!-- fr:journal kind=decision scope=spec id=q5-open-ends-findings created=2026-10-06T17:20:22+00:00 -->
### q5-open-ends-findings · decision · Open ends = open + out-of-scope findings

Operator chose: folded state open or out-of-scope in spec/plan/debug journals archive moves; rework origin_items and spec-section heuristics dropped.

<!-- fr:journal kind=decision scope=spec id=q6-flag-else-tty-prompt created=2026-10-06T17:20:22+00:00 -->
### q6-flag-else-tty-prompt · decision · --issues/--no-issues, else TTY prompt, else list only

Operator chose: --issues (all) / --issues ids / --no-issues; no flag → y/N/select prompt on a TTY, list-only non-interactive; tracking none lists only; never blocks the archive.

<!-- fr:journal kind=decision scope=spec id=q7-brief-routes-via-archive created=2026-10-06T17:20:22+00:00 -->
### q7-brief-routes-via-archive · decision · Closeout brief routes filing through fr archive --issues

Operator chose: the brief lists out-of-scope findings and one fr archive --branch <b> --issues <ids> command instead of per-finding manual journal resolve lines.

<!-- fr:journal kind=finding scope=spec id=sr-1 created=2026-10-06T17:27:16+00:00 state=open review_scope=in -->
### sr-1 · finding [open] (reviewer: in scope) · `--issues [IDS]` (an option that is both a flag and takes an optional value) cannot be expressed in the repo's Typer CLI

check: consistency/codebase
target: spec
evidence: spec §C, R9; archive_cmd.py:373-402; typer.Option exposes no flag_value. A bare --issues before the positional plan_dir would take the plan path as its value. Pick a shape Typer supports.

<!-- fr:journal kind=finding scope=spec id=sr-2 created=2026-10-06T17:27:16+00:00 state=open review_scope=in -->
### sr-2 · finding [open] (reviewer: in scope) · Bare finding ids are not unique across the spec, plan and debug journals that one invocation moves

check: consistency/codebase
target: spec
evidence: R8/R9; closeout.py:396-402; journal/model.py:598 (ids are unique per journal). `--issues s1` can name two open ends.

<!-- fr:journal kind=finding scope=spec id=sr-3 created=2026-10-06T17:27:16+00:00 state=open review_scope=in -->
### sr-3 · finding [open] (reviewer: in scope) · Archive lists only the journals it moved in this invocation, so the brief's `--issues <ids>` can be refused and no route to file remains

check: consistency/codebase
target: spec
evidence: R8, R9, R13; archive_cmd.py:282-298 (held spec), :189-191 (a re-run moves nothing). A held spec, a later decision to file, or a re-run leaves brief ids unfileable.

<!-- fr:journal kind=finding scope=spec id=sr-4 created=2026-10-06T17:27:16+00:00 state=open review_scope=in -->
### sr-4 · finding [open] (reviewer: in scope) · The R12 write-back record names a field JournalEntry does not have and omits the fields it requires

check: consistency/codebase
target: spec
evidence: journal/model.py:89-130 (extra=forbid, no `note`; required scope/id/created/title); record/apply.py:367-380.

<!-- fr:journal kind=finding scope=spec id=sr-5 created=2026-10-06T17:27:16+00:00 state=open review_scope=in -->
### sr-5 · finding [open] (reviewer: in scope) · "After the moves succeed" is undefined for partial moves, and a moved plan dir can be left with stale refs

check: consistency/codebase
target: spec
evidence: archive.py:403-405; archive_cmd.py:519-524; :580 vs :585 (owed_moved alone skips _repair_in_passing).

<!-- fr:journal kind=finding scope=spec id=sr-6 created=2026-10-06T17:27:16+00:00 state=open review_scope=in -->
### sr-6 · finding [open] (reviewer: in scope) · The retarget overwrites and stages matrix.yaml and the reports even when the operator has uncommitted edits in them

check: consistency/codebase
target: spec
evidence: §B; archive_cmd.py:263, :310 (the dirty-guard precedent); artifact-versioning rule case 3.

<!-- fr:journal kind=finding scope=spec id=sr-7 created=2026-10-06T17:27:16+00:00 state=open review_scope=in -->
### sr-7 · finding [open] (reviewer: in scope) · The Test Plan is post-merge only and covers none of the testable requirements

check: consistency/codebase
target: spec
evidence: spec Test Plan; R2, R5–R7, R9–R13 are unit-testable.

<!-- fr:journal kind=finding scope=spec id=sr-8 created=2026-10-06T17:27:16+00:00 state=open review_scope=in -->
### sr-8 · finding [open] (reviewer: in scope) · Test Plan expects `fr acceptance check` to be clean of archive warnings, but a stale ref already exists that this design never retargets

check: consistency/codebase
target: spec
evidence: matrix.yaml:335 (2026-09-27-spec-ref-writers spec ref); check.py:121-126.

<!-- fr:journal kind=finding scope=spec id=sr-9 created=2026-10-06T17:27:16+00:00 state=open review_scope=in -->
### sr-9 · finding [open] (reviewer: in scope) · Skill and explainer prose that describes the per-finding manual filing route R13 replaces is not in scope

check: consistency/codebase
target: spec
evidence: plugins/super-fr/skills/fr-goal/SKILL.md:119; docs/explainers/01-fr-goal.md:1025; explainers-currency rule.

<!-- fr:journal kind=finding scope=spec id=sr-10 created=2026-10-06T17:27:16+00:00 state=open review_scope=in -->
### sr-10 · finding [open] (reviewer: in scope) · The move recorder is described in contradictory terms and has two names

check: consistency/codebase
target: spec
evidence: §B vs §A (MoveLog vs MovedPaths; module-level vs not a global); archive.py:403,540,570,615,647.

<!-- fr:journal kind=finding scope=spec id=sr-11 created=2026-10-06T17:27:16+00:00 state=open review_scope=in -->
### sr-11 · finding [open] (reviewer: in scope) · The textual retarget is not anchored to origin/levels positions

check: consistency/codebase
target: spec
evidence: §B; R5; acceptance/model.py:183-208 (notes/scenario/walks are free strings).

<!-- fr:journal kind=finding scope=spec id=sr-12 created=2026-10-06T17:27:16+00:00 state=open review_scope=in -->
### sr-12 · finding [open] (reviewer: in scope) · §C handles `tracking: none` but not a malformed services declaration

check: consistency/codebase
target: spec
evidence: closeout.py:142-151; services/require.py:17-25.

<!-- fr:journal kind=finding scope=spec id=sr-13 created=2026-10-06T17:27:16+00:00 state=open review_scope=in -->
### sr-13 · finding [open] (reviewer: in scope) · The brief's "drop the flag to file none" contradicts R10's interactive prompt

check: consistency/codebase
target: spec
evidence: §C brief vs R10 rule 7.

<!-- fr:journal kind=finding scope=spec id=sr-14 created=2026-10-06T17:27:16+00:00 state=open review_scope=in -->
### sr-14 · finding [open] (reviewer: in scope) · The repo-slug source cites a precedent that does not exist

check: consistency/codebase
target: spec
evidence: fr/closeout.py has no slug resolution; check.py:42 resolve_identity; gitseam.py:174.

<!-- fr:journal kind=review scope=spec id=spec-review-r1 created=2026-10-06T17:27:16+00:00 -->
### spec-review-r1 · review · independent spec review: 14 findings

Findings raised: sr-1, sr-2, sr-3, sr-4, sr-5, sr-6, sr-7, sr-8, sr-9, sr-10, sr-11, sr-12, sr-13, sr-14 (all in scope). Decisions q1–q7 are each honoured, with no contradiction (fr-spec-reviewer).

<!-- fr:journal kind=finding scope=spec id=sr-1-resolved created=2026-10-06T17:27:16+00:00 state=fixed resolves=sr-1 -->
### sr-1-resolved · finding [fixed] · resolves sr-1: `--issues [IDS]` (an option that is both a flag and takes an optional value) cannot be expressed in the repo's Typer CLI

R9/§C: `--issues` now takes a required value (`all` or a comma list of ids); `--no-issues` is a bool; both together is a usage error.

<!-- fr:journal kind=finding scope=spec id=sr-2-resolved created=2026-10-06T17:27:16+00:00 state=fixed resolves=sr-2 -->
### sr-2-resolved · finding [fixed] · resolves sr-2: Bare finding ids are not unique across the spec, plan and debug journals that one invocation moves

Ids are qualified `<scope>/<slug>/<id>` (same token as the R11 marker); a bare id is accepted only when it is unambiguous, otherwise refused.

<!-- fr:journal kind=finding scope=spec id=sr-3-resolved created=2026-10-06T17:27:16+00:00 state=fixed resolves=sr-3 -->
### sr-3-resolved · finding [fixed] · resolves sr-3: Archive lists only the journals it moved in this invocation, so the brief's `--issues <ids>` can be refused and no route to file remains

R9: explicit qids are resolved against their journal wherever it lives, whether or not this invocation moved anything.

<!-- fr:journal kind=finding scope=spec id=sr-4-resolved created=2026-10-06T17:27:16+00:00 state=fixed resolves=sr-4 -->
### sr-4-resolved · finding [fixed] · resolves sr-4: The R12 write-back record names a field JournalEntry does not have and omits the fields it requires

§C Write-back: the builder is extracted from record/apply.py into fr.journal.model.resolution_entry and shared by both writers.

<!-- fr:journal kind=finding scope=spec id=sr-5-resolved created=2026-10-06T17:27:16+00:00 state=fixed resolves=sr-5 -->
### sr-5-resolved · finding [fixed] · resolves sr-5: "After the moves succeed" is undefined for partial moves, and a moved plan dir can be left with stale refs

§0: a contextvar MoveLog fed by _git_mv, and _after_moves in a finally on every exit path. The §2 background sentence is corrected.

<!-- fr:journal kind=finding scope=spec id=sr-6-resolved created=2026-10-06T17:27:16+00:00 state=fixed resolves=sr-6 -->
### sr-6-resolved · finding [fixed] · resolves sr-6: The retarget overwrites and stages matrix.yaml and the reports even when the operator has uncommitted edits in them

R2/R6/§A/§B: paths_dirty guards on the matrix, the reports and each archived usage file.

<!-- fr:journal kind=finding scope=spec id=sr-7-resolved created=2026-10-06T17:27:16+00:00 state=fixed resolves=sr-7 -->
### sr-7-resolved · finding [fixed] · resolves sr-7: The Test Plan is post-merge only and covers none of the testable requirements

The Test Plan now lists unit/CLI checks per requirement group; the post-merge close-out is kept.

<!-- fr:journal kind=finding scope=spec id=sr-8-resolved created=2026-10-06T17:27:16+00:00 state=fixed resolves=sr-8 -->
### sr-8-resolved · finding [fixed] · resolves sr-8: Test Plan expects `fr acceptance check` to be clean of archive warnings, but a stale ref already exists that this design never retargets

Test Plan narrowed to the close-out's own moves; the existing stale ref is retargeted by hand in this PR.

<!-- fr:journal kind=finding scope=spec id=sr-9-resolved created=2026-10-06T17:27:16+00:00 state=fixed resolves=sr-9 -->
### sr-9-resolved · finding [fixed] · resolves sr-9: Skill and explainer prose that describes the per-finding manual filing route R13 replaces is not in scope

R13/§C: the SKILL.md paragraph, both mirrors and the explainer .md/.html are in scope.

<!-- fr:journal kind=finding scope=spec id=sr-10-resolved created=2026-10-06T17:27:16+00:00 state=fixed resolves=sr-10 -->
### sr-10-resolved · finding [fixed] · resolves sr-10: The move recorder is described in contradictory terms and has two names

§0: one `MoveLog` held in a ContextVar the command sets; public signatures are unchanged.

<!-- fr:journal kind=finding scope=spec id=sr-11-resolved created=2026-10-06T17:27:16+00:00 state=fixed resolves=sr-11 -->
### sr-11-resolved · finding [fixed] · resolves sr-11: The textual retarget is not anchored to origin/levels positions

§B: only block-list items directly under `origin:` or `levels.<level>:` are rewritten.

<!-- fr:journal kind=finding scope=spec id=sr-12-resolved created=2026-10-06T17:27:16+00:00 state=fixed resolves=sr-12 -->
### sr-12-resolved · finding [fixed] · resolves sr-12: §C handles `tracking: none` but not a malformed services declaration

R10/§C: a ServicesError means list-only, with the brief's warning.

<!-- fr:journal kind=finding scope=spec id=sr-13-resolved created=2026-10-06T17:27:16+00:00 state=fixed resolves=sr-13 -->
### sr-13-resolved · finding [fixed] · resolves sr-13: The brief's "drop the flag to file none" contradicts R10's interactive prompt

The brief line now says `--no-issues files none`.

<!-- fr:journal kind=finding scope=spec id=sr-14-resolved created=2026-10-06T17:27:16+00:00 state=fixed resolves=sr-14 -->
### sr-14-resolved · finding [fixed] · resolves sr-14: The repo-slug source cites a precedent that does not exist

§C Filing: the slug comes from resolve_identity; its two-segment limit is noted.
