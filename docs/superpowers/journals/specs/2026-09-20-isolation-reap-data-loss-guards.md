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
