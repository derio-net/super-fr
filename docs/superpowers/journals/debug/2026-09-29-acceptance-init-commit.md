# Journal: 2026-09-29-acceptance-init-commit

<!-- fr:journal kind=repro scope=debug id=repro-dirty created=2026-09-29T11:09:50+00:00 -->
### repro-dirty · repro · acceptance init leaves its writes uncommitted and reports .gitignore as created

Take 10 (#817) runs A and B, fr 4.35.0, GitLab, ci: none. `fr acceptance init` created .claude/rules/acceptance-matrix.md and appended to an existing .gitignore; the brainstorm resolve committed only docs/, so the worktree stayed dirty until closeout stashed both paths (A). B was clean only because the orchestrator committed them by hand. Output printed `created .gitignore` for an existing file (acceptance_cmd.py:644).
