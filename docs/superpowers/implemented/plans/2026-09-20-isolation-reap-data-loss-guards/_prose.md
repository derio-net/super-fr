# A merged PR is not permission to delete a working tree

Spec: `docs/superpowers/specs/2026-09-20-isolation-reap-data-loss-guards-design.md`
Issues: [#435](https://github.com/derio-net/super-fr/issues/435) (uncommitted work
destroyed), [#467](https://github.com/derio-net/super-fr/issues/467) (unpushed commit
destroyed).

## What this plan is actually fixing

`fr`'s gc reaps a workspace the moment its PR reads `MERGED`, and the teardown it calls
guards exactly one thing: an **open** PR. Everything else about that workspace —
uncommitted edits, a commit that never left the machine — is deleted with no prompt, no
warning, no stash, no salvage copy.

The shape of the defect is an asymmetry that is visible in a single file. The
**speculative** classifier, `_merged_by_content`, will not act on a dirty tree
(`local.py:812`). The **authoritative** path, `pr_state == "MERGED"`, does not look
(`local.py:696`). Confidence about the *classification* was silently read as confidence
about the *working tree*, and those are unrelated pieces of state.

So the plan's job is small and sharply bounded: make the authoritative path ask what the
speculative path always asked, plus the one further question that `git status` cannot
answer — is there a commit here that exists nowhere else?

## Why it is four phases and not one

Each phase adds exactly one guard, or one truthful report about a guard, and each is
independently falsifiable:

1. **Dirty worktree (#435)** — the new types, the hazard query, and the one wiring point.
   The walking skeleton, because it is where the enforcement site is chosen, and that
   choice is the design.
2. **Unlanded content (#467)** — the network-touching half, kept separate so its cost and
   its failure modes (offline, stale ref, wrong default branch) can be reasoned about
   without the local check in the frame.
3. **gc's reporting** — a refusal is a *decision*, and gc must not file it as a failure or
   promise in `--dry-run` an action the live run will refuse. Also the two places the CLI
   currently states, in prose, that an open PR is the only reason a teardown is ever
   refused.
4. **The obligation code cannot enforce**, plus the repo's standing rules — version,
   matrix, mirrors.

## The one enforcement site

Everything in phase 1 exists to justify a two-line insertion into `_down_worktree_tail`,
between the OPEN-PR guard and `_teardown_container`. That function is the single narrow
waist every reap already passes through: `fr isolation down`, `down --all`,
`down --worktree`, and both of gc's reap branches (which get there by calling
`down(state, force=False)` on a sibling Target). It is shared by the devcontainer and
host-worktree modes, which differ only in `_teardown_container`. Guarding there covers
every caller that exists and every caller not yet written.

`external` mode is not in that set and is not being guarded: `ExternalTarget` is a
standalone class that never reaches this code, and its `down` removes no worktree —
an adopted checkout belongs to its preparer.

## Two traps this plan names on purpose

**`verify_merge` is the wrong reuse.** It looks exactly right for phase 2 — fetch plus
`branch_changes_present`, already tested — and it is wrong, because it also calls
`self._pr(state)`, which shells out to `gh`/`glab`/`tea`. gc made that same call one line
before deciding to reap. Reusing it buys a second host-CLI round trip per candidate on a
host-wide sweep, to recompute a value the caller is already holding, and then throws away
the `verified` field the PR-less path can never satisfy. Phase 2 does the two steps it
needs directly, and leaves a comment saying why, because "just use verify_merge" is the
obvious-looking edit a future reader will otherwise make.

**#467's own wording would not fix #467.** It asks to refuse "when the branch is ahead of
its remote". GitHub's auto-delete-branch means that after a squash-merge there usually is
no remote branch left — `@{upstream}` does not resolve, and the check goes quiet in
precisely the shape that fired the issue. The question worth asking is not whether the
work was *pushed* but whether it *survives the deletion*, which is content against
`origin/<default>`.

## What "done" looks like

A dirty or unlanded merged workspace survives every reap path and says why, naming the
branch and the files. A clean, fully-landed one is still reaped — that second half is the
regression risk, and it has its own acceptance row and its own post-merge live check,
because a guard that never reaps has replaced a data-loss bug with a nagging one.
