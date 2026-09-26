# Dynamic brainstorm question rounds — implementation plan

Spec: `docs/superpowers/specs/2026-09-26-dynamic-brainstorm-question-rounds-design.md`.

fr-goal's opening Q&A stops being "one batch of at most four" and becomes one
operator gate with one question round sized to the feature, or two when the
second is announced before round 1 ends or the operator asks for it. The
brainstorm step record declares the rounds, and `fr run resolve` verifies the
declaration against the transcript.

## Phases

1. **Walking skeleton: record kind v2.** `QuestionRounds` on the record
   artifact, the `record` kind moves 1 → 2 with a stamp-only migration, and the
   template stops hardcoding `schema_version: 1` (spec-review s2). It is
   dogfooded with `fr migrate artifacts --yes` on this run's own live records,
   so every later phase resolves on a v2 record.
2. **The gate.** `answered_rounds_since` groups the transcript's question
   calls into rounds. The declaration is threaded through `apply_record` →
   `resolve_in_process` → `_resolve_body` → `_gate_provenance` (spec-review
   s1) and through three new flags, and the §3.C verdict table is enforced.
3. **The contract prose.** Every surface that states fr-goal's operator
   contract changes (spec §3.A.1), pinned by a tripwire. Then the mirrors, the
   explainer (a byte-identical re-render check first), the README, the change
   fragment and the acceptance rows.

## Why this order

Phase 2 cannot pass without phase 1's field, and phase 3's prose describes
phase 2's mechanism. Prose that ships ahead of the gate would promise a
verification that does not exist yet.
