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
