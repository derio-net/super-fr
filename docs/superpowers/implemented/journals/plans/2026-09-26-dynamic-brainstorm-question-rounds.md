# Journal: 2026-09-26-dynamic-brainstorm-question-rounds

<!-- fr:journal kind=decision scope=plan id=plan-three-phases created=2026-09-26T12:45:07 -->
### plan-three-phases · decision · Three phases: record v2 skeleton -> gate -> contract prose

Phase 1 is the walking skeleton (record kind bump, dogfooded via fr migrate artifacts on this run's own live records so later phases resolve on v2). Gate before prose so the prose never promises a verification that does not exist.

<!-- fr:journal kind=discovery scope=plan id=record-fixtures-hardcoded-schema-version created=2026-09-26T13:03:32 phase=1 -->
### record-fixtures-hardcoded-schema-version · discovery · Several test fixtures hardcoded record schema_version: 1, breaking on the v2 bump (phase 1)

Bumping RECORD_SCHEMA_VERSION broke three fixtures that build a record body from scratch rather than through render_template: tests/unit/record_support.py's implement_record, test_record_apply.py's _review_record, and test_validate_artifacts.py's GOOD_RECORD, plus test_record_schema.py's own SPEC_EXAMPLE and its schema_version-refused-with-a-named-needle case. All now reference the live fr.record.model.RECORD_SCHEMA_VERSION constant instead of the literal 1, the same fix record/template.py needed. Worth remembering for phase 2/3 and any future record-shape bump: grep for `"schema_version": 1` / `schema_version: 1` in tests/ before assuming the version-bump obligations end at registry.py + model.py + migration + template.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-09-26T13:06:41 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · Template gate wiring untested: tests recompute gated= instead of going through record_brief (phase 1)

tests/unit/test_record_template.py copied record_brief's gated= logic; deleting the wiring would stay green.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-09-26T13:06:41 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · Unreadable-record refusal not asserted byte-identical; no invalid-YAML case (phase 1)

test_migration_record_questions.py checked only a missing stamp and only a schema-invalid body.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-09-26T13:06:41 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · v1 fixture lacks the `schema_version: 1` line every real template-rendered record carries (phase 1)

The stamp-rewrite path for real in-flight records was untested.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-09-26T13:06:41 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · Migration guard refuses an empty record that parse_record accepts (phase 1)

record_questions._guard raised on None; the file would stay stale and block the CLI gate.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-09-26T13:06:41 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · Whitespace-only questions.reason accepted for rounds: 2 (phase 1)

model.py used `not self.reason`; phase 2 writes the reason into a journal decision.

<!-- fr:journal kind=review scope=plan id=review-phase-1 created=2026-09-26T13:06:41 phase=1 -->
### review-phase-1 · review · Phase 1 code review: 5 in-scope findings, 0 out of scope (phase 1)

Dispatched code reviewer over 6342e663..HEAD (packages, tests) against spec §3.B, plan 01.yaml and artifact-versioning.md. No blocking issues; versioning obligations met. Raised p1-r1..p1-r5 (2 medium, 3 low), all verified against the code and fixed with tests. Two sub-threshold notes (message names live version; frozen-ness tested by config) not filed.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-09-26T13:06:41 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: Template gate wiring untested: tests recompute gated= instead of going through record_brief (phase 1)

New test drives record_brief for the gated brainstorm step; implement-phase brief asserted to carry no questions hint.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-09-26T13:06:41 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: Unreadable-record refusal not asserted byte-identical; no invalid-YAML case (phase 1)

Refusal asserts byte-identity; new invalid-YAML (truncated) case asserts failed + byte-identical.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-09-26T13:06:41 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: v1 fixture lacks the `schema_version: 1` line every real template-rendered record carries (phase 1)

Stamp test parametrized over no-stamp and schema_version: 1; the latter asserts exact text with only the stamp line changed.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-09-26T13:06:41 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: Migration guard refuses an empty record that parse_record accepts (phase 1)

Guard treats None as {} like parse_record; new test stamps a comment-only record.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-09-26T13:06:41 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: Whitespace-only questions.reason accepted for rounds: 2 (phase 1)

Validator strips reason; parametrized whitespace case added.

<!-- fr:journal kind=decision scope=plan id=p2-rounds-share-one-walk created=2026-09-26T13:20:43 phase=2 -->
### p2-rounds-share-one-walk · decision · operator_answered_since is now "at least one answered round" over answered_rounds_since's walk (phase 2) (phase 2)

P2.T1.S3. The two predicates read the same records by the same rules (main thread,
stamped at/after `since`, answered = non-empty `toolUseResult.answers` paired by
tool_use id). Every asked id belongs to exactly one round and a round counts when any
of its ids was answered, so `bool(answered_rounds_since(...))` equals the old result
exactly; operator_answered_since delegates to it and its existing tests stay green
unchanged. The gate calls answered_rounds_since once and derives the observed/unobserved
split from it, so the two can never disagree inside one resolve.

<!-- fr:journal kind=decision scope=plan id=p2-round-two-needs-a-spec created=2026-09-26T13:20:43 phase=2 -->
### p2-round-two-needs-a-spec · decision · A declared second round with no spec to journal it on is refused, like --no-questions (phase 2) (phase 2)

Spec §3.C says the `gate-question-rounds-<step>` decision goes "to the same journal"
as the no-questions entry. That journal is the spec this resolve emits, else one an
earlier step emitted; with neither, review r1-5's reasoning applies unchanged — the
reason would reach only stderr. So `rounds: 2` without a reachable spec is refused
before the transcript is read and before any byte moves. The brainstorm step always
emits its spec, so the shipped fr-goal path never hits it.

<!-- fr:journal kind=finding scope=plan id=p2-member-resolve-dropped-gate-flags created=2026-09-26T13:20:43 phase=2 state=open review_scope=in -->
### p2-member-resolve-dropped-gate-flags · finding [open] (reviewer: in scope) · Gate flags on a grouped-member resolve were silently dropped (phase 2) (phase 2)

Found by the new "questions on a resolve that clears no gate" test: `_resolve_body`
delegates a `for_each` member (implement-phase, review-phase) to `_resolve_member`
BEFORE the review r1-7 "clears none" refusal, so `--no-questions --reason` (and now
`questions`) on a member resolve exited 0 with the flags ignored — on both the flag
path and the record path. Fixed: the member branch refuses gate flags first, via one
`_refuse_gate_flags` helper shared with the top-level refusal. Both paths tested in
tests/unit/test_run_question_rounds.py.

<!-- fr:journal kind=finding scope=plan id=p2-member-resolve-dropped-gate-flags-resolved created=2026-09-26T13:20:43 phase=2 state=fixed resolves=p2-member-resolve-dropped-gate-flags -->
### p2-member-resolve-dropped-gate-flags-resolved · finding [fixed] · resolves p2-member-resolve-dropped-gate-flags: Gate flags on a grouped-member resolve were silently dropped (phase 2) (phase 2)

member branch now refuses gate flags before delegating; tested on both paths.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-09-26T13:37:27 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · Round-3 refusal suggested --no-questions, which would record a false 'cleared without asking' (phase 2)

question_rounds_refusal pointed at the bypass whose provenance (answered_by: agent) contradicts an operator who answered.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-09-26T13:37:27 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · Unverified notice claimed a rounds: 1 declaration was recorded when nothing is written (phase 2)

Only rounds: 2 journals.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-09-26T13:37:27 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · Round.answered is always True (phase 2)

Constant field; its test only checked the code against itself.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-09-26T13:37:27 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · answered_rounds_since duplicated _this_session (phase 2)

Third copy of the harness/session front half; plan P2.T1.S3 asked for sharing.

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-09-26T13:37:27 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · Test Plan 3 only partly covered: declined gate, ungated step, no-spec round-two, member --no-questions untested (phase 2)

The _clears_gate branch and two new refusals had no test.

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-09-26T13:37:27 phase=2 state=open review_scope=in -->
### p2-r6 · finding [open] (reviewer: in scope) · Retry idempotence keyed on id only kept a stale body; retry test hand-wrote the entry (phase 2)

A retry with a changed reason silently kept the first body.

<!-- fr:journal kind=finding scope=plan id=p2-r7 created=2026-09-26T13:37:27 phase=2 state=open review_scope=out -->
### p2-r7 · finding [open] (reviewer: out of scope) · Flag-path journal append not rolled back when a later resolve step refuses (phase 2)

Pre-existing for gate-no-questions entries (guard=None on the flag path); the round-two entry inherits it.

<!-- fr:journal kind=finding scope=plan id=p2-r8 created=2026-09-26T13:37:27 phase=2 state=open review_scope=in -->
### p2-r8 · finding [open] (reviewer: in scope) · Bookkeeping tool calls between question batches split one round and can strand the gate (phase 2)

Reviewer tagged this out of scope as a spec design risk; reclassified in scope by the orchestrator because this change introduces the round rule and the n>2 refusal that makes it strand a gate.

<!-- fr:journal kind=review scope=plan id=review-phase-2 created=2026-09-26T13:37:27 phase=2 -->
### review-phase-2 · review · Phase 2 code review: 7 in-scope findings (1 reclassified), 1 out of scope (phase 2)

Dispatched code reviewer over 37410263 and eb4da954 against spec §3.B/§3.C and plan 02.yaml. Grouping rule, operator_answered_since equivalence, verdict table, pre-write refusals and both threading paths verified correct. Raised p2-r1 (medium) and p2-r2..r6 (low) in scope, p2-r7/p2-r8 out of scope; p2-r8 reclassified in. Fixes in ab531445, each pinned by tests; 384 targeted tests re-run green by the orchestrator. Side effect accepted: a --no-questions retry with a changed reason is now refused rather than silently keeping the stale entry (same rule as p2-r6).

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-09-26T13:37:27 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: Round-3 refusal suggested --no-questions, which would record a false 'cleared without asking' (phase 2)

Refusal now offers --state failed and re-running the step; tests assert --no-questions absent from every refusing verdict.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-09-26T13:37:27 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: Unverified notice claimed a rounds: 1 declaration was recorded when nothing is written (phase 2)

rounds: 1 reads 'accepted, unverified'; rounds: 2 keeps 'recorded as claimed too'; both pinned.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-09-26T13:37:27 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: Round.answered is always True (phase 2)

Field removed; tests updated.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-09-26T13:37:27 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: answered_rounds_since duplicated _this_session (phase 2)

answered_rounds_since uses _this_session; None semantics unchanged, existing tests green.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-09-26T13:37:27 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: Test Plan 3 only partly covered: declined gate, ungated step, no-spec round-two, member --no-questions untested (phase 2)

Four refusal tests over both paths asserting exit 2, byte-identical snapshot, unmoved HEAD.

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-09-26T13:37:27 phase=2 state=fixed resolves=p2-r6 -->
### p2-r6-resolved · finding [fixed] · resolves p2-r6: Retry idempotence keyed on id only kept a stale body; retry test hand-wrote the entry (phase 2)

_append_gate_decision refuses a differing body before any write; real first-resolve retry test and changed-reason test on both paths.

<!-- fr:journal kind=finding scope=plan id=p2-r7-resolved created=2026-09-26T13:37:27 phase=2 state=open resolves=p2-r7 out_of_scope=true -->
### p2-r7-resolved · finding [out-of-scope] · resolves p2-r7: Flag-path journal append not rolled back when a later resolve step refuses (phase 2)

Existing behaviour of the flag path for gate-no-questions entries since r1-6; retry idempotence is the existing mitigation. Not caused by this change.

<!-- fr:journal kind=finding scope=plan id=p2-r8-resolved created=2026-09-26T13:37:27 phase=2 state=fixed resolves=p2-r8 -->
### p2-r8-resolved · finding [fixed] · resolves p2-r8: Bookkeeping tool calls between question batches split one round and can strand the gate (phase 2)

ROUND_NEUTRAL_TOOLS (Claude Code progress trackers) do not close a round; TodoWrite-between = 1 round, Read-between = 2 rounds pinned; spec §3.C updated.

<!-- fr:journal kind=discovery scope=plan id=p3-explainer-byte-identity-confirmed created=2026-09-26T13:54:15 phase=3 -->
### p3-explainer-byte-identity-confirmed · discovery · Unmodified 01-fr-goal.md re-render matched the committed .html byte-for-byte before any edit (phase 3)

Followed .claude/rules/explainers-currency.md's verification step: rendered the
UNMODIFIED docs/explainers/01-fr-goal.md from `/` with
`uv run --isolated --no-project --with markdown --with pyyaml python
~/.claude/plugins/marketplaces/derio-net--blog-craft/tools/render_explainer.py
<md> --style broadsheet --embed-fonts -o <scratch>.html` and diffed it against the
committed 01-fr-goal.html — identical. So the real render after the prose edit is
known to reflect only what was written, not renderer or environment drift.

<!-- fr:journal kind=discovery scope=plan id=p3-verification-log created=2026-09-26T13:54:15 phase=3 -->
### p3-verification-log · discovery · Phase 3 verification commands (executor-reported) (phase 3)

tests_p3_t1: uv run pytest tests/unit/test_tripwire_fr_goal_question_rounds.py -q --no-cov -> 60 passed (with test_tripwire_explainers_fresh.py); guard sweep uv run pytest tests/unit/test_tripwire_*.py tests/unit/test_skill_*.py tests/unit/test_opencode_agent_mirror.py -q --no-cov -n auto -> 322 passed, 97 skipped
tests_p3_t2: uv run pytest tests/unit/test_tripwire_fr_goal_question_rounds.py tests/unit/test_tripwire_explainers_fresh.py -q --no-cov -> 60 passed
tests_p3_t3: uv run fr acceptance check -> 256 rows OK (ci:222, skipped:24, not-implemented:9, scheduled:1), only pre-existing archived-spec-path warnings unrelated to this change
uv run --no-project python scripts/bump-version.py --check -> ok, versions agree
uv run ruff check packages/ tests/ -> All checks passed!
uv run ruff format --check packages/ tests/ -> 544 files already formatted
uv run mypy packages/fr/src -> Success: no issues found in 167 source files
uv run pytest -q --no-cov -n auto -> 6127 passed, 97 skipped in 335.83s

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-09-26T13:54:15 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

Guard suite (test_tripwire_*.py, test_skill_*.py, test_opencode_agent_mirror.py, 322 passed/97 skipped) came back clean against the new prose — nothing to fix.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-09-26T13:54:15 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

No refactor step in this task; the explainer/README edits are prose-only substitutions of the old contract's wording for the new one, verified byte-identical against the unmodified baseline render before editing and re-rendered afterward — nothing left to clean up.

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-09-26T14:04:40 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · Skill told the agent to cross-examine 'in prose, not a tool call', which merges both rounds and gets rounds: 2 refused (phase 3)

answered_rounds_since closes a round only on a non-neutral tool call; following fr-goal SKILL.md:48/:50 made round 1 and round 2 one round on Claude Code.

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-09-26T14:04:40 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · Tripwire 'questions:' marker vacuous: matched the Harness clause heading (phase 3)

Deleting the record-declaration sentence left the test green.

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-09-26T14:04:40 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · Tripwire phrase lists line-bound, case-sensitive, incomplete; published .html, index.html and the OpenCode command not swept (phase 3)

Test Plan 6 was only partly asserted.

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-09-26T14:04:40 phase=3 state=open review_scope=in -->
### p3-r4 · finding [open] (reviewer: in scope) · docs/explainers/index.html still promised one batched Q&A in a single short round (phase 3)

Hand-authored published landing page missed by the §3.A.1 table.

<!-- fr:journal kind=finding scope=plan id=p3-r5 created=2026-09-26T14:04:40 phase=3 state=open review_scope=in -->
### p3-r5 · finding [open] (reviewer: in scope) · Residual old-contract wording in README and 01-fr-goal.md outside the §3.A.1 line numbers (phase 3)

README:8,66,382; explainer :34, :81 mermaid, :531, :537.

<!-- fr:journal kind=finding scope=plan id=p3-r6 created=2026-09-26T14:04:40 phase=3 state=open review_scope=in -->
### p3-r6 · finding [open] (reviewer: in scope) · Acceptance notes overclaimed what the tripwire asserts (phase 3)

Sizing rule and 'every surface' claims were not backed.

<!-- fr:journal kind=finding scope=plan id=p3-r7 created=2026-09-26T14:04:40 phase=3 state=open review_scope=in -->
### p3-r7 · finding [open] (reviewer: in scope) · Announced round 2 with nothing opened: prose contradicted itself (phase 3)

Resolve-after-last-announced-round vs round-2-only-what-round-1-opened.

<!-- fr:journal kind=finding scope=plan id=p3-r8 created=2026-09-26T14:04:40 phase=3 state=open review_scope=in -->
### p3-r8 · finding [open] (reviewer: in scope) · Explainer gate paragraph described only the answered-question check (phase 3)

No mention of the declared-round verification or the PR record.

<!-- fr:journal kind=finding scope=plan id=p3-r9 created=2026-09-26T14:04:40 phase=3 state=open review_scope=in -->
### p3-r9 · finding [open] (reviewer: in scope) · Skill did not say rounds: 2 is journaled and reaches the PR body (phase 3)

Operator-visible consequence undocumented.

<!-- fr:journal kind=finding scope=plan id=p3-r10 created=2026-09-26T14:04:40 phase=3 state=open review_scope=in -->
### p3-r10 · finding [open] (reviewer: in scope) · Change fragment summary omitted operator-request trigger, record v2 and the flags (phase 3)

User-observable surface missing from release notes.

<!-- fr:journal kind=finding scope=plan id=p3-r11 created=2026-09-26T14:04:40 phase=3 state=open review_scope=out -->
### p3-r11 · finding [open] (reviewer: out of scope) · Explainer :533-535 still describes gate provenance as a typed claim defaulting to agent (phase 3)

Observed-provenance gate predates this change; lines untouched by it.

<!-- fr:journal kind=review scope=plan id=review-phase-3 created=2026-09-26T14:04:40 phase=3 -->
### review-phase-3 · review · Phase 3 prose review: 10 in-scope findings (1 critical), 1 out of scope (phase 3)

Dispatched reviewer checked every §3.A.1 surface, prose-vs-code agreement (QuestionRounds, answered_rounds_since, ROUND_NEUTRAL_TOOLS, question_rounds_refusal), harness neutrality, tripwire quality, fragment and acceptance notes. Critical p3-r1 (prose contradicted the round-separation mechanism) and p3-r2..r10 fixed in 9e406808..2223ac1f; orchestrator verified 'in prose' gone and re-ran the tripwire, explainer-fresh and tool-neutrality tests (246 passed).

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-09-26T14:04:40 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: Skill told the agent to cross-examine 'in prose, not a tool call', which merges both rounds and gets rounds: 2 refused (phase 3)

§1: checking answers against the code is what separates rounds; harness clause: back-to-back calls within a round, real tool calls between rounds, progress trackers do not separate. Tripwire requires the new markers and forbids the 'in prose' phrasings on all three copies.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-09-26T14:04:40 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: Tripwire 'questions:' marker vacuous: matched the Harness clause heading (phase 3)

Marker is now 'questions: {rounds' plus design-risk, operator-request, (round 2 of 2).

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-09-26T14:04:40 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: Tripwire phrase lists line-bound, case-sensitive, incomplete; published .html, index.html and the OpenCode command not swept (phase 3)

Whitespace-collapsed, casefolded matching; extended phrase list; sweep covers 01-fr-goal.html, index.html, .opencode/commands/fr-goal.md; sizing and round markers asserted.

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-09-26T14:04:40 phase=3 state=fixed resolves=p3-r4 -->
### p3-r4-resolved · finding [fixed] · resolves p3-r4: docs/explainers/index.html still promised one batched Q&A in a single short round (phase 3)

index.html edited in place at the five places; swept by the tripwire.

<!-- fr:journal kind=finding scope=plan id=p3-r5-resolved created=2026-09-26T14:04:40 phase=3 state=fixed resolves=p3-r5 -->
### p3-r5-resolved · finding [fixed] · resolves p3-r5: Residual old-contract wording in README and 01-fr-goal.md outside the §3.A.1 line numbers (phase 3)

All listed lines reworded; .html regenerated after a byte-identical baseline render.

<!-- fr:journal kind=finding scope=plan id=p3-r6-resolved created=2026-09-26T14:04:40 phase=3 state=fixed resolves=p3-r6 -->
### p3-r6-resolved · finding [fixed] · resolves p3-r6: Acceptance notes overclaimed what the tripwire asserts (phase 3)

Both notes rewritten via fr acceptance set-status to state exactly what is asserted where.

<!-- fr:journal kind=finding scope=plan id=p3-r7-resolved created=2026-09-26T14:04:40 phase=3 state=fixed resolves=p3-r7 -->
### p3-r7-resolved · finding [fixed] · resolves p3-r7: Announced round 2 with nothing opened: prose contradicted itself (phase 3)

'An announced round 2 is a ceiling, not a promise' — resolve with rounds: 1 when round 1 opened nothing; pinned.

<!-- fr:journal kind=finding scope=plan id=p3-r8-resolved created=2026-09-26T14:04:40 phase=3 state=fixed resolves=p3-r8 -->
### p3-r8-resolved · finding [fixed] · resolves p3-r8: Explainer gate paragraph described only the answered-question check (phase 3)

Two sentences added on declared-round verification and the PR record; page regenerated.

<!-- fr:journal kind=finding scope=plan id=p3-r9-resolved created=2026-09-26T14:04:40 phase=3 state=fixed resolves=p3-r9 -->
### p3-r9-resolved · finding [fixed] · resolves p3-r9: Skill did not say rounds: 2 is journaled and reaches the PR body (phase 3)

Skill names the gate-question-rounds-<step> spec-journal decision; pinned.

<!-- fr:journal kind=finding scope=plan id=p3-r10-resolved created=2026-09-26T14:04:40 phase=3 state=fixed resolves=p3-r10 -->
### p3-r10-resolved · finding [fixed] · resolves p3-r10: Change fragment summary omitted operator-request trigger, record v2 and the flags (phase 3)

Summary names both triggers, never a third, questions: field, record v2, --question-rounds.

<!-- fr:journal kind=finding scope=plan id=p3-r11-resolved created=2026-09-26T14:04:40 phase=3 state=open resolves=p3-r11 out_of_scope=true -->
### p3-r11-resolved · finding [out-of-scope] · resolves p3-r11: Explainer :533-535 still describes gate provenance as a typed claim defaulting to agent (phase 3)

Pre-existing staleness from the observed-provenance change; this PR did not touch those lines. Candidate follow-up issue at the merge touchpoint.

<!-- fr:journal kind=finding scope=plan id=p2-r7-resolved-2 created=2026-09-26T14:31:54 state=open resolves=p2-r7 tracked_by=#690 -->
### p2-r7-resolved-2 · finding [deferred → #690] · resolves p2-r7: Flag-path journal append not rolled back when a later resolve step refuses

Filed at closeout as #690.

<!-- fr:journal kind=finding scope=plan id=p3-r11-resolved-2 created=2026-09-26T14:31:55 state=open resolves=p3-r11 tracked_by=#691 -->
### p3-r11-resolved-2 · finding [deferred → #691] · resolves p3-r11: Explainer :533-535 still describes gate provenance as a typed claim defaulting to agent

Filed at closeout as #691.
