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
