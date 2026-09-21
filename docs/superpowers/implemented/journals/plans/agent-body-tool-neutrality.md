# Journal: agent-body-tool-neutrality

<!-- fr:journal kind=discovery scope=plan id=98facedf3458 created=2026-09-21T16:43:12 phase=1 -->
### 98facedf3458 · discovery · no-refactor-because P1.T1 (phase 1)

Small targeted edit; nothing to clean up after green.

<!-- fr:journal kind=discovery scope=plan id=76fe2c18afa1 created=2026-09-21T16:43:12 phase=1 -->
### 76fe2c18afa1 · discovery · no-refactor-because P1.T2 (phase 1)

Small targeted edit; nothing to clean up after green.

<!-- fr:journal kind=discovery scope=plan id=9171f9ab2894 created=2026-09-21T16:43:13 phase=1 -->
### 9171f9ab2894 · discovery · no-refactor-because P1.T3 (phase 1)

Small targeted edit; nothing to clean up after green.

<!-- fr:journal kind=discovery scope=plan id=8d211dfd6339 created=2026-09-21T16:47:53 phase=1 -->
### 8d211dfd6339 · discovery · Pre-fix scan of the agent trees: 16 hits, 4 canonical (phase 1)

Widening the tripwire to plugins/super-fr/agents/*.md and .opencode/agent/*.md with extra_tools={'isolation: "worktree"': claude-code} went red on 16 mentions: canonical fr-phase-executor.md lines 6 (frontmatter description), 27 and 119 (the flag) and 33 (Agent), each replicated across all four generated .opencode/agent files. That confirms the spec's §1 claim exactly — the mirror test guarantees Claude-only prose reaches every OpenCode agent file — and shows the frontmatter description is a real leak surface no clause can cover, which is why it had to be reworded rather than scoped.

<!-- fr:journal kind=discovery scope=plan id=b4946151143f created=2026-09-21T16:47:53 phase=1 -->
### b4946151143f · discovery · The matrix row already cited both test files, so the evidence update is notes-only (phase 1)

harness-tool-neutrality was already status: ci with levels.unit naming tests/unit/test_harness_vocabulary.py and tests/unit/test_tripwire_skill_tool_neutrality.py — the two files this phase extended. No new test file was created, so set-status re-passed the existing refs and carries the widening in --notes instead of inventing a level ref. Its 'acceptance' sentence still reads 'No skill names...' though the scan now also covers agent bodies; left as-is to keep the diff minimal, and worth a wording pass if the row is ever touched again.

<!-- fr:journal kind=finding scope=plan id=940066a17abd created=2026-09-21T16:54:47 phase=1 state=fixed -->
### 940066a17abd · finding [fixed] · SPEC ASSUMPTION WRONG: an existing #420 tripwire demanded the flag verbatim in the very description the spec neutralises (phase 1)

The spec (§2.1) says the frontmatter description must be reworded neutrally because it cannot sit inside a clause. It did not know that tests/unit/test_tripwire_phase_executor_worktree.py::test_agent_description_carries_the_constraint asserts the OPPOSITE: 'isolation: "worktree"' in description, verbatim, with a negation in the same sentence — deliberately strict, its docstring rejecting looser checks. The two are unsatisfiable together: a YAML folded description cannot carry a '**Harness — ...:**' clause without shipping bold markdown in the blurb every harness displays when choosing an agent. Resolved in favour of the spec: the description is neutral ('Dispatch it INTO that workspace, never into a second worktree'), and the #420 assertion was widened to accept either the literal flag or that neutral phrasing, via a _rules_out_a_second_worktree predicate requiring the naming and the negation in ONE sentence. Not a #420 regression, and the proof is two sibling tests in the same file: fr-goal's dispatch section still names the flag verbatim inside its own scoped **Harness — dispatch:** clause (test_fr_goal_dispatch_section_says_without_the_flag) and the refusal hook is still registered (test_hook_is_registered_for_the_agent_tool). Widening an assertion is only safe if it still rejects the old prose, so test_a_merely_descriptive_description_does_not_count exercises the predicate on the pre-fix wording ('inside an already-active fr-isolation workspace') and requires it to fail.

<!-- fr:journal kind=review scope=plan id=713c7b8d4b35 created=2026-09-21T17:02:17 phase=1 -->
### 713c7b8d4b35 · review · Phase 1 review vs spec+plan+code (phase 1)

Raised: (a) #420 description test had to be widened — accepted: flag still named verbatim in fr-goal's scoped clause and hook still registered, non-vacuity test added; (b) matrix acceptance sentence still says 'No skill' — cosmetic, left. No open findings.
