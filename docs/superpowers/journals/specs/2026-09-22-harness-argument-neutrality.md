# Journal: 2026-09-22-harness-argument-neutrality

<!-- fr:journal kind=decision scope=spec id=q1-argument-vocabulary created=2026-09-22T13:45:22 -->
### q1-argument-vocabulary · decision · Operator: shared ARGUMENT_VOCABULARY in fr.harness, extra_tools removed

AskUserQuestion 2026-09-22: harness-specific ARGUMENTS get a closed, harness-keyed, regex vocabulary beside TOOL_VOCABULARY, scanned by scan_prose on every surface; the test-local extra_tools escape hatch from #532 is removed.

<!-- fr:journal kind=decision scope=spec id=q2-rules-in-scope created=2026-09-22T13:45:22 -->
### q2-rules-in-scope · decision · Operator: rules are scanned too

Canonical rules plus both rule mirrors (.opencode/instructions, .hermes/SOUL.d) and the repo-local .claude/rules; carve-out and other Claude-only rule prose scoped as Harness clauses; the hand-maintained .claude/rules/fr-isolation-required.md mirror updated to match.

<!-- fr:journal kind=decision scope=spec id=q3-negation-governs created=2026-09-22T13:45:23 -->
### q3-negation-governs · decision · Operator: #420 description check requires the negation to govern the phrase

never/without/not must precede the second-worktree phrase within the same clause (bounded window); the adversarial review's four wrong descriptions become must-fail cases.

<!-- fr:journal kind=decision scope=spec id=q4-smoke-first created=2026-09-22T13:45:23 -->
### q4-smoke-first · decision · Operator: separate OpenCode smoke before the paid run

Post-merge Test Plan: confirm the OpenCode node runs the released version, then dispatch the executor on a toy phase whose suite exceeds 2 minutes and confirm it is not killed and nothing is left running at handback — before the paid verification run.

<!-- fr:journal kind=decision scope=spec id=d-headings-exempt created=2026-09-22T13:45:24 -->
### d-headings-exempt · decision · Agent decision (within approved scope): Markdown headings are not scanned

Measured before designing: a rules scan flags '## Plan Skill Override', '# Worktree Skill Override', '## fr-* Skill Overview', '### 1. Agent sessions…' — English words in headings, not tool mentions. A heading states a topic, never an instruction, so heading lines are skipped. Skills were unaffected only because none had such headings.

<!-- fr:journal kind=review scope=spec id=e2dccbb99cdb created=2026-09-22T13:46:39 -->
### e2dccbb99cdb · review · Spec review vs codebase

Checked every named symbol/test/file exists as described. Findings fixed in the spec: (F1) AGENTS.md's actual skills-only wording is at lines 93 and 343-344, not the phrase first cited; (F2) extra_tools has three unit tests in test_harness_vocabulary.py besides the agent tripwire — they are rewritten, not just the one caller. Q&A answers q1-q4 and d-headings-exempt all reflected in §2-§6.
