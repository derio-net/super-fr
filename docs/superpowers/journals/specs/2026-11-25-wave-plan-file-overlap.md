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
