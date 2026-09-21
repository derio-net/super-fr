# Journal Hardening for #429

## Problem

`fr journal add` treats a supplied duplicate `--id` as a silent successful no-op. That
looks like an update succeeded even though the journal remains unchanged. In addition,
an invalid journal scope reaches `_SCOPE_DIR` and raises an unhandled `KeyError`, and a
hand-edited journal containing duplicate entry ids lets one resolution ambiguously affect
more than one entry.

## Design

Keep `add` create-only and keep `resolve` append-only. A duplicate `add --id` exits 2,
names the id, and directs the caller to `fr journal resolve`; it must not write the file.

Validate `spec`, `plan`, and `debug` before every command resolves a journal path. An
invalid scope exits 2 with the existing concise validation wording instead of a traceback.

`parse_journal` will reject a repeated entry id with `JournalParseError`. Every
fail-closed command that parses a journal therefore refuses before writing or reporting a
misleading state. `render` retains its intentional fail-open behavior for malformed input.

## Acceptance

- A duplicate `fr journal add --id` exits 2, explains that the id already exists, and
  leaves the journal byte-identical.
- Every journal command receiving an invalid scope exits 2 without a traceback.
- Parsing a journal with duplicate entry ids fails; `resolve` does not append to it.

## Implementation Plans

| Plan | Repo | File | Depends on |
| --- | --- | --- | --- |
| `2026-09-19-gh-429-journal-hardening` | `derio-net/super-fr` | `2026-09-19-gh-429-journal-hardening` | None |

## Test Plan

Post-merge, operator-driven: run the focused journal command and model tests, then create
a throwaway journal and confirm duplicate add, invalid scope, and duplicate parsed-id
commands fail without modifying it.
