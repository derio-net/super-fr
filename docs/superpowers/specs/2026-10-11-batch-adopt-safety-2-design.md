# Batch adopt safety — hold adopted agents, adopt sessions on main, a better `--list`

**Status:** draft · **Run:** `2026-10-11-feat-batch-adopt-safety-2` (`fr-goal`) ·
**Issues:** super-fr#1081, super-fr#1069, super-fr#1071

## Background

`fr triage batch adopt` (spec `2026-10-06-triage-batch-adopt-design.md`) puts a
hand-started session under the wave driver as an existing batch. The 2026-10-07 host
sweep (that spec's Test Plan item 5) used it on a real host and found three gaps.

1. **The R6 message sets idle agents working (#1081).** `adopt_message`
   (`packages/fr/src/fr/commands/triage_batch_cmd.py`, `adopt_message`) opens with
   "this session is now batch X, driven by `fr triage batch drive`" and says nothing
   about waiting. Of the first 9 adopted sessions, 3 started work within a minute with
   no go-ahead from the operator. One migrated artifacts and pushed, one merged
   `origin/main`, and one started an fr-debugging run. The operator's rule is that
   nothing is implemented without their express confirmation. The workaround that
   worked was to send a HOLD prompt before adopting.
2. **A session on the default branch cannot be adopted (#1069).** `adopt_batch`
   refuses `--branch <default>` ("adopt never renames it") and refuses a branch
   checked out in the main worktree. That is right for a rename. But 17 of the 32
   live sessions on the sweep host sat in a base clone on `main` with real work and
   no branch. The sweep moved them by hand: `fr isolation up --branch <b>`, adopt,
   then a message telling the agent where to move.
3. **`adopt --list` is too thin to choose from (#1071).** `_list_sessions` prints
   tab, workspace label, status, `label_refs(label)` and the tab label. On the sweep
   host it found refs for 3 of 42 tabs, and 2 of those 3 were wrong: a PR number was
   read as an issue, and a bare `#97` gave no ref. herdr auto-titles drift from the
   work, so a label alone is weak evidence. Everything a better listing needs is
   already local. `herdr agent list` reports each agent's `cwd` and its harness
   session id (`agent_session.value`, captured live on this host 2026-10-11). The fr
   session index (`fr.isolation.sessions.read_session_index`) maps that id to a
   workspace. The forge knows the open PR on a branch.

## Requirements

R1. By default, the one message adopt sends the agent (R6 of the 2026-10-06 spec) ends with an explicit hold: acknowledge the message only; make no commits, merges, rebases, artifact migrations, pushes or PR edits; start no skill or pipeline run; and wait for the operator's go-ahead.
R2. The held message no longer presents the wave driver as the agent's instruction: it states the batch identity ("now tracked as batch X") and the push target, then the hold.
R3. `fr triage batch adopt --no-hold` sends the message without the hold lines, and the plan output names which form will be sent.
R4. Without `--yes`, adopt's plan prints the exact message text the agent will receive, with a placeholder where a PR adopt has yet to open will be named.
R5. Given `--branch` equal to the repo's default branch, adopt does not refuse. It creates the batch branch's fr isolation workspace from freshly-fetched `origin/<default>` (what `fr isolation up --branch <batch-branch>` does) and binds the adopted agent's session to that workspace when the runner reports a session id. It records the dispatch event on the batch branch, marks every member issue on the forge as a dispatch does, and sends the message.
R6. On the default-branch path, the message names both the batch branch and the new workspace's path, and tells the agent that all further work on this batch happens in that workspace, not the base clone. The hold of R1 applies unless `--no-hold`.
R7. The default-branch path refuses before any write when: the base clone has uncommitted changes (the refusal lists the paths); the local default branch has commits that `origin/<default>` lacks (the refusal lists them); the runner reports the agent's working directory and it is outside this checkout; or the batch branch already exists, locally or on the remote, and is not this adoption's own earlier work.
R8. The default-branch path never changes the base clone's working tree, index, HEAD or default branch.
R9. The default-branch path is resumable: re-run with the same arguments, an existing fr workspace for the batch branch in this checkout counts as done, and adopt finishes the remaining steps.
R10. A runner's session description gains three optional fields: the agent's working directory, its harness session id and its harness. Each defaults to unknown, so a runner that reports none of them still works unchanged. The herdr runner fills all three from `herdr agent list`.
R11. `adopt --list` prints a header line, then one tab-separated line per runner tab with these columns: tab, workspace label, agent status, state, repo, branch, fr workspace, PR, refs, tab label. An unknown value prints `-`.
R12. The listing's state is one of: `no agent` (no single agent in the tab); `batch` (the tab is already labelled with a batch's item id); `on default branch` (the agent's checkout has the repo's default branch checked out); `adoptable` (any other branch); or `unknown` (the working directory is not reported or is not in a git checkout).
R13. The repo and branch columns come from the agent's working directory: the checkout's `origin` repo, and its current branch.
R14. The fr workspace column is the workspace whose session binding holds the agent's session id; otherwise the fr workspace whose worktree contains the working directory; otherwise `-`.
R15. The PR column is the open PR whose head is that branch (`#<n>`), with the issues it closes. Each distinct repo-and-branch pair is read from the forge once per listing.
R16. The refs column contains every `<repo>#<n>` in the tab label, and every bare `#<n>`, resolved against the agent's repo. Each ref is classified through the forge as an issue or a PR (`super-fr#314 (pr)`). Each distinct ref is read once per listing, and a ref whose read fails or whose forge cannot classify it prints `(?)`.
R17. `adopt --list` writes nothing, and a forge read failure never fails it; only a failure to list the runner's sessions does.
R18. The fr-triage skill documents `--no-hold`, adopting a session on the default branch, and the listing's state column, within its 120-line cap.

## Design

### A. The held message (R1–R4)

`adopt_message` gains `hold: bool = True` and `workspace: Path | None = None`. It
builds its lines as follows:

```
fr triage batch adopt: this session is now tracked as batch <id> (<item-id>).
<branch line — today's rename line, or "Your branch is <new>; keep pushing to it.",
 or on the default-branch path: "Your batch branch is <new>, in the fr workspace
 <path>. Do all further work on this batch there, never in the base clone.">
[The PR is now <pr>; the earlier one was closed as superseded.]
[Reserved version for this batch: <v>.]
HOLD: acknowledge this message only. Make no commits, merges, rebases, artifact
migrations, pushes or PR edits, and start no skill or pipeline run. Wait for the
operator's go-ahead.
```

The last block is omitted under `--no-hold`. The word "driven" no longer appears: the
driver acts on the forge, and the agent needs no instruction from it.

The plan (step 6 of `adopt_batch`) prints `  runner: message the agent (held)` or
`(not held)`, then the message indented under `    | `. `_pr_ref()` reads
`state["pr"]`, which is unknown before `--yes`. When a PR will be opened, the plan
prints `#<new PR>` instead. A test pins every line of the held text, so a rewording
is a reviewed diff.

`batch_adopt_command` gains `--no-hold` (default held) and passes it through. `drive`
never adopts, so no other caller exists.

### B. Adopting a session on the default branch (R5–R9)

`adopt_batch` splits at step 4 on `old == default`. Today that case raises the
refusal. It now takes a new branch `_adopt_from_default(...)`, which reuses steps
1–3 (batch, runner, session refusals) and step 5's reservation and event, and
replaces the git and PR part:

1. **Refusals (R7)**, every one before the first write:
   - `checkout.dirty_paths()` is not empty → refuse and list them. This is a new
     `gitseam.Checkout` method, `git status --porcelain` in the main worktree; git
     runs only in `gitseam` (its tripwire).
   - `checkout.unpushed(default)` is not empty → refuse and list `<sha> <subject>`.
     This is a new method, `git log origin/<default>..<default> --format=%h %s`, run
     after `checkout.fetch()`.
   - `session.cwd` is known, and its git toplevel is not `checkout.main_worktree()` →
     refuse ("the agent works in <cwd>, not in this checkout; pass --checkout").
   - The batch branch exists locally or on the remote and no fr workspace for it is
     recorded in this checkout → refuse. This is the same rule as R9 of the 2026-10-06
     spec, keyed on the workspace instead of a rename.
2. **Plan**: `branch: <default> stays; new workspace <path> on <new> from
   origin/<default>` (or `workspace exists: <path>` on a re-run), then the record,
   forge marks and held-message lines as today. There is no PR to supersede and no
   remote branch to publish or delete. The batch branch carries no commits yet, so
   the agent publishes it on its first push once released.
3. **Steps, under `--yes`**: `create workspace` (skipped when it exists, R9), `bind
   session` (only when `session.session` is known), `adopt tab`, `record the dispatch
   event`, `mark every member on the forge`, `message the agent`. These run in the
   same resumable step loop as today, with the same stop report.

**Creating the workspace.** Use the in-process API `fr isolation up` itself calls:
`fr.commands.isolation_cmd._target(checkout.path).up(profile=None, branch=new,
base=f"origin/{default}")`, then `fr.isolation.sessions.attach(state.repo_root, new,
session_id, harness=...)`. This needs no subprocess and no second `fr`, and it honours
`FR_ISOLATION_TARGET` exactly as the CLI does. The target selection moves to a public
`fr.isolation.routing`-level helper if `_target` stays private; the plan decides which,
and the move is a refactor with no behaviour change. A binding failure is a warning,
not a stop, because bindings are traceability (`run_cmd._bind_session`'s rule).

**R8, enforced.** The only git commands on this path are read-only ones (`status`,
`fetch`, `log`) plus `worktree add`, which `up` runs and which never touches the main
worktree's checkout. A test snapshots `git rev-parse HEAD`, `git status --porcelain`
and the default branch's sha before and after a `--yes` run, and asserts equality.

The harness for `attach` comes from the runner's report (herdr's `agent` field,
`claude` → `claude`), else `unknown`.

### C. Session description fields (R10)

`fr_dispatch.protocols.AdoptTarget` (a frozen dataclass) gains:

```python
cwd: str | None = None
session: str | None = None
harness: str | None = None
```

Each is defaulted, so every existing constructor and the `fr_dispatch.testing`
contract keep working. `HerdrRunner.list_sessions` fills them from the single agent's
`cwd`, `agent_session.value` and `agent` keys, and leaves them None when the tab has
no single agent. `fr-claude-cloud` implements no `SessionAdopter` and is untouched.

### D. `adopt --list` (R11–R17)

Classification is a pure function in `fr/triage/batch.py`, beside `label_refs`:
`session_row(target, facts) -> SessionRow`. Here `facts` is a small, fully read
record per session (repo, branch, default branch, workspace, PR, classified refs), so
the state rules of R12 are unit-tested without git or a forge. The command gathers
those facts:

- **git**, per distinct cwd: a new read-only `gitseam` helper `checkout_facts(cwd)`
  returning toplevel, origin repo, current branch, default branch and whether the
  toplevel is a linked worktree, or None when cwd is not a checkout. It reuses
  `Checkout.at`, `origin_repo`, `default_branch`, plus `git branch --show-current`.
- **fr workspace**: `read_session_index(target.session)["worktree"]`, else the
  `list_states` entry of that checkout whose worktree contains cwd.
- **forge**, through `make_client` for the repo's host: one `list_prs_by_head` per
  distinct (repo, branch); its records already carry `closingIssuesReferences`. For
  refs, one new `GhClient.ref_kind(repo, number) -> "issue" | "pr" | None` per
  distinct ref. GitHub's implementation reads `repos/<repo>/issues/<n>` through
  `gh api`, where a `pull_request` key means a PR. The REST client uses the same
  route. glab and tea raise `UnsupportedForgeOperation`, which prints `(?)`. Every
  forge exception in the listing is caught per read (R17).
- **bare `#<n>`**: a new `label_bare_refs(label)` returns the numbers that
  `_LABEL_REF` did not already match. They resolve against the session's repo name.
  When the repo is unknown, they print as `#<n> (?)`.

The output is a header line `TAB\tWORKSPACE\tSTATUS\tSTATE\tREPO\tBRANCH\tFR
WORKSPACE\tPR\tREFS\tLABEL` and then the rows. The fr workspace column prints the
worktree path, abbreviated with `~`. The PR column prints `#<n> closes a#1,b#2`.

### E. Docs (R18)

In fr-triage `SKILL.md`, the adopt sentence on line 97 is rewritten in place to name
`--no-hold`, the default-branch path and the state column, without adding lines (the
skill sits at its 120-line cap). The OpenCode and Hermes mirrors are regenerated
(`scripts/sync-opencode.py`, `scripts/sync-hermes.py`). The change fragment is
`bump: minor` (new flag, new adopt path, new listing columns).

## Verification

strategy: candidate
- triage-adopt-holds-agent: candidate — scenario `tests/scenarios/triage-adopt-hold.sh` runs the installed `fr` against a fake herdr and fake gh and greps the plan's printed message for the hold, and for its absence under `--no-hold`.
- triage-adopt-list-columns: candidate — scenario `tests/scenarios/triage-adopt-list.sh` runs `adopt --list` over a fake herdr whose agents sit in a temporary checkout, with a fake gh that answers one issue and one PR.
- triage-adopt-default-branch: none — CI unit tests over a real temporary git repo with `FR_ISOLATION_TARGET=worktree` cover every refusal, the created workspace, resumption, and the base clone left byte-identical. A scenario would repeat those tests through a slower fake-forge harness.
- triage-adopt-live-sweep: live — only a real herdr host with real agents shows that the listing correlates live sessions and that a held agent actually waits. No pre-merge strategy reaches real agents.

## Test Plan

1. post-merge — operator-driven: on the herdr host, run `fr triage batch adopt
   --list` and check that each live agent's repo, branch, fr workspace and PR are
   right, and that a PR ref is shown as `(pr)`. Then adopt one idle session on a
   feature branch and one on `main` (on a throwaway batch), and confirm that both
   agents acknowledge and wait without committing, pushing or starting a run.
   (`triage-adopt-live-sweep`)

## Non-goals

- Carrying uncommitted base-clone work into the new workspace. The operator chose a
  refusal; the agent moves its own work once released.
- An `--offline` listing. Forge reads are bounded at one per distinct ref or branch.
- Adopting from runners other than herdr. The protocol fields are optional, and other
  runners adopt nothing today.
- Releasing a held agent. That is the operator's own message.

## Implementation Plans

| Plan | Status |
|------|--------|
