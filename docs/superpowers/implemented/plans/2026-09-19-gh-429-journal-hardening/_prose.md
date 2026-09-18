# #429 journal hardening

Spec: `docs/superpowers/specs/2026-09-19-gh-429-journal-hardening-design.md`

## Approach

The change preserves the append-only resolution model. One agentic phase first
pins the externally visible failures and then applies the smallest shared
validation and parser changes needed to make every reader or mutation safe.

## Verification

Run the focused command and model tests, formatter and lint, then the relevant
journal suite. The deliver step will run the full suite and verify the journal
gate is clean.
