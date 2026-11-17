<!-- fr:journal-schema=4 -->
# Journal: 2026-11-17-batch-acceptance-edits

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-17T09:30:05+00:00 input=true -->
### operator-brief · discovery · The operator's brief for batch acceptance-edits, verbatim

/fr-goal Acceptance edits and artifact adoption

Batch `acceptance-edits` of derio-net/super-fr: 6 issues, delivered as ONE pull request.

## super-fr#1439: acceptance amend --op reword --origin: an origin-only correction bakes a pending reword into the row's definition
Still live: `commands/acceptance_cmd.py:1023-1028` fills `acceptance` from `effective(root)` for an origin-only reword. A pending reword's amended statement is therefore baked into the row's base definition. The fold result is unchanged, but the fragment states the amendment twice.

## super-fr#1394: Restore acceptance row notes replaced by the sweep's link commands
Data cleanup, still owed: 33 rows across `docs/acceptance/features/*.yaml` still carry a bare `notes: tracked by derio-net/super-fr#N` (e.g. `2026-10-11-debt-engine.yaml:110`). The command itself was fixed in #1387 (link-only keeps the note). The replaced texts must be recovered from the history of `docs/acceptance/matrix.yaml`, from before the fragment split, and restored with `fr acceptance amend`/`set-status`.
Note: Only rows whose old note was more than the walk-owed boilerplate need it.

## super-fr#1390: Non-UTF-8 spec bytes raise UnicodeDecodeError in the repair
`_applies` in `packages/fr/src/fr/artifacts/spec_test_plan_heading.py:79-80` uses `path.read_text()`, and `_fn` at `:84` uses `.decode("utf-8")`. Both raise `UnicodeDecodeError` on non-UTF-8 bytes. The failure is loud and nothing is corrupted. Still live.
Note: `matrix_anchors.py:95` `_applies` has the same pattern. Check how the gate reports a raising `applies` at the same time.

## super-fr#1154: pre-existing _committable runs its own git check-ignore instead of a shared helper
Still live: `_committable` (`commands/acceptance_cmd.py:1413-1428`) runs its own `check-ignore`. Similar ad-hoc calls exist in `artifacts/commit.py:505`, `triage/gitseam.py:905`, `isolation/scaffold.py:664` and `run/visual.py:243`.
Note: Refactor only, low value.

## super-fr#1219: migrate artifacts --adopt: run id is <date>-<branch>, so bulk adoption on one branch adopts only the first plan
Still live: `packages/fr/src/fr/run/adopt.py:864` sets `resolved_branch = branch or current_branch(repo_root)`, and :921 derives the id with `derive_run_id(resolved_branch)`. Every plan adopted on one branch therefore gets the same `<date>-<branch>` id, and every plan after the first is refused at :929.
Note: Same binding as #1191 item 4.

## super-fr#1461: fr migrate artifacts does not rename a <slug>-design acceptance fragment to the one spelling
Fragments created before #1451 are `<slug>-design.yaml` with `feature: <slug>-design`; writers since create `<slug>.yaml`, so a feature can end up with two fragments. Wanted: a `Repair` on `acceptance-fragment` renaming it, merging or refusing by row id.
Note: Repair under the artifact-versioning rule. Batch acceptance-edits.

## Why these belong together
#1394 must restore the 33 overwritten row notes, not only stop new damage (origins: fixes ship without repairing what older versions wrote).

## Delivery rules
- Work on branch `feat/batch-acceptance-edits`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#1439
  Closes derio-net/super-fr#1394
  Closes derio-net/super-fr#1390
  Closes derio-net/super-fr#1154
  Closes derio-net/super-fr#1219
  Closes derio-net/super-fr#1461
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

Never add the `approved-fr` label: it is the operator's approval to merge, and fr voids it on your next push.

<!-- fr:journal kind=decision scope=spec id=d1-adopt-id created=2026-11-17T09:30:05+00:00 decided_by=operator -->
### d1-adopt-id · decision · Adopted runs are named after their plan folder's slug

Every adoption given no --run-id (single fr run adopt and bulk --adopt) takes the plan folder's slug as its run id. Operator answer, round 1 question 1 (recommended option).

<!-- fr:journal kind=decision scope=spec id=d2-adopt-branch created=2026-11-17T09:30:05+00:00 decided_by=operator -->
### d2-adopt-branch · decision · Adoption keeps the checkout's branch, warning on the default branch

The run's branch stays the checked-out branch; when that is the default branch, adoption says so once per run and names --branch. Operator answer, round 1 question 2 (recommended option).

<!-- fr:journal kind=decision scope=spec id=d3-design-fragment-merge created=2026-11-17T09:30:05+00:00 decided_by=operator -->
### d3-design-fragment-merge · decision · Both spellings present — merge, refuse on an id held differently

The -design fragment repair merges into <slug>.yaml, keeps an identical entry once, and on an id held differently writes nothing and fails the artifact naming the id. Operator answer, round 1 question 3 (recommended option).

<!-- fr:journal kind=decision scope=spec id=d4-note-text created=2026-11-17T09:30:05+00:00 decided_by=operator -->
### d4-note-text · decision · A restored note is the old note plus "; tracked by <tracker>"

The 17 restored notes are the pre-sweep note followed by "; tracked by derio-net/super-fr#N". Operator answer, round 1 question 4 (the non-recommended option, chosen over the verbatim restore).

<!-- fr:journal kind=decision scope=spec id=d5-non-utf8 created=2026-11-17T09:30:05+00:00 decided_by=operator -->
### d5-non-utf8 · decision · Undecodable artifacts keep refusing, with a plainly named reason

Both repairs raise "<path> is not UTF-8 text (byte 0x.. at offset N)"; the gate and fr migrate artifacts print it instead of the codec error. Operator answer, round 1 question 5 (recommended option).

<!-- fr:journal kind=decision scope=spec id=d6-helper-scope created=2026-11-17T09:30:05+00:00 decided_by=operator -->
### d6-helper-scope · decision · One check-ignore helper for every site but triage's git seam

ignored_paths and is_ignored in one module; acceptance_cmd, artifacts/commit, isolation/scaffold and run/visual call it; triage/gitseam keeps its own call. Operator answer, round 1 question 6 (recommended option).

<!-- fr:journal kind=decision scope=spec id=d7-verification created=2026-11-17T09:30:05+00:00 decided_by=operator -->
### d7-verification · decision · CI tests verify every row; no walk, gate developer, no Test Plan

Operator answer, round 1 question 7 (recommended option).

<!-- fr:journal kind=finding scope=spec id=s-r1 created=2026-11-17T09:38:26+00:00 state=open review_scope=in -->
### s-r1 · finding [open] (reviewer: in scope) · R5/R7 cannot hold: the spec kind's stamp read decodes the file before any repair predicate runs

`read_verbatim` (registry.py:148) raises UnicodeDecodeError in `_chain_for` before `_applies` runs, so routing only the repairs changes nothing the operator sees. Route `read_verbatim` through the named decode and use one formatter at the runner's seven `type(e).__name__` sites.

<!-- fr:journal kind=finding scope=spec id=s-r2 created=2026-11-17T09:38:26+00:00 state=open review_scope=in -->
### s-r2 · finding [open] (reviewer: in scope) · R6 targets the matrix_anchors repair, which is not registered; the live non-UTF-8 matrix path is the retiring split hop

matrix_anchors.py:123-126: not registered since the matrix kind retired. A non-UTF-8 matrix.yaml fails in the stamp read and the 5 -> 6 split hop (`conversions`, matrix_fragments.py:258/:270). Point R6 there and test through run_migrations.

<!-- fr:journal kind=finding scope=spec id=s-r3 created=2026-11-17T09:38:26+00:00 state=open review_scope=in -->
### s-r3 · finding [open] (reviewer: in scope) · The -design fragment repair trips R16's merged-row-edit check, which is keyed by fragment path

amend.py:127-189: `merged_row_edits` iterates the default ref's fragments by path; after the rename every merged row of `<slug>-design.yaml` reads as removed, so check/deliver refuse, on consumer branches and in main's CI. The R16 check must read a merged `-design` fragment as its `<slug>.yaml` spelling.

<!-- fr:journal kind=finding scope=spec id=s-r4 created=2026-11-17T09:38:26+00:00 state=open review_scope=in -->
### s-r4 · finding [open] (reviewer: in scope) · Fragment repair: declare the merge target as a companion; removal staging already works

Declare `<slug>.yaml` as a companion so the uncommitted-changes veto holds it (runner.py:564-595); the deleted `-design` path is the action's own path, which changed_paths includes and commit_paths stages (commit.py:997-1007, :1039): no new runner support.

<!-- fr:journal kind=finding scope=spec id=s-r5 created=2026-11-17T09:38:26+00:00 state=open review_scope=in -->
### s-r5 · finding [open] (reviewer: in scope) · The `origin_only` flag on AmendmentItem breaks every amendment and changes the record shape

`model_dump(exclude_none=True)` would carry `origin_only=False` into the closed-world Amendment for every item, and a record entry could set it (a shape change). Fill from the row's own definition in its pending fragment instead; no model change.

<!-- fr:journal kind=finding scope=spec id=s-r6 created=2026-11-17T09:38:26+00:00 state=open review_scope=in -->
### s-r6 · finding [open] (reviewer: in scope) · Default-branch warning compares `main` with `origin/main`, so it never fires

`default_ref_name`/`remote_default_ref` return `origin/main`; strip the remote prefix, read `fr.git.remote_default_ref` directly, and state the no-remote / GitRefusal case (no warning).

<!-- fr:journal kind=finding scope=spec id=s-r7 created=2026-11-17T09:38:26+00:00 state=open review_scope=in -->
### s-r7 · finding [open] (reviewer: in scope) · R8's shared check-ignore helper has no error contract

The four sites differ on exit 128, missing git and output parsing (whitespace split, quoted non-ASCII). Specify the error contract, use -z, and pin each site's error behaviour in a test.

<!-- fr:journal kind=finding scope=spec id=s-r8 created=2026-11-17T09:38:26+00:00 state=open review_scope=in -->
### s-r8 · finding [open] (reviewer: in scope) · Spec-slug run ids collide with the later plan-slug id of the same feature

A spec-only adoption named after the spec stem takes the id the plan's later adoption needs, and `--supersede` cannot match it (it keys on emitted.plan, adopt.py:879-898).

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-17T09:38:26+00:00 -->
### spec-review-1 · review · independent spec review: 8 findings

findings: s-r1, s-r2, s-r3, s-r4, s-r5, s-r6, s-r7, s-r8 (all in scope). Decisions d1-d7 each honoured; no contradiction found. Every cited file:line verified by the reviewer; the orchestrator re-checked s-r1 (registry.py:148), s-r2 (matrix_anchors.py:123-126), s-r3 (amend.py:127-160) and s-r6 (git.py:181) before fixing.

<!-- fr:journal kind=lens scope=spec id=lens-errors-1 created=2026-11-17T09:38:26+00:00 lens=errors step=spec-review -->
### lens-errors-1 · lens · The change rewrites failure reporting (non-UTF-8 refusals, the runner's formatter) and the check-ignore helper's fail-toward behaviour at four sites

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-17T09:38:26+00:00 lens=tests step=spec-review -->
### lens-tests-1 · lens · Fold equality and the merged-row check need fixtures holding a merged -design fragment on a default ref, which unit fixtures easily skip

<!-- fr:journal kind=finding scope=spec id=s-r1-resolved created=2026-11-17T09:38:26+00:00 state=fixed resolves=s-r1 -->
### s-r1-resolved · finding [fixed] · resolves s-r1: R5/R7 cannot hold: the spec kind's stamp read decodes the file before any repair predicate runs

R5/R7 now cover the stamp read; design C routes read_verbatim through the named decode and adds one runner formatter for all seven sites.

<!-- fr:journal kind=finding scope=spec id=s-r2-resolved created=2026-11-17T09:38:26+00:00 state=fixed resolves=s-r2 -->
### s-r2-resolved · finding [fixed] · resolves s-r2: R6 targets the matrix_anchors repair, which is not registered; the live non-UTF-8 matrix path is the retiring split hop

R6 now names the matrix stamp read and the retiring split hop (conversions included); design C routes those reads through the named decode.

<!-- fr:journal kind=finding scope=spec id=s-r3-resolved created=2026-11-17T09:38:26+00:00 state=fixed resolves=s-r3 -->
### s-r3-resolved · finding [fixed] · resolves s-r3: The -design fragment repair trips R16's merged-row-edit check, which is keyed by fragment path

Added R17; design F keys merged_row_edits/outside_merged_row_edits by the one spelling, merging a tip's -design fragment by the repair's rule.

<!-- fr:journal kind=finding scope=spec id=s-r4-resolved created=2026-11-17T09:38:26+00:00 state=fixed resolves=s-r4 -->
### s-r4-resolved · finding [fixed] · resolves s-r4: Fragment repair: declare the merge target as a companion; removal staging already works

Added R16 and the companions declaration; design F states removal staging needs no runner change and a test pins it.

<!-- fr:journal kind=finding scope=spec id=s-r5-resolved created=2026-11-17T09:38:26+00:00 state=fixed resolves=s-r5 -->
### s-r5-resolved · finding [fixed] · resolves s-r5: The `origin_only` flag on AmendmentItem breaks every amendment and changes the record shape

Design A now fills from the row's own pending definition; no model or shape change.

<!-- fr:journal kind=finding scope=spec id=s-r6-resolved created=2026-11-17T09:38:26+00:00 state=fixed resolves=s-r6 -->
### s-r6-resolved · finding [fixed] · resolves s-r6: Default-branch warning compares `main` with `origin/main`, so it never fires

R12 and design E strip the remote prefix, read fr.git.remote_default_ref directly, and warn nothing without a nameable default ref.

<!-- fr:journal kind=finding scope=spec id=s-r7-resolved created=2026-11-17T09:38:26+00:00 state=fixed resolves=s-r7 -->
### s-r7-resolved · finding [fixed] · resolves s-r7: R8's shared check-ignore helper has no error contract

R8 and design D give the error contract (-z, exit 0/1 answers, empty set / False otherwise) and pin each site's behaviour in a test.

<!-- fr:journal kind=finding scope=spec id=s-r8-resolved created=2026-11-17T09:38:26+00:00 state=fixed resolves=s-r8 -->
### s-r8-resolved · finding [fixed] · resolves s-r8: Spec-slug run ids collide with the later plan-slug id of the same feature

R9 and design E keep the branch-derived id for spec-only adoption, so it never takes a plan-slug id.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-17T09:38:29+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  acceptance-amend-origin-only-keeps-statement: none
  adopt-default-branch-warning: none
  adopt-run-id-from-plan-slug: none
  fragment-design-spelling-repair: none
  spec-repairs-name-undecodable-files: none
row_kinds:
  acceptance-amend-origin-only-keeps-statement: none
  adopt-default-branch-warning: none
  adopt-run-id-from-plan-slug: none
  fragment-design-spelling-repair: none
  spec-repairs-name-undecodable-files: none
run_gate: developer
run_kind: candidate
```

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-17-batch-acceptance-edits-p2 created=2026-11-17T09:40:29+00:00 -->
### phase-split-2026-11-17-batch-acceptance-edits-p2 · decision · ask: phase 2 serves its own asks (#1390, #1154, #1219), a separate subsystem (artifacts runner, git, run adoption)

<!-- fr:journal kind=decision scope=spec id=tier-2026-11-17-batch-acceptance-edits-p1 created=2026-11-17T09:40:33+00:00 -->
### tier-2026-11-17-batch-acceptance-edits-p1 · decision · hard: phase 1 changes the merged-row check (R16 of repo-feature-settings) every fr acceptance check and deliver rely on

<!-- fr:journal kind=decision scope=spec id=d8-restore-scope created=2026-11-17T12:44:18+00:00 narrows=derio-net/super-fr#1394 decided_by=operator -->
### d8-restore-scope · decision · #1394 restores 12 of 17 rows: the 5 later walked keep their walk notes

Recovery first read fragment row definitions, not the fold; 9 of the 17 rows were re-noted on 2026-11-14. The operator chose: splice the old text in before the tracker on the 4 walk-owed rows, keep the 5 walked rows' walk notes (their walk evidence supersedes the pre-sweep text). 8 bare rows restored by phase 1, 4 by the orchestrator.

<!-- fr:journal kind=decision scope=spec id=exit-change-1 created=2026-11-17T14:31:26+00:00 -->
### exit-change-1 · decision · exit change: the run -> strategy none

Operator decision d7 (round 1, question 7): CI tests verify every row, no walk; the spec named each row none but omitted the run-level line, so the shape's candidate default applied

before: kinds ['candidate', 'none'], gates ['developer']
after: kinds ['none'], gates ['developer']
lowered with an operator answer: the run: kind `candidate` -> `none` waits for less

```yaml
answered_by: operator
lowered:
- run:kind
```
