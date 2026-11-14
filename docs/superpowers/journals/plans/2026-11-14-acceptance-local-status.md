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
