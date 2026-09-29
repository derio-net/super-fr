# Spec review checks fidelity and invention — implementation plan

Spec: `docs/superpowers/specs/2026-09-29-spec-fidelity-invention-design.md` (super-fr#773).

Two agentic phases, one per independently reviewable ask:

1. **The check itself (R1–R4).** A new `fr/fidelity.py` verifies the reviewer's
   `requirement-fidelity` clause partition and `design-inventory` block. It is
   wired as the `fidelity` derived evidence on `spec-review` (four `run_cmd.py`
   tables, both manifest copies), which also enforces remove-only: a flagged
   finding closes `fixed` or `refuted`. `unconfirmed` is retired for new writes.
   This phase is the skeleton, and its first task is the smoke: a sound review
   yields the evidence line. Tier `hard`, because the partition and the
   fence-aware parser are where the subtle bugs live.
2. **What the operator sees (R5–R7).** The `delegated=true` decision token and
   the record 4 → 5 bump, the PR body's delegated list and `## Design
   inventory`, then the reviewer and skill prose, both mirror syncs and the
   explainer regeneration.

The live row `spec-fidelity-live-invention-caught` is `verify: post-merge`
(Test Plan 8, take 10). It is not a phase.
