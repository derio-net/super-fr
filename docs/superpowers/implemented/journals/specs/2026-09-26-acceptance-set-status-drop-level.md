# Journal: 2026-09-26-acceptance-set-status-drop-level

<!-- fr:journal kind=decision scope=spec id=d-carrier created=2026-09-26T00:39:23 -->
### d-carrier · decision · Drops are carried CLI-only via RecordTarget; the record kind's shape is unchanged

Operator chose CLI-only over adding `drop_levels` to AcceptanceItem. The record artifact kind keeps version 1 (no stamp bump, no migration), so the release stays a patch. Step records still cannot drop refs; a step that needs one runs the verb.

<!-- fr:journal kind=decision scope=spec id=d-conflict created=2026-09-26T00:39:23 -->
### d-conflict · decision · The same ref in both --level and --drop-level is refused, exit 2

Contradictory intent in one call. It is refused with nothing changed, like an absent-ref drop.

<!-- fr:journal kind=decision scope=spec id=d-empty-evidence created=2026-09-26T00:39:23 -->
### d-empty-evidence · decision · A drop that empties a ci/scheduled row's evidence is allowed

The status is the operator's explicit call in the same command, with --notes; set-status never judged status against evidence, and `fr acceptance check` stays the gate.

<!-- fr:journal kind=finding scope=spec id=sr-1 created=2026-09-26T00:42:07 state=open review_scope=in -->
### sr-1 · finding [open] (reviewer: in scope) · §2.C says drops reach the engine via RecordTarget, but _acceptance_writes never receives the target

apply.py:550-552 takes no target; :756 call site. Spec must name the field, default, and plumbing.

<!-- fr:journal kind=finding scope=spec id=sr-2 created=2026-09-26T00:42:07 state=open review_scope=in -->
### sr-2 · finding [open] (reviewer: in scope) · Engine behaviour is undefined for drops that do not line up with record.acceptance

Drops keyed by an id with no item, by a create-branch item, or passed with run_id would be silently ignored.

<!-- fr:journal kind=finding scope=spec id=sr-3 created=2026-09-26T00:42:07 state=open review_scope=in -->
### sr-3 · finding [open] (reviewer: in scope) · Test Plan covers only the CLI; the engine-side drop_levels refusal and drop_levels itself go untested

The CLI pre-flight exits before the engine; needs direct drop_levels and apply_record tests, plus the empty-evidence decision pinned.

<!-- fr:journal kind=finding scope=spec id=sr-4 created=2026-09-26T00:42:07 state=open review_scope=in -->
### sr-4 · finding [open] (reviewer: in scope) · §2.D hedges on the mirrors: OpenCode does carry acceptance-matrix.md, Hermes does not

sync-opencode.py:63-64 mirrors it; sync-hermes.py:41-45 excludes it.

<!-- fr:journal kind=finding scope=spec id=sr-5 created=2026-09-26T00:42:07 state=open review_scope=in -->
### sr-5 · finding [open] (reviewer: in scope) · Reusing _parse_levels for --drop-level prints a wrong flag name on malformed input

acceptance_cmd.py:303-312 hardcodes '--level must be'.

<!-- fr:journal kind=finding scope=spec id=sr-6 created=2026-09-26T00:42:07 state=open review_scope=in -->
### sr-6 · finding [open] (reviewer: in scope) · Repeated identical --drop-level in one call is unspecified

Dedupe vs refuse; dedupe matches merge_levels.

<!-- fr:journal kind=finding scope=spec id=sr-7 created=2026-09-26T00:42:07 state=open review_scope=in -->
### sr-7 · finding [open] (reviewer: in scope) · Spec does not state the same-PR move of the lifecycle-acceptance-drop-level matrix row

acceptance-matrix rule: a PR shipping the surface a not-implemented row waits on moves it in the same PR.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-09-26T00:42:07 -->
### spec-review-1 · review · independent spec review: 7 findings (all in scope)

fr-spec-reviewer checked the spec against d-carrier, d-conflict and d-empty-evidence (all honoured) and against the codebase, with file:line for every named helper. Raised sr-1 through sr-7, all in scope, all fixed in the spec.

<!-- fr:journal kind=finding scope=spec id=sr-1-resolved created=2026-09-26T00:42:07 state=fixed resolves=sr-1 -->
### sr-1-resolved · finding [fixed] · resolves sr-1: §2.C says drops reach the engine via RecordTarget, but _acceptance_writes never receives the target

§2.C names RecordTarget.acceptance_drops (default_factory=dict), a drops param on _acceptance_writes passed from apply_record, and drop-before-merge in the move branch.

<!-- fr:journal kind=finding scope=spec id=sr-2-resolved created=2026-09-26T00:42:07 state=fixed resolves=sr-2 -->
### sr-2-resolved · finding [fixed] · resolves sr-2: Engine behaviour is undefined for drops that do not line up with record.acceptance

§2.C refuses all three misalignments with RecordRefusedError; Test Plan item 10.

<!-- fr:journal kind=finding scope=spec id=sr-3-resolved created=2026-09-26T00:42:07 state=fixed resolves=sr-3 -->
### sr-3-resolved · finding [fixed] · resolves sr-3: Test Plan covers only the CLI; the engine-side drop_levels refusal and drop_levels itself go untested

Test Plan items 7-10 add empty-evidence, drop_levels unit and apply_record engine tests.

<!-- fr:journal kind=finding scope=spec id=sr-4-resolved created=2026-09-26T00:42:07 state=fixed resolves=sr-4 -->
### sr-4-resolved · finding [fixed] · resolves sr-4: §2.D hedges on the mirrors: OpenCode does carry acceptance-matrix.md, Hermes does not

§2.D states the OpenCode mirror is regenerated and Hermes is untouched.

<!-- fr:journal kind=finding scope=spec id=sr-5-resolved created=2026-09-26T00:42:07 state=fixed resolves=sr-5 -->
### sr-5-resolved · finding [fixed] · resolves sr-5: Reusing _parse_levels for --drop-level prints a wrong flag name on malformed input

§2.A: _parse_levels gains a flag parameter; Test Plan item 6.

<!-- fr:journal kind=finding scope=spec id=sr-6-resolved created=2026-09-26T00:42:07 state=fixed resolves=sr-6 -->
### sr-6-resolved · finding [fixed] · resolves sr-6: Repeated identical --drop-level in one call is unspecified

§2.A: a repeated drop is deduplicated; Test Plan item 8.

<!-- fr:journal kind=finding scope=spec id=sr-7-resolved created=2026-09-26T00:42:07 state=fixed resolves=sr-7 -->
### sr-7-resolved · finding [fixed] · resolves sr-7: Spec does not state the same-PR move of the lifecycle-acceptance-drop-level matrix row

New §2.E moves the row to ci via set-status in the same PR.
