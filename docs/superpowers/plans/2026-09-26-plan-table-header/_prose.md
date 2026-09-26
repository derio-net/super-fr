# plan-table-header plan

Implements docs/superpowers/specs/2026-09-26-plan-table-header-design.md (gh#603).
Phase 1 unifies the header definition and makes every table error name it (walking
skeleton: exercises the test loop on the smallest change). Phase 2 makes `create`
append the missing section and shares the helper with `migrate`. Phase 3 bumps to 4.23.1,
flips the acceptance rows and runs the full gate.
