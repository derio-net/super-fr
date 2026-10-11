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
R5. Given `--branch` equal to the repo's default branch, adopt does not refuse. It enters the batch branch's fr isolation workspace in the checkout's main worktree (what `fr isolation up --branch <batch-branch>` does: a new branch cut from freshly-fetched `origin/<default>`, or a resume of the existing workspace). It binds the adopted agent's session to that workspace when the runner reports a session id, records the dispatch event on the batch branch, marks every member issue on the forge as a dispatch does, and sends the message.
R6. On the default-branch path, the message names the batch branch and the new workspace's path. It tells the agent to do all further work on this batch in that workspace, never in the base clone, and to publish the branch only with `git push -u origin <batch-branch>`, never pushing the default branch. The hold of R1 applies unless `--no-hold`.
R7. The default-branch path refuses before any write when: the main worktree does not have the default branch checked out; the main worktree has uncommitted changes (the refusal lists the paths); the local default branch has commits that `origin/<default>` lacks (the refusal lists them); the runner reports the agent's working directory and it is outside this checkout's main worktree; or the batch branch already exists locally or on the remote, unless it is an fr workspace of this checkout whose branch has no commits beyond `origin/<default>`, or one this session is already bound to.
R8. The default-branch path never changes the main worktree's tracked files, index, HEAD or default branch.
R9. The default-branch path is resumable: re-run with the same arguments, it resumes the batch branch's existing workspace (allowed by R7) as `fr isolation up` resumes one, starting a container that never started, and finishes the remaining steps. A stop report that names the re-run command repeats `--no-hold` and `--checkout` when they were given.
R10. A runner's session description gains three optional fields: the agent's working directory, its harness session id and its harness. Each defaults to unknown, so a runner that reports none of them still works unchanged. The herdr runner fills them from `herdr agent list`: the working directory from `foreground_cwd`, else `cwd`; the session id from `agent_session.value`; the harness from `agent` when it is `claude`, `opencode` or `hermes`, else unknown.
R11. `adopt --list` prints a header line, then one tab-separated line per runner tab with these columns: tab, workspace label, agent status, state, repo, branch, fr workspace, PR, refs, tab label. An unknown value prints `-`.
R12. The listing's state is the first that applies: `no agent` (the tab holds no single agent); `batch` (the tab label contains `/run/batch-`, the test adopt's own refusal uses); `unknown` (the working directory is unreported, is not in a git checkout, or its default branch cannot be read); `on default branch` (the checkout has the default branch checked out); `detached` (no branch is checked out); `adoptable` (any other branch).
R13. The repo and branch columns come from the agent's working directory: the checkout's `origin` repo as `owner/name`, and its current branch.
R14. The fr workspace column is the workspace whose session binding holds the agent's session id; otherwise the fr workspace whose worktree contains the working directory; otherwise `-`.
R15. The PR column is the newest OPEN PR whose head is the session's branch, from the session's own repo (not a fork), with the issues it closes. It is looked up only for `adoptable` rows, and each distinct repo-and-branch pair is read from the forge once per listing.
R16. The refs column holds every issue or PR reference in the tab label: `owner/name#<n>` as written; `name#<n>` resolved to the agent's `owner/name` when the names match, and otherwise left unresolved; and a bare `#<n>` resolved against the agent's repo. A resolved ref is classified through the forge as an issue or a PR (`derio-net/super-fr#314 (pr)`), each distinct ref read once per listing. An unresolved ref, or one whose read fails or whose forge cannot classify it, prints with `(?)`.
R17. `adopt --list` writes nothing. A failure of one session's git read, forge client construction or forge read degrades only that row's cells to `-` or `(?)`; only a failure to list the runner's sessions fails the command.
R18. The fr-triage skill documents `--no-hold`, adopting a session on the default branch, and the listing's state column, within its 120-line cap.

## Design

### A. The held message (R1–R4)

`adopt_message` gains `hold: bool = True` and `workspace: Path | None = None`. It
builds its lines as follows:

```
fr triage batch adopt: this session is now tracked as batch <id> (<item-id>).
<branch line — today's rename line, or "Your branch is <new>; keep pushing to it.",
 or on the default-branch path: "Your batch branch is <new>, in the fr workspace
 <path>. Do all further work on this batch there, never in the base clone. Publish
 it only with `git push -u origin <new>`; never push <default>.">
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
refusal. It now takes a new function `_adopt_from_default(...)`, which reuses steps
1–3 (batch, runner, session refusals) and step 5's reservation and event, and
replaces the git and PR part. Every git read runs with cwd `checkout.main_worktree()`,
never `checkout.path`, which may be a linked worktree.

1. **Refusals (R7)**, every one before the first write:
   - `checkout.worktree_of(default)` is not the main worktree → refuse ("the base
     clone is on <branch>, not <default>").
   - `checkout.dirty_paths()` is not empty → refuse and list them. This is a new
     `gitseam.Checkout` method (`git status --porcelain` in the main worktree).
   - `checkout.unpushed(default)` is not empty → refuse and list `<sha> <subject>`.
     This is a new method (`git log origin/<default>..<default> --format=%h %s`), run
     after `checkout.fetch()`.
   - `session.cwd` is known and `Checkout.at(cwd).main_worktree()` is not this
     checkout's main worktree → refuse ("the agent works in <cwd>, not in this
     checkout; pass --checkout").
   - The batch branch exists locally or on the remote → refuse, unless
     `fr.isolation.adopt.reusable_workspace(...)` (below) accepts it: an fr workspace
     recorded in this checkout for that branch, whose branch has no commits beyond
     `origin/<default>` (`checkout.unpushed`-style count, a new `Checkout.ahead(ref,
     base)`), or one whose session list already holds this session. A workspace left
     with commits by an earlier failed dispatch is refused, never silently reused.
2. **Plan**: `branch: <default> stays; workspace <path> on <new> from origin/<default>`
   (`resume workspace <path>` on a re-run), then the record, forge marks and the
   printed message as today. There is no PR to supersede and no remote branch to
   publish or delete. The batch branch carries no commits yet; the message tells the
   agent how to publish it once released (R6).
3. **Steps, under `--yes`**: `enter workspace` (always run; R9's resume), `bind
   session` (only when `session.session` is known; a failure is a printed warning,
   never a stop, as `run_cmd._bind_session` rules), `adopt tab`, `record the dispatch
   event`, `mark every member on the forge`, `message the agent`. They run in the
   same resumable step loop as today. Its stop report's re-run command echoes
   `--no-hold` and `--checkout <path>` when given, on both paths.

**The isolation seam.** The batch tripwire
(`tests/unit/test_forge_adapter_batch_ops.py`, `_FORGE_CLIS` bans `fr.isolation` in
every `batch*` module, `_ISOLATION_ALLOWED` admits only the rename) stays the rule.
A new module `fr/isolation/adopt.py` owns every isolation call adopt and `--list`
make, and `_ISOLATION_ALLOWED` grows by exactly its imports, with
`test_the_isolation_allowance_is_the_rename_alone` renamed and updated in the same
diff to pin the new, still closed, set:

- `enter_workspace(repo_root, branch) -> Path` calls the backend selection that
  `fr.run.workspace._select_target` already wraps (`isolation_cmd._target`, which
  honours `FR_ISOLATION_TARGET`), then `.up(profile=None, branch=branch)`. It always
  calls `up`: on an existing workspace `up` is a documented resume, so a devcontainer
  whose first start failed after its state was recorded (local.py's "record before
  the side effect", gh#578) is started on the re-run rather than skipped.
- `bind_session(repo_root, branch, session_id, harness) -> str | None` wraps
  `sessions.attach` and returns a warning instead of raising.
- `reusable_workspace(repo_root, branch, session_id) -> Path | None` and
  `session_worktree(session_id) -> Path | None` (from `read_session_index`), and
  `workspace_containing(repo_root, path) -> Path | None` (from `list_states`).

`repo_root` is always `checkout.main_worktree()`. The default devcontainer mode starts
a container, exactly as `fr isolation up` would for this branch; that is the
operator's chosen behaviour (decision `default-branch-cuts-workspace`).

**R8, enforced.** `up` runs `worktree add` plus config writes (the new branch's
upstream, `info/exclude`), none of which touch the main worktree's checkout, index or
the default branch. A test snapshots `git rev-parse HEAD`, `git status --porcelain`
and the default branch's sha in the main worktree before and after a `--yes` run, and
asserts equality.

### C. Session description fields (R10)

`fr_dispatch.protocols.AdoptTarget` (a frozen dataclass) gains:

```python
cwd: str | None = None
session: str | None = None
harness: str | None = None
```

Each is defaulted and appended after the existing fields, so every existing
constructor and `fr_dispatch.testing.check_adopt_contract` keep working.
`HerdrRunner.list_sessions` fills them from the single agent's `foreground_cwd` (else
`cwd`), `agent_session.value` and `agent` (mapped to `claude`, `opencode` or
`hermes`, else None), the order `fr_herdr.restart` already reads them in, and leaves
them None when the tab has no single agent. The exact-equality test in
`tests/unit/test_fr_herdr_runner.py` gains the new fields. `fr-claude-cloud`
implements no `SessionAdopter` and is untouched.

### D. `adopt --list` (R11–R17)

`fr.triage` may not import `fr_dispatch` (`tests/unit/test_import_direction.py`), so
the pure part takes plain values. In `fr/triage/batch.py`, beside `label_refs`:

- `parse_refs(label) -> list[LabelRef]` is new (`label_refs` keeps its
  callers) and recognises `owner/name#n`, `name#n` and bare `#n`, each once, in
  order. A `LabelRef` holds `owner` (or None), `name` (or None) and `number`.
  `resolve_ref(ref, repo) -> str | None` gives `owner/name` per R16.
- `session_state(*, has_agent, label, toplevel, branch, default) -> str` returns R12's
  state. Every edge (detached, unreadable default, batch label) has a unit test.

The command (`_list_sessions`) unpacks each runner session and gathers, per row,
inside its own `try` (R17):

- **git**: a new classmethod `gitseam.Checkout.facts(cwd) -> CheckoutFacts | None`
  (toplevel, origin URL, `owner/name`, current branch or None, default branch or
  None, main worktree), None when cwd is not a checkout. It stays on `Checkout`, so
  the gitseam tripwire's admitted surface (`Checkout`, `Worktree`, `GitError`) is
  unchanged.
- **fr workspace**: `fr.isolation.adopt.session_worktree(session)`, else
  `workspace_containing(facts.main_worktree, cwd)`.
- **forge**: one client per host, built by `make_client(<origin URL>)` inside the
  row's guard, and cached by host. For each distinct (repo, branch) of an
  `adoptable` row: `list_prs_by_head`, filtered to `state == OPEN` and
  `isCrossRepository` false, newest first; its `closingIssuesReferences` give the
  closed issues. For each distinct resolved ref: a new
  `GhClient.ref_kind(repo, number) -> "issue" | "pr" | None`. GitHub (`@_hosted`, per
  `tests/unit/test_gh_host.py`) reads `gh api repos/<repo>/issues/<n>`, where a
  `pull_request` key means a PR; the REST client reads the same route; glab and tea
  raise `UnsupportedForgeOperation`, which prints `(?)`.

The output is a header line `TAB\tWORKSPACE\tSTATUS\tSTATE\tREPO\tBRANCH\tFR
WORKSPACE\tPR\tREFS\tLABEL` and then the rows. The fr workspace column prints the
worktree path with `$HOME` shown as `~`. The PR column prints `#<n> closes a#1,b#2`.

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
