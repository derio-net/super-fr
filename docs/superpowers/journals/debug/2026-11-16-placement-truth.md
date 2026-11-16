<!-- fr:journal-schema=4 -->
# Journal: 2026-11-16-placement-truth

<!-- fr:journal kind=repro scope=debug id=repro-1438 created=2026-11-16T18:18:16+00:00 -->
### repro-1438 · repro · Quiet/stealth plan with no nameable product checkout parses with repo_root = fr worktree, unmarked

parser.py:302 'product_checkout_for(layout, repo_root) or repo_root'. Repro: a quiet plan whose workspace is gone (no FR_REPO_ROOT, cwd outside any workspace): Plan.repo_root is the fr worktree toplevel and nothing on Plan says the checkout could not be named. The candidate lookup (paths.py:170) re-runs space_for per recorded workspace on every parse.
