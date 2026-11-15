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
R2. In that case it prints that the issue closes when the branch merges, and the exact `Closes <ref>` line to carry in that branch's PR body.
R3. On the default branch (the current branch is the remote's default branch, `fr.git.remote_default_ref`), resolve closes the filed issue as debt-engine R24 states. When the default branch cannot be read, or HEAD is detached, resolve behaves as off the default branch.
R4. The PR body that `deliver` renders has a `## Owed actions discharged` section: one `Closes <ref>` line per discharged `owed` entry, in the run's spec and plan journals, whose `filed_as` names an issue in this repo, or "None.". `deliver` refuses a live PR body that lacks a line the section lists.
R5. This change amends debt-engine R24: the filed issue of a discharged owed entry closes when the discharge reaches the default branch (R3, or the closing line of R4), never before.
R6. A refused `fr archive <plan>` (a single plan, any refusal, non-zero exit) writes no file, stages nothing, and makes no forge write. The archive follow-ups (owed filing, open-end filing) do not run after a refusal.
R7. A plan held under `fr archive --branch` or skipped under `fr archive --all` records the owed entries of its unticked manual phases (debt-engine R22), as today, except when HEAD is the default branch. There it writes and stages nothing, and prints the owed entries it would record.
R8. `fr archive --dry-run` is accepted in every mode (a plan dir, `--all`, `--branch`, `--sweep-only`, and the quiet/stealth merged record). It prints what the run would do — moves, holds, skips, owed entries written, issues filed or reused, ref repairs — and exits with the code the same run without `--dry-run` would return.
R9. A dry run writes no file in the checkout, changes no index, HEAD or branch, and makes no forge write. It may read: git (a fetch of remote-tracking refs included) and the forge. It never prompts: with no `--issues`, it lists the open ends it would offer.
R10. Owed-issue reuse lists only open issues carrying the `fr:owed` label, filtered by the forge. When that listing reaches its limit or cannot be read, fr files no owed issue, prints a warning naming the reason, and leaves every owed entry in its journal.
R11. Closing an owed issue (R3) reads that one issue by number, never a listing of open issues, and keeps today's ownership checks (`owned_owed_key`: this account, `fr:owed`, the entry's marker as the last line).

## Design

### A. Resolve closes at merge (R1–R5)

`resolve_cmd`'s owed branch (`journal_cmd.py:582-585`) asks one question first:
*is HEAD on the remote's default branch?* A small helper, `_on_default_branch(root)`,
reads `fr.git.remote_default_ref(root)` (`git.py:179`) and the current branch
(`git symbolic-ref --short HEAD`). Anything but a clean match — a `GitRefusal`, `None`,
a detached HEAD — answers *no* (R3, fail safe: no early close).

- **Yes** → `_close_owed_issue` as today, except that its listing is replaced by one
  read by number (R11, §D).
- **No** → no forge call. It prints the `Closes <owner/repo>#<n>` line (only when
  `_own_issue` accepts the ref; otherwise the existing "not closing … close it
  yourself" warning) and says the issue closes when the branch merges.

`fr/record/pr_body.py` gets a section, `## Owed actions discharged`, rendered from the
run's spec and plan journals: every `owed` entry whose effective state is `fixed` and
whose `filed_as` resolves through `_own_issue` (moved to a shared module, so the
renderer and resolve accept the same refs). A run with none renders "None.". Each line
is one keyword per issue, `Closes owner/repo#n` (the existing one-keyword-per-line rule).
`deliver`'s live-body check already refuses a missing required section. This one also
refuses a live body missing a listed line. An owed entry discharged in an earlier,
merged PR is listed again; closing a closed issue is harmless. These lines are exempt
from the gated-issue `Refs` rule only for `fr:owed` issues that the owed entry filed.

The archived spec `2026-10-11-debt-engine-design.md` is frozen and is not edited. R5 is
recorded as an amendment of acceptance row `debt-owed-discharge`.

### B. A refusal writes nothing (R6, R7)

In `archive_command`'s plan loop (`archive_cmd.py:1005-1015`) the single-plan refusal
no longer calls `_write_manual_owed`. `_with_followups` learns whether `fn` exited with
a refusal: a `typer.Exit` with a non-zero code skips `_after_moves` entirely. Moves made
before the exit are impossible in the single-plan path (it refuses before `git mv`).
`--all` and `--branch` never exit non-zero over a hold, so their follow-ups still run.

`_write_manual_owed` takes the default-branch answer of §A's helper. On the default
branch it prints `would record owed: <key> — <title>` for each phase and returns
without writing or noting the journal, so `_owed_step` has nothing from it to file.

### C. `fr archive --dry-run` (R8, R9)

The archive's writes are spread across many helpers (`archive_plan_dir`,
`archive_journal`, the spec sweep, `_repair_in_passing`, `write_back`,
`write_owed_back`, `_record_merged`'s commit and push). Threading a flag through each
would leave every future write a chance to forget it. The dry run therefore runs the
**real** command against a **disposable copy**:

1. `git worktree add --detach <scratch> HEAD` under a temp dir, then replay the working
   tree's uncommitted state into it: `git diff --binary HEAD` applied, plus untracked,
   non-ignored files copied. The real checkout's index, HEAD and files are untouched.
2. Run the same `fr archive` arguments (minus `--dry-run`) in-process with the repo
   root pointed at the scratch tree and `_make_gh_client` returning a **preview forge**:
   a `GhClient` wrapper whose reads delegate to the real client and whose writes
   (`create_issue`, `comment_issue`, `edit_issue_state`, `ensure_labels`, …) are
   recorded and answered with a synthetic ref (`<repo>#dry-run-<k>`). A forge write
   method the wrapper does not know raises, so a new write path fails the dry run
   loudly instead of writing.
3. For quiet and stealth, the placement commit and push are intercepted the same way:
   the record is written in the scratch copy of the placement branch, never pushed.
4. Print the real run's output, then a summary: `git status --porcelain` of the scratch
   tree (what would be staged) and the recorded forge writes. Remove the worktree in a
   `finally`. Exit with the code the real run returned.

`merge_evidence(…, fetch=True)` still fetches. That updates remote-tracking refs only,
which R9 allows. `--dry-run` never prompts (`_file_open_ends`'s TTY prompt is skipped,
and the listed ends are printed).

### D. Owed issues are found by label, and fail closed (R10, R11)

`_existing_owed` calls `gh.list_issues(repo, "open", OWED_LIST_LIMIT,
fields=OWED_ISSUE_FIELDS, labels=[FR_OWED.name])`. It returns a result type instead of a
bare dict: the found keys, or a reason (`listing reached its limit of <n>`, or the read
error). `file_owed_ends` files nothing when it gets a reason, and returns one
`FiledOwed(error=…)` per end, so `_owed_step` warns per entry and the journals stay as
they are. Today's "best-effort dedupe" (`return {}` on error, then file anyway) is the
duplicate path and is removed.

`_close_owed_issue` reads the one issue (`gh.view_issue_record(repo, number)`, its
fields widened to carry `author` where the forge reports it) and applies
`owned_owed_key` to it, plus a check that the issue is open.

## Verification

strategy: candidate
gate: developer

## Acceptance rows

- `owed-close-at-merge` (R1–R5) — resolve off the default branch closes nothing and
  prints the closing line; on the default branch it closes; `deliver`'s body carries the
  line. Business claim: owed work stays visible on the forge until its fix lands.
- `archive-refusal-writes-nothing` (R6, R7) — a refused archive leaves the tree, the
  index and the forge as they were; on the default branch a hold writes nothing.
- `archive-dry-run` (R8, R9) — `fr archive --dry-run` reports what a run would do and
  changes nothing, with the real run's exit code.
- `owed-reuse-uncapped` (R10, R11) — a repo with more open issues than the listing
  limit never gets a duplicate `fr:owed` issue; a listing that cannot be complete files
  nothing.
- Amendment of `debt-owed-discharge` (R5): the issue closes when the discharge reaches
  the default branch.
