# Journal: 2026-09-29-acceptance-init-commit

<!-- fr:journal kind=repro scope=debug id=repro-dirty created=2026-09-29T11:09:50+00:00 -->
### repro-dirty · repro · acceptance init leaves its writes uncommitted and reports .gitignore as created

Take 10 (#817) runs A and B, fr 4.35.0, GitLab, ci: none. `fr acceptance init` created .claude/rules/acceptance-matrix.md and appended to an existing .gitignore; the brainstorm resolve committed only docs/, so the worktree stayed dirty until closeout stashed both paths (A). B was clean only because the orchestrator committed them by hand. Output printed `created .gitignore` for an existing file (acceptance_cmd.py:644).

<!-- fr:journal kind=root-cause scope=debug id=rc-init-uncommitted created=2026-09-29T11:09:53+00:00 -->
### rc-init-uncommitted · root-cause · init is the one fr writer that bypasses commit_records

Every record-writing command commits exactly the paths it wrote through fr.records_commit.commit_records (gh#610). `init_cmd` writes up to seven files (matrix, rule, CI file, three reports, .gitignore) and commits none of them. The next `acceptance add` / resolve commits only the paths IT wrote (matrix + reports), so the rule file and .gitignore are orphaned in the tree. Separately, `InitOutcome` has only created/skipped, so the one file init edits (.gitignore, via _append_gitignore_line) is filed under `created`.

<!-- fr:journal kind=hypothesis scope=debug id=h-directive-rows created=2026-09-29T11:09:54+00:00 -->
### h-directive-rows · hypothesis · Process-directive rows are a separate defect, not the same root cause

Rows like basket-delivery, basket-single-phase (level unit = the plan's 01.yaml), basket-user-input-boundaries and basket-browser-check state how the pipeline must run, not what the product does. Nothing in Row, acceptance add, the record engine or the fr-brainstorming §3 guidance refuses them. Independent of init's commit gap. Detection design is open. Stopped to ask the operator per the batch's more-than-one-root-cause rule.

<!-- fr:journal kind=decision scope=debug id=d-scope created=2026-09-29T11:33:49+00:00 -->
### d-scope · decision · Operator: fix both causes in this PR; refuse directives by a structural ref rule

Asked at the more-than-one-root-cause stop. Operator chose: both (A) init commit + created/modified and (B) process-directive rows in this PR; (B) as a structural rule — a level ref into fr's own pipeline artifacts (docs/superpowers/) is refused. Enforced where rows are WRITTEN (the step-record engine every add/set-status/brainstorm record goes through), not where the matrix is loaded, so no existing matrix stops parsing and the matrix kind's current_version does not move.

<!-- fr:journal kind=finding scope=debug id=f-init-commit created=2026-09-29T11:52:21+00:00 state=fixed -->
### f-init-commit · finding [fixed] · init commits its writes and reports modified; pipeline level refs refused

Source: acceptance_cmd.init_cmd commits outcome.written via commit_records; scaffold.InitOutcome.modified (+ .written); acceptance.model.pipeline_ref_error; record/apply._acceptance_writes refuses item.levels refs under docs/superpowers/. Pinned first (red, commit on the draft PR) by tests/unit/test_acceptance_init_commit.py — 12 tests; full suite 7579 passed. Rows acceptance-init-commits-writes and acceptance-refuses-pipeline-evidence (ci). fr-brainstorming §3 names the refusal.

<!-- fr:journal kind=review scope=debug id=review-1 created=2026-09-29T11:55:50+00:00 -->
### review-1 · review · Independent adversarial review: 4 findings, 3 fixed, 1 accepted

Fixed: (1) one gitignored written path (e.g. a repo ignoring .claude/) failed the whole git add, so nothing was committed — init now drops ignored paths via git check-ignore and names them; (2) prune_stale_reports deletions were uncommitted — InitOutcome.removed, committed when tracked (untracked deletions skipped, since git add of one fails the add); (4) pipeline_ref_error bypassable by docs/./ or x/../ — posixpath.normpath. Each pinned by a test that fails without it. Accepted, no change: (3) a user's own uncommitted .gitignore edits ride along in the init commit — the same whole-file semantics every fr bookkeeping writer has. Test naming: rerun test renamed and documented as a regression guard.
