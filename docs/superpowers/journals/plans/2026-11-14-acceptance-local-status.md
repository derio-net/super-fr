<!-- fr:journal-schema=4 -->
# Journal: 2026-11-14-acceptance-local-status

<!-- fr:journal kind=discovery scope=plan id=p1-local-helpers created=2026-11-14T11:06:05+00:00 phase=1 -->
### p1-local-helpers · discovery · phase 1's local helpers, for deliver's stamp (phase 2) (phase 1)

`fr.acceptance.local`:
- `level_ref_paths(row) -> tuple[str, ...]` — the sorted unique repo paths of a row's level refs; the ONE ref-path computation (a stamp's `files` keys must equal it, R5).
- `head_blobs(product_root, paths) -> dict[path, blob sha]` — one batched `git ls-tree -r -z HEAD -- <paths>`; build the stamp's `files` from it.
- `local_debt(rows, product_root, *, ci_active) -> dict[row_id, reason]` (`promote to ci` | `unstamped` | `stale: <path>`); `local_reasons(rows, product_root)` wraps it, asking `ci_active` only when a row is local — every surface calls that once per fold.
- `local_error(row, root, *, own=None) -> str | None` (own = repo name, from the fragments' `repo:`; resolved from the origin remote when omitted).
- `local_tag(row, reason)` — `local <date>` / `local, <reason>`; `fr.debt.render.status_tag(..., local=reason)`.
`fr.acceptance.edit.stamp_local(text, row_id, stamp: LocalStamp) -> str` rewrites the row block, else the latest set-status amendment of row_id; raises AcceptanceError when neither sets it local. `fr.acceptance.model.LocalStamp(at, tree, log, files)`; `Row.local`, `SetStatus.local`; fold rule in `fr.acceptance.fold._stamp_after`.

<!-- fr:journal kind=discovery scope=plan id=p1-writers-in-engine created=2026-11-14T11:06:05+00:00 phase=1 -->
### p1-writers-in-engine · discovery · local_error is enforced in fr.record.apply only; the CLI writers reach it through the engine (phase 1)

`add`, `set-status` and `amend` all write through `fr.record.apply.apply_record`, so local_error sits there (row path and the `_Amending.amend` set-status path), with the fragments' repo identity as `own`. A CLI-side copy would have had to resolve the identity from the origin remote, which a fixture or quiet checkout may not have. Every refusal is exit 2 with the fragments byte-identical (tests/unit/test_acceptance_local_writers.py).

<!-- fr:journal kind=finding scope=plan id=p1-local-reset-clears-stamp created=2026-11-14T11:06:05+00:00 phase=1 state=open review_scope=in -->
### p1-local-reset-clears-stamp · finding [open] (reviewer: in scope) · any write that sets a row local again clears its stamp, including set-status --issue (link-only) on a local row (phase 1)

Per §A a set-status amendment to `local` without a stamp clears the row's stamp, and a pending row rewritten in place is re-rendered without it. The link-only form passes the row's current status, so linking an issue to a stamped `local` row leaves it `unstamped` (debt) until the next deliver. Consistent with the spec's clear-on-reset rule; worth a decision in phase 2 (preserve the stamp when the status does not move?) or a doc line.

<!-- fr:journal kind=discovery scope=plan id=p1-docs-owed created=2026-11-14T11:06:05+00:00 phase=1 -->
### p1-docs-owed · discovery · fr docs check is stale for docs/reference/cli.md (acceptance_cmd.py, status_cmd.py) — phase 2's docs task (phase 1)

Phase 1 changed `fr acceptance status/check/summary/digest` output and `fr status`'s open count; no page was edited (docs are phase 2). `fr docs check` currently reports docs/reference/cli.md stale; phase 2 must edit or re-stamp it with the other pages R8 names.

<!-- fr:journal kind=discovery scope=plan id=p1-figures-key created=2026-11-14T11:06:05+00:00 phase=1 -->
### p1-figures-key · discovery · debt figures carry acceptance_local_debt; the board shows it as `local debt N` (phase 1)

`fr.debt.render.figures` adds `acceptance_local_debt` (AcceptanceDebt.local_debt: local rows with a reason, not already contested); `fr.triage.debt.clean_figures` keeps it as `local_debt` (0 for an older digest), and the board appends `local debt N` to the acceptance debt line. `local` itself is in LISTED_STATUSES, so the board's "Listed, not debt" line shows `local N`.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-14T11:06:05+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

the refusal is two calls to local_error beside walked_error in fr.record.apply; nothing duplicated to fold together

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-14T11:06:05+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

stamp_local reuses _row_blocks/_amendment_starts/replace_row/render_amendment_block; nothing left to extract

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-11-14T11:06:05+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

the hop is a stamp-only guard plus one validator helper; nothing to clean

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-11-14T11:19:34+00:00 phase=1 -->
### review-p1 · review · phase 1 review: 2 findings (2 in), both fixed, plus one fold crash found while testing the fix (phase 1)

A code reviewer in a separate context, read-only, checked 616aa8cb3..HEAD (packages/, tests/) against spec R1, R2, R3, R5, R7 and §A-§C, and reproduced p1-r1 on a scratch fixture. Fixes are in edfdd9ade (p1-r1, plus the unhashable stamp the new merged-path test exposed) and c61b989cb (p1-r2). ruff and mypy are clean, and 1649 targeted acceptance/record/fold/debt/triage/gatebackfill/migration tests pass.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-14T11:19:34+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · a status-unchanged write (link-only --issue, note) on a local row drops its stamp and re-runs local_error, so a fresh row becomes unstamped debt and the write is refused once the repo has CI (phase 1)

Raised by the phase 1 reviewer (record/apply.py pending Row rebuild, the merged move() set-status amendment, local_error on every local write).

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-14T11:19:34+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · no test pins that a git ls-tree failure reads as debt, and the stale reason then names an unchanged file (phase 1)

Raised by the phase 1 reviewer (acceptance/local.py head_blobs).

<!-- fr:journal kind=finding scope=plan id=p1-fold-stamp-unhashable created=2026-11-14T11:19:34+00:00 phase=1 state=open review_scope=in -->
### p1-fold-stamp-unhashable · finding [open] (reviewer: in scope) · a stamped set-status amendment is unhashable (LocalStamp.files is a dict), so the fold's Counter crashes on the first fragment deliver stamps (phase 1)

Found by the orchestrator while writing the merged-path test for p1-r1. Every fr command that folds the matrix would have raised TypeError once phase 2 stamped a merged row's amendment.

<!-- fr:journal kind=discovery scope=plan id=p1-review-handoff-p2 created=2026-11-14T11:19:34+00:00 phase=2 -->
### p1-review-handoff-p2 · discovery · For phase 2: head_blobs now returns None when git cannot read HEAD; the fold keeps an already-local row's stamp (phase 2)

- `fr.acceptance.local.head_blobs(root, paths) -> dict[str, str] | None`: None means git could not read HEAD (not a repo, no commit). `_deliver_local_stamp_plan` must refuse on None, not build a stamp with empty files.
- `fr.acceptance.fold._stamp_after(row, amendment)`: a set-status carrying a stamp replaces the row's own; one carrying none keeps an already-`local` row's stamp and leaves a row moving into `local` unstamped. `deliver` restamps via `stamp_local` (row block or latest pending set-status amendment), which replaces any kept stamp.
- `local_error` runs on a move INTO `local` only; an already-`local` row is not re-checked (like `ci`).
- `LocalStamp` hashes by value.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-14T11:19:34+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: a status-unchanged write (link-only --issue, note) on a local row drops its stamp and re-runs local_error, so a fresh row becomes unstamped debt and the write is refused once the repo has CI (phase 1)

edfdd9ade. local_error only on a move into local (both record paths); the pending path keeps existing.local while the row stays local; the fold keeps an already-local row's stamp unless the amendment carries one. Spec R5 and §A amended. Tests cover the pending link-only write, the merged link-only write, and link-only after CI appears (promote to ci, not refused).

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-14T11:19:34+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: no test pins that a git ls-tree failure reads as debt, and the stale reason then names an unchanged file (phase 1)

c61b989cb. head_blobs returns None on a git failure, and local_debt reports 'stale: HEAD unreadable' for every stamped row. Tests cover a non-repo dir and a repo with no commit.

<!-- fr:journal kind=finding scope=plan id=p1-fold-stamp-unhashable-resolved created=2026-11-14T11:19:34+00:00 phase=1 state=fixed resolves=p1-fold-stamp-unhashable -->
### p1-fold-stamp-unhashable-resolved · finding [fixed] · resolves p1-fold-stamp-unhashable: a stamped set-status amendment is unhashable (LocalStamp.files is a dict), so the fold's Counter crashes on the first fragment deliver stamps (phase 1)

edfdd9ade. LocalStamp.__hash__ hashes by value (files as sorted items). test_a_stamped_amendment_is_hashable plus the merged-path writer test fold a stamped amendment end to end.

<!-- fr:journal kind=finding scope=plan id=p1-local-reset-clears-stamp-resolved created=2026-11-14T11:19:34+00:00 phase=1 state=fixed resolves=p1-local-reset-clears-stamp -->
### p1-local-reset-clears-stamp-resolved · finding [fixed] · resolves p1-local-reset-clears-stamp: any write that sets a row local again clears its stamp, including set-status --issue (link-only) on a local row (phase 1)

The executor's open finding is the same defect as p1-r1, fixed in edfdd9ade.

<!-- fr:journal kind=decision scope=plan id=p2-stamp-plan-shape created=2026-11-14T13:05:45+00:00 phase=2 -->
### p2-stamp-plan-shape · decision · deliver's stamp is planned after the leftovers gate and written beside _flush_gate_decisions (phase 2)

`run_cmd._deliver_local_stamp_plan(repo_root, state, tests)` runs right after
`_deliver_leftovers_gate`, reading the deliver unit's verified `tests` from the
cursor (`units.evidence_of`). It finds the feature fragment at
`artifact_root(repo_root)/docs/acceptance/features/<spec slug>.yaml`, takes the rows
that fragment holds at `local` plus the rows whose latest `set-status` amendment in
it is `local`, keeps those whose effective status is `local`, and builds every stamp
in memory with `stamp_local` (refusing, exit 2, each row it cannot stamp: a witness
that is not a fresh log or `reused:`, an uncommitted code path, an unreadable HEAD,
a path not committed at HEAD). `_deliver_local_stamp_write` writes it with
`write_text_atomic` through `_remember` and `_note_record_write`, immediately before
`_flush_gate_decisions`, after `_refuse_missing_emits` and the PR gate. The witness
parsing is `_local_stamp_witness`, beside `_reuse_tests_witness`. The stamp's `at`
is the UTC date; `log` is the witness without its `;tree=` suffix.

<!-- fr:journal kind=finding scope=plan id=p2-move-into-local-level-order created=2026-11-14T13:05:45+00:00 phase=2 state=open review_scope=in -->
### p2-move-into-local-level-order · finding [open] (reviewer: in scope) · set-status --status local --level on a MERGED row was refused as having no level ref (phase 2)

`fr.record.apply._Amending.move` planned the `set-status` amendment before the
`add-level` ones, and `amend` checks `local_error` on the row after the set-status
alone, so a merged row moved into `local` with its `--level` in the same command was
always refused ("needs a level ref"). Phase 1 tested the pending-row path only.
Found by tests/unit/test_deliver_local_stamp.py::test_a_pending_set_status_amendment_is_stamped_in_place.

<!-- fr:journal kind=discovery scope=plan id=p2-tracking-none-offers-local created=2026-11-14T13:05:45+00:00 phase=2 -->
### p2-tracking-none-offers-local · discovery · under tracking none (no CI) the leftover fix now offers local before the gate (phase 2)

tests/unit/test_deliver_leftovers.py::test_under_tracking_none_only_the_gate_route_applies
asserted no `set-status` in the fix; its fixture has no CI, so R6 now offers
`set-status --status local`, which needs no tracker. The test now asserts there is no
`--issue` route, which is what it was guarding.

<!-- fr:journal kind=finding scope=plan id=p2-move-into-local-level-order-resolved created=2026-11-14T13:05:45+00:00 phase=2 state=fixed resolves=p2-move-into-local-level-order -->
### p2-move-into-local-level-order-resolved · finding [fixed] · resolves p2-move-into-local-level-order: set-status --status local --level on a MERGED row was refused as having no level ref (phase 2)

a move into local now plans its level amendments before the set-status (87627d6c9); covered by the deliver amendment test

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-11-14T13:05:45+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

the R6 fix is one conditional prefix in unaccounted, reusing _feature_flag; nothing to extract

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-11-14T13:05:45+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

a scenario script and its one-line test wiring; no production code to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t4 created=2026-11-14T13:05:45+00:00 phase=2 -->
### no-refactor-p2-t4 · discovery · no-refactor-because P2.T4 (phase 2)

docs, rule, skill text and regenerated mirrors only; no code to refactor

<!-- fr:journal kind=review scope=plan id=review-p2 created=2026-11-14T13:17:20+00:00 phase=2 -->
### review-p2 · review · phase 2 review: 4 findings (3 in, 1 out); the 3 in scope fixed in 4ef8ebf8c (phase 2)

A code reviewer in a separate context, read-only, reviewed 92257fc..HEAD (code, scenario, acceptance moves, docs) adversarially against R4, R6, R8, R9 and §C/§D. It confirmed that the stamp write follows every deliver refusal, that a refused resolve and a --record restore leave the fragment byte-identical, that the witness rules hold, that quiet placement writes and commits at the artifact root, that only this feature's rows are stamped, that the R6 command is printed only under ci none, that the move() level-order fix is correct, and that the five ci moves cite tests CI runs. It ran 28 unit tests, the scenario, fr docs check and fr acceptance check. Fixes are in 4ef8ebf8c: test_deliver_local_stamp.py, test_deliver_leftovers.py and the scenario pass (30 tests); ruff, mypy and docs check are clean.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-14T13:17:20+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · _local_stamp_plan folds the matrix before checking the feature fragment sets any row local, so a deliver with no local row runs git and can refuse in the stamp's name (phase 2)

Raised by the phase 2 reviewer (run_cmd.py _local_stamp_plan).

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-14T13:17:20+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · the fr-acceptance explainer says a stale row clears when a run delivers it again; deliver re-stamps only a row the run sets local again (phase 2)

Raised by the phase 2 reviewer (docs/explainers/fr-acceptance.md).

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-14T13:17:20+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · the scenario's fr debt check is absence-only and never shown to fail (phase 2)

Raised by the phase 2 reviewer (tests/scenarios/acceptance-local-status.sh).

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-11-14T13:17:20+00:00 phase=2 state=open review_scope=out -->
### p2-r4 · finding [open] (reviewer: out of scope) · a fresh deliver tests log is not tied to the tree it ran on, so a commit after the suite still stamps HEAD's tree (phase 2)

Raised by the phase 2 reviewer; R4 sanctions HEAD's tree at stamp time, and _verify_tests_log has never bound a fresh log to a tree.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-14T13:17:20+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: _local_stamp_plan folds the matrix before checking the feature fragment sets any row local, so a deliver with no local row runs git and can refuse in the stamp's name (phase 2)

4ef8ebf8c. The plan returns before the fold when the fragment sets no row local. test_a_fragment_with_no_local_row_never_folds fails without the fix and passes with it.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-14T13:17:20+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: the fr-acceptance explainer says a stale row clears when a run delivers it again; deliver re-stamps only a row the run sets local again (phase 2)

4ef8ebf8c. The explainer now says "until a run sets it local again and delivers", matching the rule and the reference page.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-14T13:17:20+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: the scenario's fr debt check is absence-only and never shown to fail (phase 2)

4ef8ebf8c. The scenario expects fr debt to list the fresh row as `earned [local 2026-11-14]` and, after the test edit, `earned [local, stale: tests/test_x.py]`.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-11-14T13:17:20+00:00 phase=2 state=open resolves=p2-r4 out_of_scope=true -->
### p2-r4-resolved · finding [out-of-scope] · resolves p2-r4: a fresh deliver tests log is not tied to the tree it ran on, so a commit after the suite still stamps HEAD's tree (phase 2)

Not caused by this change. deliver's fresh-log witness (_verify_tests_log) checks the writer and the time, never the tree, for every run; R4 adopts it as it is. Binding a fresh log to its tree is a deliver-wide change; to be filed at deliver.

<!-- fr:journal kind=review scope=plan id=review-lenses created=2026-11-14T13:52:17+00:00 -->
### review-lenses · review · lens review: docs-accuracy 5, errors 3, tests 5 findings, all in scope, all fixed

Three read-only reviewers, one per lens, reviewed the whole diff from merge base 616aa8cb3. docs-accuracy and errors independently found the unknown-CI fail-open (one fix). Fixes: fa950cb3b, 2c123e3c7, b1dc5c31c, 8de5630a1 (spec R3/R7), 394531162 (tests, each shown red under the reviewer's mutation and green after revert), 2fa26d493 (lint). Local-status tests 105 passed; pinned-file tests 1763 passed; ruff, mypy, fr docs check and the writing-standards check clean.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1 created=2026-11-14T13:52:17+00:00 state=open review_scope=in -->
### l-docs-accuracy-r1 · finding [open] (reviewer: in scope) · pages, rule and skill said every writer refuses local; the code refuses a move into local and keeps the stamp on a link or note write

Raised by the docs-accuracy lens reviewer.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2 created=2026-11-14T13:52:17+00:00 state=open review_scope=in -->
### l-docs-accuracy-r2 · finding [open] (reviewer: in scope) · rule and RULE_TEMPLATE said at least one / a level ref; local_error requires every level ref in this repo and resolving

Raised by the docs-accuracy lens reviewer.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r3 created=2026-11-14T13:52:17+00:00 state=open review_scope=in -->
### l-docs-accuracy-r3 · finding [open] (reviewer: in scope) · no doc named stale: HEAD unreadable; RULE_TEMPLATE omitted missing files and moved refs; DebtRow docstring listed three reasons

Raised by the docs-accuracy lens reviewer.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r4 created=2026-11-14T13:52:17+00:00 state=open review_scope=in -->
### l-docs-accuracy-r4 · finding [open] (reviewer: in scope) · fr-acceptance explainer said fr acceptance status lists a row only while debt or contested; it also lists walked and fresh local rows

Raised by the docs-accuracy lens reviewer.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r5 created=2026-11-14T13:52:17+00:00 state=open review_scope=in -->
### l-docs-accuracy-r5 · finding [open] (reviewer: in scope) · ci_active is False on a ServicesError, so a malformed fr-profiles.yaml permits local, makes R6 offer it and hides promote to ci

Raised by the docs-accuracy lens reviewer.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1 created=2026-11-14T13:52:17+00:00 state=open review_scope=in -->
### l-errors-r1 · finding [open] (reviewer: in scope) · a malformed CI declaration makes ci_active False: local rows in a CI repo never promote to ci, local_error allows them, the PR body offers local, the parse error discarded

Raised by the errors lens reviewer.

<!-- fr:journal kind=finding scope=plan id=l-errors-r2 created=2026-11-14T13:52:17+00:00 state=open review_scope=in -->
### l-errors-r2 · finding [open] (reviewer: in scope) · a malformed local stamp (empty tree/log, non-date at) reads as fresh; neither LocalStamp nor the validator checks its shape

Raised by the errors lens reviewer.

<!-- fr:journal kind=finding scope=plan id=l-errors-r3 created=2026-11-14T13:52:17+00:00 state=open review_scope=in -->
### l-errors-r3 · finding [open] (reviewer: in scope) · the 1->2 migration refusal said fix by hand without naming the fix, against the never-hand-edit rule

Raised by the errors lens reviewer.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1 created=2026-11-14T13:52:17+00:00 state=open review_scope=in -->
### l-tests-r1 · finding [open] (reviewer: in scope) · the refused-resolve-no-stamp test pinned the write only after the PR gate

Raised by the tests lens reviewer.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2 created=2026-11-14T13:52:17+00:00 state=open review_scope=in -->
### l-tests-r2 · finding [open] (reviewer: in scope) · report, digest, summary and gate-backfill reader never shown to compute local debt from a real fold

Raised by the tests lens reviewer.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3 created=2026-11-14T13:52:17+00:00 state=open review_scope=in -->
### l-tests-r3 · finding [open] (reviewer: in scope) · no test that a fresh local row is left out of fr status's open count

Raised by the tests lens reviewer.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4 created=2026-11-14T13:52:17+00:00 state=open review_scope=in -->
### l-tests-r4 · finding [open] (reviewer: in scope) · deliver refusals not committed at HEAD and git cannot read HEAD untested; a non-local tests witness never exercised through deliver

Raised by the tests lens reviewer.

<!-- fr:journal kind=finding scope=plan id=l-tests-r5 created=2026-11-14T13:52:17+00:00 state=open review_scope=in -->
### l-tests-r5 · finding [open] (reviewer: in scope) · contested plus local-debt double-count guard in acceptance_from_matrix untested

Raised by the tests lens reviewer.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1-resolved created=2026-11-14T13:52:17+00:00 state=fixed resolves=l-docs-accuracy-r1 -->
### l-docs-accuracy-r1-resolved · finding [fixed] · resolves l-docs-accuracy-r1: pages, rule and skill said every writer refuses local; the code refuses a move into local and keeps the stamp on a link or note write

b1dc5c31c: rule, reference, explainer, skill and RULE_TEMPLATE now say a MOVE to local is checked and a write that keeps a row local keeps its stamp.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2-resolved created=2026-11-14T13:52:17+00:00 state=fixed resolves=l-docs-accuracy-r2 -->
### l-docs-accuracy-r2-resolved · finding [fixed] · resolves l-docs-accuracy-r2: rule and RULE_TEMPLATE said at least one / a level ref; local_error requires every level ref in this repo and resolving

b1dc5c31c (rule, skill) and 2fa26d493 (RULE_TEMPLATE wording rewrapped): every level ref must name an existing test in this repo.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r3-resolved created=2026-11-14T13:52:17+00:00 state=fixed resolves=l-docs-accuracy-r3 -->
### l-docs-accuracy-r3-resolved · finding [fixed] · resolves l-docs-accuracy-r3: no doc named stale: HEAD unreadable; RULE_TEMPLATE omitted missing files and moved refs; DebtRow docstring listed three reasons

b1dc5c31c: every surface names all reasons (stale: <path> incl. missing file and moved refs, stale: HEAD unreadable, promote to ci, ci unknown); debt/model.py docstring too.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r4-resolved created=2026-11-14T13:52:17+00:00 state=fixed resolves=l-docs-accuracy-r4 -->
### l-docs-accuracy-r4-resolved · finding [fixed] · resolves l-docs-accuracy-r4: fr-acceptance explainer said fr acceptance status lists a row only while debt or contested; it also lists walked and fresh local rows

b1dc5c31c: the explainer describes status's walked and fresh-local lines and says 'as open' for the owed-verification sentence.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r5-resolved created=2026-11-14T13:52:17+00:00 state=fixed resolves=l-docs-accuracy-r5 -->
### l-docs-accuracy-r5-resolved · finding [fixed] · resolves l-docs-accuracy-r5: ci_active is False on a ServicesError, so a malformed fr-profiles.yaml permits local, makes R6 offer it and hides promote to ci

fa950cb3b: ci_unknown/ci_known_none; writers refuse local naming the error, R6 offers local only where fr knows there is no CI, a local row is debt as ci unknown. Spec R3 amended in 8de5630a1. Tests in test_acceptance_local_writers.py and test_deliver_leftovers.py fail without the fix.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1-resolved created=2026-11-14T13:52:17+00:00 state=fixed resolves=l-errors-r1 -->
### l-errors-r1-resolved · finding [fixed] · resolves l-errors-r1: a malformed CI declaration makes ci_active False: local rows in a CI repo never promote to ci, local_error allows them, the PR body offers local, the parse error discarded

Same defect as l-docs-accuracy-r5, fixed in fa950cb3b.

<!-- fr:journal kind=finding scope=plan id=l-errors-r2-resolved created=2026-11-14T13:52:17+00:00 state=fixed resolves=l-errors-r2 -->
### l-errors-r2-resolved · finding [fixed] · resolves l-errors-r2: a malformed local stamp (empty tree/log, non-date at) reads as fresh; neither LocalStamp nor the validator checks its shape

2c123e3c7: LocalStamp requires an ISO date, git shas for tree and files, a non-empty log; parametrised test_a_malformed_stamp_is_refused. Spec R7 amended in 8de5630a1.

<!-- fr:journal kind=finding scope=plan id=l-errors-r3-resolved created=2026-11-14T13:52:17+00:00 state=fixed resolves=l-errors-r3 -->
### l-errors-r3-resolved · finding [fixed] · resolves l-errors-r3: the 1->2 migration refusal said fix by hand without naming the fix, against the never-hand-edit rule

2c123e3c7: the refusal names both fixes (restamp schema_version 2 after a merge, or move the rows off local with fr acceptance set-status) and the migrate command to rerun.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1-resolved created=2026-11-14T13:52:17+00:00 state=fixed resolves=l-tests-r1 -->
### l-tests-r1-resolved · finding [fixed] · resolves l-tests-r1: the refused-resolve-no-stamp test pinned the write only after the PR gate

394531162: test_the_last_refusal_missing_emits_writes_no_stamp[record|flags] and test_the_exit_guard_refusal_writes_no_stamp; the flag forms fail with the write moved after the PR gate.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2-resolved created=2026-11-14T13:52:17+00:00 state=fixed resolves=l-tests-r2 -->
### l-tests-r2-resolved · finding [fixed] · resolves l-tests-r2: report, digest, summary and gate-backfill reader never shown to compute local debt from a real fold

394531162: five tests over a real no-CI repo (report, summary, digest, gate-backfill EvidenceReader, fr debt engine), each failing when its local_reasons call is replaced by {}.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3-resolved created=2026-11-14T13:52:17+00:00 state=fixed resolves=l-tests-r3 -->
### l-tests-r3-resolved · finding [fixed] · resolves l-tests-r3: no test that a fresh local row is left out of fr status's open count

394531162: test_fr_status_open_count_leaves_out_a_fresh_local_row (1 open unstamped, 0 open fresh); fails when every local row counts.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4-resolved created=2026-11-14T13:52:17+00:00 state=fixed resolves=l-tests-r4 -->
### l-tests-r4-resolved · finding [fixed] · resolves l-tests-r4: deliver refusals not committed at HEAD and git cannot read HEAD untested; a non-local tests witness never exercised through deliver

394531162: three deliver-level tests, exit 2 naming the row, no stamp; each fails under its own mutation.

<!-- fr:journal kind=finding scope=plan id=l-tests-r5-resolved created=2026-11-14T13:52:17+00:00 state=fixed resolves=l-tests-r5 -->
### l-tests-r5-resolved · finding [fixed] · resolves l-tests-r5: contested plus local-debt double-count guard in acceptance_from_matrix untested

394531162: test_a_contested_local_debt_row_is_counted_once; fails when the guard is removed.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved-2 created=2026-11-14T14:29:51+00:00 state=open resolves=p2-r4 tracked_by=derio-net/super-fr#1454 -->
### p2-r4-resolved-2 · finding [deferred → derio-net/super-fr#1454] · resolves p2-r4: a fresh deliver tests log is not tied to the tree it ran on, so a commit after the suite still stamps HEAD's tree

Real but not caused by this change (deliver's fresh-log witness has never bound a tree); filed as derio-net/super-fr#1454.
