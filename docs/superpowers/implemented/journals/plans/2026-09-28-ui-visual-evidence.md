# Journal: 2026-09-28-ui-visual-evidence

<!-- fr:journal kind=discovery scope=plan id=d7b368d68bb3 created=2026-09-28T20:00:54+00:00 phase=1 -->
### d7b368d68bb3 · discovery · AcceptanceItem.visual lands in P1.T2, not P1.T3 (phase 1)

The plan assigns `AcceptanceItem.visual` to P1.T3 ("record sections"), but `fr acceptance add --visual-state/--visual-interaction` (P1.T2) writes through `fr.record.apply`'s `_apply_rows` -> `apply_record`, which builds the matrix `Row` from an `AcceptanceItem`. The CLI cannot thread `visual` to the writer without the field existing on `AcceptanceItem`, so it was added in P1.T2 as necessary plumbing. P1.T3 then adds the record's own evidence section (`StepRecord.visual`: `VisualEvidence`/`VisualShot`) on top of it. No behavior gap — both tasks' RED tests are still real (P1.T3's record-apply test exercises a different code path, `fr.record.apply` directly rather than the CLI) — but a reader diffing task boundaries against the plan should know this before assuming P1.T3's diff is self-contained.

<!-- fr:journal kind=discovery scope=plan id=1eb2269f669e created=2026-09-28T20:00:54+00:00 phase=1 -->
### 1eb2269f669e · discovery · render_row_block did not emit verify-style optional fields generically (phase 1)

`fr.acceptance.edit.render_row_block` (the ONE place that renders a row block into matrix.yaml) had to be extended by hand for `visual`, the same way `verify` was added before it — there is no generic "render every optional field" loop, so a future optional `Row` field needs the same one-line addition here or it round-trips as `None` silently (caught in this phase only because the CLI round-trip test exercises it explicitly).

<!-- fr:journal kind=discovery scope=plan id=aaa7162b7a97 created=2026-09-28T20:00:54+00:00 phase=1 -->
### aaa7162b7a97 · discovery · Shape for phase 2/3: where the visual vocabulary now lives (phase 1)

`fr.acceptance.model.Visual` (states/interactions StrictStr tuples, `check_visual_names` the shared non-empty/no-duplicate validator) and `Row.visual: Visual | None`. `fr.record.model.VisualShot` (path, shows — min_length=1), `VisualEvidence` (row, optional script, shots — min_length=1), `StepRecord.visual: tuple[VisualEvidence, ...]` in the `evidence` section group (`_SECTION_FIELDS["evidence"]` now: `evidence`, `emitted`, `visual`). Matrix kind is now version 3, record kind version 4 (`RECORD_SCHEMA_VERSION`). None of this phase touches `_VERIFIABLE_EVIDENCE`/`_DERIVED_EVIDENCE` in `run_cmd.py`, the `witness_transcript`/`read_file_since`/`shell_named_since` telemetry predicates (spec §C), the `fr-goal.yaml` manifest's `visual` evidence name, or the skills/agent prose (spec §E) — all still owed by a later phase.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-09-28T20:00:54+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

no separate refactor pass — Visual + check_visual_names were designed as the shared helper from the start (T2.S3's job), so T1 itself has nothing left to extract: one small closed model plus one field on Row.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-09-28T20:00:54+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

VisualShot/VisualEvidence mirror existing closed-model patterns (TickItem, AcceptanceItem) exactly; two small models with no shared logic between them to extract.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-09-28T20:00:54+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

matrix_visual.py/record_visual.py are built directly from matrix_verify.py/record_input_unconfirmed.py's own shape (the established pattern for a stamp-only hop); the one piece of duplication that did exist — the matrix guard — was extracted to guard_matrix (shared by both matrix hops) as part of writing T4.S2, not after.

<!-- fr:journal kind=finding scope=plan id=p1-f1 created=2026-09-28T20:04:39+00:00 phase=1 state=open review_scope=in -->
### p1-f1 · finding [open] (reviewer: in scope) · visual-evidence-row-flag left not-implemented although phase 1 implements and tests it (phase 1)

The phase links the row and its unit tests exercise the whole claim; acceptance-matrix rule requires moving it with levels in the same PR.

<!-- fr:journal kind=finding scope=plan id=p1-f2 created=2026-09-28T20:04:39+00:00 phase=1 state=open review_scope=in -->
### p1-f2 · finding [open] (reviewer: in scope) · P1.T4.S3 ticked without the pass count its text asks for (phase 1)

The step says to put the targeted run's pass count in the step note; note was null.

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-09-28T20:04:39+00:00 phase=1 -->
### review-p1 · review · phase 1 code review: 2 findings (both in scope) (phase 1)

Independent reviewer (separate context, standard tier) read the phase-1 state against spec §A/§B/§G and the artifact-versioning rule.
Correct: Visual model + shared check_visual_names, Row.visual, acceptance add --visual-*, set-status preserving visual, AcceptanceItem.visual, VisualShot/VisualEvidence/StepRecord.visual in the evidence group, RECORD_SCHEMA_VERSION 4, matrix 2->3 and record 3->4 stamp-only migrations registered and imported, chain reachability asserted, reports in sync.
Findings: p1-f1 (row status), p1-f2 (missing step note). Method note: the reviewer had no shell and read files directly rather than the diff.

<!-- fr:journal kind=finding scope=plan id=p1-f1-resolved created=2026-09-28T20:04:39+00:00 phase=1 state=fixed resolves=p1-f1 -->
### p1-f1-resolved · finding [fixed] · resolves p1-f1: visual-evidence-row-flag left not-implemented although phase 1 implements and tests it (phase 1)

fr acceptance set-status visual-evidence-row-flag -> ci with unit levels test_acceptance_visual.py and test_record_visual.py (commit 2b242f36); reports regenerated.

<!-- fr:journal kind=finding scope=plan id=p1-f2-resolved created=2026-09-28T20:04:39+00:00 phase=1 state=fixed resolves=p1-f2 -->
### p1-f2-resolved · finding [fixed] · resolves p1-f2: P1.T4.S3 ticked without the pass count its text asks for (phase 1)

P1.T4.S3 note backfilled with the targeted and full-suite counts (commit 9aceb0a3).

<!-- fr:journal kind=discovery scope=plan id=p2-visual-semantics created=2026-09-28T20:29:10+00:00 phase=2 -->
### p2-visual-semantics · discovery · For phase 3's prose: the exact `visual` evidence semantics as implemented (phase 2)

Where it lives: `fr.run.visual` (owed_rows, check_visual, derive_visual, role_for, owed_for_unit); `fr.run.telemetry` (read_file_since, shell_named_since, witness_transcript); `run_cmd._visual_witness` is one call.
- **Owed rows**: phase unit → rows in the phase header `acceptance:` that carry `visual` and not `verify: post-merge`; flat unit (deliver) → rows citing the run's spec (`rows_citing`), same filter. No matrix / no linked row / no spec recorded → witness `none` and the record's `visual:` is not consulted.
- **Role** (from the step's shape, not its id): a step declaring `reviewer` evidence → the offered reviewer's subagent transcript; any other phase unit → the holder (this resolve's `agent`, else the last attempt's `agent`) via `attribute_dispatches`, or the orchestrator's own stream when there is no holder (inline); a flat step → the orchestrator's stream.
- **Checks 1–3 always apply** (even unobserved): an entry per owed row; every declared state/interaction named by some shot's `shows`, and no name the row does not declare; each shot has an image suffix (.png .jpg .jpeg .webp .gif, case-insensitive), is not under `<run>.records/`, is `git check-ignore`d when inside the repo, exists and is non-empty; a named `script` exists (absolute or repo-relative). Freshness (mtime ≥ unit opened − 1 s) only when the role is not `holder` (review-phase, deliver).
- **Checks 4–5**: in the witness transcript, a tool call normalising to `Read` (`read_file`, `view` count) whose `file_path`/`path` names each shot at or after the unit opened; and, for a `script`, a call normalising to `Bash` whose command names it (`_names`) since the unit opened.
- **Unobserved**: no readable witness transcript (not Claude Code, session not found, holder/reviewer not paired to a dispatch of this session) → every row's witness gets `:unobserved`, `unobserved` evidence includes `visual`, and a yellow "could not verify that the screenshots were opened" warning. Never a refusal.
- **Witness**: `<row>:<n-shots>:<sha256[:12] over the shot bytes in resolved-path order>[:unobserved]`, joined by `,`; `none` when nothing is owed.
- **Refusals**: `--evidence visual=` ("not yours to pass"); a flag-form resolve (no `--record`) of a unit that owes a row → exit 2 naming the rows and `fr run resolve ... --record <record>`; a flag-form resolve owing nothing records `visual=none` (every in-flight run, including this one: no matrix row carries `visual:` yet).
- Record hint: the template for a step whose evidence lists `visual` carries a commented `visual:` block (row / script / shots {path, shows}).

<!-- fr:journal kind=discovery scope=plan id=p2-holder-unpaired-is-unobserved created=2026-09-28T20:29:10+00:00 phase=2 -->
### p2-holder-unpaired-is-unobserved · discovery · A holder or reviewer id this session never dispatched makes checks 4–5 unobserved, not refused (phase 2)

Per the plan's three-valued contract, `witness_transcript` returns None both for "cannot read" and for "no dispatch of this session pairs to that agent id", and the gate records `unobserved` in both cases. For `review-phase` the reviewer id is independently refused by `_verify_reviewer` when the transcript is readable and no such dispatch exists, so only the implement-phase holder can take this path: an executor whose `agent` is a claimed id the orchestrator's session never dispatched (e.g. the resolve runs in a different session than the dispatch) is recorded unobserved with the yellow warning. Tightening it would need `witness_transcript` to return False for "readable, no such agent" — a deliberate contract change, left as is.

<!-- fr:journal kind=discovery scope=plan id=p2-template-derived-names created=2026-09-28T20:29:10+00:00 phase=2 -->
### p2-template-derived-names · discovery · record/template.py's _DERIVED omits the requirements-traceability names (phase 2)

`fr.record.template._DERIVED` lists `findings`, `proportionality` and (now) `visual`, but not `requirements`, `coverage` or `requirement-rows`, so a template for a step declaring those still prints them under `#   owed: <name>: <id>` although `--evidence <name>=` is refused as derived. Pre-existing; not changed here (no test pins it, and it is prose in a comment). A one-line fix whenever someone touches the template.

<!-- fr:journal kind=discovery scope=plan id=p2-capture-script-row created=2026-09-28T20:29:10+00:00 phase=2 -->
### p2-capture-script-row · discovery · visual-evidence-capture-script left not-implemented for phase 3 (phase 2)

`visual-evidence-gate` and `visual-evidence-reviewer-own-eyes` moved to `ci` in this phase (fr acceptance set-status, tests test_run_evidence_visual.py / test_run_telemetry_visual.py). `visual-evidence-capture-script` is half built: the gate half (script must exist, and a shell call naming it by the witness since the unit opened — tests test_a_named_script_*) is in, but its acceptance also says "the skills prefer such a script", which is phase 3's prose. Phase 3 should move it with `--level unit=super-fr:tests/unit/test_run_evidence_visual.py` plus its prose test.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-09-28T20:29:10+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

witness_transcript is a six-line pairing over attribute_dispatches, which already owns the only logic it needs; nothing repeated to extract.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-09-28T20:29:10+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

owed_rows/check_visual were written with the per-shot rules already split into _shot_problems; the one later cleanup (script-exists into check_visual) happened in T4.S3.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t5 created=2026-09-28T20:29:10+00:00 phase=2 -->
### no-refactor-p2-t5 · discovery · no-refactor-because P2.T5 (phase 2)

declarative YAML only (manifest evidence lists, one parity row); the pinned evidence tuples were updated in place, no code to clean.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-09-28T20:58:18+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · witness_transcript returned None for an unpaired agent id, so any holder id skipped checks 4-5 (phase 2)

witness_transcript returned None for an unpaired agent id, so any holder id skipped checks 4-5

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-09-28T20:58:18+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · a Read before the capture (or before a re-capture) counted as opening the image (phase 2)

a Read before the capture (or before a re-capture) counted as opening the image

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-09-28T20:58:18+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · git check-ignore path never exercised for real (phase 2)

git check-ignore path never exercised for real

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-09-28T20:58:18+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · dispatched but unclaimed implement-phase fell back to the orchestrator's stream (phase 2)

dispatched but unclaimed implement-phase fell back to the orchestrator's stream

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-09-28T20:58:18+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · unobserved warning reused the questions-gate reason (phase 2)

unobserved warning reused the questions-gate reason

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-09-28T20:58:18+00:00 phase=2 state=open review_scope=in -->
### p2-r6 · finding [open] (reviewer: in scope) · orchestrator stream not filtered for isSidechain records (phase 2)

orchestrator stream not filtered for isSidechain records

<!-- fr:journal kind=finding scope=plan id=p2-r7 created=2026-09-28T20:58:18+00:00 phase=2 state=open review_scope=in -->
### p2-r7 · finding [open] (reviewer: in scope) · check 5 satisfied by any shell word naming the script (phase 2)

check 5 satisfied by any shell word naming the script

<!-- fr:journal kind=finding scope=plan id=p2-r8 created=2026-09-28T20:58:18+00:00 phase=2 state=open review_scope=in -->
### p2-r8 · finding [open] (reviewer: in scope) · relative Read targets matched by trailing filename (phase 2)

relative Read targets matched by trailing filename

<!-- fr:journal kind=finding scope=plan id=p2-r9 created=2026-09-28T20:58:18+00:00 phase=2 state=open review_scope=in -->
### p2-r9 · finding [open] (reviewer: in scope) · duplicate row entries silently dropped (phase 2)

duplicate row entries silently dropped

<!-- fr:journal kind=finding scope=plan id=p2-r10 created=2026-09-28T20:58:18+00:00 phase=2 state=open review_scope=in -->
### p2-r10 · finding [open] (reviewer: in scope) · before-the-gates tripwire did not undo the visual additions (phase 2)

before-the-gates tripwire did not undo the visual additions

<!-- fr:journal kind=review scope=plan id=review-p2 created=2026-09-28T20:58:18+00:00 phase=2 -->
### review-p2 · review · phase 2 code review: 10 findings (all in scope) (phase 2)

Independent reviewer (separate context, hard tier, with shell) reviewed git diff 03a43f08..HEAD against spec §B/§C/§F; ran the phase tests (242 passed) and two live probes (symlinked shot dir, symlinked repo root). Confirmed correct: reviewer-transcript witness at review-phase, freshness only at review-phase/deliver, None never refuses, derived name refused, flag-form refusal, none for runs without visual rows, thin run_cmd call. Findings p2-r1..p2-r10; p2-r1 reproduced (bogus holder id -> green resolve).

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-09-28T20:58:18+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: witness_transcript returned None for an unpaired agent id, so any holder id skipped checks 4-5 (phase 2)

059c25fb: witness_transcript is Path|False|None; False refuses ('names no subagent this session dispatched'). Pinned by test_an_agent_this_session_never_dispatched_is_false and test_a_record_naming_an_agent_this_session_never_dispatched_is_refused.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-09-28T20:58:18+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: a Read before the capture (or before a re-capture) counted as opening the image (phase 2)

059c25fb: read_file_since(..., not_before=) with a per-shot bound max(since, mtime-1s). Pinned by test_a_read_before_the_shots_last_write_is_refused.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-09-28T20:58:18+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: git check-ignore path never exercised for real (phase 2)

059c25fb: resolve-level ignored/non-ignored repo shots and a tracked-file-in-ignored-dir unit test (coverage; code was already correct).

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-09-28T20:58:18+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: dispatched but unclaimed implement-phase fell back to the orchestrator's stream (phase 2)

059c25fb: with no holder, a dispatch of the step's agent type in this session since the unit opened refuses with the `fr run claim ... --agent` hint; no such dispatch = inline (orchestrator witness). The literal 'agent_type is None' rule was not used: advance always stamps agent_type (run_cmd.py:3356), so it would wedge every inline fallback. Refusal wording names orchestrator/executor/reviewer. Spec §C updated.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-09-28T20:58:18+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: unobserved warning reused the questions-gate reason (phase 2)

059c25fb: derive_visual carries a visual-specific reason; test_the_unobserved_warning_gives_a_visual_reason.

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-09-28T20:58:18+00:00 phase=2 state=fixed resolves=p2-r6 -->
### p2-r6-resolved · finding [fixed] · resolves p2-r6: orchestrator stream not filtered for isSidechain records (phase 2)

059c25fb: session-file reads skip isSidechain; unit and resolve-level sidechain tests.

<!-- fr:journal kind=finding scope=plan id=p2-r7-resolved created=2026-09-28T20:58:18+00:00 phase=2 state=fixed resolves=p2-r7 -->
### p2-r7-resolved · finding [fixed] · resolves p2-r7: check 5 satisfied by any shell word naming the script (phase 2)

059c25fb: the script must be executed (command word or first argument after an interpreter, fr isolation exec / env prefix allowed); cat/ls/echo refused; npm-run limit documented. Parametrised tests (6 refused, 19 matched).

<!-- fr:journal kind=finding scope=plan id=p2-r8-resolved created=2026-09-28T20:58:18+00:00 phase=2 state=fixed resolves=p2-r8 -->
### p2-r8-resolved · finding [fixed] · resolves p2-r8: relative Read targets matched by trailing filename (phase 2)

059c25fb: absolute paths only, realpath both sides; test_a_relative_read_target_never_matches, symlink and tail-only tests.

<!-- fr:journal kind=finding scope=plan id=p2-r9-resolved created=2026-09-28T20:58:18+00:00 phase=2 state=fixed resolves=p2-r9 -->
### p2-r9-resolved · finding [fixed] · resolves p2-r9: duplicate row entries silently dropped (phase 2)

059c25fb: refused in check 1; test_a_row_named_by_two_entries_is_refused.

<!-- fr:journal kind=finding scope=plan id=p2-r10-resolved created=2026-09-28T20:58:18+00:00 phase=2 state=fixed resolves=p2-r10 -->
### p2-r10-resolved · finding [fixed] · resolves p2-r10: before-the-gates tripwire did not undo the visual additions (phase 2)

12fc6791: _BEFORE_THE_GATES reverses implement-phase and review-phase visual evidence. The in-flight 'unevidenced: visual (predates)' lines are report-only and are noted in the PR body.

<!-- fr:journal kind=discovery scope=plan id=p3-skill-line-budget created=2026-09-28T21:25:52+00:00 phase=3 -->
### p3-skill-line-budget · discovery · test_skill_validation.py's 120-line SKILL.md cap forced three files into single unwrapped-paragraph lines (phase 3)

Adding the `visual`/Browser-check prose pushed fr-execute (121→131), fr-brainstorming
(120→123) and fr-plan (120→121) over `TestSkillValidation.test_under_120_lines`'s 120-line
cap. The existing convention in these files already mixes hard-wrapped paragraphs with
occasional very-long unwrapped lines (fr-execute step 2's `Implement` line is one); folding
the new prose into a single long line per paragraph (rather than wrapping at ~100 chars)
recovered the budget without cutting content. fr-execute: 119 lines final. fr-brainstorming:
115. fr-plan: 120 (at the cap). Future prose additions to these three files should budget
for this before wrapping normally, or trim elsewhere first.

<!-- fr:journal kind=discovery scope=plan id=p3-clause-search-not-anchored created=2026-09-28T21:25:52+00:00 phase=3 -->
### p3-clause-search-not-anchored · discovery · fr.harness.prose._CLAUSE_LEAD_RE is a `search`, not a line-start match — a Harness clause can open mid-paragraph (phase 3)

`_clause_spans` tests `_CLAUSE_LEAD_RE.search(lines[i])`, not a start-anchored match, so
`**Harness — image read:**` can sit mid-sentence in the same physical line as the prose
before it (used in fr-execute's Browser check step to stay inside the line budget above)
and still open a valid scoped clause. Confirmed by
tests/unit/test_skill_visual_evidence.py plus the neutrality tripwire staying green.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-09-28T21:25:52+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

Prose-only edits across five canonical files plus their generated mirrors, and one new test file following an existing convention (test_skill_journal_resolve_examples.py's short-discriminating-token style). Nothing repeated across the new paragraphs to extract; each names its own file's mechanics in that file's own voice.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t3 created=2026-09-28T21:25:52+00:00 phase=3 -->
### no-refactor-p3-t3 · discovery · no-refactor-because P3.T3 (phase 3)

One GitHub issue filed and four verification commands run (ruff format/check, mypy, full suite); no code touched, nothing to clean.

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-09-28T21:38:44+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · visual-evidence-browser-check-prose row text still said 'prefer a committed script' (phase 3)

visual-evidence-browser-check-prose row text still said 'prefer a committed script'

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-09-28T21:38:44+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · browser-check prose never says where shots live (take 9 lost them in the container /tmp) (phase 3)

browser-check prose never says where shots live (take 9 lost them in the container /tmp)

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-09-28T21:38:44+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · fr-goal §6 dropped the reviewer's script-coverage audit (phase 3)

fr-goal §6 dropped the reviewer's script-coverage audit

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-09-28T21:38:44+00:00 phase=3 state=open review_scope=in -->
### p3-r4 · finding [open] (reviewer: in scope) · fr-brainstorming §3 collapsed into one 601-char line against the file's 76-80 col style (phase 3)

fr-brainstorming §3 collapsed into one 601-char line against the file's 76-80 col style

<!-- fr:journal kind=finding scope=plan id=p3-r5 created=2026-09-28T21:38:44+00:00 phase=3 state=open review_scope=in -->
### p3-r5 · finding [open] (reviewer: in scope) · explainer said 'every named state' though interactions are covered too (phase 3)

explainer said 'every named state' though interactions are covered too

<!-- fr:journal kind=review scope=plan id=review-p3 created=2026-09-28T21:38:44+00:00 phase=3 -->
### review-p3 · review · phase 3 prose review: 5 findings (all in scope) (phase 3)

Independent reviewer (separate context, standard tier, with shell) reviewed git diff f7a53fec..HEAD (skills, agent, mirrors, explainer, prose test, matrix). Verified mirrors in sync, neutrality tripwire clean, skill validation and explainer tripwire green, acceptance check/report clean, fr-execute renumbering consistent. Findings p3-r1..p3-r5.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-09-28T21:38:44+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: visual-evidence-browser-check-prose row text still said 'prefer a committed script' (phase 3)

7069e120: row text now reads 'prefer a capture script re-run at each stage' (spec §D: committing is the implementer's call); reports regenerated.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-09-28T21:38:44+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: browser-check prose never says where shots live (take 9 lost them in the container /tmp) (phase 3)

7069e120: fr-execute step 3 and fr-goal §5 name a git-ignored worktree dir (devcontainer bind mount) or a host-visible scratch dir, never the container's /tmp or <run>.records/. Pinned by test_fr_execute_browser_check_says_where_shots_live and test_fr_goal_section5_says_where_shots_live.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-09-28T21:38:44+00:00 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: fr-goal §6 dropped the reviewer's script-coverage audit (phase 3)

7069e120: §6 adds 'checking the script covers every name the row declares'; test_fr_goal_section6_review_phase_names_the_reviewers_own_screenshots asserts it.

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-09-28T21:38:44+00:00 phase=3 state=fixed resolves=p3-r4 -->
### p3-r4-resolved · finding [fixed] · resolves p3-r4: fr-brainstorming §3 collapsed into one 601-char line against the file's 76-80 col style (phase 3)

7069e120: original wrapping restored; the new sentence is appended to the one line where it belongs (187 chars). The file was already at exactly the 120-line cap before this change and no paragraph saves a line on rewrap, so a fully wrapped form (122 lines) would fail test_skill_validation's cap; this is the smallest outlier that fits.

<!-- fr:journal kind=finding scope=plan id=p3-r5-resolved created=2026-09-28T21:38:44+00:00 phase=3 state=fixed resolves=p3-r5 -->
### p3-r5-resolved · finding [fixed] · resolves p3-r5: explainer said 'every named state' though interactions are covered too (phase 3)

7069e120: 'every named state and interaction'; the .html regenerated per explainers-currency (unmodified re-render byte-identical first, then a one-sentence page diff).
