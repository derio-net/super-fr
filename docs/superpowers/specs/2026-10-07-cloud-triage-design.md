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
session's plugins cannot be reloaded on request (`/reload-plugins` is unavailable
over a remote connection). The session's CLI is a pre-warmed spare that loaded
its configuration before the environment's setup script ran, so a plugin that
script installs reaches the session late or not at all, and its agent types are
not there when the session starts; agent files committed in the repo's
`.claude/agents/` are (discoveries `spare-preload`, `plugin-late-load`,
`agents-late-load`, `repo-agents`). A cloud session's `status_bucket` follows the platform's
summary of its last turn: BLOCKED means it waits on the operator, with a
`needs_action` line saying for what; COMPLETED means the agent judged its last
task done and the session can still be messaged (discovery
`cloud-session-status`).

The operator wants triage, the runners and the driver to run in a cloud session,
as one more scope among many: several drivers, on several hosts or on one,
covering different repo sets and orgs, kept apart by per-issue claims (spec
`2026-10-06-triage-claims`). The decisions are journal entries `d1`-`d11`; the
independent spec reviews' findings `s1`-`s30` are resolved in this text.

## Requirements

R1. A `github-rest` forge backend implements, with GitHub's REST API only and no GraphQL call, every forge operation fr performs on the triage path (collect, check, render, batch dispatch, merge, cancel, adopt, drive, claims, export) and on the run path a worker or close-out session uses (deliver's live PR body read, close-out's PR body read, adopt's PR status, isolation's PR-for-branch, linked PRs), and every forge command fr hands an agent to run (`FORGE_COMMANDS`: PR create, edit and ready, issue close and edit, label create); with it selected, a refused GraphQL call is an error, never a silent empty answer, except for the client methods whose contract already answers `None` when the forge cannot say (§A).
R2. `github-rest` returns the same records the GraphQL-backed backend returns for the same forge state, field for field, except where REST cannot express a field; each such field is listed, with how it is derived or why it is absent.
R3. The backend is chosen by one host-level setting, `forge.api: rest | graphql` (default `graphql`), resolved before any forge client exists and without a scope, from `FR_FORGE_API`, else the host file `~/.config/fr/forge.yaml`, else `graphql`, and honoured by every place fr builds a GitHub client or calls `gh`; the cloud environment's setup script writes that file (an `export` there never reaches the session's shells, discovery `spare-preload`).
R4. A scope's state lives in a state directory inside the workspace that runs the driver (the git toplevel of the driver's working directory, or `--workspace`), excluded from git through the repository's `info/exclude` (under `git rev-parse --git-common-dir`, so a linked worktree is covered) so no tracked file changes; an existing `~/.cache/fr/triage/<scope>/` has its durable files (the `REF_FILES` set plus `facts.json` and `scope.yaml`) imported on first use and is left in place. A command run outside any clone, with no `--workspace`, keeps using `~/.cache/fr/triage/<scope>/` exactly as today, so no host invocation that works now starts refusing. Workspaces of one scope stay one state because every state write is wrapped by the ref (R5), and the same-host `drive.lock` stays keyed per scope under `~/.cache/fr/triage/<scope>/`, whatever workspace the state lives in.
R5. A scope's durable copy is a git ref, `refs/fr/triage/<scope-id>`, whose tree holds an explicit list of files (judgements, origins, subsystems, the page fragments and their manifests, snapshots, authored sources, merge stops, the lease, the scope's durable settings, and the cloud runner's pending requests, session records and re-home ledger); fr fetches it before it reads state and pushes it, as a compare-and-swap, after every change it makes; only the scope that owns a ref writes it.
R6. A single-repo scope keeps its ref in that repo.
R7. A scope over several repos or an org keeps its ref in a state repo the operator names once. When at least one repo in the scope is private, fr asks the operator to choose one of the private ones. When all are public, fr asks the operator to choose between a new repo just for the refs and one of the public repos, and warns that a private repo's issue later added to a wave would then leak.
R8. fr refuses, naming the issue and the state repo, to add an issue to a judged set, a batch or a wave when the issue's repo is private and the scope's state repo is public, and makes the same check before every push of the state ref and before every state export, reading the state repo's own visibility from the forge before each push and refusing when it cannot be read, so a repo whose visibility changed, or a hand-edited file, is caught before it leaves the workspace.
R9. One driver runs per scope: a lease in the state ref (holder = scope id plus driver identity, start, expiry) replaces the process-id `drive.lock` as the cross-host check. The driver identity is `host:<host id>` for a host driver and `cloud:<host id>` for a cloud driver, so neither a new pid nor a re-homed session changes it. The holder renews it every pass; its duration is three wake intervals plus the safety-net Routine's period (default 3 × 5 + 60 = 75 minutes); a driver with the same holder identity renews its own expired lease; any other driver is refused, and an expired lease held by someone else is reported and taken over only by an explicit operator command.
R10. The driver loop is an adapter. The existing host loop (`fr triage batch drive`) is the first implementation and behaves as today; `claude-cloud` is the second. The driver adapter, not the repo, decides which runner a scope's batches use: a cloud scope dispatches every batch through `claude-cloud`, whatever `launch.runner` the repo's `.fr/triage.yaml` names, and ignores that file's `post_merge` and `post_merge_restart` (R20).
R11. The `claude-cloud` driver runs in one long-lived cloud session on a model the operator sets (Sonnet by default), started with a fixed identity: its brief carries a host id and the scope's state repo, and the first step of every wake writes the host id to `~/.config/fr/host-id` and `forge.api: rest` to `~/.config/fr/forge.yaml` when either is missing, so a fresh container derives the same scope id. It wakes from scheduled self-messages at an interval the operator sets, from GitHub activity on its batch PRs, and from a recurring Routine as a safety net, and relies on no background process to stay alive or to wake; the last two wake sources are owed a measurement (§E).
R12. On every wake, the `claude-cloud` driver restores the workspace state from the ref when it is missing or older than the ref, runs one driver pass, pushes the state ref, and schedules its next wake.
R13. fr makes every decision of a pass (dispatch, merge, update, hand-back, re-home, close, claims) with the same policy code the host driver runs; the agent only executes the session actions fr requests and reports each outcome back through fr.
R14. A `claude-cloud` runner implements the runner protocol as a mailbox: dispatch, message, close, re-home and status are requests with stable ids that fr writes for the driver's agent to execute with its session tools; an unexecuted or unrecorded request stays pending in the scope's state and is replayed, never duplicated; every session it creates carries the batch's item id as a tag, so a dispatch whose result was lost is found again.
R15. The runner maps each cloud session's state onto fr's session statuses (working → working; blocked → blocked; review_ready → idle; completed → idle; failed → blocked) and reports a blocked session's `needs_action` text beside its status. A batch's stage stays derived from forge facts and never from a session's state.
R16. Every run records the `fr` version it started with. (The plugin's version is lockstepped with `fr`'s, so it is not recorded separately; the agents a worker dispatches are the repo's `agents` artifact, whose stamp fr's own gate checks, R19.)
R17. The driver acts on version drift only when it is incompatible: the run's recorded `fr` major differs from the current release's. It then re-homes the session at its next idle moment (the session pushes its work and stops; a fresh session continues the same branch from a resume brief built from the run cursor and journal), at most once per (run, release). A run with no recorded versions is reported, never re-homed.
R18. The driver itself runs the current release: before each pass it compares the installed `fr` with the latest release and, when older, reinstalls and runs the pass on the new one; when the release's major differs from the one its own session started with, it re-homes itself (R17), since the skill text it loaded cannot be relied on to refresh in place (discovery `plugin-late-load`).
R19. A cloud session's fr agents come from the repo, not the plugin: `.claude/agents/fr-spec-reviewer.md` and `.claude/agents/fr-phase-executor.md` are a new artifact kind, `agents` (§H), written by `fr init`, stamped with the version they were rendered for, refreshed by `fr migrate artifacts --yes` and checked by `fr validate artifacts`, so a release that changes them leaves the repo's CI red until it is migrated. The cloud environment's setup script installs the `fr` CLI and the plugin into the container (rsync installed, the Claude settings files seeded), and `scripts/install.sh` fails, rather than warning and exiting 0, when it cannot register the plugin. The worker brief's first step checks `fr --version` (installing super-fr when it is missing) and that `fr-spec-reviewer` and `fr-phase-executor` are dispatchable agent types; when they are not, the worker ends BLOCKED with a `needs_action` naming the missing `agents` artifact, and is not re-homed, since a fresh session would start the same way. A worker enters fr-isolation through the CLI itself; the plugin's hooks are defence in depth there, and their presence in a worker session is an owed measurement (§H).
R20. The `post_merge` step is an operation of the environment the driver runs in: the host runs the repo's `post_merge` argument list as today; the cloud runs nothing, since every new session installs the current release at its start and the driver updates itself (R18).
R21. The fr-triage skill documents the cloud driver, `forge.api`, the state ref, the state repo choice and the privacy guard, within its existing line budget.
R22. A phase unit's or `deliver`'s test evidence may be the forge's CI instead of a local suite log: `evidence: {tests: ci}`. On a `done` resolve fr accepts it only when HEAD is pushed and no code path is uncommitted; the branch has an open, non-conflicting pull request; and the repo's **gate checks** (the names in `.fr/ci.yaml`'s `gate_checks`, else the base branch's required status checks; neither → `ci` refused) have each completed with success on the CI sha — HEAD, or the nearest pushed first-parent ancestor whose code tree equals HEAD's. Every other check is ignored. The witness records the CI sha, the base sha CI merged it with, and HEAD's code tree, so `tests: reuse` keeps working and nobody mistakes it for a test of HEAD alone. A pending gate refuses with its own exit code and "resolve again when CI finishes"; a failed or absent one refuses naming it; a repo whose `fr services` CI is `none`, or a forge other than GitHub, refuses `ci` outright. A local log stays accepted everywhere (§I).
R23. In a Claude Code cloud session, when an fr command fails because the cloud environment lacks a prerequisite this spec relies on (the REST backend setting, the registered plugin, the repo's `agents` artifact, a current `fr`, `rsync`), fr says so and tells the operator how to fix the environment once: edit the cloud environment's setup script (or create a new environment) with the script `fr cloud setup-script` prints, and start a new session. `fr cloud doctor` lists every prerequisite and its state. Nothing of this prints on a host (§H, decision d11).

## Design

### A. `github-rest`: a forge backend, not a cloud feature

**Selection (R3).** `fr.forgeapi.resolve()` takes no argument and reads
`FR_FORGE_API`, else `api:` in the host file `~/.config/fr/forge.yaml` (beside
`host-id`, same `$HOME` rule as `scope_config.host_id_path`), else `graphql`. It
needs no forge client and no scope, so the run-path callers, which have none,
resolve it the same way; a repo-level key is deliberately not offered: collect
reads `.fr/triage.yaml` through the client the setting picks. A scope's
`scope-durable.yaml` (§B) records the `forge_api` the scope was driven with;
restoring a fresh workspace from the ref writes it to `forge.yaml` only when that
file is absent, and the host file always wins over it. The resolved value is
consulted in one place per seam:

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
- the agent-facing commands (`hostclient.FORGE_COMMANDS["github"]` :85-96: PR
  create/edit/ready, issue close, `issue edit --add-label`, label create) gain a
  `github-rest` variant spelled as `gh api` calls on the matching REST routes, and
  fr names that variant in every brief and refusal line when `rest` is selected;
- `RealGhRestClient` never falls back to GraphQL. Its error contract is per
  method, never blanket: a method whose `GhClient` contract answers `None` when
  the forge cannot say (`pr_for_branch`, `issues_enabled`, ghclient.py :323-332)
  keeps that contract, so isolation's callers (`isolation/local.py` :2962) are
  unchanged; every other method raises on a 403 rather than returning the soft
  empty answer some GraphQL methods return on `GhError` (`list_linked_prs`,
  real_ghclient.py :130) (R1). `pr_for_branch` takes only a checkout, so the REST
  client derives `owner/repo` from that checkout's `origin` URL.

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
| `gh pr checks --required` | the required contexts from `GET branches/{base}` (`protection.required_status_checks`, readable without admin) united with `GET rules/branches/{base}` (ruleset contexts), joined with the check runs by name and by status context. `GET branches/{base}/protection/required_status_checks` is NOT used: it needs admin and answers 403 to the cloud token (discovery `p1-required-checks-route-refused`). |
| `gh pr merge --match-head-commit` | `PUT pulls/{n}/merge` with `sha`. |
| `viewerDefaultMergeMethod` | **Gap:** REST has none, so `repo_merge_methods` answers `default: None`. `.fr/triage.yaml` gains an optional `merge_method: merge \| squash \| rebase`, which `choose_method` uses when the forge names no default (on either backend); under `rest`, a repo allowing several methods with no such setting refuses merge and drive, naming the key. |
| `closingIssuesReferences` node ids (`id`, `repository.id`, `owner.id`) | **Gap:** not produced; collect reads none. |
| `author.name` on list records | **Gap:** absent from REST list records; `login` is present. |
| `reviewDecision: REVIEW_REQUIRED` | **Gap:** derived from submitted reviews only, so it is never `REVIEW_REQUIRED`. |
| `gh pr ready` | **Gap:** GitHub REST has no ready-for-review. The `github-rest` command uses the Claude Code cloud proxy's `POST repos/{r}/pulls/{n}/ccr/ready_for_review`, which exists only behind that proxy, where `forge.api: rest` is selected (decision `p1-ready-via-ccr-route`). |
| `gh repo list <org>` | **Gap:** `GET orgs/{o}/repos` is refused from a cloud session (sessions are bound to their configured repositories); `list_repos` raises, and a cloud scope over an org takes its repo list from the scope itself (discovery `p1-list-repos-refused-in-cloud`). |

Closing references are parsed as GitHub does: a keyword at a word boundary,
outside code fences and inline code, followed by `#n`, `owner/repo#n` or an
issue URL on the repo's own GitHub host; refs are built on that host, never a
hard-coded `github.com`. Label removal treats a 404 for a label the issue does
not carry as success, as `gh issue edit --remove-label` does; `state_reason` is
sent in GitHub's spelling (`completed`, `not_planned`, `reopened`).

A contract test feeds the same recorded forge state to both backends and
compares their records (R2).

### B. State in the workspace, durable on a ref

**Where (R4).** `fr.triage.model.state_dir` gains a workspace input: the git
toplevel of the driver's working directory, or `--workspace PATH`. The directory
is `<workspace>/.fr/triage-state/<scope>/`, excluded through
`<git-common-dir>/info/exclude`, so no tracked file changes, on the default
branch or anywhere. Outside any clone and with no `--workspace`, the state
directory is the legacy `~/.cache/fr/triage/<scope>/`, unchanged (p3-r3: a
host command typed from `$HOME` keeps working). A legacy directory found on a
workspace's first use has only its durable files copied in (`REF_FILES` that
exist, `facts.json`, `scope.yaml`), never `merge/` scratch worktrees, a
`drive.lock` or rendered pages (p3-r2), and is left alone. `drive.lock` lives in
`~/.cache/fr/triage/<scope>/` for every workspace, so it stays the same-host
check across clones (p3-r3).

**One state across workspaces (R5, p3-r1).** Once a scope has a `state_repo`,
every triage command that reads state fetches the ref first (adopting it when
the local copy is not ahead) and every command that changes state pushes it
after the change, through one wrapper in the triage CLI, not per verb; a push
conflict refuses with the fetch-and-retry line. `fr triage state push|fetch`
remain as the explicit verbs. `.state-ref` (the last pushed or fetched sha, kept
out of `REF_FILES`) records the remote and ref it came from; a stored sha for a
different remote or ref, or one the remote no longer has, is discarded rather
than reported as another writer's push (p3-r4). A fetch that would overwrite
local changes not yet pushed refuses, and a fetch removes files the ref no
longer carries (p3-r4). `fetch_ref` fetches first and then reads the local ref,
never `ls-remote` then fetch (p3-r5). Files keep their git mode across the ref:
an executable stays 100755, restored files take the user's umask (p3-r12).

**Deciding the state repo once (p3-r7).** `_settle_state_repo` runs on an
explicit `fr triage collect` only, never inside the drive or watch loop's
collects; an undecided scope in a loop warns once per pass and keeps state
local. Visibility comes from the repo list where the forge already returns it
(org listings) and from one `GET repos/{r}` per repo otherwise, cached in facts
for the pass, never re-read per repo on every pass when the list carries it
(p3-r9). `triage` stays in `READ_ONLY_COMMANDS`: it still writes no
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
  `forge_api`, so a fresh workspace recovers them from the ref
  (`ScopeConfig` is `extra="forbid"`, scope_config.py :89, so both become
  optional fields of the host `scope.yaml` model too, where `state_repo` is
  mirrored);
- the cloud runner's mailbox (§F): `requests.yaml` (pending requests and their
  recorded results), `sessions.yaml` (every session dispatched, by item id) and
  `rehomes.yaml` (the per-(run, release) re-home ledger, §G), so a driver
  restored on a fresh container neither loses a pending request nor re-homes a
  run twice.

`facts.json` and the rendered pages are left out (fr rebuilds them). The host-only
`scope.yaml` and the host id stay out, as today. `fr.triage.gitseam` gains
`fetch_state` and `push_state`; a push is a compare-and-swap
(`--force-with-lease=<ref>:<old>`), so a lost lease or a second writer fails the
push rather than overwriting. Refs outside `refs/heads/` are not branches: no
branch list, no protection rules, no PRs. The wave export to `docs/triage`
(`export:`) keeps working for repos that want a reviewed copy; it is no longer
how state survives. **Owed measurement:** that the cloud git proxy accepts a
push of a ref outside `refs/heads/`, to the session's repo and to a state repo
the session did not start with; Test Plan 16 measures both.

**Where the ref lives (R6, R7).** Recorded as `state_repo` in
`scope-durable.yaml` (in the ref) and mirrored to the host's `scope.yaml`. The
first collect of a scope with none decides it: one repo → that repo, no
question; several or an org → it reads each repo's visibility (`GET
repos/{owner}/{repo}`, recorded in facts) and asks, as R7 states. A
non-interactive run with no `state_repo` keeps state local and warns once per
pass. The cloud driver is started with its state repo (R11), so it can fetch its
ref before it has any local state.

**Identity.** The scope id is `sha256(name, host id)` (`scope_config.py`), and
`FR_HOST_ID` already overrides the host id, which otherwise lives in
`~/.config/fr/host-id` (scope_config.py :34). Each tool call is a fresh shell,
so an environment variable set during one wake does not reach the next: the
cloud driver's brief carries its host id, and the first step of every wake
writes it to `~/.config/fr/host-id` when the file is missing (R11). A fresh
container therefore derives the same scope id, finds its own ref, and
recognises its own claims.

### C. The privacy guard

One predicate, `fr.triage.privacy.leak_risk(scope, state_repo, keys)`, true when
any key's repo is private and the state repo is public. A key whose repo is not
one the scope covers (hand-edited, or left from a repo removed from a group) has
its visibility read like any other, and an unreadable one counts as private, so
it can never ride a push to a public state repo unchecked (p3-r8). It is called by
`batch create`/`edit` (`--issue`, `--add-issue`), by the wave setters, by every
judgement write that adds a key, by `push_state` and by `state export`. Each
refuses with exit 2, naming the issue, its repo and the state repo. The scope's
repos' visibility is read from facts, refreshed by every collect, so a repo made
private after the fact is caught at the next push. The state repo's own
visibility is not in facts (it need not be a repo in the scope, and a fresh
container has no `facts.json`), so `push_state` and `state export` read it with
`GET repos/{state_repo}` immediately before writing, and refuse when it cannot be
read; with no facts yet, the keys' repos are read the same way. The lease push
that opens a pass (§E step 1) is a push like any other and goes through the same
check (R8).

### D. The lease

`lease.yaml` in the ref: `holder` (scope id plus driver identity:
`cloud:<host id>` for the cloud driver, `host:<host id>` for a host driver; both
are stable across a restart with a new pid and across a re-homed driver session,
which keeps the host id its brief carries), `started`, `expires`. Duration:
three wake intervals plus the safety-net Routine's period, computed from the
configured values: 3 × 5 + 60 = 75 minutes by default. Taken and
renewed by the compare-and-swap push; released on a clean stop. A driver whose
holder identity matches renews its own expired lease; anyone else is refused,
and an expired foreign lease is reported and taken only with `fr triage lease
take --yes` (R9). `drive_lock.py` stays as the fast same-host first check.

### E. The driver adapter

`fr.triage.driver` defines `Driver`: run passes until done, given a runner, a
forge client and a state store. `host` wraps today's loop unchanged (R10). The
driver supplies the runner: dispatch, adopt and the drive loop take the runner
from the driver adapter instead of a batch's `launch.runner` default
(`triage_batch_cmd.py` :1094, :1269, :1487 read it from the repo's
`.fr/triage.yaml` today, `herdr` on this repo), so a host scope and a cloud scope
over the same repo, reading the same file, each dispatch through their own runner.
A batch's explicit `launch.runner` other than the driver's is reported and not
dispatched. The cloud driver ignores `post_merge` and `post_merge_restart` (§H).
`claude-cloud` is not a loop; it is a pass fr runs once per wake (R12):

```
fr triage drive pass --scope S --statuses statuses.json --outbox outbox.json
```

1. restore state from the ref if needed; check and renew the lease (a push,
   so it runs the privacy check of §C);
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
ran within the interval only renews the lease. **Owed measurements:** only
`send_later` self-wakes were observed (discoveries `wake-probe`,
`wake-probe-restart`); that PR-activity events wake an idle driver session, and
that a recurring Routine fires into the existing driver session rather than a
new one, are unobserved, and Test Plan 17 observes each.

### F. The `claude-cloud` runner

A new workspace package, `packages/fr-claude-cloud` (entry point `fr.runners:
claude-cloud`), a sibling of `fr-herdr` with the same obligations: a member of
the uv workspace and of the root `dependencies` (pyproject.toml :9), the
coverage `source` (:57), a version surface in `scripts/version_surfaces.py`, the
mypy command in AGENTS.md and CI, the runner-package list the devcontainer
scaffold's `POST_CREATE` keeps as a literal (pinned by
`tests/integration/test_runner_package_lists.py`; `install.sh` derives its own
`--with` set), an entry in `test_import_direction.py` (it never imports
`fr.triage`, and `fr` never imports it), and the `fr_dispatch.testing` run-unit
contract.

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
- `existing_dispatches` reads the recorded sessions (`sessions.yaml`, in the ref,
  §B) plus the tagged sessions the agent last listed, so a dispatch whose result was lost is found again, not
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

`fr run start` records `fr_version` in the run cursor (no separate plugin
version: the plugin's version is lockstepped with `fr`'s, `scripts/version_surfaces.py`,
and the version the session actually loaded is not readable from inside it,
discovery `plugin-late-load`). That changes the cursor's shape: the `run` kind's
`current_version` moves 9 → 10 with a registered migration (old cursors get no
field, which R17 treats as unknown) and its structure validator, per `.claude/rules/artifact-versioning.md`,
and the repo's own cursors are migrated in the same PR (R16).

Each pass reads every active batch's cursor from its batch branch
(`read_file_at_ref` on the branch head, REST contents) and compares the recorded
`fr_version` major with the latest release's. Equal → nothing. Different → one
`rehome` request at the session's next idle, recorded per (run, release) in
`rehomes.yaml`, which travels in the ref (§B), so it is never repeated, not even
by a driver restored on a fresh container. No recorded version → reported once, never re-homed (R17).
Artifact readability is not judged by the driver: a session whose `fr` meets a
newer artifact is already refused by fr's own migration gate, which tells it what
to do.

### H. Worker sessions and `post_merge`

**Agents come from the repo (R19).** A cloud session's CLI is a pre-warmed spare
that loaded its agent types before the setup script ran: the plugin's
`super-fr:fr-*` agents were absent for five minutes and two user turns in a
fresh session, while the same agents committed under the repo's
`.claude/agents/` were dispatchable in its first turn (discoveries
`spare-preload`, `repo-agents`). The reviewer gate already accepts the bare name
(`run_cmd._same_agent`). So the two agents become a new artifact kind, `agents`,
registered in `fr.artifacts.registry` like the others
(`.claude/rules/artifact-versioning.md`):

- **files:** `.claude/agents/fr-spec-reviewer.md` and
  `.claude/agents/fr-phase-executor.md`, each the canonical
  `plugins/super-fr/agents/<name>.md` with one added front-matter key,
  `fr_artifact_version`, the stamp. The canonical files ship in the `fr` wheel as
  generated package data, as the verification strategies do, guarded by a
  tripwire, so every harness's `fr` can render them;
- **written** by `fr init` (a new scaffold step) for every fr-enabled repo, and
  in this repo too, replacing the symlinks this branch committed as an
  experiment;
- **migrated** by `fr migrate artifacts --yes`: a release that changes either
  canonical file moves the kind's `current_version`, and the migration
  re-renders both files from the installed `fr`, so the repo's CI is red
  (`fr validate artifacts`, the migration gate) until someone migrates it, as
  with every other kind;
- **validated** by `fr validate artifacts`: present, stamped, front matter
  parses, `name` matches the file.

The plugin keeps shipping its own `super-fr:` agents for host sessions; a host
session then sees both names, which is harmless, and the gate accepts either.

**The setup script** (shipped as a template in the `fr` wheel and printed by
`fr cloud setup-script`, never installed by fr: it is environment configuration
the operator pastes, measured in discovery `setup-script`) installs `rsync`, seeds
`~/.claude/plugins/installed_plugins.json` (`{"version":2,"plugins":{}}`) and
`~/.claude/settings.json` (`{}`) when absent, clones the super-fr marketplace,
runs `scripts/install.sh`, and writes `api: rest` to `~/.config/fr/forge.yaml`.
`install.sh` itself now fails, naming the missing file, instead of warning and
exiting 0 when it cannot register the plugin.

**Telling the operator how to fix the environment (R23, d11).**
`fr.cloud.detect()` is true when `CLAUDE_CODE_REMOTE=true` (set by the harness
in every shell of a Claude Code cloud session) — no other signal, so a host is
never mistaken for the cloud. `fr.cloud.check()` returns each cloud
prerequisite that is missing, with the fix: `forge.api` not `rest`
(`~/.config/fr/forge.yaml`), the super-fr plugin not registered in
`installed_plugins.json`, the repo's `agents` artifact missing or stale, the
installed `fr` older than the latest release, `rsync` absent. Three places use
it:

- `fr cloud doctor` prints every check, exits 1 when any fails;
- `fr cloud setup-script` prints the script above, filled for this repo;
- any fr command that fails in a cloud session for a reason `check()` explains
  (a GraphQL 403 under `graphql`, a refusal naming the `agents` artifact, an
  older fr than the run needs) appends one block after its own error, the
  same wording everywhere (`fr.cloud.remedy_block`):

```
This is a Claude Code cloud session, and its environment is missing: <items>.
Fix it once for every future session: open the cloud environment menu in the
session's title bar → Edit → Setup script, paste the output of
`fr cloud setup-script`, and start a new session (new sessions run the script;
this one does not). Or create a new environment with that script.
Docs: https://code.claude.com/docs/en/claude-code-on-the-web
```

On a host the block never prints. The worker brief's BLOCKED `needs_action`
(R19) quotes the same block, so an operator reading the board sees the fix.

**The worker brief's first step:** `fr --version` (install super-fr when it is
missing, d7's fallback), then confirm `fr-spec-reviewer` and `fr-phase-executor`
are dispatchable agent types. When they are not, the repo lacks a current
`agents` artifact: the worker ends its turn BLOCKED with a `needs_action` naming
it (`fr init` or `fr migrate artifacts --yes`, then a new session), and is not
re-homed, since a fresh session from the same commit would start the same way.
A worker enters fr-isolation through the CLI (`fr isolation up`), so isolation
does not depend on the plugin's hooks; whether those hooks are live in a worker
session is an owed measurement, observed in Test Plan 17.

**`post_merge`** becomes a driver-environment operation: `host` runs the configured
argument list; the cloud driver runs nothing, because every session it starts
installs the current release and the driver updates itself before each pass
(R18, R20).

### I. CI as test evidence

A cloud container is small (4 cores here, discovery `slow-suite`): this repo's
full suite, about 2.5 minutes on a 12-core host, takes about 20 minutes there,
while the repo's own CI runs it sharded four ways on every push to a PR. So a
phase executor or `deliver` may name the CI run instead of a local log
(R22). What CI proves is narrower than a local log, and the design says so
rather than hiding it: a `pull_request` workflow checks out the synthetic merge
of the head into the base (`actions/checkout` with no `ref:`), so a green run
vouches for "this code tree merged with that base", recorded as such.

**Gate checks.** Only named checks count (other workflows, the change-fragment
or acceptance gates, a second app's status, finish at their own times and are
not test results). `.fr/ci.yaml` (one key, `gate_checks: [<check name>, …]`)
names them. The gate set is the UNION of the file on the PR's base branch
(`origin/<base>`) and the file at HEAD, so a branch can add a gate but never
drop one its base declares; a branch that adds or edits `.fr/ci.yaml` does so in
its own reviewed diff (p2-r2). With neither file, the gates are the NAMES the
base branch requires (protection summary and rulesets, §A's routes), read
whether or not those checks have reported yet, so a required check not created
yet is pending, never skipped (p2-r1); with no file and no required check, `ci`
is refused, naming both ways to declare one. This repo ships `.fr/ci.yaml` with
`gate_checks: [ci-ok]` (`ci.yml`'s aggregator, which needs every test job). A
gate check whose conclusion is `skipped` is a failure here, not a pass.

**Reading checks: `GhClient.commit_checks(repo, sha)`.** A new protocol method
returning `{name, workflow, status, conclusion, url}` per check: check runs
from `GET commits/{sha}/check-runs?filter=latest` (workflow from the run's check
suite, as §A's `workflowName`), commit statuses from `GET commits/{sha}/status`
(latest per context). Latest per (workflow, name), so a failed attempt re-run
green counts as green. `RealGhRestClient` and `RealGhClient` both implement it
with those REST routes (`gh api` works on either backend); the fake client
serves fixtures; glab and tea raise `UnsupportedForgeOperation`.

`fr.run.ci_evidence.verify_ci(repo_root, client)`, in order, every refusal
before any write:

1. `fr services` CI is not `none` and the forge is GitHub; else refuse.
2. HEAD is the remote branch's head (`git ls-remote`, through `fr.git`) and
   `dirty_code_paths` is empty; else refuse naming what is unpushed or dirty.
3. The CI sha: walk HEAD's first-parent ancestors (at most 50) while
   `code_tree(<rev>) == code_tree(HEAD)`; the first one CI reported gate checks
   on is the CI sha. fr's own bookkeeping commits change no code path
   (`code_tree` excludes fr's artifact trees), so a `chore(fr)` commit on top of
   a tested sha needs no new CI run.
4. An open PR exists for the branch and `pr_view`'s `mergeable` is not
   `CONFLICTING`; else refuse with that reason (GitHub runs no `pull_request`
   workflow for a conflicting PR, so waiting would never end).
5. Every gate check on the CI sha is completed with `success`; pending →
   refuse with exit **75** and "CI has not finished for <sha>; resolve again
   when it does" (the cursor unmoved); failed, cancelled, skipped or absent →
   exit 2 naming each and its URL. A gate that is absent while any other check
   on the sha is still running counts as pending, not absent: an aggregator
   such as `ci-ok` gets no check run until the jobs it needs finish (discovery
   `p2-gate-absent-while-running`). Absent with every other check completed is
   a refusal. Likewise a FAILED gate while any other check in the gate's own
   workflow is unfinished is pending: a re-run creates its new gate check only
   when the jobs it needs finish (p2-r4). A walk on which no commit has any
   check at all is pending only while the newest walked commit is less than
   15 minutes old (committer time); after that it is refused, "no CI ran for
   <sha>", so fr itself ends a wait no workflow will ever answer (p2-r5). Every
   pending message names the URL of each unfinished check or, with none
   reported, the PR's checks page, so the orchestrator can report it (p2-r6).
6. Witness `ci:<ci sha>+<base>;tree=<code_tree(HEAD)>` — `<base>` is the base
   sha CI merged the CI sha with, taken from a check suite whose
   `pull_requests[].head.sha` equals the CI sha, and the literal `unknown` when
   no listed PR's head is the CI sha (GitHub reports the PR's current state, so a
   different head means the base may have moved since the run) (p2-r3).
   `_latest_tests_witness` and `tests: reuse` read the `;tree=` part unchanged.
   The PR body renders a `ci:` witness as "CI (`<gates>`) green on `<ci sha>`
   merged with `<base>`", never as a local full-suite run, and the missing-tests
   refusal hint offers `tests: ci` beside a log path where a CI is configured
   (p2-r8). The open-PR lookup reads only the PR's number, state and mergeable,
   never its files (p2-r7).

The token is recognised before the phase-log branch of the evidence dispatch
(`run_cmd`'s `"tests" in offered and phase is not None` comes first today and
would read `ci` as a file path). On a non-`done` resolve, `tests: ci` is
accepted without reading CI and recorded as the bare claim `ci`: a failed phase
vouches for no tree, as a failed local-log resolve already does.

**Waiting.** Exit 75 is not an idle point: the unit stays held. In a cloud
session the PR-activity subscription wakes the orchestrator when the run ends.
Everywhere else fr-goal tells the orchestrator to wait with a bounded loop
(re-run the resolve every 2 minutes, at most 45 minutes, then report the unit
blocked with the gate's URL).

**Prose this changes,** all in this PR: fr-goal §5 (what fr verifies for an
executor's evidence, and the `ci` alternative), §6 (the draft PR is opened when
`implement` starts for a run that uses `ci`, an exception to "never open the PR"
that names this requirement), §8 (`deliver` may say `tests: ci`); the
fr-phase-executor agent (commit, push, return `tests_log: ci` instead of
running the full suite, when the brief says so), with its OpenCode and Hermes
mirrors, shipping to other repos through the `agents` kind's re-render (R19);
and the `01-fr-goal` explainer if it describes local-only test evidence
(`.claude/rules/explainers-currency.md`). The local-log path is unchanged.

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
   view --json`; a 403 from it is raised, not swallowed, by every method except
   `pr_for_branch` and `issues_enabled`, which answer `None` as their contract
   says; with `rest` selected, no `FORGE_COMMANDS` entry fr prints for an agent
   names a GraphQL-backed `gh` command (R1, R3).
3. Unit: `forge.api` resolves from `FR_FORGE_API`, then `~/.config/fr/forge.yaml`,
   else `graphql`, with no scope and no forge call; a fresh shell with only the
   file set resolves `rest`; a ref restore writes `scope-durable.yaml`'s value to
   the file only when it is absent (R3).
4. Unit: state lives in the workspace; the repository's `info/exclude` (under
   the git common dir, from a linked worktree too) gains the entry and no tracked
   file changes; a `~/.cache` copy is imported once (R4).
5. Unit: `push_state`/`fetch_state` round-trip every `REF_FILES` entry into a
   fresh clone, merge stops, lease, `requests.yaml`, `sessions.yaml` and
   `rehomes.yaml` included; a concurrent writer's push fails the compare-and-swap
   (R5, R9).
6. Unit: the state-repo decision for one repo, a mixed set, and an all-public
   set, including the warning; a fresh workspace recovers `state_repo` and
   `forge_api` from the ref; the wake's first step writes the brief's host id to
   `~/.config/fr/host-id` when missing and the scope id is unchanged (R6, R7, R11).
7. Unit: the privacy guard refuses a private issue into a batch, a wave, a push
   and a `state export` when the state repo is public, and allows them when it is
   private; the state repo's visibility is read from the forge before each push,
   with no `facts.json` and when the state repo is outside the scope; an
   unreadable visibility refuses the push, the lease push included (R8).
8. Unit: a second driver is refused by the lease; the same holder renews its own
   expired lease; a re-homed cloud driver (new session, same host id) renews the
   lease as the same holder; an expired foreign lease is reported and not taken
   without the operator command; the duration is computed from the configured
   interval and Routine period, 75 minutes by default (R9).
9. Unit: `drive pass` over a fixture scope makes the same decisions the host loop
   makes for the same facts; `drive record` applies every result; a pass whose
   results were lost re-emits its pending requests, and replaying them creates no
   second session (tag lookup); a driver restored from the ref on a fresh
   workspace still holds its pending requests and recorded sessions; with one
   `.fr/triage.yaml` naming `herdr`, a host scope dispatches through herdr and a
   cloud scope through `claude-cloud`, and the cloud driver runs no `post_merge`
   (R10, R13, R14).
10. Unit: the status mapping, `completed` → idle with a conflict handed back by
    message, `needs_action` reported through `SessionNotes`, and a session's state
    never changing a batch's stage (R15).
11. Unit: the run kind's 9 → 10 migration, its validator, and every hop of the
    chain; a run started now records its `fr` version (R16).
12. Unit: drift — same major requests nothing; a different major requests one
    re-home per (run, release), never two, also after a restore from the ref; a
    run with no version is reported only; the driver's self-update reinstalls on
    a newer release and self-re-homes on a new major, keeping its lease (R17, R18).
13. Unit: the worker brief's first step checks `fr --version` and installs only
    when missing, then checks the two agent types and, when either is missing,
    ends BLOCKED naming the `agents` artifact with no re-home request; the cloud
    driver's `post_merge` runs nothing; `install.sh` exits non-zero when it cannot
    register the plugin (R19, R20).
14. Scenario (`candidate`): a scripted pass against the fake forge and a fake
    session executor, from an empty workspace restored from the ref (R12).
15. Unit: the fr-triage skill names the cloud driver, `forge.api`, the state ref,
    the state repo choice and the privacy guard, and stays within its line budget
    (R21).
16. **Live, pre-merge (`client-live`), this cloud environment:** with
    `forge.api: rest` in `~/.config/fr/forge.yaml` and the branch build, collect,
    check and render `derio-net/super-fr` with no GraphQL error, and the board
    matches a host render of the same moment; push and fetch the scope's
    `refs/fr/triage/<scope-id>` through the cloud git proxy, to the session's own
    repo and to a state repo the session did not start with (R1, R2, R5).
17. **Live, pre-merge (`client-live`), this cloud environment:** a Sonnet driver
    session drives a wave of two small throwaway super-fr issues on its own
    scope beside the host driver: dispatches a worker session per batch, whose
    first turn lists `fr-spec-reviewer` and `fr-phase-executor` from the repo's
    `agents` artifact (and records whether the plugin's hooks are live there),
    shows a blocked worker's `needs_action`, hands back a conflict by message,
    re-homes one worker on a simulated major drift, lets the workers deliver
    (deliver's PR body read over REST, the PR opened with the REST spelling of
    `FORGE_COMMANDS`), merges, closes out, and survives a container restart by
    restoring from the ref; it observes, once each, a PR-activity event waking
    the idle driver and the hourly Routine firing into the existing driver
    session (R11-R15, R17-R20).
18. Unit: the `agents` kind — `fr init` writes both files from the wheel's copy
    with the stamp; `fr validate artifacts` passes them and fails a missing,
    unstamped or stale one; moving the kind's `current_version` makes the
    migration re-render both and every hop of the chain is asserted; the wheel's
    copy matches `plugins/super-fr/agents/` (tripwire) (R19).
19. Unit: `tests: ci` on an implement-phase and a `deliver` record — accepted
    when the gate checks (`.fr/ci.yaml`, else required checks) are green on the
    CI sha, recording `ci:<ci sha>+<base sha>;tree=<tree>`, which `tests: reuse`
    then accepts; accepted through a `chore(fr)` commit on top of the tested sha
    (same code tree) without a new run; a non-gate check failing is ignored; a
    gate re-run green after a failed attempt counts as green; refused (exit 75,
    cursor unmoved) while a gate is pending; refused (exit 2) when HEAD is
    unpushed, a code path is dirty, no PR is open, the PR conflicts, a gate
    failed, was skipped or is absent, no gates are declared, `fr services` says
    `ci none`, or the forge is not GitHub; recognised before the phase-log
    branch; on a `failed` resolve recorded as the bare claim without a forge
    call; a local log is still accepted (R22).
20. Unit: `fr.cloud.detect()` is true only with `CLAUDE_CODE_REMOTE=true`;
    `fr cloud doctor` reports each prerequisite (forge.api, plugin registered,
    `agents` artifact, `fr` current, `rsync`) and exits 1 on any failure;
    `fr cloud setup-script` prints a script that, run under a fresh tmp HOME,
    produces the state `doctor` passes (rsync and the clone stubbed); a GraphQL
    403 under `graphql` and an `agents`-artifact refusal in a cloud session end
    with the remedy block, byte for byte the same text, and on a host neither
    does (R23).

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
