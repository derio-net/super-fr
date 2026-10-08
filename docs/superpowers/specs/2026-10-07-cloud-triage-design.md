# Cloud triage: the driver, the runners and the forge in a Claude cloud session

## Background

`fr triage` and the wave driver run today on the operator's host, inside herdr,
against GitHub through the `gh` CLI. A Claude Code cloud session can do none of
that (spec journal `2026-10-07-cloud-triage`, discovery `cloud-constraints`):

- its egress proxy refuses GitHub GraphQL (HTTP 403) and allows REST only, and
  nearly every forge call fr makes goes through a GraphQL-backed `gh` command:
  on the triage path (collect, claim writes, merge, drive, adopt, export) and on
  the run path a worker uses (deliver's live PR body, close-out, adopt's PR
  status, isolation's PR-for-branch);
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
`needs_action` line saying for what; COMPLETED means the agent judged its last
task done and the session can still be messaged (discovery
`cloud-session-status`).

The operator wants triage, the runners and the driver to run in a cloud session,
as one more scope among many: several drivers, on several hosts or on one,
covering different repo sets and orgs, kept apart by per-issue claims (spec
`2026-10-06-triage-claims`). The decisions are journal entries `d1`-`d8`; the
independent spec review's findings `s1`-`s15` are resolved in this text.

## Requirements

R1. A `github-rest` forge backend implements, with GitHub's REST API only and no GraphQL call, every forge operation fr performs on the triage path (collect, check, render, batch dispatch, merge, cancel, adopt, drive, claims, export) and on the run path a worker or close-out session uses (deliver's live PR body read, close-out's PR body read, adopt's PR status, isolation's PR-for-branch, linked PRs); with it selected, a refused GraphQL call is an error, never a silent empty answer.
R2. `github-rest` returns the same records the GraphQL-backed backend returns for the same forge state, field for field, except where REST cannot express a field; each such field is listed, with how it is derived or why it is absent.
R3. The backend is chosen by one setting, `forge.api: rest | graphql` (default `graphql`), resolved before any forge client exists, from `FR_FORGE_API` or the host's `scope.yaml`, and honoured by every place fr builds a GitHub client or calls `gh`; the cloud environment's setup script exports `FR_FORGE_API=rest`.
R4. A scope's state lives in a state directory inside the workspace that runs the driver (the git toplevel of the driver's working directory, or `--workspace`), excluded from git through `.git/info/exclude` so no tracked file changes; an existing `~/.cache/fr/triage/<scope>/` is imported on first use and left in place.
R5. A scope's durable copy is a git ref, `refs/fr/triage/<scope-id>`, whose tree holds an explicit list of files (judgements, origins, subsystems, the page fragments and their manifests, snapshots, authored sources, merge stops, the lease, and the scope's durable settings); fr fetches it before it reads state and pushes it, as a compare-and-swap, after every change it makes; only the scope that owns a ref writes it.
R6. A single-repo scope keeps its ref in that repo.
R7. A scope over several repos or an org keeps its ref in a state repo the operator names once. When at least one repo in the scope is private, fr asks the operator to choose one of the private ones. When all are public, fr asks the operator to choose between a new repo just for the refs and one of the public repos, and warns that a private repo's issue later added to a wave would then leak.
R8. fr refuses, naming the issue and the state repo, to add an issue to a judged set, a batch or a wave when the issue's repo is private and the scope's state repo is public, and makes the same check before every push of the state ref and before every state export, so a repo whose visibility changed, or a hand-edited file, is caught before it leaves the workspace.
R9. One driver runs per scope: a lease in the state ref (holder = scope id plus driver identity, start, expiry) replaces the process-id `drive.lock` as the cross-host check. The holder renews it every pass; its duration is three wake intervals plus the safety-net Routine's period (default 90 minutes); a driver with the same holder identity renews its own expired lease; any other driver is refused, and an expired lease held by someone else is reported and taken over only by an explicit operator command.
R10. The driver loop is an adapter. The existing host loop (`fr triage batch drive`) is the first implementation and behaves as today; `claude-cloud` is the second.
R11. The `claude-cloud` driver runs in one long-lived cloud session on a model the operator sets (Sonnet by default), started with a fixed identity: `FR_HOST_ID` and the scope's state repo are given to it at start and restored into its workspace on every wake. It wakes from scheduled self-messages at an interval the operator sets, from GitHub activity on its batch PRs, and from a recurring Routine as a safety net, and relies on no background process to stay alive or to wake.
R12. On every wake, the `claude-cloud` driver restores the workspace state from the ref when it is missing or older than the ref, runs one driver pass, pushes the state ref, and schedules its next wake.
R13. fr makes every decision of a pass (dispatch, merge, update, hand-back, re-home, close, claims) with the same policy code the host driver runs; the agent only executes the session actions fr requests and reports each outcome back through fr.
R14. A `claude-cloud` runner implements the runner protocol as a mailbox: dispatch, message, close, re-home and status are requests with stable ids that fr writes for the driver's agent to execute with its session tools; an unexecuted or unrecorded request stays pending in the scope's state and is replayed, never duplicated; every session it creates carries the batch's item id as a tag, so a dispatch whose result was lost is found again.
R15. The runner maps each cloud session's state onto fr's session statuses (working → working; blocked → blocked; review_ready → idle; completed → idle; failed → blocked) and reports a blocked session's `needs_action` text beside its status. A batch's stage stays derived from forge facts and never from a session's state.
R16. Every run records the super-fr plugin version and the `fr` version it started with.
R17. The driver acts on version drift only when it is incompatible: the run's recorded `fr` major differs from the current release's. It then re-homes the session at its next idle moment (the session pushes its work and stops; a fresh session continues the same branch from a resume brief built from the run cursor and journal), at most once per (run, release). A run with no recorded versions is reported, never re-homed.
R18. The driver itself runs the current release: before each pass it compares the installed `fr` with the latest release and, when older, reinstalls and runs the pass on the new one; when the release's major differs from the one its own session started with, it re-homes itself (R17) so its skill text is current too.
R19. A cloud worker session gets super-fr from the cloud environment's setup script, which runs before the session starts so the plugin's agents and hooks are loaded. The worker brief makes the worker check `fr --version` and the plugin's agents before its first step; when they are missing, it installs super-fr and asks to be re-homed, because a running session cannot load a plugin's agents (discovery `no-plugin-agents`).
R20. The `post_merge` step is an operation of the environment the driver runs in: the host runs the repo's `post_merge` argument list as today; the cloud runs nothing, since every new session installs the current release at its start and the driver updates itself (R18).
R21. The fr-triage skill documents the cloud driver, `forge.api`, the state ref, the state repo choice and the privacy guard, within its existing line budget.

## Design

### A. `github-rest`: a forge backend, not a cloud feature

**Selection (R3).** `fr.forgeapi.resolve()` reads `FR_FORGE_API`, else the
host's `scope.yaml` `forge_api:`, else `graphql`. It needs no forge client, so a
repo-level key is deliberately not offered: collect reads `.fr/triage.yaml`
through the client the setting picks. The resolved value is consulted in one
place per seam:

- `hostclient.client_for_backend("github")` and `client_for_url` return
  `RealGhRestClient` when it is `rest` (today `client_for_backend` is
  provenance-blind and never reads config; it gains this one input, not repo
  config), so `triage_cmd.make_forge()` (:92), `triage_batch_cmd.make_client()`
  (:222) and every `client_for(...)` on the run path (`run_cmd.py` :6037,
  `run/closeout.py` :346, `run/adopt.py` :747, `isolation/local.py` :2962) get it
  without edits at the call site;
- the module-level helpers that call `gh` directly (`fr.gh.view_pr_body` :177 and
  the `list_*`/`view_*` helpers) route to the REST implementation when it is
  `rest`;
- `RealGhRestClient` never falls back to GraphQL, and its methods raise on a 403
  rather than returning the soft empty answer some GraphQL methods return on
  `GhError` (`list_linked_prs`, real_ghclient.py :130) (R1).

**Calls.** Every call is `gh api` against REST routes (the proxy injects auth;
`gh api` works where `gh pr list --json` does not). Pagination is explicit
(`per_page=100`) and the `limit` arguments keep their meaning. Per-PR reads
(files, checks, mergeable, reviews) are made only for open PRs, as the GraphQL
backend's fields are. Writes (`issue edit`, `issue comment`, `pr create`, `pr
close`, `pr merge`) use the matching REST routes.

**Field map (R2).**

| GraphQL field | REST derivation |
|---|---|
| `closingIssuesReferences` | parsed from the PR body and title with GitHub's closing keywords (`close[sd]`, `fix(e[sd])`, `resolve[sd]`, same-repo `#n`, `owner/repo#n`, issue URLs). **Gap:** issues linked by hand in the PR sidebar are invisible to REST. |
| `statusCheckRollup` | `GET commits/{sha}/check-runs` plus `GET commits/{sha}/status`, normalised to the rollup's entry shape: `status` and `conclusion` upper-cased; `startedAt` from `started_at`, empty for a run not yet started (GraphQL's `0001-` zero time is never produced, so `_latest_runs` treats both the same). |
| `workflowName` (on each check run) | `GET repos/{r}/actions/runs?head_sha={sha}` maps each `check_suite_id` to its workflow `name`; a check run with no Actions run (another app) gets the app's name. `collect._latest_runs` (:232) keys on `(workflowName, name)` and is unchanged. |
| `mergeable`, `mergeStateStatus` | `GET pulls/{n}` (`mergeable`, `mergeable_state`), mapped to the GraphQL enums; `null` while GitHub computes → `UNKNOWN`. |
| `reviewDecision` | derived from `GET pulls/{n}/reviews` (the latest review per reviewer). |
| `isCrossRepository` | `head.repo.full_name != base.repo.full_name`. |
| `stateReason` | the issue's `state_reason`, upper-cased. |
| `comments[].url` (comment id) | the REST comment's `html_url`, the same `#issuecomment-<id>` shape `_comment_id` parses. |
| `gh pr checks --required` | the required contexts from `GET branches/{base}/protection/required_status_checks` (404: none required), joined with the check runs. |
| `gh pr merge --match-head-commit` | `PUT pulls/{n}/merge` with `sha`. |

A contract test feeds the same recorded forge state to both backends and
compares their records (R2).

### B. State in the workspace, durable on a ref

**Where (R4).** `fr.triage.model.state_dir` gains a workspace input: the git
toplevel of the driver's working directory, or `--workspace PATH` (required for
an org or group scope run outside a clone of one of its repos). The directory is
`<workspace>/.fr/triage-state/<scope>/`, excluded through
`<git-common-dir>/info/exclude`, so no tracked file changes, on the default
branch or anywhere. A `~/.cache` directory found on first use is copied in and
left alone. `triage` stays in `READ_ONLY_COMMANDS`: it still writes no
registered artifact, only its own state directory and refs, and the rationale in
`fr.artifacts.trigger` is updated to say so.

**The ref (R5).** `refs/fr/triage/<scope-id>` points at a commit whose tree is
this explicit list (`fr.triage.state_ref.REF_FILES`), not the export set:

- `judgements.yaml`, `origins.yaml`, `subsystems.yaml`;
- the page fragment dirs and their manifests (`board/`, `origins/`,
  `architecture/`, `history/`), `snapshots/`, `authored-src/`;
- `merge-stops.json`;
- `lease.yaml` (§D);
- `scope-durable.yaml`: the scope's durable settings, `state_repo` and
  `forge_api`, so a fresh workspace recovers them from the ref.

`facts.json` and the rendered pages are left out (fr rebuilds them). The host-only
`scope.yaml` and the host id stay out, as today. `fr.triage.gitseam` gains
`fetch_state` and `push_state`; a push is a compare-and-swap
(`--force-with-lease=<ref>:<old>`), so a lost lease or a second writer fails the
push rather than overwriting. Refs outside `refs/heads/` are not branches: no
branch list, no protection rules, no PRs. The wave export to `docs/triage`
(`export:`) keeps working for repos that want a reviewed copy; it is no longer
how state survives. **Owed measurement:** that the cloud git proxy accepts a
push of a ref outside `refs/heads/`, to the session's repo and to a state repo
the session did not start with; Test Plan 12 asserts it.

**Where the ref lives (R6, R7).** Recorded as `state_repo` in
`scope-durable.yaml` (in the ref) and mirrored to the host's `scope.yaml`. The
first collect of a scope with none decides it: one repo → that repo, no
question; several or an org → it reads each repo's visibility (`GET
repos/{owner}/{repo}`, recorded in facts) and asks, as R7 states. A
non-interactive run with no `state_repo` keeps state local and warns once per
pass. The cloud driver is started with its state repo (R11), so it can fetch its
ref before it has any local state.

**Identity.** The scope id is `sha256(name, host id)` (`scope_config.py`), and
`FR_HOST_ID` already overrides the host id. The cloud driver is started with a
fixed `FR_HOST_ID` (R11), so a fresh container derives the same scope id, finds
its own ref, and recognises its own claims.

### C. The privacy guard

One predicate, `fr.triage.privacy.leak_risk(scope, state_repo, keys)`, true when
any key's repo is private and the state repo is public. It is called by
`batch create`/`edit` (`--issue`, `--add-issue`), by the wave setters, by every
judgement write that adds a key, by `push_state` and by `state export`. Each
refuses with exit 2, naming the issue, its repo and the state repo. Visibility is
read from facts, refreshed by every collect, so a repo made private after the
fact is caught at the next push (R8).

### D. The lease

`lease.yaml` in the ref: `holder` (scope id plus driver identity: the cloud
driver's session id, or `host:<host id>` for a host driver, which is stable
across a restart with a new pid), `started`, `expires`. Duration: three wake
intervals plus the safety-net Routine's period, 90 minutes by default. Taken and
renewed by the compare-and-swap push; released on a clean stop. A driver whose
holder identity matches renews its own expired lease; anyone else is refused,
and an expired foreign lease is reported and taken only with `fr triage lease
take --yes` (R9). `drive_lock.py` stays as the fast same-host first check.

### E. The driver adapter

`fr.triage.driver` defines `Driver`: run passes until done, given a runner, a
forge client and a state store. `host` wraps today's loop unchanged (R10).
`claude-cloud` is not a loop; it is a pass fr runs once per wake (R12):

```
fr triage drive pass --scope S --statuses statuses.json --outbox outbox.json
```

1. restore state from the ref if needed; check and renew the lease;
2. self-update (R18): compare the installed `fr` with the latest release; if
   older, reinstall and re-exec the pass; if the major moved past the driver
   session's own, emit a self-`rehome` request and stop;
3. collect over the configured forge backend;
4. read the session statuses and notes the agent wrote (R15), and the results of
   the previous pass's requests;
5. plan the pass with `batch_drive.drive_pass` (unchanged) and execute every
   forge action itself (merge, update, claims, labels, export);
6. write the session requests to the outbox (§F) and exit 0, or 3 when nothing
   is left to do but wait.

The agent then executes the outbox with its session tools and records each
result with `fr triage drive record --outbox outbox.json --result
results.json`, which applies them to the state and pushes the ref. The driver
section of the fr-triage skill (R21) is the agent's whole job: collect statuses,
run `pass`, execute the outbox, run `record`, schedule the next wake. Policy
stays in fr (R13), so a Sonnet driver suffices.

Wakes (R11): the agent schedules a self-message every `interval` (default 5
minutes; `send_later` has one-minute granularity) after each pass, subscribes to
PR activity on every open batch PR, and a recurring Routine fires into the
driver session hourly in case a self-message is lost. A wake that finds a pass
ran within the interval only renews the lease.

### F. The `claude-cloud` runner

A new workspace package, `packages/fr-claude-cloud` (entry point `fr.runners:
claude-cloud`), a sibling of `fr-herdr` with the same obligations: a member of
the uv workspace, a version surface in `scripts/version_surfaces.py`, the mypy
command in AGENTS.md and CI, an entry in `test_import_direction.py` (it never
imports `fr.triage`, and `fr` never imports it), and the `fr_dispatch.testing`
run-unit contract.

**Mailbox semantics (R14).** The driver uses runner results within a pass
(`dispatch` returns a handle, `close` returns closed/busy/absent, a hand-back
records "handed back" after `message`). With a mailbox those are not known until
`record`. So:

- every request has a stable id, `<item id>:<kind>:<n>`, and is stored as
  **pending** in `requests.yaml` in the state until a result is recorded;
- each runner method returns a pending result: `dispatch` returns
  `pending:<request id>`, and a batch with a pending dispatch counts as in
  flight and is never dispatched again; `close` returns `busy` while pending; a
  hand-back is recorded `handed-back (pending)` and becomes final, or is retried
  next pass, when its result arrives;
- a pending request is re-emitted on every pass until a result is recorded, and
  executing it twice is harmless: `create_session` is preceded by a
  `list_sessions` on the request's tag, the batch's item id, and is skipped
  (recording the existing session) when one exists; `send_message` carries the
  request id, and the agent skips one it has already sent; `archive_session` is
  idempotent;
- `existing_dispatches` reads the recorded sessions plus the tagged sessions the
  agent last listed, so a dispatch whose result was lost is found again, not
  duplicated.

| request | agent executes | result recorded |
|---|---|---|
| `dispatch` | `list_sessions` by tag, then `create_session` (repo, branch, model, tag, prompt = the brief) | session id |
| `message` | `send_message` | sent / refused |
| `close` | `archive_session` | closed / busy / absent |
| `rehome` | `send_message` (push and stop), then on its next idle `create_session` with the resume brief, then `archive_session` on the old one | new session id |
| `status` | `get_session` for every recorded session | `statuses.json` |

**Status and notes (R15).** `SessionStatus` stays the closed six-value Literal
(`fr_dispatch.protocols` :142), so herdr is untouched. A new optional protocol,
`SessionNotes.session_notes(items) -> dict[str, str]`, returns the
`needs_action` text of blocked sessions; the board and Needs-you-now show it when
the runner implements it. `completed` maps to **idle**, not done: it means the
agent finished its last turn and can still be messaged, so a conflict is handed
back to it rather than to a fresh session (journal `d5`'s condition is not met).

**What is herdr-only today.** `SessionRestarter` and `SessionAdopter` are
already optional, `isinstance`-checked protocols. Only two things are hardwired
and become optional: `ADOPT_LIST_RUNNER = "herdr"` (`triage_batch_cmd.py`
:1385) and the `<prefix>-wave-<n>` grouping (`batch_drive.py` :457), which a
runner without groups ignores. `claude-cloud` implements neither restart nor
adopt; re-homing is its restart (R17).

### G. Versions and drift

`fr run start` records `plugin_version` and `fr_version` in the run cursor. That
changes the cursor's shape: the `run` kind's `current_version` moves 9 → 10 with
a registered migration (old cursors get neither field, which R17 treats as
unknown) and its structure validator, per `.claude/rules/artifact-versioning.md`,
and the repo's own cursors are migrated in the same PR (R16).

Each pass reads every active batch's cursor from its batch branch
(`read_file_at_ref` on the branch head, REST contents) and compares the recorded
`fr_version` major with the latest release's. Equal → nothing. Different → one
`rehome` request at the session's next idle, recorded per (run, release) so it is
never repeated. No recorded version → reported once, never re-homed (R17).
Artifact readability is not judged by the driver: a session whose `fr` meets a
newer artifact is already refused by fr's own migration gate, which tells it what
to do.

### H. Worker sessions and `post_merge`

The cloud environment's setup script clones the super-fr marketplace, runs
`scripts/install.sh`, and exports `FR_FORGE_API=rest` (documented, not shipped
as a file: it is environment configuration). The worker brief gains a first
step: `fr --version` and the plugin's agents; when missing, install super-fr and request a re-home, since the running session cannot load the agents (R19).
`post_merge` becomes a driver-environment operation: `host` runs the configured
argument list; the cloud driver runs nothing, because every session it starts
installs the current release and the driver updates itself before each pass
(R18, R20).

## Test Plan

1. Unit: `github-rest` against a recorded REST fixture returns the records the
   GraphQL backend returns for the same state, every field compared, with each
   §A exception asserted explicitly (`closingIssuesReferences` sidebar gap,
   `workflowName`, `startedAt`, `mergeable` null) (R1, R2).
2. Unit: with `forge.api: rest`, every client factory and the direct `fr.gh`
   helpers use the REST backend, and no code path on the triage path or the run
   path reaches GraphQL: a fake `gh` that fails on `api graphql`, `issue list
   --json`, `issue view --json`, `pr list --json`, `pr view --json`, `pr checks`,
   `pr merge`, `pr create`, `pr close`, `issue edit`, `issue comment` and `repo
   view --json`; a 403 from it is raised, not swallowed (R1, R3).
3. Unit: `forge.api` resolves from `FR_FORGE_API`, then `scope.yaml`, else
   `graphql`, with no forge call (R3).
4. Unit: state lives in the workspace; `.git/info/exclude` gains the entry and no
   tracked file changes; a `~/.cache` copy is imported once (R4).
5. Unit: `push_state`/`fetch_state` round-trip every `REF_FILES` entry into a
   fresh clone, merge stops and lease included; a concurrent writer's push fails
   the compare-and-swap (R5, R9).
6. Unit: the state-repo decision for one repo, a mixed set, and an all-public
   set, including the warning; a fresh workspace recovers `state_repo` and
   `forge_api` from the ref (R6, R7, R11).
7. Unit: the privacy guard refuses a private issue into a batch, a wave, a push
   and a `state export` when the state repo is public, and allows them when it is
   private (R8).
8. Unit: a second driver is refused by the lease; the same holder renews its own
   expired lease; an expired foreign lease is reported and not taken without the
   operator command (R9).
9. Unit: `drive pass` over a fixture scope makes the same decisions the host loop
   makes for the same facts; `drive record` applies every result; a pass whose
   results were lost re-emits its pending requests, and replaying them creates no
   second session (tag lookup) (R10, R13, R14).
10. Unit: the status mapping, `completed` → idle with a conflict handed back by
    message, `needs_action` reported through `SessionNotes`, and a session's state
    never changing a batch's stage (R15).
11. Unit: the run kind's 9 → 10 migration, its validator, and every hop of the
    chain; a run started now records both versions (R16).
12. Unit: drift — same major requests nothing; a different major requests one
    re-home per (run, release), never two; a run with no versions is reported
    only; the driver's self-update reinstalls on a newer release and self-re-homes
    on a new major (R17, R18).
13. Unit: the worker brief's first step checks `fr --version` and installs only
    when missing; the cloud driver's `post_merge` runs nothing (R19, R20).
14. Scenario (`candidate`): a scripted pass against the fake forge and a fake
    session executor, from an empty workspace restored from the ref (R12).
15. Unit: the fr-triage skill names the cloud driver, `forge.api`, the state ref,
    the state repo choice and the privacy guard, and stays within its line budget
    (R21).
16. **Live, pre-merge (`client-live`), this cloud environment:** with
    `FR_FORGE_API=rest` and the branch build, collect, check and render
    `derio-net/super-fr` with no GraphQL error, and the board matches a host
    render of the same moment; push and fetch the scope's
    `refs/fr/triage/<scope-id>` through the cloud git proxy (R1, R2, R5).
17. **Live, pre-merge (`client-live`), this cloud environment:** a Sonnet driver
    session drives a wave of two small throwaway super-fr issues on its own
    scope beside the host driver: dispatches a worker session per batch, shows a
    blocked worker's `needs_action`, hands back a conflict by message, re-homes
    one worker on a simulated major drift, lets the workers deliver (deliver's PR
    body read over REST), merges, closes out, and survives a container restart by
    restoring from the ref (R11-R15, R17-R20).

## Verification

strategy: candidate
- cloud-triage-github-rest: client-live — the backend must be proven against real GitHub from an environment that blocks GraphQL; Test Plan 16.
- cloud-triage-driver-end-to-end: client-live — only real cloud sessions prove dispatch, hand-back, re-home and restart; Test Plan 17, on two throwaway super-fr issues.

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
