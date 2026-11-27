# Split plan_ops.py

Implements spec `2026-11-27-plan-ops-split-design.md` (#1518, slices 1–4) in one agentic
phase. Every move is a verbatim cut and paste in the order the spec gives (leaf error and
private I/O modules first, then the spec table, then self-review with its journal reader
and the refactor-gate read, then rework), so the tree imports cleanly after each task.
The only body change is the merged journal read. The new test `test_plan_ops_split.py`
pins the import direction and the re-exports; the rest of the suite proves the behaviour
is unchanged.
