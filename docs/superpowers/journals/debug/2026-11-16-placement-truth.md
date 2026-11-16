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

<!-- fr:journal kind=ruled-out scope=debug id=ro-one-cause created=2026-11-16T18:18:21+00:00 -->
### ro-one-cause · ruled-out · Not one cause: two independent mechanisms

1438 is a read-side substitution in parser.parse; 1433 is a write ordering in push_product_branch. No shared code. Operator chose to fix both in this one PR (asked 2026-11-16).

<!-- fr:journal kind=root-cause scope=debug id=rc-1438 created=2026-11-16T18:18:22+00:00 -->
### rc-1438 · root-cause · parse substitutes the toplevel for an unnamed product checkout and records no sign of it

The 'or repo_root' fallback is the only place the outcome None of product_checkout_for is consumed, and it discards it.
