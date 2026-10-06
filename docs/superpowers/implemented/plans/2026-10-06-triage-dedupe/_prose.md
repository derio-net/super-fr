# Triage owns duplicates — plan

Spec: `docs/superpowers/specs/2026-10-06-triage-dedupe-design.md` (super-fr#971).

One agentic phase: the change is one ask (triage finds and records duplicates), and every surface it touches —
model, engine, check, board, driver, skill — is small and reads against one spec. Tasks follow the spec's design
sections in order, so each one lands green before the next builds on it: the model first (everything reads
`duplicate_of`), then the pure candidate engine with the live-captured calibration fixture as its recall test,
then the check sets and collect's view list, then the two presentation surfaces (board, driver), then the skill
and release bookkeeping.

Do not name super-fr#971 as a phase tracking issue: the batch's PR closes it.

The candidate thresholds are the calibrated ones in spec §2/§3.B; the scratch prototype that calibrated them is a
reference for token rules only, never copied into the repo.
