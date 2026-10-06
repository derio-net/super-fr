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
R4. Adopt renames the session's branch to the batch branch (`feat/batch-<id>`, or `fix/batch-<id>` for a debug batch) everywhere fr keys on it: the local branch and its upstream, the remote branch when it was pushed, the fr isolation record and the `.fr-isolation` marker when the branch is an fr workspace, and the `branch:` of any live run cursor naming the old branch.
R5. After a rename, adopt sends the session's agent one message naming the old branch, the new branch, and that its push target changed.
R6. Adopt records one `dispatch` event (runner, handle, the batch branch, `adopted: true`), and writes the forge exactly as `batch dispatch` does: the `fr:in-progress` label and the batch marker comment on every member issue.
R7. The event's time is early enough for the batch to keep a PR the session already opened on that branch, and never earlier than the batch's last event; when the two cannot both hold, adopt refuses.
R8. Without `--yes`, adopt prints its full plan (renames, event, forge writes) and changes nothing; with `--yes`, every refusal fires before the first write.
R9. Adopt refuses: an unknown batch; a batch in the wrong stage; an unknown tab; a tab already labelled with another batch's item id; a tab with no agent or more than one; an agent that is `working` (renaming under a working agent races its next push); a branch that does not exist; a worktree mid-rebase, mid-merge or with the run cursor file modified; a target batch branch that already exists locally or on the remote; a repo whose config reserves versions, unless `--reserved-version` is given (as `--repair` requires).
R10. `fr triage batch adopt --list` prints every herdr tab (tab id, workspace label, tab label, agent status) and the `<repo>#<n>` issue refs found in its label, and writes nothing.
R11. An adopted batch is driven exactly like a dispatched one: it counts toward `--max-inflight`, its PR is found and merged, it is closed out, and its tab is closed when finished.
R12. The three call sites that recompute the batch branch read the recorded event branch instead, so close-out briefs, archive-PR attribution and marker comments name the branch the work is on.
R13. The fr-triage skill documents `batch adopt` and the sweep (list, create, adopt) within its existing line budget.

## Design

### A. The verb

`batch adopt` lives in `fr/commands/triage_batch_cmd.py` beside `dispatch`, taking
the usual `--repo/--org/--dir`, `--checkout REPO=PATH` (defaulting as `drive` does),
`--tab`, `--branch`, `--reserved-version`, `--yes`, and `--list`. `--list` takes no
batch and ignores the rest. Its name is distinct from the driver's `adopt` action
kind (`batch_drive.ActionKind`, close-outs started by hand), which keeps its name;
the help text says so.

The order is fixed so that every refusal fires before a write (R8):

1. Load judgements and facts; resolve the batch and its stage (R2).
2. Resolve the runner from the batch's launch (`resolve_launch`), require it to
   implement the new optional protocol `SessionAdopter` (below); preflight it.
3. Ask the runner to describe the tab (`describe(tab_id)`): label, workspace,
   agent name and status. Apply R9's tab and agent refusals.
4. Locate the branch's worktree in the checkout (`git worktree list --porcelain`)
   through `fr/triage/gitseam.py` — git runs only there. Apply R9's branch and
   worktree refusals; read whether the remote branch exists; read the PR on the
   old head, if any, through the forge adapter.
5. Compute the event time (C) and build the `DispatchEvent`; dry-run the write.
6. Print the plan. Without `--yes`, stop.
7. With `--yes`: rename the branch (B), rename tab and agent
   (`runner.adopt(item, tab_id)`), send the R5 message, write the event, then the
   forge writes through the same `_forge_writes` `dispatch` uses.

A failure after the first write exits 1 and prints what was done and the command
that finishes it (the `--repair` recovery pattern), never a silent half-state.

### B. Branch rename

A new function in `fr/isolation/` (so isolation owns its own keys) renames a branch
`old → new` for a worktree:

- `git branch -m old new`, then point the upstream at `origin/new` when the remote
  branch is renamed.
- When the worktree carries a valid `.fr-isolation` marker for `old`: move the
  isolation record to `state_path(repo, new)` with `branch: new`, and rewrite the
  marker's `branch`. Session bindings carried in the record move with it.
- When a live run cursor (`docs/superpowers/runs/*.yaml`) names `old`: rewrite its
  `branch:` and commit only that path in that worktree
  (`chore(fr): run <id> — branch renamed to <new> by batch adopt`).

The remote rename goes through the forge adapter as a new `GhClient` operation
backed by GitHub's branch-rename API (glab/tea raise `UnsupportedForgeOperation`, as
the other batch writes do). After it, adopt re-reads the PR on the new head; a PR
that did not follow is reported (exit 1) with the old PR's number. Whether GitHub
moves an open PR's head with the rename is **unverified**; the post-merge sweep
proves it.

### C. The event time

`at` = the earlier of now and the creation time of the open PR on the old head (if
any), then clamped to be strictly after the batch's last event. If the PR is older
than the last event, adopt refuses (R7): the batch history says that PR predates a
cancel or an earlier attempt.

### D. Recorded branch at every reader (R12)

`closeout_brief`, `attributed` and `dispatch_comment` take the branch from
`last_dispatch(batch).branch`, falling back to `batch_branch(batch)` only when no
dispatch exists. Adopt always records the batch branch (R4), so this is
defence in depth, and also correct for any future event with another branch.

### E. Runner side

`fr_dispatch.protocols` gains a `@runtime_checkable` `SessionAdopter` beside
`SessionCloser`/`SessionMessenger` — never part of `Runner`:

```python
class SessionAdopter(Protocol):
    def describe(self, tab: str) -> AdoptTarget | None: ...   # label, group, agent, status
    def adopt(self, item: WorkItem, tab: str) -> str: ...     # returns the handle
    def list_sessions(self) -> list[AdoptTarget]: ...
```

`fr_herdr.HerdrRunner` implements it with `tab list`, `agent list`/`agent get`,
`tab rename <tab> <item.id>` and `agent rename <agent> <agent_name(item.id)>`;
`fr_dispatch.testing` gains `check_adopt_contract`. `fr` never imports `fr_herdr`.

### F. The event

`DispatchEvent` gains `adopted: bool = False`. `_dump_batches` excludes defaults,
so files without an adoption are byte-identical. The judgements schema write
version moves by one and older schemas still load; a released `fr` reading an
adopted batch refuses the unknown key, which the schema bump makes explicit.
`judgements.yaml` is not a registered artifact kind (it lives in `~/.cache`), so
no artifact migration is owed.

## Test Plan

1. Unit: every R9 refusal, each with nothing written (judgements, forge, git,
   herdr fakes untouched); `--list` writes nothing.
2. Unit: a full adopt on fakes — tab and agent renamed, branch renamed in git,
   isolation record, marker and cursor; event with `adopted: true` and the clamped
   time; label and marker comment on every member.
3. Unit: `drive_pass` over an adopted batch counts it in flight, matches a PR
   opened before adoption, and plans close actions for its tab when finished.
4. **Post-merge — operator-driven:** sweep all six issue-backed sessions on the
   operator's host (frank#551, frank#813, super-fr#314, willikins#422, cnc-fr#97,
   the brain-candidates run): `--list`, `batch create` each, `batch adopt --yes`
   each, then `batch drive --once`; confirm each batch is in flight, any open PR
   followed its renamed head, each session kept working on the new branch, and the
   driver later merges and closes them.

## Non-goals

- Creating a batch from adopt (R2).
- Adopting a session on a non-herdr runner (the protocol allows it later).
- Adopting a `working` agent (R9): wait until it is idle, then adopt.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-10-06-triage-batch-adopt | `derio-net/super-fr` | `2026-10-06-triage-batch-adopt` | — |
