# S1 follow-ups — implementation plan

Spec: `docs/superpowers/specs/2026-11-28-s1-followups-design.md`.

Four phases, one per ask:

1. **The gate and the Python readers** (#1698, R1-R6): `fr.config.transition.refusing()` is the one
   Python definition; old paths, the old settings copy, `fr settings sync` and the per-kind
   `FR_SHIPPED_*_DIR` variables refuse past it, the movers keep working. Skeleton: its first task
   is the smoke (the gate module and its test, CI green).
2. **The shell and TypeScript readers** (#1698, R7-R9): version sources beside every delivered copy,
   the edit-gate library and `marker.ts` drop the old forms past 9.2 while failing closed on an
   old-only switch, `validate-plans.sh` asks fr, and one test holds the three literals together.
3. **Configuration argv from the tip** (#1699, R11-R13): pin S1's whole-manifest guard; every `.fr/`
   element of a walk argv runs from the exported tip; a `kind: cli` step naming `.fr/` is refused
   under quiet/stealth.
4. **Tests, repos home, scenarios, docs** (#1700, #1701, R10's scenarios, R14-R17).

Every test of transition behaviour forces its side of the gate (R10): in-process tests monkeypatch
`refusing` or `fr.__version__`, shell/TS tests use a fixture version source, subprocess tests force
the ended side with `FR_OLD_PATHS=refuse`. A release that moves fr into 9.2 must turn none of them red.
