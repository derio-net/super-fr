# Acceptance and journal state updates -- design

Status: draft (fr-goal, 2026-09-18)
Branch: `feat/acceptance-journal-state-updates`
Issues: #429; closes duplicate #431.

## 1. Goal

Give the two durable-state CLIs an explicit, schema-validated way to record
normal lifecycle transitions. An agent must never hand-edit an acceptance
matrix or journal entry merely because evidence arrived or a finding was
resolved.

After this change:

- `fr acceptance set-status <id> --status <status> [--note <text>]` changes
  one existing row's status. `--note` appends a distinct note to its existing
  `notes` rather than replacing evidence already recorded.
- `fr acceptance add-level <id> --level <level>=<repo>:<path>` adds validated
  evidence to one existing row. Repeating an already-present level reference
  is a no-op, so retried agent commands do not duplicate evidence.
- both acceptance mutations regenerate the committed report set by the same
  best-effort policy as `add`: a successful matrix update is retained and a
  report-render problem gives an actionable warning.
- `fr journal update --scope <scope> --slug <slug> --id <id> --state
  open|fixed|refuted [--note <text>]` rewrites exactly one existing finding,
  preserving its immutable identity and creation context while appending the
  supplied resolution note to its body.
- `fr journal add --id` remains create-only. A duplicate ID exits non-zero and
  names `fr journal update`, replacing its current silent no-op.

## 2. Scope and non-goals

This is an update surface, not a general editor. Acceptance updates do not
change a row's capability, acceptance statement, origin, or arbitrary notes;
journal updates do not revise a title, kind, phase, created stamp, or
non-finding entry. Neither command introduces a new artifact shape, so no
artifact schema stamp or migration changes.

Existing `fr acceptance add` duplicate-ID rejection is retained. The explicit
verbs make creation and transition unambiguous, avoid accidentally replacing
an established row through a command intended to add a new one, and preserve
the matrix's textual header/comments.

## 3. Design

### A. Acceptance mutations

Implement the commands alongside `add` in `acceptance_cmd.py`. Load and
validate the matrix first, locate the row by ID, validate requested statuses
and references through the existing `Row` and ref grammar, then write a
validated replacement matrix without losing its human header comments. The
small command-local serialization helper serves `add`, `set-status`, and
`add-level`; every mutation reloads the file before regenerating reports.

`set-status` writes the requested status even when it is unchanged. With a
note it appends the note on a new line, avoiding loss of the prior backfill
reason. `add-level` adds the ref to the selected verification-level sequence
only when absent. Unknown rows, malformed level syntax, invalid level keys,
invalid statuses, and invalid refs exit 2 without touching the matrix.

### B. Journal finding updates

`update` resolves the active-or-archived journal read path, parses it
fail-closed, finds the requested ID, and rejects a missing ID or a non-finding
entry. It produces replacement text by serializing every parsed entry, with
the target entry copied with the new state and, if supplied, the appended
note. This canonicalizes entry blocks but retains their ordering and the
journal's leading title/preamble.

The state option is required: changing a finding state is the command's
purpose. An unchanged state is allowed for a note-only progress record. Parse
or validation failures leave the original file intact. Updating an archived
journal edits that journal rather than creating a new active twin.

## 4. Tests

Add focused CLI tests proving:

1. acceptance status promotion, note preservation, level addition and retry
   de-duplication, invalid/missing targets leaving the matrix unchanged, and
   report synchronization after each mutation;
2. journal state transition updates both serialized representations, appends a
   note, makes `journal check` clean, rejects unknown/non-finding IDs, and
   makes duplicate `add --id` fail loudly without changing the file;
3. the public skills/rules that direct agents to promote acceptance evidence
   and resolve review findings name the new commands.

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| 2026-09-18-acceptance-journal-state-updates | `derio-net/super-fr` | `2026-09-18-acceptance-journal-state-updates` | — |

## 5. Test Plan

1. `uv run pytest tests/unit/test_acceptance_status_add.py tests/unit/test_journal_cmd.py -q`
2. `uv run ruff format packages/fr/src tests/unit` then `uv run ruff check packages/fr/src tests/unit`
3. `uv run pytest -q --no-cov`
4. `uv run fr acceptance check` and `uv run fr journal check --scope plan --slug 2026-09-18-acceptance-journal-state-updates`
