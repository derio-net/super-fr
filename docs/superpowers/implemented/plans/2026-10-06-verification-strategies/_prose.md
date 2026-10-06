# Verification strategies before merge — plan

Spec: `docs/superpowers/specs/2026-10-06-verification-strategies-design.md`
(batch `verification-kinds`: #818, #822 and #959 in one PR).

## Shape

There are seven agentic phases, one per independently reviewable ask in the spec's
design sections:

1. **Strategy vocabulary** (§A, and §B's parser). The skeleton phase: it adds the
   `fr/verification` package and nothing yet consumes it. It factors the
   four-place shipped-resource lookup out of `workflow/resolve.py` so that
   strategies and shapes share it.
2. **Shape changes** (§B, §E). Matrix 3 → 4 and record 7 → 8, each with a frozen
   reader, an atomic body rewrite and the chain assertion. Every `post-merge`
   consumer moves to `is_post_merge`. The acceptance CLI gains `--issue` and
   `--walk`, and the forge command table gains the issue commands. The phase ends
   by migrating this repo's own artifacts. It is the riskiest phase, so it is
   tagged `hard`.
3. **The walk and deliver** (§C, §D). `fr verification walk`, the `walk` evidence
   (owed only when a spec chooses a pre-merge agent strategy), the
   `## Pre-merge verification owed` section, and the premature-`Closes` refusal.
4. **Awaiting-live** (§F). The label, the close-out brief and the triage set.
5. **Conflict hand-back** (§G). A structured conflict, the pure decision, the
   `SessionMessenger` protocol and the executor. Tagged `hard`, because it changes
   the drive executor's stop path that every batch passes through.
6. **Pre-release** (§H). The workflow and the command. Only `--dry-run` is
   verifiable before merge.
7. **Dogfood and docs** (§I). super-fr's `.fr/candidate-install`, one scenario per
   candidate row, skills and both mirror generators, the explainer, and the change
   fragment.

Phases 4, 5 and 6 depend only on what they read (2, 1 and 1 respectively). Phase 7
closes the plan after all of them.

## Notes for executors

- Always `uv run fr …` inside the worktree.
- After any skill edit, run BOTH `scripts/sync-opencode.py` and
  `scripts/sync-hermes.py`.
- The operator's `fr` must never change. The conftest guard (gh#683) enforces this
  in tests, and the walk asserts it at runtime.
- No member issue is a phase `tracking_issue`.
