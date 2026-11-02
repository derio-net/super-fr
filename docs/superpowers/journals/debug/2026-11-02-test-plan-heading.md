<!-- fr:journal-schema=3 -->
# Journal: 2026-11-02-test-plan-heading

<!-- fr:journal kind=repro scope=debug id=f65495f1f836 created=2026-11-02T15:15:38+00:00 -->
### f65495f1f836 · repro · A numbered '## 6. Test Plan (…)' heading is read as no Test Plan

Repro: spec with `## 6. Test Plan (post-merge, operator-driven)` and one list item. `fr.spec.test_plan_steps(text)` returns [] (no section), so `fr closeout outcome --step 1 --owed` refuses 'has no `## Test Plan` section', `fr archive` skips the R19 hold, `fr debt` lists nothing. Separately, acceptance/check.py, acceptance_cmd inventory, run/closeout.py and plan_ops self-review test `'## Test Plan' in text` (substring), which DOES match '## Test Plan (post-merge…)' but not '## 6. Test Plan' — so two readers disagree on the same spec. Live: docs/superpowers/specs/2026-07-23-hermes-agent-compat-design.md:353. Archived: ~55 near-miss headings (frozen, not touched).
