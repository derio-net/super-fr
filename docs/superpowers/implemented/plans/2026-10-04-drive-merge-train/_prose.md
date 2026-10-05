# Drive merge train: implementation plan

This plan has one agentic phase, which changes three things:

- The pure pass (`drive_pass`) works out one train per repo. It emits merge actions only for the head and for the green members after it.
- The executor (`_Driver`) stops a repo's train at the first head that does not merge, and answers each remaining member `queued`.
- Each pass prints one train line per repo, and the summary counts the queued PRs.
- `batch_merge` gains `HeadMovedError`, a `MergeStopError` subclass, so a moved head stops the train while a refusal is stepped over.
- The fr-triage skill's description of the driver states the train; both mirrors are regenerated.

The train's order is wave, then `order`, then id. That order does not change when a member leaves, unlike `merge_order` (review spr-order-unstable).

Spec: `docs/superpowers/specs/2026-10-04-drive-merge-train-design.md`. `merge_ready`'s outcomes, `_land` and `fr triage batch merge` keep their behaviour (spec §D).
