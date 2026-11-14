# A `local` acceptance status — implementation plan

Spec: `docs/superpowers/specs/2026-11-14-acceptance-local-status-design.md` (issue #1453).

Phase 1 builds the vocabulary and every reader: the `local` status and its stamp, the
fold's stamp rules, `local_debt`/`local_error` in `fr.acceptance.local`, the writers'
refusals, the renderers and `stamp_local`, the fragment kind 1 → 2, and the debt surfaces.
Phase 2 is the one writer of stamps, `deliver`, plus the leftover offer, the candidate
scenario and the docs. Phase 2 is `hard` because it inserts a write into deliver's gate
sequence, between refusals that every run relies on.
