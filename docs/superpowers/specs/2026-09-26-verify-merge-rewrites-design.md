# verify-merge survives later rewrites and checks the fetched branch

## Problem

`branch_changes_present` (`packages/fr/src/fr/isolation/local.py:287`) reports a
file as landed only when every non-blank line the branch ADDED still appears in
`<base_ref>:<path>` (`_branch_change_present_in_file`, `:259`). A merge that
lands AFTER the branch's own merge and rewrites those same lines makes the file
read as `missing`, so `fr isolation verify-merge` says NOT verified for a PR
that is genuinely merged. It fails safe (a STOP), but it blocks every closeout
in a batch queue merged back to back (super-fr#665, #598).

With `.changes/` fragments (#666) a PR no longer edits version lines, but it
ADDS `.changes/<slug>.yaml`, and the release bot's next commit on the default
branch (`release: vX.Y.Z`) DELETES it after consuming it. The fragment the
branch added is then absent from `origin/<default>`, so without a fix
`verify-merge` reports NOT verified for EVERY merged PR: this is now the
dominant repro. The generated acceptance reports
(`docs/acceptance/report_*.{html,md}`) are rewritten by nearly every PR and
still reproduce the original shape too.

Third repro, found live 2026-09-26 on a merged, clean, fully-pushed workspace
(`feat/batch-container-git-ownership`, PR #694 merged, housekeeping #701
merged): `fr isolation down --branch <that>` refused with 9 files "not on
origin/main", and `_reap_hazard` (`:1120`) uses the same `branch_changes_present`.
A normal fr-goal closeout runs `fr archive` (`packages/fr/src/fr/archive.py`),
which `git mv`s the branch's added fr artifacts — a plan dir (`:388`), a run
cursor (`:469`), its usage capture (`:489`), a scoped journal (`:514`), a fully-
implemented spec (`:553`) — from `docs/superpowers/<kind>/…` to
`docs/superpowers/implemented/<kind>/…` on the default branch. The content is
on `origin/main`, but under a different path than the branch added it at, so
neither the whole-file fast path nor the per-line/blob fallback (design §A)
ever looks there: the reap check does not follow the rename, and after a normal
closeout `down` refuses **every** merged feature workspace, making `--force`
routine — exactly the habit the guard exists to prevent (super-fr#598).

Second half: `LocalWorktreeDevcontainerTarget.verify_merge` (`:992`) passes
`refs=None` to `_verdict`, which then checks only the local `branch` ref
(`refs or [branch]`, `:1068`). A local branch can be stale relative to what was
pushed and merged. `verify_merge_reaped` already resolves and checks the fetched
`origin/<branch>` plus the local one via `_branch_refs` (`:1036`); the
non-reaped path does not.

## Design

### A. A rewritten file counts as landed if the branch's blob was once on the base

In `_branch_change_present_in_file`, when the per-line containment check fails,
fall back to a blob-equality check (option 1 of #598). The fallback runs on EVERY path that would otherwise return False, including the two early returns (path absent on `base_ref`, i.e. deleted later; no added lines) provided the branch itself still has the file. A branch that DELETED the file has no blob to compare, so a pure-deletion file that differs stays a STOP, as today. The file counts as landed
when `git rev-parse <branch>:<path>` equals `git rev-parse <c>:<path>` for some
commit `c` in `merge_base..base_ref` (restricted to commits touching `<path>`,
via `git rev-list <merge_base>..<base_ref> -- <path>`). That is: the branch's
exact content of the file existed on the base after the merge and was later
rewritten by another change.

Properties, all kept:

- **Fails safe.** A blob that never appeared on the base (an orphan commit
  pushed after the merge, a line that never landed) matches no `c` and stays
  `missing`. A commit that deleted the path, an unresolvable rev, or a failed
  git call reads as "no match", never as a pass.
- **Content-based, not ancestry-based**, so squash, rebase and merge-commit all
  behave the same.
- The existing whole-file fast path and per-line containment run first and are
  unchanged; the fallback only adds passes for files they reject.
- Cost is bounded to commits touching the one differing path.
- **No `.changes/` special case.** The release-bot deletion needs none: the
  fragment is on the base in the squash commit (blob equal to the branch's) and
  is deleted by a later commit, so it takes the path-absent-on-base early return
  into this same fallback and matches that squash commit's blob. A special
  case that exempted `.changes/*.yaml` would also wave through a fragment that
  never landed, so it is deliberately not added. Rebase and multi-commit
  merges keep the final blob of the file on the base too; a fragment reworded
  during the merge (blob differs) reads as missing, i.e. a safe STOP.

### C. An archived fr artifact counts as landed at its `implemented/` path

`fr.archive`'s five move rules are a closed, path-shaped mapping — every
destination is the source path with `implemented/` spliced in right after
`docs/superpowers/`: `plans/<dir>/…` → `implemented/plans/<dir>/…`,
`specs/<file>` → `implemented/specs/<file>`, `journals/<scope-dir>/<file>` →
`implemented/journals/<scope-dir>/<file>`, `runs/<id>.yaml` →
`implemented/runs/<id>.yaml`, `usage/<id>.yaml` → `implemented/usage/<id>.yaml`
(confirmed by reading `archive.py`: `_git_mv` only, never a content rewrite —
the move never edits the bytes it relocates). A small local helper
(`_archived_path` in `packages/fr/src/fr/isolation/local.py`, not imported from
`fr.archive` — `test_import_direction.py` has no rule against `isolation`
importing `archive`, but this module already avoids depending on the archive
command, so the five-kind mapping is a local constant instead) derives the
alternate path from that closed set; nothing outside it (a plain `docs/**` file,
a path already under `implemented/`) gets one.

When a changed path differs on `base_ref` (or is entirely absent there — the
common case: the branch's original path no longer exists on `origin/main` once
archive has moved it), `_branch_change_present_in_file` now checks BOTH the
same-path landed test (design §A, unchanged) and, only if that fails and the
path is one of the five archived kinds, the identical test — per-line
containment, falling back to blob equality — against `<base_ref>:<archived
path>`. Containment rather than requiring exact blob equality on the archived
side too: a closeout commonly appends a line (a journal resolution, a cursor
advance) on top of the branch's own content before `fr archive` moves it, so
the archived blob is a superset of what the branch added, not byte-identical
to it — the same reason design §A's own per-line check exists.

Why exact-blob-or-containment is the smallest safe choice, not a broader
`docs/**` exemption: a `docs/**` exemption would wave through ANY doc edit that
never landed, as long as some `implemented/` doc happens to exist; restricting
to the five kinds and requiring the branch's own content (by line or by blob)
to be positively present at the archived path keeps the same soundness as §A —
a path with no matching archived file, or one whose content differs, stays
missing, exactly as today.

Properties, all kept:

- **Only fr's own five archived kinds get an alternate path.** A code file, or
  a doc under `docs/` that is not `docs/superpowers/{plans,specs,journals,
  runs,usage}/…`, is checked at its original path only.
- **Positive content evidence only** — same containment/blob-equality logic as
  §A, just aimed at a second candidate path. Nothing is waved through by path
  shape alone.
- **Dirty or unpushed work still hazards.** `_reap_hazard` and the down-time
  check gate on worktree cleanliness and ref resolution before ever reaching
  `branch_changes_present`; this change only widens what counts as "present"
  for one path, it does not touch those gates.
- Both callers of `branch_changes_present` on the shared code path —
  `verify_merge` and `_reap_hazard`/the down-time check (`:1706`) — gain this
  for free; there is one implementation, not two.

### B. `verify_merge` checks the fetched remote branch too

`verify_merge` resolves refs with `_branch_refs(state.branch, remote)`: fetch the
branch, then check `<remote>/<branch>` AND the local branch (both, as the reaped
path does). Consequences, per the operator's answers:

- A stale local ref can no longer decide alone; the fetched remote ref is
  checked as well.
- Unpushed local commits still refuse (the local ref is still checked), and dirty
  worktrees are unaffected (that is `_reap_hazard`, not touched here).
- `_branch_refs` runs at `repo_root` (refs are shared across linked worktrees) and raises `IsolationError` naming the branch when neither ref resolves.
- A failed fetch of the branch (e.g. GitHub deleted the merged branch) is not a
  verdict: fall back to whichever refs still resolve, as `_branch_refs` does. The
  overall `verified` still requires content present, PR `MERGED` and a successful
  default-branch fetch.

### Non-goals

- Known limit (accepted, same as the whole-file fast path): a byte-identical `.changes/<same-slug>.yaml` landed by another PR after this branch's merge-base would satisfy the fallback for that one file; every other changed file is still checked and `verified` still needs the PR `MERGED`. Line numbers cited in this spec describe `origin/main` before the fix.
- Known limit (out of scope, fails safe): if a concurrent merge edited the file elsewhere BEFORE the branch landed and a later merge then rewrote the branch's lines, no base blob equals the branch's blob and the file still reads missing (STOP).
- `isolation/scaffold.py` and `artifacts/commit.py` are being edited by another
  batch (container-git-ownership) and are not touched.
- `_reap_hazard` and the `down`-time check call `branch_changes_present`, so they
  gain fix A and fix C (both widened, safety-relevant passes, hence tested
  below); their own ref selection is unchanged.
- No exemption for `docs/**` generally, and no attempt to make `fr archive`
  itself content-rewrite-aware — the mapping is derived from `archive.py`'s
  existing move rules, not invented, and stays a closed set of five kinds.
- The verdict is not weakened: nothing turns a STOP into a pass except positive
  blob-equality evidence from the base's own history.

## Acceptance

`fr isolation verify-merge` reports a merged branch as verified when a later
merge to the default branch rewrote lines the branch added, provided the
branch's exact file content was present on the base at some point after the
merge; it checks the fetched remote branch as well as the local one; and it
(along with `_reap_hazard`/`down`) reports a branch's fr artifacts as landed
when `fr archive` has moved them to their `docs/superpowers/implemented/…`
path with matching content.

## Test Plan

- Unit (real throwaway repos): a branch adds lines to a file, is squash-merged,
  and a later commit rewrites those same lines. `branch_changes_present` reports
  present (red before the fix).
- Unit: an orphan branch content that never landed, plus a later rewrite of the
  file, still reports missing.
- Unit: a file deleted from the base after the merge counts as landed; a branch-side pure deletion stays missing.
- Unit: `_reap_hazard` reports no hazard for a branch whose lines a later merge rewrote, and still reports one for unlanded content.
- Unit: a branch adds `.changes/feat-x.yaml` plus a code file, is squash-merged,
  and a `release: vX.Y.Z` commit then deletes the fragment. `branch_changes_present`
  and `verify_merge` (PR stubbed MERGED, real origin) report present/verified
  (red against the original `local.py`: the fragment read as missing). A fragment
  that never landed on the base stays missing, and an orphan code file still reads
  missing after the fragment landed and was consumed.
- Unit: a branch adds a plan, a spec, and a scoped journal under
  `docs/superpowers/…` plus a code file, is squash-merged, then a closeout
  commit on main appends a line to each doc and `git mv`s it to its
  `implemented/` path. `branch_changes_present` and `verify_merge` (PR stubbed
  MERGED, real origin) report present/verified; `_reap_hazard` reports no
  unlanded-content hazard. Guards: a doc never on main under either path stays
  missing; an archived copy with different content stays missing; an orphan
  code file that never landed stays missing even though the docs were
  archived; a non-fr `docs/**` file gets no archive alternate and stays
  missing when absent; a dirty worktree still hazards even with everything
  else archived and landed (red against the original `local.py`).
- Unit: `verify_merge` raises `IsolationError` when neither ref resolves.
- Unit: `verify_merge` with a stale local ref and an advanced fetched
  `origin/<branch>`, and with an unpushed local commit, refuses; a deleted remote
  branch falls back to the local ref.
- Update the acceptance matrix with one row for this behaviour, status `ci`.
- Full test suite, `ruff`, `mypy`.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-26-verify-merge-rewrites | `derio-net/super-fr` | `2026-09-26-verify-merge-rewrites` | — |
