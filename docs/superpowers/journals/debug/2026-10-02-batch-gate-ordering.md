# Journal: 2026-10-02-batch-gate-ordering

<!-- fr:journal kind=hypothesis scope=debug id=h1-one-root-cause created=2026-10-02T18:03:56+00:00 -->
### h1-one-root-cause · hypothesis · Batch premise: one ordering defect between a step and the record it needs

The batch was grouped as one root cause (a step consuming a record before it exists). Tested by tracing each member's mechanism in code.

<!-- fr:journal kind=ruled-out scope=debug id=h1-verdict created=2026-10-02T18:03:56+00:00 -->
### h1-verdict · ruled-out · Ruled out: the three members have three distinct mechanisms

#761: fr-brainstorming SKILL.md §0 never runs `fr run advance` before questions; and `question_rounds_refusal` (run_cmd.py:1061) caps rounds at 2 for every run on the fr-goal manifest, which standalone one-question-per-turn brainstorming cannot satisfy — a design decision, as the issue's own comment says.
#699: step records are transient (deleted by the resolve that applies them, since #628 on 2026-09-26, the day of #694). By spec-review the brainstorm record is gone BY DESIGN; its decisions live in the spec journal, which fr-spec-reviewer.md now names as its input. No ordering defect remains in code; at most a prose clarification.
#768: _proportionality_witness (run_cmd.py:1938) calls run_report(..., base=None) with no fallback and `fr run resolve` has no --base; _verified_evidence (run_cmd.py:1808) runs derived witnesses serially, each raising Exit(2). The requirement-rows witness the issue names was removed in 5.0.0 (#851); visual (and findings) still sit behind the first refusal.

<!-- fr:journal kind=decision scope=debug id=d1-operator created=2026-10-02T18:12:29+00:00 -->
### d1-operator · decision · Operator: three fixes, one PR; #761 records the driver; #768 uses the isolation base ref; #699 clarify + close

Asked after h1-verdict. #761: the cursor records who drives it; standalone brainstorm gates need >=1 answered question since the gate opened, no round cap; skill advances right after start. #768: proportionality base falls back to the isolation-recorded start ref, then the local default branch; every derived witness evaluated, refusals reported together. #699: brief + reviewer prose state the brainstorm record is not an input.

<!-- fr:journal kind=root-cause scope=debug id=rc-768 created=2026-10-02T18:16:59+00:00 -->
### rc-768 · root-cause · #768: the proportionality witness had no base but the remote default, and derived witnesses exited at the first refusal

_proportionality_witness called run_report(base=None); with no remote default branch it refused, and `fr run resolve` has no --base. _verified_evidence ran derived witnesses (proportionality, single-phase, visual, findings) serially, each raising Exit(2), so later ones were never evaluated.

<!-- fr:journal kind=finding scope=debug id=fix-768 created=2026-10-02T18:17:00+00:00 state=fixed -->
### fix-768 · finding [fixed] · #768 fixed: base fallback chain + all derived refusals together

IsolationState.base_sha records the commit a cold-start up cut the branch from (carried across resume). _proportionality_base: remote default -> isolation start commit -> local main/master (never the current branch), printing which base was used. _verified_evidence evaluates every derived witness and refuses once with all failures. Tests: test_run_evidence.py::test_deliver_without_a_remote_*, ::test_every_derived_witness_is_evaluated_and_every_refusal_reported, ::test_deliver_with_no_determinable_base_is_refused_naming_it; test_isolation_hostworktree.py::test_cold_start_up_records_the_start_commit.

<!-- fr:journal kind=root-cause scope=debug id=rc-699 created=2026-10-02T18:18:18+00:00 -->
### rc-699 · root-cause · #699: the reviewer treated a transient step record as an input

Step records are transient (#628, the day of #694): brainstorm's is applied to the spec journal and deleted by the resolve that applies it, and spec-review cannot open before that (needs: [spec]). Its decisions are the spec journal's decision entries. Nothing told the reviewer that no record is an input, so it filed the absence as finding s5. The dispatch brief the reviewer actually sees is the orchestrator's prompt, written from fr-goal §2, so the contract lives there and in the agent's Inputs section.

<!-- fr:journal kind=finding scope=debug id=fix-699 created=2026-10-02T18:18:19+00:00 state=fixed -->
### fix-699 · finding [fixed] · #699 fixed: reviewer and fr-goal §2 say no step record is an input

fr-spec-reviewer.md Inputs and fr-goal SKILL.md spec-review paragraph (plus OpenCode/Hermes mirrors). Pinned by tests/unit/test_spec_reviewer_inputs.py.
