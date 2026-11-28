# Plan: isolation gc moves to a GcSweeper collaborator (#1521)

One agentic phase. The spec (`2026-11-27-isolation-gc-sweeper-design.md`) lists exactly which
fourteen methods move from `LocalWorktreeDevcontainerTarget` to `GcSweeper` in
`fr/isolation/gc.py`, which stay because `HostWorktreeTarget` overrides them or other target
methods use them, and the nine test call sites that change their receiver.

The order is: a failing test that tells the two target classes apart through the sweeper;
the move itself (receivers rewritten only); the test receivers; then the guards, the budget,
the change fragment and the docs stamp. No behaviour changes, so every other gc test is the
preservation contract and must pass unchanged.
