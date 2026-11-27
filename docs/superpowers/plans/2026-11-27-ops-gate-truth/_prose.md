# Ops gate truth — implementation plan

Spec: `docs/superpowers/specs/2026-11-27-ops-gate-truth-design.md` (R1-R20). Batch `ops-gate-truth`, closing derio-net/super-fr#1617 and #1621 in one PR.

Three phases, one per ask, in dependency order:

1. **Stale ops workspace (R1-R6).** `fr/ops/refresh.py` compares the ops workspace with `origin/<default>` before stages 4-7. On the operator's confirmation it commits the gate records, merges the default branch in through a new `OpsTree.merge_commit` port, pushes leased, reopens the changed ops host-side and re-checks trust. A refresh after stage 4 sends the run back to stage 4. This is the skeleton: its first task is the smoke.
2. **Every gate walks its rows (R7-R16).** The `(rows: …)` step pointer; `row_walked`, the one rule for a walked row that the driver and the gate both read; `fr closeout outcome` walks the named rows in the same commit; `gate_items`/`gate_blockers` cover both post-merge gates, and `fr gate pass --gate tester` refuses on them; the DevOps stage asks about uncovered rows, excludes walks the PR head carries, reports what its own gate owes, and says `archive held` when the archive was held; self-review warns about an uncovered gated row.
3. **Definition of Done (R17-R20).** `fr.run.dod`, `fr run dod` (its own module, because `run_cmd.py` is at its line budget), the pickup briefs, and the gate's final line.

Tests are unit tests with the existing fake ports (`tests/unit/test_ops_gate.py`'s FakeTree/FakeHost/FakePrompt) and fixture repos. The repo declares `tests: ci`, so each phase runs its fast tier last and CI is the suite evidence.
