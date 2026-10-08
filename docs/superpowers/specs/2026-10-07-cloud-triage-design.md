# Cloud triage: the driver, the runners and the forge in a Claude cloud session

## Background

`fr triage` and the wave driver run today on the operator's host, inside herdr,
against GitHub through the `gh` CLI. A Claude Code cloud session can do none of
that (spec journal `2026-10-07-cloud-triage`, discovery `cloud-constraints`):

- its egress proxy refuses GitHub GraphQL (HTTP 403) and allows REST only, and
  nearly every forge call on the triage path (collect, claim writes, merge,
  drive, adopt, export) goes through a GraphQL-backed `gh` command;
- it has no herdr, and the cloud sessions a driver would dispatch are created,
  messaged and inspected with tools only the session's agent holds, not with an
  API fr's Python can call;
- the driver's state and lock live in `~/.cache/fr/triage/<scope>/`, the lock is
  keyed to a process id, and the loop is one long `while True` process.

What the container does keep was measured, not assumed (discoveries `wake-probe`,
`wake-probe-restart`): scheduled self-wakes arrive on time; a session woken every
ten minutes keeps one container, its disk and its processes; a restart keeps the
disk (`~/.cache`, `/tmp`, the clone, the worktree) and kills every process. A
session's plugins cannot be reloaded in place (`/reload-plugins` is unavailable
over a remote connection), and a cloud session has no super-fr plugin until
something installs it. A cloud session's `status_bucket` follows the platform's
summary of its last turn: BLOCKED means it waits on the operator, with a
`needs_action` line saying for what (discovery `cloud-session-status`).

The operator wants triage, the runners and the driver to run in a cloud session,
as one more scope among many: several drivers, on several hosts or on one,
covering different repo sets and orgs, kept apart by per-issue claims (spec
`2026-10-06-triage-claims`). The decisions are journal entries `d1`-`d8`.

## Requirements

R1. A `github-rest` forge backend implements every operation the triage path uses (collect, check, render, batch dispatch, merge, cancel, adopt, drive, claims and export) with GitHub's REST API only, and makes no GraphQL call.
R2. `github-rest` returns the same records the GraphQL-backed backend returns for the same forge state, field for field, except where REST cannot express a field; each such field is listed, with how it is derived or why it is absent.
R3. The backend is chosen by one setting (`forge.api: rest | graphql`, default `graphql`) honoured by every place fr builds a GitHub client for the triage path; the cloud environment selects `rest`.
R4. A scope's state (judgements, facts, snapshots, merge stops, scope config) lives in a git-ignored directory in the workspace that runs the driver, not in `~/.cache`; an existing `~/.cache/fr/triage/<scope>/` is imported on first use and left in place.
R5. A scope's durable copy is a git ref, `refs/fr/triage/<scope-id>`, that fr fetches before it reads state and pushes after every change it makes to it; only the scope that owns a ref ever writes it.
R6. A single-repo scope keeps its ref in that repo.
R7. A scope over several repos or an org keeps its ref in a state repo the operator names once. When at least one repo in the scope is private, fr asks the operator to choose one of the private ones. When all are public, fr asks the operator to choose between a new repo just for the refs and one of the public repos, and warns that a private repo's issue later added to a wave would then leak.
R8. fr refuses, naming the issue and the state repo, to add an issue to a judged set, a batch or a wave when the issue's repo is private and the scope's state repo is public, and makes the same check before every push of the state ref and before every state export, so a repo whose visibility changed, or a hand-edited file, is caught before it leaves the workspace.
R9. One driver runs per scope: a lease in the state ref (holder, start, expiry) replaces the process-id `drive.lock`; the holder refreshes it on every pass; a second driver is refused; an expired lease is reported and is taken over only by an explicit operator command.
R10. The driver loop is an adapter. The existing host loop (`fr triage batch drive`) is the first implementation and behaves as today; `claude-cloud` is the second.
R11. The `claude-cloud` driver runs in one long-lived cloud session on a model the operator sets (Sonnet by default). It wakes from scheduled self-messages at an interval the operator sets, from GitHub activity on its batch PRs, and from a recurring Routine as a safety net, and it relies on no background process to stay alive or to wake.
R12. On every wake, the `claude-cloud` driver restores the workspace state from the ref when it is missing or older than the ref, runs one driver pass, pushes the state ref, and schedules its next wake.
R13. fr makes every decision of a pass (dispatch, merge, update, hand-back, re-home, close, claims) with the same policy code the host driver runs; the agent only executes the session actions fr requests and reports each outcome back through fr.
R14. A `claude-cloud` runner implements the runner protocol as a mailbox: dispatch, message, close, re-home and status are requests fr writes for the driver's agent to execute with its session tools, and their results are recorded in the scope's state before the pass ends.
R15. The runner maps each cloud session's state onto fr's session statuses (working → working; blocked → blocked, carrying the `needs_action` text; review_ready → idle; completed → done; failed → blocked with the failure named). A batch's stage stays derived from forge facts and never from a session's state.
R16. Every run records the super-fr plugin version and the `fr` version it started with.
R17. The driver acts on version drift only when it is incompatible (a newer major, or an artifact the session's `fr` cannot read). It then re-homes the session at its next idle moment: the session pushes its work and stops, and a fresh session continues the same branch from a resume brief built from the run cursor and journal. It re-homes a session at most once per version jump.
R18. The driver itself always runs the current `fr`: it runs `fr` from the merged default branch, or re-executes after its own reinstall, as the host driver does today.
R19. A cloud worker session gets super-fr from the cloud environment's setup script. The worker brief makes the worker check `fr --version` before its first step and, only when `fr` is missing, install super-fr itself before going on.
R20. The `post_merge` step is an operation of the environment the driver runs in: the host runs the repo's `post_merge` argument list as today; the cloud runs nothing, since every new session installs the current release at its start.
R21. The fr-triage skill documents the cloud driver, `forge.api`, the state ref, the state repo choice and the privacy guard, within its existing line budget.

## Design

### A. `github-rest`: a forge backend, not a cloud feature

`hostclient.client_for_backend` gains a third GitHub choice, `RealGhRestClient`,
built when `forge.api: rest` (repo `.fr/triage.yaml`, host `scope.yaml`, or
`FR_FORGE_API`; the cloud environment's setup script exports `rest`). Both call
sites that build a client for the triage path — `triage_cmd.make_forge()` (:92)
and `triage_batch_cmd.make_client(url)` (:222) — go through it, so no command
changes.

Every call is `gh api` against REST routes (the proxy injects auth; `gh api`
works where `gh pr list --json` does not). The GraphQL-only fields map as
follows (R2):

| GraphQL field | REST derivation |
|---|---|
| `closingIssuesReferences` | parsed from the PR body and title with GitHub's closing keywords (`close[sd]`, `fix(e[sd])`, `resolve[sd]`, same-repo `#n`, `owner/repo#n`, issue URLs). Manual "linked issues" set in the sidebar are not visible to REST: listed as a known gap. |
| `statusCheckRollup` | `GET commits/{sha}/check-runs` plus `GET commits/{sha}/status`, normalised to the rollup's entry shape so `collect._latest_runs` is unchanged. |
| `mergeable`, `mergeStateStatus` | `GET pulls/{n}` (`mergeable`, `mergeable_state`), mapped to the GraphQL enums. |
| `reviewDecision` | derived from `GET pulls/{n}/reviews` (latest review per reviewer). |
| `isCrossRepository` | `head.repo.full_name != base.repo.full_name`. |
| `stateReason` | the issue's `state_reason`, upper-cased. |
| `gh pr checks --required` | the required contexts from `GET branches/{base}/protection/required_status_checks` (404: none required), joined with the check runs. |
| `gh pr merge --match-head-commit` | `PUT pulls/{n}/merge` with `sha`. |

Writes (`gh issue edit`, `gh issue comment`, `gh pr create`, `gh pr close`) use
the matching REST routes. Pagination is explicit (`per_page=100`), and the
`limit` arguments keep their meaning. Per-PR reads (files, checks, mergeable) are
made only for open PRs, as the GraphQL backend's fields are.

A contract test feeds the same recorded forge state to both backends and
compares their records (R2).

### B. State in the workspace, durable on a ref

`fr.triage.model`'s state directory moves from `~/.cache/fr/triage/<scope>/` to
`<workspace>/.fr/triage-state/<scope>/` (git-ignored; added to the repo's
`.gitignore` by `fr init` and by the first write). The workspace is the clone
the driver runs from. A `~/.cache` directory found on first use is copied in and
left alone (R4).

The durable copy is the ref `refs/fr/triage/<scope-id>` (scope id from `fr
triage scope show`). It points at a commit whose tree is the state directory's
durable files, the same set `fr triage state export` writes today. `fr.triage.
gitseam` gains `fetch_state` and `push_state`; push is a compare-and-swap
(`--force-with-lease=<ref>:<old>`), so a lost lease or a second writer fails the
push rather than overwriting. Refs outside `refs/heads/` are not branches: no
branch list, no protection rules, no PRs. The wave export to `docs/triage`
(`export:`) keeps working for repos that want a reviewed copy; it is no longer
how state survives.

Where the ref lives (R6, R7) is recorded in the host's `scope.yaml` as
`state_repo:`. `fr triage collect` on a scope with no `state_repo` decides it:
one repo → that repo, no question; several or an org → it reads each repo's
visibility (`GET repos/{owner}/{repo}`, recorded in facts) and asks, as R7
states. A
non-interactive run with no `state_repo` keeps state local and warns once per
pass.

### C. The privacy guard

One predicate, `fr.triage.privacy.leak_risk(scope, state_repo, keys)`, true when
any key's repo is private and the state repo is public. It is called by
`batch create`/`edit` (`--issue`, `--add-issue`), by the wave setters, by every
judgement write that adds a key, by `push_state` and by `state export`. Each
refuses with exit 2, naming the issue, its repo and the state repo. Visibility is
read from facts, refreshed by every collect, so a repo made private after the
fact is caught at the next push (R8).

### D. The lease

`lease.yaml` in the state tree: `holder` (scope id plus driver session or host
pid), `started`, `expires`. Taken by a compare-and-swap push of the ref,
refreshed every pass, released on a clean stop. `drive_lock.py` keeps the
host-local lock as a fast first check; the lease is the cross-host truth (R9).
`fr triage lease take --yes` is the operator's take-over.

### E. The driver adapter

`fr.triage.driver` defines `Driver` with one operation the policy cares about:
run passes until done, given a runner, a forge client and a state store. `host`
wraps today's loop unchanged (R10). `claude-cloud` is not a loop; it is a pass
fr runs once per wake (R12):

```
fr triage drive pass --scope S --statuses statuses.json --outbox outbox.json
```

1. restore state from the ref if needed, check and refresh the lease;
2. collect over the configured forge backend;
3. read the session statuses the agent wrote (R15);
4. plan the pass with `batch_drive.drive_pass` (unchanged) and execute every
   forge action itself (merge, update, claims, labels, export);
5. write the session actions to the outbox (R14) and exit 0, or 3 when nothing
   is left to do but wait.

The agent then executes the outbox with its session tools and records each
result with `fr triage drive record --outbox outbox.json --result
results.json`, which applies them to the state (dispatch events with the new
session id, hand-back events, re-home events) and pushes the ref. The driver
skill (a short section of fr-triage, R21) is the agent's whole job: collect
statuses, run `pass`, execute the outbox, run `record`, schedule the next wake.
Policy stays in fr (R13), so a Sonnet driver suffices.

Wakes (R11): the agent schedules a self-message every `interval` (default 5
minutes; `send_later` has one-minute granularity) after each pass, subscribes to
PR activity on every open batch PR, and a recurring Routine fires into the
driver session hourly in case a self-message is lost. A wake that finds a pass
already ran within the interval only checks the lease and goes back to sleep.

### F. The `claude-cloud` runner

`fr_dispatch` gains `fr-claude-cloud` (entry point `fr.runners: claude-cloud`),
a sibling of `fr-herdr`, implementing `Runner`, `SessionInspector`,
`SessionMessenger`, `SessionCloser` and a new `SessionRehomer`. Each method
appends a request to the pass's outbox and returns what the request will
produce; the handle of a dispatch is the session id the agent records later.
Requests:

| request | agent executes | result recorded |
|---|---|---|
| `dispatch` | `create_session` (repo, branch, model, prompt = the brief) | session id |
| `message` | `send_message` | sent / refused |
| `close` | `archive_session` | closed / busy / absent |
| `rehome` | `send_message` (push and stop), then on its next idle `create_session` with the resume brief, then `archive_session` on the old one | new session id |
| `status` | `get_session` for every recorded session | `statuses.json` |

The herdr-only parts of the triage code (the `ADOPT_LIST_RUNNER` constant, the
`<prefix>-wave-<n>` workspace grouping, `restart_idle`) become optional
capabilities a runner may lack, checked with `isinstance` as the other session
protocols already are. `claude-cloud` has no workspaces and no restart; re-homing
is its restart (R17).

### G. Versions and drift

`fr run start` records `plugin_version` and `fr_version` in the run cursor (a
cursor shape change: stamp bump, migration and validator per
`.claude/rules/artifact-versioning.md`) (R16). Each pass compares every active
run's recorded versions with the driver's `fr`: same major and every artifact
kind the run uses still readable by the run's `fr` → nothing; otherwise one
`rehome` request at the session's next idle, recorded per (run, driver version)
so it is not repeated (R17). The host runner may keep `restart_idle`; it is no
longer required for correctness.

### H. Worker sessions and `post_merge`

The cloud environment's setup script clones the super-fr marketplace and runs
`scripts/install.sh` (documented, not shipped as a file: it is environment
configuration). The worker brief gains a first step: `fr --version`; when
missing, run the install itself, then continue (R19). `post_merge` becomes a
driver-environment operation: `host` runs the configured argument list; the
cloud driver runs nothing, because no session it starts keeps an old install
(R20).

## Test Plan

1. Unit: `github-rest` against a recorded REST fixture returns the records the
   GraphQL backend returns for the same state, every field compared, with the
   R2 exceptions asserted explicitly (R1, R2).
2. Unit: with `forge.api: rest`, both client factories build the REST backend,
   and no code path on the triage path reaches a GraphQL-backed `gh` call (a
   fake `gh` that fails on `graphql`, `issue list --json`, `pr list --json`,
   `pr view --json`, `pr checks`, `pr merge`, `repo view --json`) (R3).
3. Unit: state lives in the workspace; a `~/.cache` copy is imported once (R4).
4. Unit: `push_state`/`fetch_state` round-trip into a fresh clone; a concurrent
   writer's push fails the compare-and-swap (R5, R9).
5. Unit: the state-repo decision for one repo, a mixed set, and an all-public
   set, including the warning (R6, R7).
6. Unit: the privacy guard refuses a private issue into a batch, a wave and a
   push when the state repo is public, and allows it when the state repo is
   private (R8).
7. Unit: a second driver is refused by the lease; an expired lease is reported
   and not taken without the operator command (R9).
8. Unit: `drive pass` over a fixture scope writes the same decisions the host
   loop makes for the same facts, and `drive record` applies every outbox result
   (R10, R13, R14).
9. Unit: the status mapping, including `needs_action` on a blocked session, and
   a `completed` session never changing a batch's stage (R15).
10. Unit: drift — compatible drift requests nothing; an incompatible jump
    requests one re-home, never two (R16, R17).
11. Scenario (`candidate`): a scripted pass against the fake forge and a fake
    session executor, from an empty workspace restored from the ref (R12).
12. **Live, pre-merge (`client-live`), this cloud environment:** collect, check
    and render `derio-net/super-fr` with `forge.api: rest` from the branch build;
    no GraphQL error, and the board matches a host render of the same moment
    (R1, R2).
13. **Live, pre-merge (`client-live`), this cloud environment:** a Sonnet driver
    session drives a wave of two small throwaway super-fr issues on its own
    scope beside the host driver: dispatches a worker session per batch, reports
    a blocked worker's `needs_action`, hands back a conflict, re-homes one
    worker on a simulated incompatible version, merges, closes out, and survives
    a container restart by restoring from the ref (R11, R12, R14, R15, R17-R20).

## Verification

strategy: candidate
- cloud-triage-github-rest: client-live — the backend must be proven against real GitHub from an environment that blocks GraphQL; Test Plan 12.
- cloud-triage-driver-end-to-end: client-live — only real cloud sessions prove dispatch, hand-back, re-home and restart; Test Plan 13, on two throwaway super-fr issues.

## Non-goals

- Other forges' REST adapters: glab and tea keep raising
  `UnsupportedForgeOperation` for batch operations.
- Other cloud agents than Anthropic's: revisit if one is used (journal `d7`).
- Keeping sessions always current: a session stays self-consistent; re-homing
  is the answer to incompatible drift (journal `d4`).
- Cross-repo batches (super-fr#1070).
- The Needs-you board columns themselves (super-fr#1086); this spec only makes
  the cloud runner report `needs_action`.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-10-07-cloud-triage | `derio-net/super-fr` | `2026-10-07-cloud-triage` | — |
