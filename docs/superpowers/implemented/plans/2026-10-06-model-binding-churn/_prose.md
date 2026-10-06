# Model bindings survive provider churn — plan

Spec: `docs/superpowers/specs/2026-10-06-model-binding-churn-design.md` (super-fr#591).

Two agentic phases, one per independently reviewable ask:

1. **The engine and the operator-facing CLI** (R1–R5, R10, R12). A new package,
   `fr.bindings`, has four modules:
   - `catalogue` parses `opencode models --verbose` and keeps snapshots;
   - `probe` runs the live `opencode run` probe, classifies it as
     live/dead/unknown and caches the verdict;
   - `choose` applies the pure family → tier → provider-hint rules with the 2×
     autonomy predicate;
   - `health` holds `check_bindings`, the one entry point.

   `fr models set` probes before persisting, and `fr models check` reports and
   asks. All of it is proven with three candidate scenarios against a stub
   `opencode`. This is the skeleton phase: it ships end to end by itself.
2. **The run integration** (R6–R9, R11). `fr run start` prints its notice, and the
   gated brief gains the `dead_bindings`/`binding_offers` keys that fr-goal's
   question round reads. One pre-dispatch guard runs on BOTH dispatch paths and
   substitutes autonomously within the 2× bound, recording the substitution in the
   run journal in the same commit as the cursor. Its write order keeps the
   invariant "recorded if and only if applied". The phase also covers the skill
   sentence, the mirrors, the parity row and AGENTS.md.

   It is tier `hard`: it changes the dispatch path that every run relies on, and a
   wrong write order there produces exactly the silent substitution the issue
   forbids.

Fixtures for the probe and the catalogue are captured from the real `opencode`
CLI, never composed. The one exception is the in-catalogue "not supported" text,
which is transcribed from #591 and labelled as such.
