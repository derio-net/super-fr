# UI evidence is visual — implementation plan

Spec: `docs/superpowers/specs/2026-09-28-ui-visual-evidence-design.md` (closes super-fr#779).

Three phases, serial:

1. **Skeleton — data shapes.** The `visual` field on an acceptance row (`Visual{states, interactions}`),
   the `visual` record section (`VisualEvidence{row, script, shots[{path, shows}]}`), the acceptance
   CLI flags, and the two stamp-only migrations (matrix 2→3, record 3→4), dogfooded with
   `fr migrate artifacts --yes`. Nothing enforces anything yet, and no row in this repo carries `visual`.
2. **The gate.** Two transcript predicates (`read_file_since`, `shell_named_since`) and
   `witness_transcript` in `fr.run.telemetry`; a pure `fr.run.visual` (owed rows, checks 1–3);
   the derived `visual` evidence in `fr run resolve` (checks 4–5 against the owing agent's
   transcript, `unobserved` where none is readable); the shipped `fr-goal.yaml` declaring it on
   implement-phase, review-phase and deliver; the parity row. Tier `hard`, because the witness
   selection (holder / reviewer / orchestrator) and the three-valued transcript contract are
   where a subtle bug would pass silently.
3. **Prose.** The browser-check step in fr-execute, the executor agent, fr-goal §1/§5/§6/§8,
   fr-brainstorming §3 and fr-plan; both mirror generators; the explainer paragraph and its
   regeneration; the OpenCode follow-up issue; the full suite.

The live-run row (`visual-evidence-live-run`) is `verify: post-merge`: no phase advances it.
No member issue is a phase `tracking_issue` (the batch's delivery rules).

Risk: PR #786 (requirements grammar) touches `fr/requirements.py`'s quote handling. This plan
only *calls* `rows_citing` from it, so a rebase conflict there is unlikely.
