<!-- fr:journal-schema=4 -->
# Journal: 2026-11-16-placement-truth

<!-- fr:journal kind=repro scope=debug id=repro-1438 created=2026-11-16T18:18:16+00:00 -->
### repro-1438 · repro · Quiet/stealth plan with no nameable product checkout parses with repo_root = fr worktree, unmarked

parser.py:302 'product_checkout_for(layout, repo_root) or repo_root'. Repro: a quiet plan whose workspace is gone (no FR_REPO_ROOT, cwd outside any workspace): Plan.repo_root is the fr worktree toplevel and nothing on Plan says the checkout could not be named. The candidate lookup (paths.py:170) re-runs space_for per recorded workspace on every parse.

<!-- fr:journal kind=repro scope=debug id=repro-1433 created=2026-11-16T18:18:18+00:00 -->
### repro-1433 · repro · A refused quiet fr push leaves the head it never pushed recorded in HEADS on local fr

git_policy/product.py:105 _record_pushed_head commits HEADS on local fr, then atomic_push runs; when the remote refuses the push (e.g. a pre-receive hook on the feature branch), the record commit stays on local fr and the next fr push publishes it.

<!-- fr:journal kind=hypothesis scope=debug id=hyp-one-cause created=2026-11-16T18:18:19+00:00 -->
### hyp-one-cause · hypothesis · Both members share one root cause

Batched as one root cause.
