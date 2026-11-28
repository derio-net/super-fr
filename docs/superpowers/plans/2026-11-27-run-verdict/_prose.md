# Plan: `run_cmd.py` refuses through a typed verdict; its clusters move to `fr/run`

Spec: `docs/superpowers/specs/2026-11-27-run-verdict-design.md` (issue #1519).

Six agentic phases, one per slice of the spec, in the issue's order. Each later slice uses
the types phase 1 builds, and each earlier one shrinks the file the later ones edit, so the
phases are strictly serial.

Every phase has the same shape:

1. **Capture first.** Before a line moves, a throwaway script drives every refusal path of
   the functions about to move through the current code, with a recording console (fixed
   width, colour on), and commits the stderr bytes and exit code as fixtures. This is the
   red step: the test that compares the new module's output with the fixture cannot pass yet.
2. **Move.** The cluster moves to its `fr/run` module, its names made public. Refusals
   become `RunRefusal` or a `Verdict`, warnings go to a `warn` callable, and `run_cmd.py`
   turns each back into print-and-exit at the call site (`_refusals()`, `_settle`). So
   `derive`, `_advance_once` and `resolve_in_process` keep seeing `typer.Exit` where they do
   today.
3. **Re-point.** Importers and tests use the new module. A test that patched a moved name
   patches it where it now lives, with a fake of the new shape.
4. **Lower the budget**, stamp the docs pages `fr docs check` names, and run the quality
   gate and the fast tier last.

Phase 1 is the skeleton. Its first task is the smoke, and it lands the contract every other
phase relies on. It and phase 5 (about 2,400 lines of evidence verifiers on the
`fr run resolve` gate path) are `hard`. The rest are `standard`.
