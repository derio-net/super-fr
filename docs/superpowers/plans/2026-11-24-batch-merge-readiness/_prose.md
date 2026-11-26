# Batch merge readiness — plan

Spec: `docs/superpowers/specs/2026-11-24-batch-merge-readiness-design.md`.

Four agentic phases, one per ask:

1. **Delivered from the cursor, one readiness function** (R1-R5, R12) — facts gain the cursor's read status (schema 17), `fr.triage.readiness.batch_readiness` decides every verdict, and the queue's `_ready` and the driver's `_member_reports` return its `admits`. This closes #1578's merge hole; it is the skeleton and the risky change (the gate every merge passes), so it is `hard`.
2. **The Batches page** (R4-R8) — close-out, archive and export verdicts (`other_readiness`, `QueueSnapshot.refused`) and the card that leads with the verdict, from the same plan the queue merges by (#1581).
3. **gc keeps a running run** (R9) — a guard in `_reap_or_classify` only; `down` unchanged.
4. **A minimal fr-debugging workflow** (R10, R11) — the shipped shape, the `debug` artifact, the debug journal's readers, and the skill driving the run; super-fr#1655 keeps stations and staffing.

Phases 2-4 each depend on phase 1 only. The repo declares `tests: ci`; each executor runs the fast tier last.
