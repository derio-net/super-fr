# Owed trackers and archive side effects — design

Batch `owed-archive`: derio-net/super-fr#1400, #1183, #1301, #1184, delivered as one PR.

## 1. Goal

`fr` acts on the forge and on the working tree at moments when the result cannot yet
be known to stand. This change ties those side effects to the moment they become true.

- **#1400.** `fr journal resolve --state fixed` on an `owed` entry closes the entry's
  filed issue right after the local commit, on any branch
  (`packages/fr/src/fr/commands/journal_cmd.py:582-585`, `_close_owed_issue` at :746).
  If the PR that carries the resolution is abandoned, the issue stays closed and the
  owed work disappears from the forge.
- **#1183.** A refused `fr archive <plan>` (blockers, no `--force`, exit 2) still calls
  `_write_manual_owed` (`archive_cmd.py:1006-1007`) before it refuses. The owed entry is
  written and `git add`-ed (`:729-734`), with no default-branch check. The `finally` in
  `_with_followups` then runs `_owed_step`, which files it as an `fr:owed` issue.
- **#1301.** `fr archive` files forge issues (`_owed_step` :746, `file_open_ends` :695)
  and has no preview.
- **#1184.** `_existing_owed` (`archive_followups.py:467-473`) reads at most 200 open
  issues of every label. Past that it misses an existing owed marker and files a
  duplicate. `_close_owed_issue` (`journal_cmd.py`) has the same 200-issue listing.

## 2. Operator decisions (question round 1)

1. #1400: the issue closes **at merge**. Off the default branch, resolve closes nothing
   and the PR body that `deliver` renders carries a `Closes <ref>` line. On the default
   branch it closes at once, as today.
2. #1183: **a refusal writes nothing**. A plan held under `--branch` or skipped under
   `--all` still records its R22 owed entries, except when HEAD is the default branch.
3. #1301: `--dry-run` may make **forge reads only**: no file write, no git change, no
   forge write; the exit code is the one the real run would return.
4. #1184: **label filter and fail closed**: list only open `fr:owed` issues; when the
   list reaches its limit (or cannot be read), file nothing and warn. Closing reads the
   one issue by number.
5. Verification: strategy `candidate`, gate `developer`. No post-merge Test Plan rows.

## Requirements

R1. Off the default branch, `fr journal resolve … --state fixed` on an `owed` entry that has a filed issue (`filed_as`) records the discharge and makes no forge write: it closes no issue and posts no comment.
R2. In that case it prints that the issue closes when the branch merges, and the exact `Closes <owner/repo>#<n>` line to carry in that branch's PR body.
R3. On the default branch (HEAD is the local branch of the remote's default ref, `origin/main` → `main`), resolve closes the filed issue as debt-engine R24 states. When the default ref cannot be read, or HEAD is detached, resolve behaves as off the default branch.
R4. The PR body that `deliver` renders has a `## Owed actions discharged` section: one `Closes <owner/repo>#<n>` line per `owed` entry discharged ON THE BRANCH — in any spec, plan or debug journal, live or archived, whose resolution record is absent from that journal at the default ref — whose `filed_as` names an issue in this repo, or "None.". `deliver` refuses a live PR body that has no closing reference (any closing keyword, as `closing_refs` reads it) to an issue the section lists, under `forge.pr_body: full` and `minimal` alike.
R5. A `Closes` line that R4 lists is not a premature close: `deliver`'s gated-issue `Refs` rule does not refuse it. When the same issue is also held by that rule (an owed row's `issues:` ref, a post-merge-gated row, or an unanswered narrowing decision), the hold wins: R4 lists it as `Refs <ref>` with the reason, and R4's per-line check does not apply to it.
R6. This change amends debt-engine R24: the filed issue of a discharged owed entry closes when the discharge reaches the default branch (R3, or R4's closing line), never before.
R7. A refused `fr archive` — any non-zero exit or exception in a single-plan run, the placement refusal included — writes no file, leaves the index as it was, and makes no forge write. The archive follow-ups (owed filing, open-end filing) do not run after a refusal. When the single-plan move fails after staging part of the plan's moves, the moves it staged for that plan are undone before it refuses.
R8. A plan held under `fr archive --branch` or skipped under `fr archive --all` records the owed entries of its unticked manual phases (debt-engine R22), as today, except when HEAD is the default branch. There it writes and stages nothing, and prints the owed entries it would record.
R9. R7 and R8 amend debt-engine R22: a refused archive, and a hold on the default branch, leave no owed entry and file no issue.
R10. `fr archive --dry-run` is accepted in every mode (a plan dir, `--all`, `--branch`, `--sweep-only`, and the quiet/stealth merged record). It prints what the run would do — moves, holds, skips, owed entries written, issues filed or reused, ref repairs, and under quiet/stealth the record it would append and the push it would make — and exits with the code the same run without `--dry-run` would return.
R11. A dry run writes no file in the checkout or in the placement's `fr` worktree or tracking clone, changes no index, HEAD, branch or remote branch, and makes no forge write. It may read: git (a fetch of remote-tracking refs included) and the forge. It never prompts: with no `--issues`, it lists the open ends it would offer. A forge call the dry run's forge does not know as a read is refused and recorded, and the dry run then exits 1 naming it.
R12. Owed-issue reuse lists only open issues carrying the `fr:owed` label, filtered by the forge. When that listing reaches its limit or fails, fr files no owed issue (and ensures no label), prints a warning naming the reason, and leaves every owed entry in its journal.
R13. On a forge whose adapter cannot list issues (`UnsupportedForgeOperation`: GitLab and Gitea today), owed actions stay in the journal, as under `forge.issues: off`: `fr archive` says so, `fr journal file --id <owed>` reports it without failing, and `deliver` accepts such an owed entry as recorded.
R14. Closing an owed issue (R3) reads that one issue by number, never a listing of open issues, and keeps today's ownership checks (`owned_owed_key`: this account, `fr:owed`, the entry's marker as the last line), plus a check that the issue is open.

## Design

### A. Resolve closes at merge (R1–R6)

`resolve_cmd`'s owed branch (`journal_cmd.py:582-585`) asks one question first:
*is HEAD on the default branch?* `fr.docs.load.on_default_branch` (`docs/load.py:90`)
already answers it — it compares `symbolic-ref --short HEAD` with the default ref minus
its remote, and a detached HEAD is on no branch. It moves to `fr.git` (docs keeps a
re-export or imports it), and resolve calls it with `fr.git.remote_default_ref(root)`
(`git.py:179`). A `GitRefusal` or `None` from `remote_default_ref` answers *no* (R3).
`fr.artifacts.commit.on_default_branch` is not used: it falls back to local branch
names, which R3 excludes.

- **Yes** → `_close_owed_issue` as today, its listing replaced by one read by number
  (R14, §D).
- **No** → no forge call. It prints the `Closes <owner/repo>#<n>` line (only when
  `_own_issue` accepts the ref; otherwise the existing "not closing … close it yourself"
  warning) and says the issue closes when the branch merges.

`_own_issue` and its ref regexes move to a module both `journal_cmd` and
`fr/record/pr_body.py` import, so the renderer and resolve accept the same refs.

`pr_body.py` renders `## Owed actions discharged` from the journals the branch changed
against the merge-base with the default ref (`fr.proportionality.feature_diff`'s base):
for each changed journal (spec, plan or debug; live or archived), every `owed` entry
whose effective state is `fixed` there and is not `fixed` in that journal's version at
the default ref. That covers the common case s-r1 names — an owed entry from an earlier,
archived plan discharged on a later branch. A branch with no fr-goal `deliver` relies on
R2's printed line.

`premature_closes` (`pr_body.py:344`) gets the exemption of R5: a ref in the discharged
set is dropped from its candidates unless it is also in its `holding`, `narrowed` or
`tracking` sets; in that case R4 renders it `Refs <ref> — held: <reason>`. The live-body
check in `_deliver_pr_gate` (`run_cmd.py:7015`) gains the R4 check, using `closing_refs`
so `Fixes owner/repo#n` counts. It runs before the `forge.pr_body` branch, so it applies
under `minimal` too (the closing-keyword checks already do, `run_cmd.py:7025`).

The archived spec `2026-10-11-debt-engine-design.md` is frozen and is not edited. R6 is
recorded as an amendment of row `debt-owed-discharge`, and R9 as an amendment of row
`owed-durable-at-archive`.

### B. A refusal writes nothing (R7–R9)

In `archive_command`'s plan loop (`archive_cmd.py:1005-1015`) the single-plan refusal
no longer calls `_write_manual_owed`. `_with_followups` (`archive_cmd.py:816`) skips
`_after_moves` when `fn` raised anything — a `typer.Exit` with a non-zero code, the
placement `SettingsError` (`:907`), or any other exception. A zero exit and a normal
return still run the follow-ups, so `--all` and `--branch` (which never exit non-zero
over a hold) are unchanged.

`archive_plan_dir` (`archive.py:442-488`) stages the plan move and then the journal and
run moves, any of which can raise `ArchiveError`. On that error it reverses the `git mv`s
it already staged for that plan (newest first) before re-raising, so the single-plan
refusal (`archive_cmd.py:1041-1046`) leaves the index as it was. A reversal that itself
fails is reported, naming each staged path, in the same refusal.

`_write_manual_owed` takes the default-branch answer of §A. On the default branch it
prints `would record owed: <key> — <title>` for each phase and returns without writing
or noting the journal, so `_owed_step` has nothing from it to file.

### C. `fr archive --dry-run` (R10, R11)

The archive's product-checkout writes are spread across many helpers
(`archive_plan_dir`, `archive_journal`, the spec sweep, `_repair_in_passing`,
`write_back`, `write_owed_back`). Threading a flag through each would leave every future
write a chance to forget it. For every mode except the quiet/stealth record, the dry run
therefore runs the **real** command against a **disposable copy**:

1. Prune stale scratch worktrees first (`git worktree prune`, then remove any
   registered worktree under the temp root named `fr-archive-dry-run-*` whose process is
   gone), so a dry run killed before its `finally` leaves nothing that lasts.
2. `git worktree add --detach <tmp>/fr-archive-dry-run-<pid> HEAD`. Replay the index
   (`git diff --cached --binary HEAD | git apply --index`), then the worktree
   (`git diff --binary | git apply`), then copy untracked, non-ignored files. The staged
   and unstaged split is preserved, so `paths_dirty` and `_edited_in_worktree` give the
   same answers as in the real checkout. Ignored files are not copied. The plan checks
   that `fr archive` reads none of them, and adds a test that pins this.
3. Run the same arguments (minus `--dry-run`) in-process with the repo root pointed at
   the scratch tree and `_make_gh_client` returning a **preview forge**: a wrapper that
   delegates an explicit allowlist of read methods (`view_issue`, `view_issue_record`,
   `list_issues`, `list_prs`, `viewer_login`, `default_branch`, the PR/merge reads the
   gate makes, …) to the real client and answers every other attribute with a recording
   stub. `create_issue` answers with a URL in the forge's own shape,
   `https://<host>/<repo>/issues/<n>` with `n` counting up from 900000, so `_issue_ref`
   and `TRACKED_BY_RE` accept it and the output reads "filed" as the real run would. Any
   other write is recorded and answers `None`. A method outside both the allowlist and
   the known writes is recorded as **refused**.
4. Print the real run's output, then a summary: `git status --porcelain` of the scratch
   tree (what would be staged) and the recorded forge writes. Remove the worktree in a
   `finally`. Exit with the real run's code, or 1 when anything was refused (R11). The
   broad `except`s in the follow-ups cannot hide a refusal, because the record is read
   after the run, not raised through it.

**Quiet and stealth** (`_record_merged`, `archive_cmd.py:237`) write outside the
checkout (the `fr` worktree, the stealth tracking clone) and push through git, not the
forge client, so no scratch copy contains them. This mode gets a read-only path
instead: `_record_merged(…, preview=True)` resolves the merge sha (forge and git reads)
and prints the record it would append and the branch it would push, and returns before
`merged_status.append_record`, `_commit_merged_record`, `commit_paths`,
`stealth.commit_and_push`, `atomic_push` and `_push_fr`.

`merge_evidence(…, fetch=True)` still fetches. That updates remote-tracking refs only,
which R11 allows. `--dry-run` never prompts: `_open_ends_step`'s TTY prompt is skipped,
and the listed ends are printed.

### D. Owed issues are found by label, and fail closed (R12–R14)

`_existing_owed` (`archive_followups.py:467`) calls `gh.list_issues(repo, "open",
OWED_LIST_LIMIT, fields=OWED_ISSUE_FIELDS, labels=[FR_OWED.name])` and returns a result
type instead of a bare dict: the found keys, or a reason (`listing reached its limit of
<n>`, the read error, or `unsupported`). `file_owed_ends` files nothing and calls no
`ensure_labels` when it gets a reason, and returns one `FiledOwed(error=…)` per end, so
`_owed_step` warns per entry and the journals stay as they are. Today's best-effort
dedupe (`return {}` on error, then file anyway) is the duplicate path and is removed.

`unsupported` (`UnsupportedForgeOperation`, GitLab and Gitea) is reported as R13 says:
`_owed_step` prints "this forge cannot list issues by label: owed actions stay in the
journal", like its `ForgeQuietError` branch. `fr journal file --id <owed>` prints the
same and exits 0 without recording `filed_as`, and `deliver`'s leftover check accepts
an owed entry as recorded when the repo's forge adapter cannot list issues, as it does
under `forge.issues: off`.

`_close_owed_issue` reads the one issue (`gh.view_issue_record(repo, number)`;
`ISSUE_VIEW_FIELDS` on the gh CLI path, `gh.py:288`, gains `author` and `state`, which
the REST record already carries) and applies `owned_owed_key` plus an open-state check.

## Verification

strategy: candidate
gate: developer

There is no `## Test Plan`: the operator chose no post-merge rows (d5), and every
behaviour here shows in a candidate install against a recording forge stub.

## Negative evidence per row

The tests lens asks for negative evidence. Each row's scenario and unit tests prove the
side effect that must NOT happen:

- `owed-close-at-merge`: resolving off the default branch makes no forge call (the
  recording `gh` log is empty); on the default branch it makes exactly one close; the
  rendered body lists an archived journal's discharged entry; a held issue is rendered
  `Refs`, and `deliver` accepts it.
- `archive-refusal-writes-nothing`: after a refused archive, the tree and index are
  byte-identical (`git status --porcelain` and `git diff --cached` unchanged) and the
  forge log is empty, also with `--issues`; a move that fails halfway leaves the index as
  it was; a hold on the default branch writes nothing.
- `archive-dry-run`: after a dry run in each mode, the checkout, the index, the `fr`
  worktree and the forge log are unchanged; the exit code matches the real run's; an
  unknown forge call exits 1.
- `owed-reuse-uncapped`: with more open issues than the listing limit, an existing
  `fr:owed` marker is reused; a listing at its limit, or failed, files nothing and
  creates no label; an unsupported forge leaves the entry in the journal and
  `fr journal file` exits 0.

## Acceptance rows

- `owed-close-at-merge` (R1–R6) — resolve off the default branch closes nothing and
  prints the closing line; on the default branch it closes; `deliver`'s body carries the
  line for every owed entry discharged on the branch. Business claim: owed work stays
  visible on the forge until its fix lands.
- `archive-refusal-writes-nothing` (R7–R9) — a refused archive leaves the tree, the
  index and the forge as they were; on the default branch a hold writes nothing.
- `archive-dry-run` (R10, R11) — `fr archive --dry-run` reports what a run would do and
  changes nothing, with the real run's exit code.
- `owed-reuse-uncapped` (R12–R14) — a repo with more open issues than the listing
  limit never gets a duplicate `fr:owed` issue; a listing that cannot be complete files
  nothing.
- Amendments: `debt-owed-discharge` (R6) and `owed-durable-at-archive` (R9).

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-15-owed-archive-side-effects | `derio-net/super-fr` | `2026-11-15-owed-archive-side-effects` | — |
