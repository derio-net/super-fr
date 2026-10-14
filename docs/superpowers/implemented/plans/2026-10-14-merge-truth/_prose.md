# Post-merge truth: labels, claims and archive PRs after a batch merges

Spec: `2026-10-14-merge-truth-design.md`. Batch `merge-truth`. There is one PR on `feat/batch-merge-truth` (#1196).

## Phases

1. **Closed issues settle** (R1–R6, R15, standard, skeleton). This phase does the following:
   - Collect reads closed hits under either label.
   - A new `settle_closed` writer releases this scope's own marker and removes both labels.
   - `claim sync` and every drive pass settle `stale` and `release-pending` entries.
   - Closed members are no longer refreshed.
   - `clean-labels` removes both labels.
   - The copy and the board note say what clears the set.
   - `claim take` records first.
   - `scope retire` updates the stored facts.

   Two fake-forge scenarios prove the settle and the retire → check → sync path. This phase closes #1190.1/.3/.4, #1161 and #1160.
2. **Archive PRs** (R7–R12, hard). This phase does the following:
   - Archive PRs found by head get live checks, and linked ones are found.
   - Closing repos are read every pass.
   - Waiting lines are printed, and they are never misfiled as failing-CI Needs.
   - The board names the PR.
   - Drafts are marked ready, then merged.
   - Conflicting archive PRs are handed back to the close-out, through a new `archive_conflict` judgements event (schema 10). The PR then goes under Needs you now with a recorded stop. Conflicting export PRs go straight there.

   This phase closes #1172 and #1190.2.
3. **Drive robustness** (R13, R14, standard). An unresolvable default branch holds the repo instead of aborting the pass. A test pins that `wait_out` renewal spends no GraphQL. This phase closes #1176 and #1178.

No member issue is a phase `tracking_issue`: the batch's claim and label lifecycle belongs to triage, not to the bridge.

## Notes for executors

- `fr` is always `uv run fr` inside this worktree.
- Long suites go to a log with a shell redirect. Run targeted tests per step, and the full suite only last.
- Judgements schema 10 (phase 2): another open PR may also claim 10. If that happens, the later merge renumbers.
- After editing `plugins/super-fr/skills/fr-triage/SKILL.md`, run BOTH `scripts/sync-opencode.py` and `scripts/sync-hermes.py`.
