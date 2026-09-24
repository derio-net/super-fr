# Journal: 2026-09-24-fr-goal-scope-proportion-cost

<!-- fr:journal kind=decision scope=spec id=d-scope created=2026-09-24T20:23:35 -->
### d-scope · decision · Scope: #597 §1+§4, #593 opt 0+2

Operator chose A (findings in/out of scope), C (proportionality), D (per-step main-session cost), E (independent spec review). Performance section (#597 §3) and orchestrator model/restart (#597 §2, #593 opt 1) deferred.

<!-- fr:journal kind=decision scope=spec id=d-out-of-scope created=2026-09-24T20:23:36 -->
### d-out-of-scope · decision · Out-of-scope is a new non-blocking fold state

Operator chose a new `out-of-scope` resolution state over autonomous issue filing or classify-at-add.

<!-- fr:journal kind=decision scope=spec id=d-harnesses created=2026-09-24T20:23:36 -->
### d-harnesses · decision · Main-session cost covers Claude Code and OpenCode

Operator chose both harnesses; OpenCode via read-only SQLite reader.

<!-- fr:journal kind=decision scope=spec id=d-spec-reviewer created=2026-09-24T20:23:36 -->
### d-spec-reviewer · decision · Spec review by a new fr-spec-reviewer agent

Operator chose a shipped read-only agent over a generic subagent.

<!-- fr:journal kind=decision scope=spec id=d-plan-files created=2026-09-24T20:23:37 -->
### d-plan-files · decision · Plans gain optional per-phase files/estimate_lines

Operator chose a structured plan field (plan shape change) over prose heuristics.

<!-- fr:journal kind=decision scope=spec id=d-design-approved created=2026-09-24T20:23:37 -->
### d-design-approved · decision · Design approved as presented

Operator approved sections A, C, D, E and cross-cutting in one pass.

<!-- fr:journal kind=finding scope=spec id=sr-f1 created=2026-09-24T20:48:45 state=open -->
### sr-f1 · finding [open] · Journal bump unnecessary: parser ignores unknown tokens; deferred precedent

<!-- fr:journal kind=finding scope=spec id=sr-f1-resolved created=2026-09-24T20:48:45 state=fixed resolves=sr-f1 -->
### sr-f1-resolved · finding [fixed] · resolves sr-f1: Journal bump unnecessary: parser ignores unknown tokens; deferred precedent

Out-of-scope written as state=open + out_of_scope=true; no journal bump.

<!-- fr:journal kind=finding scope=spec id=sr-f2 created=2026-09-24T20:48:46 state=open -->
### sr-f2 · finding [open] · Plan 2->3 is not stamp-only (Literal[2], writers, cncd)

<!-- fr:journal kind=finding scope=spec id=sr-f2-resolved created=2026-09-24T20:48:46 state=fixed resolves=sr-f2 -->
### sr-f2-resolved · finding [fixed] · resolves sr-f2: Plan 2->3 is not stamp-only (Literal[2], writers, cncd)

Follow tier/skeleton precedent: optional omitted fields + fr_version floor; no plan bump.

<!-- fr:journal kind=finding scope=spec id=sr-f3 created=2026-09-24T20:48:47 state=open -->
### sr-f3 · finding [open] · Operator guard not structural: add --resolves bypass; self-attested flag

<!-- fr:journal kind=finding scope=spec id=sr-f3-resolved created=2026-09-24T20:48:47 state=fixed resolves=sr-f3 -->
### sr-f3-resolved · finding [fixed] · resolves sr-f3: Operator guard not structural: add --resolves bypass; self-attested flag

Enforced in the fold/journal check (both paths); Claude Code verifies via operator_answered_since; advisory elsewhere with parity row.

<!-- fr:journal kind=finding scope=spec id=sr-f4 created=2026-09-24T20:48:48 state=open -->
### sr-f4 · finding [open] · reviewer rule is phase-bound; orchestrator exclusion misstated

<!-- fr:journal kind=finding scope=spec id=sr-f4-resolved created=2026-09-24T20:48:48 state=fixed resolves=sr-f4 -->
### sr-f4-resolved · finding [fixed] · resolves sr-f4: reviewer rule is phase-bound; orchestrator exclusion misstated

Flat-step evidence target specified; reviewer = dispatch provenance, per-harness strength + parity row; Test 13 reworded.

<!-- fr:journal kind=finding scope=spec id=sr-f5 created=2026-09-24T20:48:49 state=open -->
### sr-f5 · finding [open] · read_claude_code does not dedupe duplicate-usage records

<!-- fr:journal kind=finding scope=spec id=sr-f5-resolved created=2026-09-24T20:48:49 state=fixed resolves=sr-f5 -->
### sr-f5-resolved · finding [fixed] · resolves sr-f5: read_claude_code does not dedupe duplicate-usage records

Confirmed live (27/40 ids duplicated). Shared dedupe helper for both readers; historical measured not rewritten, labelled in fr run cost.

<!-- fr:journal kind=finding scope=spec id=sr-f6 created=2026-09-24T20:48:50 state=open -->
### sr-f6 · finding [open] · Session source unspecified; resumed runs under-count

<!-- fr:journal kind=finding scope=spec id=sr-f6-resolved created=2026-09-24T20:48:50 state=fixed resolves=sr-f6 -->
### sr-f6-resolved · finding [fixed] · resolves sr-f6: Session source unspecified; resumed runs under-count

Candidate set = Attempt.session values + workspace bindings + current; summed; any unreadable -> nothing.

<!-- fr:journal kind=finding scope=spec id=sr-f7 created=2026-09-24T20:48:50 state=open -->
### sr-f7 · finding [open] · Window boundary precision and completion paths

<!-- fr:journal kind=finding scope=spec id=sr-f7-resolved created=2026-09-24T20:48:51 state=fixed resolves=sr-f7 -->
### sr-f7-resolved · finding [fixed] · resolves sr-f7: Window boundary precision and completion paths

Second-precision truncation rule; written in _complete_step on done (covers group completion); pre-start turns unmeasured.

<!-- fr:journal kind=finding scope=spec id=sr-f8 created=2026-09-24T20:48:51 state=open -->
### sr-f8 · finding [open] · Issue offer is an unlisted touchpoint; spec-scope findings not rendered

<!-- fr:journal kind=finding scope=spec id=sr-f8-resolved created=2026-09-24T20:48:52 state=fixed resolves=sr-f8 -->
### sr-f8-resolved · finding [fixed] · resolves sr-f8: Issue offer is an unlisted touchpoint; spec-scope findings not rendered

Offer rides the merge touchpoint, non-blocking, applied at post-merge close-out; deliver renders both scopes.

<!-- fr:journal kind=finding scope=spec id=sr-f9 created=2026-09-24T20:48:52 state=open -->
### sr-f9 · finding [open] · Parity states/kind wrong

<!-- fr:journal kind=finding scope=spec id=sr-f9-resolved created=2026-09-24T20:48:53 state=fixed resolves=sr-f9 -->
### sr-f9-resolved · finding [fixed] · resolves sr-f9: Parity states/kind wrong

Rows are kind interaction with enforced/partial/advisory/absent states; spec-review-independence row added.

<!-- fr:journal kind=finding scope=spec id=sr-f10 created=2026-09-24T20:48:53 state=open -->
### sr-f10 · finding [open] · Base helper, failure modes, merge-base unspecified

<!-- fr:journal kind=finding scope=spec id=sr-f10-resolved created=2026-09-24T20:48:54 state=fixed resolves=sr-f10 -->
### sr-f10-resolved · finding [fixed] · resolves sr-f10: Base helper, failure modes, merge-base unspecified

Named fr.git.remote_default_ref, None/GitRefusal behaviour, merge-base diff, evidence stores merge-base:sha256.

<!-- fr:journal kind=finding scope=spec id=sr-f11 created=2026-09-24T20:48:54 state=open -->
### sr-f11 · finding [open] · SKILL §2 'Fix every finding' and spec-review tier missing

<!-- fr:journal kind=finding scope=spec id=sr-f11-resolved created=2026-09-24T20:48:54 state=fixed resolves=sr-f11 -->
### sr-f11-resolved · finding [fixed] · resolves sr-f11: SKILL §2 'Fix every finding' and spec-review tier missing

SKILL §2 reworded in scope; tier: standard on manifest step; allowlist generalised only if hook requires it.

<!-- fr:journal kind=finding scope=spec id=sr-f12 created=2026-09-24T20:48:55 state=open -->
### sr-f12 · finding [open] · Reviewer tag not persisted; silent reclassification

<!-- fr:journal kind=finding scope=spec id=sr-f12-resolved created=2026-09-24T20:48:55 state=fixed resolves=sr-f12 -->
### sr-f12-resolved · finding [fixed] · resolves sr-f12: Reviewer tag not persisted; silent reclassification

review_scope token on findings; render flags reclassification.

<!-- fr:journal kind=review scope=spec id=sr-review-1 created=2026-09-24T20:48:56 -->
### sr-review-1 · review · Independent spec review (Explore subagent), 12 findings, all in-scope, all fixed

Reviewer: dispatched read-only subagent (not the author). Findings sr-f1..sr-f12; f1, f2, f4, f5 verified by the orchestrator against code/transcript before fixing.
