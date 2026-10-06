# Triage batch adopt — put a running session under the wave driver

**Status:** draft · **Run:** `2026-10-06-feat-triage-batch-adopt` (`fr-goal-light`)

## Background

`fr triage batch drive` (spec `2026-10-02-wave-driver-design.md`) drives batches it
dispatched itself: it counts them toward `--max-inflight`, finds their PRs, merges
them, closes them out, and closes their herdr sessions. It knows a session only
through the batch's `dispatch` event and a herdr tab labelled with the batch's item
id (`<owner>/<repo>/run/batch-<id>`, `fr.triage.batch.batch_item_id`).

Work started by hand — a `/fr-goal` typed into a herdr tab — has neither. The only
way to bring it under the driver today is `batch dispatch`, which launches a SECOND
session on the same issues. `batch dispatch --repair`
(`fr/commands/triage_batch_cmd.py`, `_record_missing`) records a dispatch without
launching, but only for a session the runner already reports live under the batch's
label, and only on the batch branch `feat/batch-<id>`.

Three facts of the current code shape the design:

1. **PRs are matched by the recorded branch, exactly.** `batch._branch_prs` takes a
   PR as the batch's when `head_ref == event.branch`; `collect` reads PRs by that
   head. A hand-started session works on its own branch.
2. **PRs older than the dispatch are ignored.** `batch.of_dispatch` drops a PR
   created before `event.at`. A session that already opened its PR would never be
   matched by an event stamped "now".
3. **Three call sites recompute the branch** instead of reading the event:
   `closeout_brief` and `attributed` in `fr/triage/batch_drive.py`, and
   `dispatch_comment` in `fr/triage/batch_dispatch.py`.

A branch name is also the key of fr's own state for a session started by
`/fr-goal`: the isolation record `<git-common-dir>/fr/isolation/<branch>.json`
(`fr.isolation.types.state_path`), the `.fr-isolation` marker's `branch` (the edit
gate denies edits when HEAD drifts from it), and the run cursor's committed
`branch:` field (`find_run` locates the run by it at close-out). Five of the six
issue-backed sessions on the operator's host are `/fr-goal` runs.

## Requirements

R1. `fr triage batch adopt <batch> --tab <herdr-tab-id> --branch <current-branch>` puts a running herdr session under the wave driver for an existing batch, and launches nothing.
R2. The batch must already exist (made by `batch create`); adopt never creates one, and it accepts only a batch whose stage `batch dispatch` would accept (`proposed`, `cancelled`, `abandoned`).
R3. Adopt renames the tab to the batch's item id and renames the tab's agent to the runner's agent name for that item, so the driver's existing matching (sessions, close, focus, conflict hand-back) finds the session.
R4. Adopt renames the session's branch to the batch branch (`feat/batch-<id>`, or `fix/batch-<id>` for a debug batch) everywhere fr keys on it: the local branch and its upstream; the fr isolation record, the `.fr-isolation` marker and every bound session's index file when the branch is an fr workspace; and the `branch:` of any live run cursor naming the old branch.
R5. When the old branch was pushed, adopt publishes the batch branch and deletes the old remote branch. When an open PR has the old branch as head, adopt first opens a new PR from the batch branch carrying the old PR's title, body and draft state, then comments on the old PR naming the new one and closes it.
R6. After the renames, adopt sends the session's agent one message naming the old branch, the batch branch, the new PR (if any) and the reserved version (if any), and saying that its push target changed.
R7. Adopt records one `dispatch` event (runner, the tab as handle, the batch branch, the reserved version), stamped before any new PR is opened so the driver matches that PR, and writes the forge exactly as `batch dispatch` does: the `fr:in-progress` label and the batch marker comment on every member issue.
R8. Without `--yes`, adopt prints its full plan (renames, PR moves, event, forge writes) and changes nothing; with `--yes`, every refusal fires before the first write.
R9. Adopt refuses: an unknown batch; a batch in the wrong stage; a runner that cannot adopt sessions; an unknown tab; a tab labelled with another batch's item id; a tab with no agent or more than one; an agent that is `working` (renaming under a working agent races its next push); a branch that does not exist; a worktree mid-rebase or mid-merge, or with the run cursor file modified; a batch branch that already exists locally or on the remote and is not this adoption's own earlier, partial work (R10).
R10. Adopt is resumable: re-run with the same arguments after a failure, it treats every step already done (branch already renamed with its marker and record matching, tab already labelled with this batch's item id, new PR already open, event already recorded, label and marker already present) as done, and finishes the rest.
R11. Adopt reserves a version exactly as `batch dispatch` does when the repo's config reserves versions.
R12. `fr triage batch adopt --list` prints every herdr tab (tab id, workspace label, tab label, agent status) and the `<repo>#<n>` issue refs fr finds in its label, and writes nothing.
R13. An adopted batch is driven exactly like a dispatched one: it counts toward `--max-inflight`, its PR is found and merged, it is closed out, and its tab is closed when finished.
R14. The three call sites that recompute the batch branch read the recorded event branch instead, so close-out briefs, archive-PR attribution and marker comments name the branch the work is on.
R15. The fr-triage skill documents `batch adopt` and the sweep (list, create, adopt) within its existing line budget.

## Design

### A. The verb

`batch adopt` lives in `fr/commands/triage_batch_cmd.py` beside `dispatch`, taking
the usual `--repo/--org/--dir`, `--checkout PATH` (the one clone of the batch's repo,
as `dispatch` takes it: a batch is always one repo, so `drive`'s `REPO=PATH` form has
nothing to choose between), `--tab`, `--branch`, `--yes`, and `--list`. `--list` takes no batch and ignores the
rest. Its name is distinct from the driver's `adopt` action kind
(`batch_drive.ActionKind`, close-outs started by hand), which keeps its name; the
help text says so.

The order is fixed so that every refusal fires before a write (R8):

1. Load judgements and facts; resolve the batch and its stage (R2). A batch whose
   last event is an adoption of this same tab and branch resumes (R10).
2. Resolve the runner from the batch's launch (`resolve_launch`); require the new
   optional protocol `SessionAdopter` (§E); preflight it.
3. `describe(tab)`: label, workspace, agent name, agent status. Apply R9's tab and
   agent refusals.
4. Read the git side through `fr/triage/gitseam.py` (worktree list, rebase/merge
   state, local and remote branch existence) and the open PR on the old head
   through the forge adapter. Apply R9's branch and worktree refusals.
5. Reserve the version (R11) as `dispatch` does (`_reservation`), take the event
   time (`_now_after(batch)`) and build the `DispatchEvent`; dry-run the write.
6. Print the plan. Without `--yes`, stop.
7. With `--yes`, in this order, each step skipped when already done (R10): local
   rename (§B); remote publish and PR move (§C); tab and agent rename
   (`runner.adopt`); the event; the forge writes (`_forge_writes`, as `dispatch`);
   the message (R6, through `SessionMessenger` when the runner has it).

A failure exits 1 naming what was done and what remains; the remedy is always the
same command again (R10).

**The one git exception.** The batch modules run git only through `gitseam`'s
declared operations (`tests/unit/test_forge_adapter_batch_ops.py`). Adopt adds two
declared operations to that seam (publish the batch branch, delete the old remote
branch), and calls exactly one function outside it, `fr.isolation.rename_branch`,
because isolation owns its own keys and the git calls that move them. The tripwire
gains that one allowance by name.

### B. Local branch rename (`fr/isolation/rename.py`)

`rename_branch(repo_root, worktree, old, new)`:

- `git branch -m old new` (the worktree's HEAD follows).
- When the worktree carries a valid `.fr-isolation` marker for `old`: move the
  isolation record to `state_path(repo, new)` with `branch: new`, keep its
  `sessions`, rewrite the marker's `branch`, and rewrite `branch` in
  `~/.cache/fr/sessions/<sid>.json` for every session the record lists
  (`fr/isolation/sessions.py`). The worktree path keeps its old slug: nothing
  re-derives a path from a branch (gc and containers key on the path).
- When a live run cursor (`docs/superpowers/runs/*.yaml`) names `old`: rewrite its
  `branch:` and commit only that path in that worktree
  (`chore(fr): run <id> — branch renamed to <new> by batch adopt`). The run id
  stays; `find_run` matches the cursor's `branch:`, not its id.
- Every refusal fires before the first write; a function already applied (state,
  marker and cursor all on `new`) returns as done (R10).

### C. Remote branch and the PR

GitHub closes an open PR when its head branch is renamed, so adopt never renames a
remote branch. It publishes instead:

1. `git push -u origin new` (a gitseam operation), which also sets the upstream.
2. With an open PR on `old`: open a new PR from `new` to the same base, with the
   old PR's title and body and the same draft state; comment
   `Superseded by #<new> — this branch was adopted as batch <id>` on the old PR;
   close it. Review threads and checks stay on the closed PR, which the comment
   links.
3. Delete the old remote branch.

The new forge operations (open PR, close PR, delete branch) go through the
`GhClient` adapter; `UnsupportedBatchOps` refuses them on glab and tea, as it does
the other batch writes.

### D. Event time

The event is stamped in step 5, before step 7 opens the new PR, so the new PR's
creation is never before the event (`batch.of_dispatch` keeps PRs created at or
after it). The old PR is closed and never the batch's. No backdating is needed.

### E. Runner side

`fr_dispatch.protocols` gains a `@runtime_checkable` `SessionAdopter` beside
`SessionCloser`/`SessionMessenger`, never part of `Runner`:

```python
@dataclass(frozen=True)
class AdoptTarget:
    tab: str
    label: str
    group: str | None
    agent: str | None   # None: no agent, or more than one
    status: str

class SessionAdopter(Protocol):
    def describe(self, tab: str) -> AdoptTarget | None: ...
    def list_sessions(self) -> list[AdoptTarget]: ...
    def adopt(self, item: WorkItem, tab: str) -> str: ...   # returns the handle
```

Labels stay raw: parsing `<repo>#<n>` out of a label is triage vocabulary and lives
in `fr.triage` (R12). `fr_herdr.HerdrRunner` implements the protocol with
`tab list`, `agent list`, `tab rename <tab> <item.id>` and
`agent rename <agent> <agent_name(item.id)>`. `agent rename` on a hand-started
agent has never been exercised by this code: the first task captures it live, and
if herdr cannot rename such an agent, the phase stops and reports before building
on it. `fr_dispatch.testing` gains `check_adopt_contract`. `fr` never imports
`fr_herdr`.

### F. The event and the recorded branch

The event is a plain `DispatchEvent`: no new field and no judgements schema
change, so a released `fr` reads an adopted batch unchanged. `closeout_brief`,
`attributed` and `dispatch_comment` take the branch from a new
`recorded_branch(batch)` helper (the last dispatch's branch, else
`batch_branch(batch)`) (R14). Adopt always records the batch branch, so this is
defence in depth.

## Test Plan

1. Unit: every R9 refusal, each with nothing written (judgements, forge, git,
   herdr fakes untouched); `--list` writes nothing.
2. Unit: a full adopt on fakes — tab and agent renamed; branch renamed in git, in
   the isolation record, marker, session indexes and cursor; old PR superseded by
   a new one carrying its title, body and draft state; one event stamped before
   the new PR; label and marker comment on every member; one message.
3. Unit: a failure at each step of §A.7, then a re-run that finishes it (R10).
4. Unit: `drive_pass` over an adopted batch counts it in flight, matches its new
   PR, and plans close actions for its tab when finished.
5. **Post-merge — operator-driven:** sweep all six issue-backed sessions on the
   operator's host (frank#551, frank#813, super-fr#314, willikins#422, cnc-fr#97,
   the brain-candidates run): `--list`, `batch create` each, `batch adopt --yes`
   each, then `batch drive --once`; confirm each batch is in flight, each open PR
   was superseded by a new one on the batch branch, each session kept working on
   the new branch, and the driver later merges and closes them.

## Non-goals

- Creating a batch from adopt (R2).
- Adopting a session on a non-herdr runner (the protocol allows it later).
- Adopting a `working` agent (R9): wait until it is idle, then adopt.
- Carrying review threads or check history to the new PR (§C): the old PR keeps
  them and the supersede comment links it.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-10-06-triage-batch-adopt | `derio-net/super-fr` | `2026-10-06-triage-batch-adopt` | — |
