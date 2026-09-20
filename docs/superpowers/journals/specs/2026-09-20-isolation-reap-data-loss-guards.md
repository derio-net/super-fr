# Journal: 2026-09-20-isolation-reap-data-loss-guards

<!-- fr:journal kind=decision scope=spec id=d1 created=2026-09-20T13:02:08 -->
### d1 · decision · Dirty = any `git status --porcelain` output, tracked and untracked alike

Operator answer, batched Q&A. Matches `_merged_by_content`'s existing check exactly, ending the asymmetry at its source. #435's own lost work included a newly-authored (untracked) phase file, so an `--untracked-files=no` spelling would not have saved it. Ignored files (.venv, .fr-isolation, __pycache__) never appear in --porcelain and so cannot wedge the sweep.

<!-- fr:journal kind=decision scope=spec id=d2 created=2026-09-20T13:02:09 -->
### d2 · decision · #467's 'ahead of its remote' is spelled content-based against origin/<default>, not @{upstream}

Operator answer, batched Q&A. GitHub's auto-delete-branch means a merged workspace usually has NO remote branch left, so an `@{upstream}..HEAD` count would go silent in exactly the shape that fired #467. Reusing `branch_changes_present` asks the better question — is anything on this branch not yet on origin/<default> — is squash-safe, and additionally catches a commit PUSHED after the merge (the #320 orphan). Accepted cost: conservative, so a pure-deletion branch can read as un-landed and warn until --force.

<!-- fr:journal kind=decision scope=spec id=d3 created=2026-09-20T13:02:09 -->
### d3 · decision · No salvage ref; refusal is the whole fix — and --force is operator-requested-and-informed only

Operator answer, batched Q&A, with an addition: 'force should only be used by the agent if the operator has requested it AND has been informed'. So #435's refs/fr-salvage fallback is out (it was offered only for the case where reaping stays unconditional, which this change ends), but the answer adds a PROSE obligation beyond the code — the fr-isolation skill must state that an agent may not reach for --force on its own initiative, and must name what would be destroyed before asking.

<!-- fr:journal kind=decision scope=spec id=d4 created=2026-09-20T13:02:09 -->
### d4 · decision · Post-merge Test Plan: reproduce #435 and #467 live, then a host-wide dry-run sweep

Operator answer, batched Q&A. Stage a dirty merged workspace and a merged workspace holding a local-only commit, confirm each refuses with the named message, then run `fr isolation gc --dry-run` across the real host to confirm genuinely-merged clean workspaces still report would-reap. The last item is the only one a fake-runner unit test cannot cover: it is the false-refusal regression that would turn gc into a permanent warner.

<!-- fr:journal kind=review scope=spec id=r1 created=2026-09-20T13:06:11 -->
### r1 · review · Spec cited ExternalContainerTarget; the class is ExternalTarget, and it is standalone

Verified against packages/fr/src/fr/isolation/external.py:54. The substance held (external mode never reaps) but the reason was stronger than stated: ExternalTarget is NOT a subclass of LocalWorktreeDevcontainerTarget, so it never reaches the guarded `_down_worktree_tail` at all. Rewritten as 'structurally out of scope, not merely untouched'.

<!-- fr:journal kind=review scope=spec id=r2 created=2026-09-20T13:06:11 -->
### r2 · review · Line anchors were approximate; re-derived against the worktree HEAD

A spec that says 'verified live' owes exact anchors. Corrected: _down_worktree_tail 564→554, _merged_by_content's status check 810→812, the --force docstring claim 552→548. local.py:696 / 178 / 498 and isolation_cmd.py:478 were already right.

<!-- fr:journal kind=review scope=spec id=r3 created=2026-09-20T13:06:12 -->
### r3 · review · Reusing verify_merge for the content guard would add a second host-CLI call per candidate

The original §3.3 said '`verify_merge` already wraps it with the fetch' — true, and the wrong reuse. verify_merge is fetch + branch_changes_present + self._pr(state), and that third call shells out to gh/glab/tea. gc already made exactly that call at local.py:694 to classify the workspace, so reusing verify_merge buys a second round trip per reap candidate on a HOST-WIDE sweep, to recompute a PR state the caller is holding — and then discards `verified`, which the PR-less merged-by-content path can never satisfy anyway. Design now has _reap_hazard do fetch + branch_changes_present directly.

<!-- fr:journal kind=review scope=spec id=r4 created=2026-09-20T13:06:12 -->
### r4 · review · gc --dry-run promises 'mutate nothing' and the content guard fetches

Unstated tension in the first draft. Resolved explicitly rather than silently: a fetch writes only remote-tracking refs, touches no workspace, and the sweep already makes a per-workspace network call (_pr_from) under --dry-run today. Skipping the fetch in dry-run was rejected — it would make the preview answer a different question from the live run, which is the one thing a preview may not do.

<!-- fr:journal kind=review scope=spec id=r5 created=2026-09-20T13:06:12 -->
### r5 · review · Missing: version bump, artifact-stamp judgement, explainers judgement

Three standing repo rules the spec had not discharged. Added §6: minor bump 4.8.0→4.9.0 (new mandatory behavior + shipped skill edit); NO artifact stamp bump, because GcAction is an in-memory value and a CLI rendering, not a persisted artifact — stated so a reviewer need not re-derive it; explainers — nothing published becomes false, but fr-isolation.html is one of the two pages with no committed .md source (explainers-currency known gap 1), so regeneration is impossible and the PR body records the omission with its cause.

<!-- fr:journal kind=review scope=spec id=r6 created=2026-09-20T13:06:13 -->
### r6 · review · WorktreeRemove-hook teardowns can now be refused — added as a named risk

`fr isolation down --worktree <path>` is how a harness exit hook reaps, and a dirty workspace now makes it exit non-zero. Judged correct rather than mitigated: an exit hook is precisely the low-attention moment #435 describes losing work in.
