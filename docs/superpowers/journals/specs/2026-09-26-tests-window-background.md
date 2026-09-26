# Journal: 2026-09-26-tests-window-background

<!-- fr:journal kind=decision scope=spec id=d1 created=2026-09-26T15:00:39 -->
### d1 · decision · Window ends at task-notification keyed by tool_use id

#607's direction; the only transcript event marking a backgrounded command's completion.

<!-- fr:journal kind=decision scope=spec id=d2 created=2026-09-26T15:00:39 -->
### d2 · decision · Background window needs completed + no non-zero exit

Mirrors foreground is_error rule.

<!-- fr:journal kind=decision scope=spec id=d3 created=2026-09-26T15:00:39 -->
### d3 · decision · Variables resolved within one command only; leading unresolvable var dropped

Syntactic like _writes today; cross-call state untrusted.

<!-- fr:journal kind=decision scope=spec id=gate-no-questions-brainstorm created=2026-09-26T15:00:40 -->
### gate-no-questions-brainstorm · decision · Operator gate `brainstorm` cleared without asking

Operator's batch brief (tests-window) fixes scope, root cause, fix direction (#607), branch, one phase, claude-sonnet-5 for every tier; no operator-owned decision remains and nothing deploys, so no Test Plan question.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-09-26T15:02:07 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · Record shapes unpinned; ack/notification content shapes under-specified

Reviewer: no fixture backs §2; content may be str or text-block list.

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-09-26T15:02:07 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · OpenCode & detach has the same zero-length-window bug; spec said unchanged

Reviewer: long_commands.py:26-33, telemetry.py:802-812.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-09-26T15:02:07 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · attribute_dispatches keying reference is wrong

Reviewer: it keys subagent metadata, not notifications.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-09-26T15:02:07 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · §3.B edge cases missing from Test Plan

Reviewer: $(mktemp), assignment after redirect, 2>&1 form, residual weakness.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-09-26T15:02:07 -->
### spec-review · review · independent spec review: 4 findings

Reviewer abfa7921b8a4c11fb verified run_cmd.py:1773, telemetry.py:626/638/652/751, long_commands.py:20-33, test files; raised s1-s4, all addressed in the spec.

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-09-26T15:02:07 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: Record shapes unpinned; ack/notification content shapes under-specified

Spec §3.A states both content shapes; §5.3 requires fixtures mirroring captured records in both shapes.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-09-26T15:02:07 state=open resolves=s2 out_of_scope=true -->
### s2-resolved · finding [out-of-scope] · resolves s2: OpenCode & detach has the same zero-length-window bug; spec said unchanged

OpenCode has no completion event; needs its own design. Spec §1 now states it stays refused; follow-up issue to be filed at merge touchpoint. This change does not cause it.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-09-26T15:02:07 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: attribute_dispatches keying reference is wrong

Reworded §3.A.

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-09-26T15:02:07 state=fixed resolves=s4 -->
### s4-resolved · finding [fixed] · resolves s4: §3.B edge cases missing from Test Plan

§3.B and §5.3 extended; residual weakness stated.

<!-- fr:journal kind=review scope=spec id=spec-review-opus created=2026-09-26T23:50:15 -->
### spec-review-opus · review · independent spec review on claude-opus-5-5 (fresh context): 4 findings

Reviewer a238c5d3a9f9c36c0 (opus). Re-run because the first review (spec-review) ran on Sonnet. Findings s5-s8, all in scope, all fixed in 33d01601 / 716b3ca4.

<!-- fr:journal kind=finding scope=spec id=s5 created=2026-09-26T23:50:50 state=open review_scope=in -->
### s5 · finding [open] (reviewer: in scope) · §2 'captured' shapes were hand-built, not captured (Opus re-review)

No captured background exchange was committed; background_rows hand-built the records. Fixed: redacted real fixture tests/fixtures/transcripts/claude-code-background.jsonl.

<!-- fr:journal kind=finding scope=spec id=s6 created=2026-09-26T23:50:51 state=open review_scope=in -->
### s6 · finding [open] (reviewer: in scope) · Timeout-moved foreground Bash replies with different ack text (Opus)

Same #594 symptom via the auto-background path. Fixed: covered in spec §2/§3.A and code.
