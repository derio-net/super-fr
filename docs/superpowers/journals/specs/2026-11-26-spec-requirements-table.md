<!-- fr:journal-schema=4 -->
# Journal: 2026-11-26-spec-requirements-table

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-26T10:59:51+00:00 input=true -->
### brief · discovery · Operator brief

in the Spec document, the Requirements are not easily human-readable, when rendered by markdown previewers. Let's wrap them in a table please. Also, I want to understand how we are using fr-isolation now together with the various supported harnesses. Can we simplify/improve the isolation if we play with the harnesses, instead of doing our own thing?

<!-- fr:journal kind=decision scope=spec id=scope-table-only created=2026-11-26T16:04:45+00:00 decided_by=operator -->
### scope-table-only · decision · This spec covers the Requirements table only; the fr-isolation simplification gets its own brainstorm next

Operator chose "Table now, isolation next". The isolation map (marker, sentinel, three decision copies, WorktreeCreate takeover, per-harness gaps) informs a separate brainstorm on its own branch.

<!-- fr:journal kind=decision scope=spec id=migration-rewrites created=2026-11-26T16:04:45+00:00 decided_by=operator -->
### migration-rewrites · decision · The spec 1 -> 2 migration rewrites live R<n>. lists into the table

Operator chose "Rewrite to table" over stamp-only. The hop builds the body in memory, round-trips the parsed requirements, writes once, and leaves an unconvertible spec byte-identical and reported. Archived specs are never touched.

<!-- fr:journal kind=decision scope=spec id=verify-candidate created=2026-11-26T16:04:45+00:00 decided_by=operator -->
### verify-candidate · decision · Verification strategy is candidate

Operator chose candidate. A scenario installs the branch, migrates a fixture list spec and checks the installed fr reads the table to the same requirements. Gate developer; nothing post-merge.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-11-28T09:20:39+00:00 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · Hard-wrapped requirements in live specs break the R4 refusal rule

See the independent spec review (spec-review).

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-11-28T09:20:39+00:00 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · R3 stamps a legacy table at 2 that R6 then refuses

See the independent spec review (spec-review).

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-11-28T09:20:39+00:00 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · One unconvertible spec refuses every fr command in the repo

See the independent spec review (spec-review).

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-11-28T09:20:39+00:00 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · Malformed two-column row handling unspecified

See the independent spec review (spec-review).

<!-- fr:journal kind=finding scope=spec id=s5 created=2026-11-28T09:20:39+00:00 state=open review_scope=in -->
### s5 · finding [open] (reviewer: in scope) · Byte-preservation promise vs Design; line endings

See the independent spec review (spec-review).

<!-- fr:journal kind=finding scope=spec id=s6 created=2026-11-28T09:20:39+00:00 state=open review_scope=in -->
### s6 · finding [open] (reviewer: in scope) · Background misstates an older fr's reaction

See the independent spec review (spec-review).

<!-- fr:journal kind=finding scope=spec id=s7 created=2026-11-28T09:20:39+00:00 state=open review_scope=in -->
### s7 · finding [open] (reviewer: in scope) · Other list-form descriptions and a docs-currency page missing

See the independent spec review (spec-review).

<!-- fr:journal kind=finding scope=spec id=s8 created=2026-11-28T09:20:39+00:00 state=open review_scope=in -->
### s8 · finding [open] (reviewer: in scope) · Test Plan names files that do not exist; Design shape omits tests, scenario, fragment

See the independent spec review (spec-review).

<!-- fr:journal kind=finding scope=spec id=s9 created=2026-11-28T09:20:39+00:00 state=open review_scope=in -->
### s9 · finding [open] (reviewer: in scope) · validate_spec reading the stamp risks an import cycle

See the independent spec review (spec-review).

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-11-28T09:20:39+00:00 -->
### spec-review · review · independent spec review: 9 findings, all in scope

fr-spec-reviewer (hard tier) checked the spec against the three operator decisions, the codebase and itself; all three decisions honoured. Additionally found live spec 2026-11-27-triage-leaves-split holds an `R9a.` id the current parser drops silently.

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-28T09:20:39+00:00 lens=tests step=spec-review -->
### lens-tests-1 · lens · the migration's round trip, refusals and CRLF/wrapped-line edge cases need adversarial test review

<!-- fr:journal kind=lens scope=spec id=lens-errors-1 created=2026-11-28T09:20:39+00:00 lens=errors step=spec-review -->
### lens-errors-1 · lens · an unconvertible spec turns into a whole-repo CLI refusal; its message and way out must be checked

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-11-28T09:20:39+00:00 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: Hard-wrapped requirements in live specs break the R4 refusal rule

Continuation lines defined (new R3): joined in the reader and the rewrite, so the round trip holds; blank lines between requirements are not prose; an id-like malformed prefix (R9a.) refuses. Test Plan covers wrapped and R9a cases.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-11-28T09:20:39+00:00 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: R3 stamps a legacy table at 2 that R6 then refuses

R7 checks cell counts only for the `| ID | Requirement |` table and says a legacy three-column table is not refused; validator test for a stamped legacy table added.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-11-28T09:20:39+00:00 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: One unconvertible spec refuses every fr command in the repo

R5 now requires the failure to name file, line, cause and the hand fix; Design states the whole-repo gate consequence and the cross-branch conflict and its resolution.

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-11-28T09:20:39+00:00 state=fixed resolves=s4 -->
### s4-resolved · finding [fixed] · resolves s4: Malformed two-column row handling unspecified

R1 requires outer pipes; R2 raises RequirementsError naming the line for a row of other than two cells; tests added.

<!-- fr:journal kind=finding scope=spec id=s5-resolved created=2026-11-28T09:20:39+00:00 state=fixed resolves=s5 -->
### s5-resolved · finding [fixed] · resolves s5: Byte-preservation promise vs Design; line endings

R4 states exactly what changes (requirement lines, blank lines around the table, stamp) and that line endings are kept; Design reads with read_utf8 and keepends; CRLF case in the Test Plan.

<!-- fr:journal kind=finding scope=spec id=s6-resolved created=2026-11-28T09:20:39+00:00 state=fixed resolves=s6 -->
### s6-resolved · finding [fixed] · resolves s6: Background misstates an older fr's reaction

Background now says any fr before this change silently skips sizing and proportionality reports no list; only validate reads the stamp; the window is accepted with the reason.

<!-- fr:journal kind=finding scope=spec id=s7-resolved created=2026-11-28T09:20:39+00:00 state=fixed resolves=s7 -->
### s7-resolved · finding [fixed] · resolves s7: Other list-form descriptions and a docs-currency page missing

R8 and Design/Design shape now name fr-plan, fr-acceptance, the fr-acceptance and 01-fr-goal explainers and the parser's docstring and error texts.

<!-- fr:journal kind=finding scope=spec id=s8-resolved created=2026-11-28T09:20:39+00:00 state=fixed resolves=s8 -->
### s8-resolved · finding [fixed] · resolves s8: Test Plan names files that do not exist; Design shape omits tests, scenario, fragment

Test Plan names test_spec_requirements_list.py, the new migration and prose test modules; Design shape draws them, the scenario, its test_scenarios.py entry and the change fragment.

<!-- fr:journal kind=finding scope=spec id=s9-resolved created=2026-11-28T09:20:39+00:00 state=fixed resolves=s9 -->
### s9-resolved · finding [fixed] · resolves s9: validate_spec reading the stamp risks an import cycle

Design specifies a function-local import of the registry's _read_spec_stamp, as validate_spec already does for fr.spec.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-28T09:20:48+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  spec-requirements-table-migrate: none
  spec-requirements-table-read: none
  spec-requirements-table-valid: none
row_kinds:
  spec-requirements-table-migrate: candidate
  spec-requirements-table-read: none
  spec-requirements-table-valid: none
run_gate: none
run_kind: candidate
```

<!-- fr:journal kind=decision scope=spec id=tier-2026-11-26-spec-requirements-table-p1 created=2026-11-28T09:29:29+00:00 -->
### tier-2026-11-26-spec-requirements-table-p1 · decision · hard: the single phase carries the spec 1->2 body-rewrite migration, which every consumer repo runs on upgrade and whose refusal blocks every fr command there
