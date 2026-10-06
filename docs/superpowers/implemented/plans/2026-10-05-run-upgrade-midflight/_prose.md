# Run upgrade mid-flight — implementation plan

Spec: `docs/superpowers/specs/2026-10-05-run-upgrade-midflight-design.md` (super-fr#891).

Three agentic phases, one per independently reviewable ask:

1. **Reshape + read** (R1–R4) — the skeleton: a pure `fr.run.reshape` plus the
   `fr run reshape` command, the drift message pointing at it, and the read-only commands
   answering a drifted cursor with a warning. This alone finishes the commonest stranded run
   (a step added after the cursor).
2. **Historical review evidence** (R7–R9) — `reviewer=historical` by hand, adoption inferring
   it from the plan journal, and its reporting (status/check, PR body section required when
   rendered). Tier `hard`: it changes the review evidence gate every run relies on.
3. **`adopt --supersede`** (R5–R6) plus the prose (R10) — carry-forward builds on phase 2's
   inference (carried units are applied after it), so it comes last.

No artifact shape change: `reviewer: historical` is a value in `UnitRecord.evidence`, and
reshape/supersede rewrite cursors within the existing model.
