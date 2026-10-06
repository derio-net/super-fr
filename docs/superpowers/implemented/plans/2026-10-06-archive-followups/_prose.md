# Archive does its own follow-ups

Batch `archive-followups` (super-fr#930, #528, #458). Spec:
`docs/superpowers/specs/2026-10-06-archive-followups-design.md`.

Phase 1 is the skeleton. It adds the move log and the `_after_moves` trigger
on every entry mode, and uses that hook for the usage refresh (#930). Phase 2
adds the matrix retarget (#528) on the same hook. Phase 3 adds open-end filing
(#458) and the closeout brief change, plus the skill and explainer prose.
Phases 2 and 3 each depend only on phase 1, but they run serially in the one
workspace.
