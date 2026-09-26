# verify-merge-rewrites plan

One agentic phase, debugging-first. Reproduce both defects of super-fr#665 with failing tests, then fix `branch_changes_present` (blob-equality fallback against `merge_base..base_ref`) and make `verify_merge` check the fetched `origin/<branch>` as well as the local ref. Verdict stays fail-safe; scaffold.py and commit.py are untouched. Spec: `docs/superpowers/specs/2026-09-26-verify-merge-rewrites-design.md`.
