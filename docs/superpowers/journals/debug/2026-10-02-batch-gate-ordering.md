# Journal: 2026-10-02-batch-gate-ordering

<!-- fr:journal kind=hypothesis scope=debug id=h1-one-root-cause created=2026-10-02T18:03:56+00:00 -->
### h1-one-root-cause · hypothesis · Batch premise: one ordering defect between a step and the record it needs

The batch was grouped as one root cause (a step consuming a record before it exists). Tested by tracing each member's mechanism in code.

<!-- fr:journal kind=ruled-out scope=debug id=h1-verdict created=2026-10-02T18:03:56+00:00 -->
### h1-verdict · ruled-out · Ruled out: the three members have three distinct mechanisms

#761: fr-brainstorming SKILL.md §0 never runs `fr run advance` before questions; and `question_rounds_refusal` (run_cmd.py:1061) caps rounds at 2 for every run on the fr-goal manifest, which standalone one-question-per-turn brainstorming cannot satisfy — a design decision, as the issue's own comment says.
#699: step records are transient (deleted by the resolve that applies them, since #628 on 2026-09-26, the day of #694). By spec-review the brainstorm record is gone BY DESIGN; its decisions live in the spec journal, which fr-spec-reviewer.md now names as its input. No ordering defect remains in code; at most a prose clarification.
#768: _proportionality_witness (run_cmd.py:1938) calls run_report(..., base=None) with no fallback and `fr run resolve` has no --base; _verified_evidence (run_cmd.py:1808) runs derived witnesses serially, each raising Exit(2). The requirement-rows witness the issue names was removed in 5.0.0 (#851); visual (and findings) still sit behind the first refusal.
