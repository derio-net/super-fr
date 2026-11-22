# Merge-train truth — implementation plan

Spec: `docs/superpowers/specs/2026-11-19-batch-train-truth-design.md` (R1–R24).

Four agentic phases, one per independently reviewable ask:

1. **The pass boundary** (R1–R10), the skeleton and the riskiest change: every `_fail` inside the
   driver's pass becomes a typed refusal or a transient failure, decided at one boundary around the
   whole loop iteration; the driver record and the failure ledger; `fr triage drive failures`.
   `hard`: it changes the error path every driver caller relies on.
2. **The supervisor, `drive status` and the activity log** (R11–R14, R22–R23): process lifetime,
   built on phase 1's record and ledger.
3. **Red and conflicting drafts** (R15–R19): the merge-train walks and the conflict probe, plus
   the one-fetch fix that sits in the same reader path. Independent of phase 2.
4. **The small fixes and the docs** (R20, R21, R24): the label-swap docstring and test, cancel
   without a clone, and the skill/explainer pages describing all of the above (last, so the docs
   describe what landed), with the generated mirrors.

TDD throughout: each task is red → green (→ refactor where named). Tests use fakes and fake
clocks; the supervisor's process tests use real child processes with bounded polling.
