# Journal: 2026-09-29-acceptance-init-commit

<!-- fr:journal kind=repro scope=debug id=repro-dirty created=2026-09-29T11:09:50+00:00 -->
### repro-dirty · repro · acceptance init leaves its writes uncommitted and reports .gitignore as created

Take 10 (#817) runs A and B, fr 4.35.0, GitLab, ci: none. `fr acceptance init` created .claude/rules/acceptance-matrix.md and appended to an existing .gitignore; the brainstorm resolve committed only docs/, so the worktree stayed dirty until closeout stashed both paths (A). B was clean only because the orchestrator committed them by hand. Output printed `created .gitignore` for an existing file (acceptance_cmd.py:644).

<!-- fr:journal kind=root-cause scope=debug id=rc-init-uncommitted created=2026-09-29T11:09:53+00:00 -->
### rc-init-uncommitted · root-cause · init is the one fr writer that bypasses commit_records

Every record-writing command commits exactly the paths it wrote through fr.records_commit.commit_records (gh#610). `init_cmd` writes up to seven files (matrix, rule, CI file, three reports, .gitignore) and commits none of them. The next `acceptance add` / resolve commits only the paths IT wrote (matrix + reports), so the rule file and .gitignore are orphaned in the tree. Separately, `InitOutcome` has only created/skipped, so the one file init edits (.gitignore, via _append_gitignore_line) is filed under `created`.
