# Journal: 2026-10-07-cloud-triage

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-10-07T12:58:09+00:00 input=true -->
### brief · discovery · Operator brief: run triage, the driver and the runners in a Claude cloud session

Verbatim, 2026-10-07 (two operator turns; the first is the context the second builds on):

> so this cloud environment is not particularly useful, if we can't install the tools we need.. We could use an fr-isolation mode here and even run herdr in theory (even in the background and talk with the other sessions via you, or create a new claude-cloud driver... Opinions? Also, can I ssh into the cloud environment and do anything useful or is this chatbox my only option?

> I do have a bunch of Claude "Cloud session credits" right now so that's a good chance to get acquainted with this environment and, why not, adapt super-fr to it. Let's get triage running in here. Not only the runners, the driver too. Let's fire a fr-brainstorming to explore it. What can we expect to get?

<!-- fr:journal kind=discovery scope=spec id=cloud-constraints created=2026-10-07T13:01:21+00:00 -->
### cloud-constraints · discovery · What blocks triage, drive and a runner in a Claude cloud container

Measured 2026-10-07 in a Claude Code cloud session (this repo, branch feat/cloud-triage).

- **Forge.** The egress proxy refuses GitHub GraphQL with HTTP 403 (REST via `gh api repos/...` works, auth injected by the proxy). Nearly every call on the triage path is GraphQL-backed through `gh issue|pr list|view --json`, `gh pr checks`, `gh pr merge`, `gh pr create`, `gh issue edit|comment`, `gh repo view --json`: collect, claim writes, merge, drive, adopt and export. REST today: `read_file_at_ref`, `viewer_login`, `edit_issue_comment`, `ensure_labels`, `delete_branch`. Seams: `triage_cmd.make_forge()` (:92, hard-codes `client_for_backend("github")`) and `triage_batch_cmd.make_client(url)` (:222); `GhClient` Protocol `ghclient.py:87`, factory `hostclient.client_for_backend` (:199).
- **Runner.** `fr_dispatch.protocols.Runner` (:36: preflight, refresh, slot_budget, existing_dispatches, can_dispatch, dispatch) plus optional SessionCloser/Inspector/Focuser/Messenger/Restarter/Adopter, loaded via the `fr.runners` entry point and `from_env()`. herdr leaks into fr in `.fr/triage.yaml` (`runner: herdr`, `post_merge_restart: idle`), `ADOPT_LIST_RUNNER = "herdr"` (`triage_batch_cmd.py:1385`), the `checkout`/`group` payload keys, and the `<prefix>-wave-<n>` workspace naming (`batch_drive.py:454`).
- **Process model.** `drive` is a `while True` loop (interval 120 s) with state under `$HOME/.cache/fr/triage/<scope>/` and a PID-based `drive.lock`; `post_merge` runs `./scripts/install.sh` in a base clone and may re-exec. On an ephemeral container the state, the lock and the loop all die with it.
- **Sessions.** The container has the `claude` CLI and tmux, no herdr. Creating, messaging and inspecting other cloud sessions, and scheduling Routines that wake a session (delivery survives restarts), are tools of the agent, not APIs fr's Python can call. A cloud runner is therefore agent-mediated: fr decides, the session's agent acts, as for `kind: agent` steps.
- **No prior art:** no spec mentions a REST fallback, GraphQL avoidance or remote sessions; `2026-07-09-multi-backend-git-host-adapters-design.md:54-61` lists the GraphQL-only fields.

<!-- fr:journal kind=decision scope=spec id=d1-scope-and-adapters created=2026-10-07T13:07:00+00:00 -->
### d1-scope-and-adapters · decision · Operator decisions, round 1: second scope, forge and driver as adapters, state in the workspace

Operator, 2026-10-07:

- **Second scope.** The cloud driver runs beside the host driver, not instead of it. Many drivers are planned, from many hosts and from the same host, over different repo combinations and orgs; a wave claiming its issues is what keeps them apart.
- **Forge is an adapter.** Not "gh": a `claude_cloud_gh` implementation of the forge adapter uses REST behind the scenes.
- **Driver is an adapter.** The driver loop becomes an adapter; a `claude_cloud_driver` implementation runs as a Routine.
- **State moves out of `~/.cache`** into the workspace, as a git-ignored file.
- **Plugin reinstalls after a merge (`post_merge`):** open. Wanted: one general solution for every fr-isolation shape, if one exists.

<!-- fr:journal kind=decision scope=spec id=d2-state-ref-and-privacy created=2026-10-07T17:20:57+00:00 -->
### d2-state-ref-and-privacy · decision · Operator decision, round 2: state on a ref, where it lives, and a privacy guard

Operator, 2026-10-07:

- **Durable state is a ref on the forge** (option a), one per scope; the git-ignored workspace file is the working copy.
- **Where the ref lives:**
  - one repo in scope: the ref goes in that repo;
  - several repos, or an org: if at least one is private, ask the operator to put it in one of the private ones;
  - all public: the operator chooses between a new repo just for the refs, or a public repo, with a warning that adding an issue from a private repo to a wave later can leak it.
- **Privacy guard:** when issues are added to a triage or a wave, a check blocks when there is a chance of a privacy violation.

Agent's reading, to confirm in the spec: the leak happens when state is pushed, so the same check also runs before every state push and every `docs/triage`-style export, not only when issues are added.

<!-- fr:journal kind=decision scope=spec id=d3-persistent-driver created=2026-10-07T17:36:03+00:00 -->
### d3-persistent-driver · decision · Operator decision, round 3: a persistent driver session

Operator, 2026-10-07: option (b), one long-lived driver session that wakes, over (a), a fresh session per Routine firing. Reason: the driver often has to step in to get runners unstuck, which an hourly, memoryless pass cannot do. The session stays long but gathers little context, since it is mostly status updates.

Open, owed a measurement before the spec commits: what the platform does to a session whose background process is still waking it, and which wake sources survive a container swap. Observed in this session at 2026-10-07 ~17:40Z: `CLAUDE_CODE_WORKER_EPOCH=5` and a container boot time of 17:32Z, well after the session began. Read as a hint that the worker or container has already been replaced during the conversation, not yet as proof.

<!-- fr:journal kind=discovery scope=spec id=wake-probe created=2026-10-07T18:41:31+00:00 -->
### wake-probe · discovery · Wake probe: a cloud session's disk and background processes over an hour of self-wakes

Measured 2026-10-07 17:38Z-18:41Z in this session: six `send_later` self-wakes ten minutes apart, each running a probe; a background shell writing one heartbeat line a minute (started 17:38:47Z, max lifetime 2 h).

- **Every wake was delivered** on time (17:49, 17:59, 18:10, 18:20, 18:30, 18:41Z), each within ~1 min of the scheduled minute.
- **Same container throughout:** container id, boot time (17:32:20Z), boot id and worker epoch (5) never changed.
- **Disk:** every marker survived (`~/.cache`, `/tmp`, the scratchpad, the base clone's `.git`, the worktree's `.fr-isolation`).
- **Background process:** alive at every wake; 63 heartbeat lines, the last at 18:40:47Z, none missed.
- **Earlier evidence:** files written at 12:43Z and 12:57Z survived the restart that produced the 17:32Z boot, and five worker diagnostic logs match epoch 5. So the disk has outlived worker restarts.
- **One probe was partial:** at 18:20Z the auto-mode permission classifier returned no verdict twice (a service error, not a denial); the probe fell back to read-only file reads.

**What this does not show:** what happens to a session idle for long with no wakes. The ten-minute wakes kept it active the whole time. The heartbeat keeps running until ~19:38Z, its 2 h limit; whether the container is still the same after that idle stretch is the next data point, read at the next operator turn.

**Design consequence:** a driver session waking every few minutes keeps one container, its disk and its processes. Restoring state from the forge ref is still needed on a new container (after a long idle, a restart or a reclaim), but is the exception, not every pass.

<!-- fr:journal kind=discovery scope=spec id=wake-probe-restart created=2026-10-07T18:45:26+00:00 -->
### wake-probe-restart · discovery · Wake probe, follow-up: a restart three minutes after the last wake kept the disk and killed the process

Observed 2026-10-07 18:45Z, with no wake scheduled and no operator turn: the platform restarted the session's container.

- New boot at 18:44:53Z (boot id `cb0ae1cf`, was `51d0eacb`); worker epoch 5 -> 6; the container id **did not change**.
- **Disk kept:** every marker survived, as did the worktree and its commits.
- **Process killed:** the heartbeat stopped at 18:44:47Z (67 lines). The harness reported the background task stopped and told the session to re-create it if needed.
- **Timing:** about 3 minutes after the last probe turn ended (~18:42Z). During the hour of ten-minute wakes, with the same background process running, no restart happened. The cause is unknown from inside the container: an idle timeout, or a platform-side restart (one MCP server disconnected around the same time).

**Design consequence:** a background process is not a reliable keep-alive or wake source; any process the driver starts must be re-creatable after a restart. The disk, including git-ignored state in the workspace, survived both restarts seen today. The forge ref remains the durable copy for when it does not (reclaim, or a session moved to a new container).

<!-- fr:journal kind=discovery scope=spec id=version-drift created=2026-10-08T09:24:40+00:00 -->
### version-drift · discovery · What a live session sees when the plugin moves under it (host, today)

Read 2026-10-08 from `scripts/install.sh` (:575-615), `plugins/super-fr/hooks/hooks.json`, `fr-binary-pin.sh` and `fr/binary_identity.py`.

- **Hook scripts: always the newest.** `install.sh` syncs the plugin in place into one `current` directory that is never deleted (gh#938), so a running session's hooks run the latest scripts. **Hook registration is the session's start version:** a hook added later never fires in it; a script removed later fails where it is registered.
- **Skills:** a skill invoked before the upgrade stays in context as the old prose; a later invocation reads the new file.
- **fr:** the SessionStart pin records `fr --identity`. Global `fr` upgraded under the session: same package dir, another version -> warn and suggest a restart. `uv run fr` from a worktree: one warning, then run. Only a PATH-reached `fr` that disagrees with the pin is refused.
- **Driver:** re-execs itself when `post_merge` changed the installed `fr` version (`triage_batch_cmd.py` :1970, :3980).
- **Artifacts:** a worker on its branch reads its branch's artifacts with its branch's `fr`; it meets newer stamps only when it merges `origin/main`, which brings the matching code in the same merge.
- **Cloud, today:** no super-fr plugin is installed in a cloud session at all; whatever installs it does so at session start, so a cloud session holds one version for life unless something reloads it. `/reload-plugins` (operator's suggestion) is unverified here: what it reloads, and whether a message sent by another session runs it as a command.

<!-- fr:journal kind=decision scope=spec id=d4-self-consistent-sessions created=2026-10-08T09:49:04+00:00 -->
### d4-self-consistent-sessions · decision · Operator decision, round 4: clean, self-consistent sessions

Operator, 2026-10-08: sessions stay self-consistent (the skills, fr and artifacts they started with, or their branch's), and the driver acts only on incompatible drift. The operator would prefer always-current sessions but accepts the harness and the cloud do not allow it.

Evidence: `/reload-plugins`, typed by the operator in this cloud session, answered "/reload-plugins isn't available over a remote connection in this session." So nothing can reload a cloud session's plugins in place.

The operator's own escape hatch for "I need the latest fr": stop the session, have the agent push its work, resume in a new session; the run cursor and the journal make resuming easy. Agent's note: that is the cloud's equivalent of `restart-idle`, a fresh session on the same branch with a resume brief, and a candidate for the driver's response to incompatible drift.

<!-- fr:journal kind=decision scope=spec id=d5-fr-decides created=2026-10-08T09:53:35+00:00 -->
### d5-fr-decides · decision · Operator decision, round 5: fr decides, the agent carries out; Sonnet drives; re-homing

Operator, 2026-10-08:

- **fr decides, the agent carries out** (option a): the cloud runner is a mailbox; fr plans each pass and does the forge work; the agent executes session requests and records their outcomes through fr.
- **The driver session runs on Sonnet;** Opus would be overkill for it.
- **Re-homing: yes.** On incompatible drift the driver has the worker push and stop, then starts a fresh session on the same branch with a resume brief. Not token-efficient, but pragmatic.
- **Status mapping:** `completed` maps to done only if it means after a close-out (see discovery `cloud-session-status`).

<!-- fr:journal kind=discovery scope=spec id=cloud-session-status created=2026-10-08T09:53:37+00:00 -->
### cloud-session-status · discovery · What a cloud session's status_bucket means

Read 2026-10-08 from the operator's own session list (15 sessions; repos and titles not recorded here).

- `status_bucket` follows the platform's **post-turn summary** of the session's last turn, a model-written classification with `status_category`, `status_detail` and `needs_action`:
  - `need_input` -> **BLOCKED**, with `needs_action` naming what the agent waits for ("express go-ahead to proceed", "confirm proceed with merge"). So BLOCKED means waiting on the operator's answer, not only a permission prompt.
  - `completed` -> **COMPLETED**, seen on idle sessions as well as archived ones. It means the agent judged its last task finished. It says nothing about fr's batch lifecycle, and the session can still be messaged.
  - **WORKING** while a turn runs; **REVIEW_READY** seen once, on a session with no summary recorded.
- **Consequence for the mapping:** session status stays a per-session signal (batch session and close-out session each have their own); the batch's stage remains derived from forge facts (PR merged, archive PR merged), never from `completed`.
- **Side finding for super-fr#1086:** BLOCKED plus `needs_action` is exactly the "agent ended its turn on a question" signal #1086 says herdr cannot give.

<!-- fr:journal kind=decision scope=spec id=d6-github-rest created=2026-10-08T09:56:27+00:00 -->
### d6-github-rest · decision · Operator decision, round 6: a general github-rest forge backend

The REST-only GitHub client is a general backend (`github-rest`), selectable anywhere by one setting; the cloud environment selects it by default. Not a cloud-only `claude_cloud_gh`. Operator, 2026-10-08.

<!-- fr:journal kind=decision scope=spec id=d7-worker-setup created=2026-10-08T10:07:00+00:00 -->
### d7-worker-setup · decision · Operator decision, round 7: worker sessions get super-fr from the environment's setup script

Operator, 2026-10-08: (a) the cloud environment's setup script installs super-fr (clone the marketplace, run install.sh); it covers most cases on the Anthropic cloud, other cloud agents to be revisited if ever used. (c) the brief telling the worker to install it is the fallback only, when `fr` is missing. Default taken without objection: one driver per scope, enforced by a lease stored in the state ref (holder session plus an expiry its wakes refresh); a second driver is refused; an expired lease is reported, never taken over silently.

<!-- fr:journal kind=decision scope=spec id=d8-verification created=2026-10-08T10:19:43+00:00 -->
### d8-verification · decision · Operator decision, round 8: verification

Operator, 2026-10-08: default strategy `candidate` (offline scenarios against a stubbed forge); `client-live` for (1) the github-rest backend against real GitHub from this cloud environment and (2) the cloud driver end to end. The end-to-end walk runs on derio-net/super-fr itself, on two small throwaway issues (the operator does not mind), which also exercises two scopes (host and cloud) on one repo.

<!-- fr:journal kind=discovery scope=spec id=no-plugin-agents created=2026-10-08T11:39:26+00:00 -->
### no-plugin-agents · discovery · spec-review cannot resolve in a cloud session without the super-fr plugin

Observed 2026-10-08 in this session: `fr run resolve --step spec-review` refused a review done by a general-purpose subagent following `plugins/super-fr/agents/fr-spec-reviewer.md` verbatim: 'this step's reviewer is super-fr:fr-spec-reviewer. Dispatch that agent and name its id.' The agent type exists only when the super-fr plugin is installed, and a session's agent types are fixed at its start (no reload over a remote connection). So the same gate will refuse `review-phase` (fr-phase-executor's reviewer) in any cloud worker session that started without the plugin. This is direct evidence for R19: the environment's setup script must install super-fr BEFORE the session starts; the brief's fallback install (R19, second half) cannot fix the agent types of a session already running, only the CLI. The review itself is recorded in the run's spec-review record; its 15 findings are fixed in the spec.

<!-- fr:journal kind=discovery scope=spec id=setup-script created=2026-10-08T11:44:48+00:00 -->
### setup-script · discovery · A cloud setup script that installs super-fr: what install.sh needs on a fresh container

Measured 2026-10-08 against a throwaway HOME in this container (Ubuntu 24.04): (1) `rsync` is missing and `install.sh` hard-requires it, so the script installs it with apt; (2) a fresh container has no `~/.claude/plugins/installed_plugins.json` and no `~/.claude/settings.json` (this session's `~/.claude` has neither), and `install.sh` then skips plugin registration with only a WARNING and exits 0, which is a silent half-install; seeding `{"version":2,"plugins":{}}` and `{}` first makes it register and enable both plugins and sync the agents (`fr-spec-reviewer`, `fr-phase-executor`) into the cache. The script (clone main into ~/.cache/fr/src/super-fr, run bootstrap.sh) exits 0 on a fresh HOME and again on a re-run, ending with `fr 5.17.1`. Not yet proven: that a cloud session started after it actually loads the plugin's agents; that is the next session's first check. Follow-up owed by the plan: `install.sh` should create those two files itself (or fail) rather than warn and exit 0.

<!-- fr:journal kind=discovery scope=spec id=spare-preload created=2026-10-08T11:52:05+00:00 -->
### spare-preload · discovery · A setup script cannot give the session it prepares the plugin's agents: the CLI is a pre-warmed spare

Observed 2026-10-08, the session after `setup-script`. The setup script ran and installed everything: `~/.claude/plugins/installed_plugins.json` lists super-fr and super-fr-dispatch 5.17.1 (installedAt 11:49:26Z), `~/.claude/settings.json` enables both, the cache holds `agents/fr-spec-reviewer.md` and `fr --version` is 5.17.1. The session nevertheless has no plugin agent types (only the built-ins), no fr-* skills and no plugin hooks. The reason is the CLI process itself: its command line is `claude --preload <spare socket>`, a pre-warmed spare that loaded its configuration before the setup script ran and was then assigned to this session (session startedAt 11:49:35Z). So R19's premise ("runs before the session starts so the plugin's agents and hooks are loaded") does not hold: the setup script runs before the session is ASSIGNED, but after the process loaded its agents. Consequence: `fr run resolve --step spec-review` refuses every reviewer this session can dispatch (the gate checks the observed agent type, `super-fr:fr-spec-reviewer`), and `review-phase` would too. Not measured: whether project-scoped config committed in the repo (`.claude/agents/`, `.claude/settings.json` enabledPlugins) is read at preload or at assignment.

<!-- fr:journal kind=discovery scope=spec id=plugin-late-load created=2026-10-08T11:53:32+00:00 -->
### plugin-late-load · discovery · The plugin loads late: skills appear mid-session, agent types never do

Observed 2026-10-08, same session as `spare-preload`. Several minutes into the session the super-fr and super-fr-dispatch skills appeared in the session's skill list (the plugin installed by the setup script was picked up after all), but an Agent dispatch of `super-fr:fr-spec-reviewer` still failed with "Agent type not found", listing only the built-ins. So skills (and possibly hooks) reload mid-session; agent types are fixed when the session starts. That narrows `spare-preload`: the setup script is not useless, but it cannot provide the agent types the reviewer gates check. Experiment in flight: the canonical agents are symlinked into the repo's `.claude/agents/` and the plugin is enabled in `.claude/settings.json`; the next cloud session's first check is whether `fr-spec-reviewer` is a dispatchable agent type there.

<!-- fr:journal kind=discovery scope=spec id=agents-late-load created=2026-10-08T11:57:24+00:00 -->
### agents-late-load · discovery · Correction to plugin-late-load: the plugin's agent types did arrive mid-session too

Observed 2026-10-08, same session, after `plugin-late-load` was written: the session was notified that `super-fr:fr-spec-reviewer` and `super-fr:fr-phase-executor` are now available agent types. So `plugin-late-load`'s "agent types never do" is wrong: skills arrived first, agent types later, both without a restart. Cause not isolated: the agents appeared after this session committed `.claude/settings.json` (project enabledPlugins) and `.claude/agents/`, so either the plugin load completes late on its own, or the project-settings write triggered a reload. Distinguishing them needs a cloud session with no repo-scoped files that waits (or polls the agent list) before its first review dispatch.

<!-- fr:journal kind=discovery scope=spec id=repo-agents created=2026-10-08T12:08:42+00:00 -->
### repo-agents · discovery · Repo-scoped agent files are dispatchable from a cloud session's first turn; the plugin's are not

Measured 2026-10-08 with two fresh cloud sessions in this environment (same setup script). Probe 1, on main (no `.claude/agents/`, no project settings): at 0-5 min and across two user turns, only the built-in agent types and no super-fr skills; `super-fr:fr-spec-reviewer` "not found" five times. Probe 2, on feat/cloud-triage (`.claude/agents/fr-spec-reviewer.md` and `fr-phase-executor.md`, symlinks to the canonical files, plus project `enabledPlugins`): `fr-spec-reviewer` and `fr-phase-executor` were listed in its first turn, and a dispatch of the bare `fr-spec-reviewer` returned at once; `super-fr:fr-spec-reviewer` was still "not found" and no super-fr skills were listed. So project agent files are read when the session is assigned, the plugin is not, and the project `enabledPlugins` did not make the plugin load at start. The reviewer gate accepts the bare name (run_cmd.py `_same_agent`). The plugin did arrive late in one session (`plugin-late-load`, `agents-late-load`) but not in probe 1 within 5 minutes, so it cannot be relied on. Consequence: a repo that runs fr-goal workers in the cloud needs the agent files committed under `.claude/agents/`.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · forge.api selection point does not exist as described

target: spec
scope: in, per the reviewer
check: codebase
evidence: spec §A / R3; hostclient.py:199-236; triage_batch_cmd.py:222; triage_cmd.py:92; collect.py:660
`client_for_url` vs `client_for_backend`; the latter is provenance-blind; a repo-level `forge.api` cannot pick the client needed to read `.fr/triage.yaml`.

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · Cloud worker and close-out sessions still hit GraphQL outside the triage path

target: spec
scope: in, per the reviewer
check: consistency
evidence: R1, R19, Test Plan 13; gh.py:177; run_cmd.py:6037; run/adopt.py:747; run/closeout.py:346; isolation/local.py:2962; real_ghclient.py:130
Workers' deliver, close-out, adopt and isolation reads are GraphQL; some fail soft.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · R2 exceptions table omits workflowName, which _latest_runs keys on

target: spec
scope: in, per the reviewer
check: codebase
evidence: §A table; collect.py:232-259
REST check-runs carry no workflow name; startedAt zero-time normalisation unstated.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · Scope id, ref name and state_repo are host-local; a new container loses them

target: spec
scope: in, per the reviewer
check: codebase
evidence: R5, R9, R12; scope_config.py:3-7, :34-35, :78-83; state_sync.py:45
scope_id derives from a per-host id; state_repo lives only in host-local scope.yaml.

<!-- fr:journal kind=finding scope=spec id=s5 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s5 · finding [open] (reviewer: in scope) · The ref's tree omits merge stops, the lease and scope config

target: spec
scope: in, per the reviewer
check: consistency
evidence: §B vs R4, §D; state_sync.py:45-46; merge_stops.py:25

<!-- fr:journal kind=finding scope=spec id=s6 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s6 · finding [open] (reviewer: in scope) · A mailbox runner conflicts with synchronous runner calls; crash window undefined

target: spec
scope: in, per the reviewer
check: consistency
evidence: R14 vs §E; protocols.py:111-138; triage_batch_cmd.py:3400-3413

<!-- fr:journal kind=finding scope=spec id=s7 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s7 · finding [open] (reviewer: in scope) · SessionStatus cannot carry needs_action

target: spec
scope: in, per the reviewer
check: codebase
evidence: R15; protocols.py:142, :155; kanban.py:57

<!-- fr:journal kind=finding scope=spec id=s8 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s8 · finding [open] (reviewer: in scope) · R15 maps completed to done unconditionally, against d5's condition

target: spec
scope: in, per the reviewer
check: decisions
evidence: d5; discovery cloud-session-status; triage_batch_cmd.py:3403-3422

<!-- fr:journal kind=finding scope=spec id=s9 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s9 · finding [open] (reviewer: in scope) · R18 cannot hold for a long-lived cloud driver given R20 and d4

target: spec
scope: in, per the reviewer
check: consistency
evidence: R18 vs R20, §H, d4; triage_batch_cmd.py:3940-3961

<!-- fr:journal kind=finding scope=spec id=s10 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s10 · finding [open] (reviewer: in scope) · Drift-check inputs undefined

target: spec
scope: in, per the reviewer
check: codebase
evidence: R17, §G; run/model.py:351-379; artifacts/registry.py:407

<!-- fr:journal kind=finding scope=spec id=s11 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s11 · finding [open] (reviewer: in scope) · The first write edits the tracked .gitignore; workspace undefined

target: spec
scope: in, per the reviewer
check: codebase
evidence: §B; artifacts/trigger.py:82-116; triage/model.py:167-175

<!-- fr:journal kind=finding scope=spec id=s12 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s12 · finding [open] (reviewer: in scope) · Pushing refs/fr/triage/* through the cloud git proxy is unmeasured

target: spec
scope: in, per the reviewer
check: consistency
evidence: R5, §B; no discovery covers it

<!-- fr:journal kind=finding scope=spec id=s13 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s13 · finding [open] (reviewer: in scope) · The lease's duration and self-renewal are unspecified

target: spec
scope: in, per the reviewer
check: consistency
evidence: R9, §D, §E

<!-- fr:journal kind=finding scope=spec id=s14 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s14 · finding [open] (reviewer: in scope) · Test Plan 2's GraphQL list is incomplete; R8 export and R16 untested

target: spec
scope: in, per the reviewer
check: consistency
evidence: Test Plan 2 vs §A; real_ghclient.py:110-119; R8; R16/§G

<!-- fr:journal kind=finding scope=spec id=s15 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s15 · finding [open] (reviewer: in scope) · fr-claude-cloud package location; some herdr-only parts already optional

target: spec
scope: in, per the reviewer
check: codebase
evidence: §F; fr-herdr/pyproject.toml; protocols.py:191-237; triage_batch_cmd.py:1385; batch_drive.py:457

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-10-08T12:14:06+00:00 -->
### spec-review · review · independent spec review: 15 findings

verified (by the reviewer): triage_cmd.py:92 make_forge; triage_batch_cmd.py:222 make_client; hostclient.py:199 client_for_backend; ghclient.py:87 GhClient; real_ghclient.py:89 RealGhClient; collect.py:232 _latest_runs; batch_drive.py:935 drive_pass; batch_drive.py:501 hand-back policy; triage_batch_cmd.py:1385 ADOPT_LIST_RUNNER; triage_batch_cmd.py:3842-3961 drive loop and re-exec; triage_claim_cmd.py:60 scope show; triage_state_cmd.py:50 state export; gitseam.py; drive_lock.py:16; scope_config.py:30,:86; triage/model.py:363-391 TriageConfig, :167 state_dir; fr_dispatch protocols.py:36-218; run_cmd.py:4590 run start; run/model.py:351 RunState; artifacts/registry.py:368-407 run kind v9; artifacts/trigger.py:82-92; verifications candidate/client-live; decisions d1-d8 honoured except d5's condition (s8).

<!-- fr:journal kind=finding scope=spec id=s16 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s16 · finding [open] (reviewer: in scope) · R19/§H rest on a premise spare-preload disproved, and their fallback (re-home) cannot help

target: spec
check: decisions
evidence: R19; §H para 1; Background ("A session's plugins cannot be reloaded in place"); journal spare-preload, plugin-late-load, agents-late-load, no-plugin-agents, d7; run_cmd.py:2387-2395
R19's "runs before the session starts so the plugin's agents and hooks are loaded" is false (spare-preload); its "a running session cannot load a plugin's agents" and the Background sentence are contradicted by agents-late-load. The remedy loops: a re-homed session is another pre-warmed spare with the same race. Fix: say the setup script installs into the container and the plugin reaches the session late; the worker's first step waits, bounded, for fr-spec-reviewer/fr-phase-executor to be dispatchable, and on timeout ends BLOCKED with a needs_action, no re-home; add an owed measurement and a Test Plan 17 observation. The gate accepts the bare agent name, so user- or repo-scoped agent files are a candidate fix. Hooks are unproven in a worker; say what a worker without them may do. R18's "re-home itself so its skill text is current" assumes skills cannot refresh in place, which plugin-late-load puts in doubt.

<!-- fr:journal kind=finding scope=spec id=s17 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s17 · finding [open] (reviewer: in scope) · §H's setup script, done as described, is the silent half-install that setup-script measured

target: spec
check: decisions
evidence: §H; journal setup-script; scripts/install.sh:94-99
§H names neither the apt install of rsync nor seeding installed_plugins.json/settings.json; the owed follow-up (install.sh creates them or fails, not warn-and-exit-0) is in no requirement or Test Plan row.

<!-- fr:journal kind=finding scope=spec id=s18 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s18 · finding [open] (reviewer: in scope) · Environment set by the setup script likely never reaches the session; FR_HOST_ID 'restored into its workspace' has no mechanism

target: spec
check: consistency
evidence: R3; R11; §B Identity; §H; journal spare-preload; scope_config.py:34-35,58-63
The CLI process starts before the setup script, so its `export` cannot reach the session's shells; FR_FORGE_API=rest may never be set. R11 never says how FR_HOST_ID is restored per wake. Persist both in files fr reads (`~/.config/fr/host-id` exists, scope_config.py:34; the forge setting needs a host-level file or the environment's own variables), and test that a fresh shell resolves both.

<!-- fr:journal kind=finding scope=spec id=s19 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s19 · finding [open] (reviewer: in scope) · forge.api is said to resolve from 'the host's scope.yaml', but scope.yaml is per scope and the run path has none

target: spec
check: codebase
evidence: R3; §A Selection; scope_config.py:30,86-106; §B scope-durable.yaml
scope.yaml is one file per scope; `resolve()` has no scope and run-path callers have none to pass; the order omits scope-durable.yaml's forge_api; ScopeConfig is extra="forbid", so forge_api/state_repo must become fields. Name one host-level source (env var, then e.g. ~/.config/fr/forge.yaml), how scope-durable.yaml feeds it, and add the model fields.

<!-- fr:journal kind=finding scope=spec id=s20 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s20 · finding [open] (reviewer: in scope) · The gh commands fr tells agents to run (pr create/edit/ready, issue close/edit) are GraphQL-backed and outside R1

target: spec
check: codebase
evidence: hostclient.py:85-96 FORGE_COMMANDS["github"]; R1; Test Plan 17
Agents run `gh pr create --draft`, `gh pr edit`, `gh pr ready`, `gh issue close`, `gh issue edit --add-label`, `gh label create` at deliver and close-out; most are GraphQL. Under rest, FORGE_COMMANDS needs a REST variant (gh api routes or an fr verb), with a test that no GraphQL-backed command is named.

<!-- fr:journal kind=finding scope=spec id=s21 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s21 · finding [open] (reviewer: in scope) · 'Raise on a 403' conflicts with GhClient methods whose contract is None on any failure

target: spec
check: codebase
evidence: §A last bullet; ghclient.py:323-332; real_ghclient.py:565-577; isolation/local.py:2962
pr_for_branch and issues_enabled promise None on failure. List per method whether it raises or keeps its contract, and test both; pr_for_branch's REST client must derive owner/repo from the checkout.

<!-- fr:journal kind=finding scope=spec id=s22 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s22 · finding [open] (reviewer: in scope) · Pending requests, re-home records and session ids are not in REF_FILES, so they are lost on a fresh container

target: spec
check: consistency
evidence: R14; §F requests.yaml; §G; §B REF_FILES; Test Plan 17
A driver restored on a new container loses pending requests, can re-home twice (breaking R17's at-most-once), and loses dispatched session ids. Add them to REF_FILES; extend Test Plans 5 and 9.

<!-- fr:journal kind=finding scope=spec id=s23 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s23 · finding [open] (reviewer: in scope) · The driver's self-re-home strands it behind its own lease

target: spec
check: consistency
evidence: R9; §D holder = session id; R18; §E step 2
A re-homed driver has a new session id, so its own lease refuses it for 90 minutes and then needs `lease take --yes`. Use `cloud:<FR_HOST_ID>` as the holder, or hand the lease over; add to Test Plans 8 and 12.

<!-- fr:journal kind=finding scope=spec id=s24 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s24 · finding [open] (reviewer: in scope) · Lease default does not match its own formula (3x5 + 60 = 75, not 90)

target: spec
check: consistency
evidence: R9; §D; §E defaults
Settle one value and test the computed duration.

<!-- fr:journal kind=finding scope=spec id=s25 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s25 · finding [open] (reviewer: in scope) · No rule says how a cloud scope's batches reach the claude-cloud runner when the repo config says herdr

target: spec
check: codebase
evidence: .fr/triage.yaml:4-7,13-17; triage_batch_cmd.py:1094-1095,1269-1270,1487-1488; Test Plan 17
Runner comes from launch.runner, defaulting to the repo's .fr/triage.yaml (herdr here), which both scopes read. State whether the driver adapter, a scope setting or --to decides, which settings the cloud driver ignores (post_merge, post_merge_restart), and test one repo config with two scopes.

<!-- fr:journal kind=finding scope=spec id=s26 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s26 · finding [open] (reviewer: in scope) · Privacy guard: no source for the state repo's visibility, and the lease push runs before any collect

target: spec
check: consistency
evidence: §C; §B; §E steps 1 and 3; R7
A dedicated state repo is not in the scope, so collect never reads its visibility; on a fresh container facts.json is absent; §E pushes the lease before collect. Read the state repo's visibility with GET repos/{state_repo} before each push; unknown refuses. Test both in Test Plan 7.

<!-- fr:journal kind=finding scope=spec id=s27 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s27 · finding [open] (reviewer: in scope) · Stale and mismatched cross-references between the design and the Test Plan

target: spec
check: consistency
evidence: §B owed measurement (says Test Plan 12; it is 16); Test Plan 16 only pushes to the session's own repo; R4/Test Plan 4 `.git/info/exclude` vs §B `<git-common-dir>/info/exclude`; Test Plan 13 vs R19

<!-- fr:journal kind=finding scope=spec id=s28 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s28 · finding [open] (reviewer: in scope) · The new runner package's obligations list misses surfaces fr-herdr is pinned in

target: spec
check: codebase
evidence: §F; pyproject.toml:9,:57; tests/integration/test_runner_package_lists.py:78 and the scaffold POST_CREATE; scripts/install.sh:94-99
Missing: root workspace dependencies, coverage source, and the scaffold's literal runner-package list.

<!-- fr:journal kind=finding scope=spec id=s29 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s29 · finding [open] (reviewer: in scope) · R16 records a plugin version with no named source, and nothing reads it

target: spec
check: codebase
evidence: R16; §G; no plugin_version helper under packages/; journal plugin-late-load
Name the source (installed_plugins.json's entry) and what a disagreement with the loaded plugin means, or drop it; R17 compares only fr_version.

<!-- fr:journal kind=finding scope=spec id=s30 created=2026-10-08T12:14:06+00:00 state=open review_scope=in -->
### s30 · finding [open] (reviewer: in scope) · Two wake sources are assumed, not measured

target: spec
check: decisions
evidence: R11; §E Wakes; journal wake-probe, wake-probe-restart, d3
Only send_later was measured. PR-activity subscriptions and a recurring Routine firing into an existing session are unobserved; list them as owed measurements and observe each in Test Plan 17.

<!-- fr:journal kind=review scope=spec id=spec-review-2 created=2026-10-08T12:14:06+00:00 -->
### spec-review-2 · review · independent spec review: 15 findings

R19 does not hold (s16); §H does not hold as written (s17, s18); §F holds as a mailbox, with durability gaps s22, s23.
verified (by the reviewer): hostclient.py:199-239; triage_cmd.py:92-97; triage_batch_cmd.py:222-225,:1385,:402,:410,:580; run_cmd.py:6037,:2387-2395; run/closeout.py:346; run/adopt.py:747; isolation/local.py:2962; gh.py:177-182,:233; real_ghclient.py:80,:130; triage/collect.py:232-256; triage/model.py:167-175; state_sync.py:45-46; merge_stops.py:25; scope_config.py:29,78-83; drive_lock.py:1; batch_drive.py:453-457,:935; triage_state_cmd.py:50; artifacts/trigger.py:82; artifacts/registry.py:407; fr_dispatch protocols.py:36,82,123,142,170; fr_dispatch testing.py:87-129; test_import_direction.py:139-160; scripts/version_surfaces.py:9; ci.yml:33; plugins/super-fr/agents/*.md. Decisions d1-d8 checked against R1-R21: no contradictions beyond s16 (R19 vs d7).

<!-- fr:journal kind=decision scope=spec id=d9-repo-agents-artifact created=2026-10-08T12:14:06+00:00 -->
### d9-repo-agents-artifact · decision · Operator decision, round 9: repo-scoped fr agents become an artifact kind

Operator, 2026-10-08, after discovery `repo-agents` (two probe sessions: the plugin's agents absent at session start, repo `.claude/agents/` files present from the first turn). Asked how fr should keep repo-scoped agent files current in repos that run cloud workers; options were a new artifact kind, `fr init` plus a separate drift check, or opt-in per repo. Answer: **a new artifact kind** (`agents`): `fr init` writes stamped copies of `fr-spec-reviewer` and `fr-phase-executor` into `.claude/agents/`; a release that changes them moves the kind's version, so `fr validate artifacts` and the migration gate keep the repo's CI red until `fr migrate artifacts --yes` re-renders them. The operator raised the idea (a new fr-init step, plus a check at every fr release, part of the migration that fails CI until done). This supersedes d7's premise that the setup script makes the plugin's agents available; d7's fallback (install `fr` when missing) stands.

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: forge.api selection point does not exist as described

R3 and §A: `forge.api` resolves from `FR_FORGE_API` or the host's `scope.yaml` before any client exists; the repo-level key is dropped with the reason; both `client_for_backend` and `client_for_url` consult it.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: Cloud worker and close-out sessions still hit GraphQL outside the triage path

R1 widened to the run path (deliver, close-out, adopt, isolation, linked PRs); §A routes the direct `fr.gh` helpers too, and the REST client raises on 403 instead of a soft empty answer; Test Plan 2 and 17 cover it.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: R2 exceptions table omits workflowName, which _latest_runs keys on

§A table adds `workflowName` (Actions runs by head_sha, mapped by check_suite_id; app name otherwise) and the `startedAt`/status normalisation; Test Plan 1 asserts them.

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s4 -->
### s4-resolved · finding [fixed] · resolves s4: Scope id, ref name and state_repo are host-local; a new container loses them

R11 starts the cloud driver with a fixed `FR_HOST_ID` (already supported, scope_config.py:29) and its state repo; §B stores `state_repo`/`forge_api` in `scope-durable.yaml` inside the ref; Test Plan 6 covers recovery.

<!-- fr:journal kind=finding scope=spec id=s5-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s5 -->
### s5-resolved · finding [fixed] · resolves s5: The ref's tree omits merge stops, the lease and scope config

R5 and §B define the ref tree as an explicit list (`REF_FILES`), merge stops, lease and durable settings included; Test Plan 5 round-trips every entry.

<!-- fr:journal kind=finding scope=spec id=s6-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s6 -->
### s6-resolved · finding [fixed] · resolves s6: A mailbox runner conflicts with synchronous runner calls; crash window undefined

R14 and §F define pending requests with stable ids stored in state, pending runner results, replay every pass, and idempotent execution via session tags; Test Plan 9 covers a lost result.

<!-- fr:journal kind=finding scope=spec id=s7-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s7 -->
### s7-resolved · finding [fixed] · resolves s7: SessionStatus cannot carry needs_action

§F adds an optional `SessionNotes` protocol for the text; `SessionStatus` is unchanged, so herdr is untouched; Test Plan 10.

<!-- fr:journal kind=finding scope=spec id=s8-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s8 -->
### s8-resolved · finding [fixed] · resolves s8: R15 maps completed to done unconditionally, against d5's condition

R15: completed → idle (messageable), with the reason in §F; a conflict is handed back by message; Test Plan 10.

<!-- fr:journal kind=finding scope=spec id=s9-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s9 -->
### s9-resolved · finding [fixed] · resolves s9: R18 cannot hold for a long-lived cloud driver given R20 and d4

R18 and §E step 2: the driver compares its `fr` with the latest release before each pass, reinstalls and re-execs when older, and re-homes itself on a new major so its skill text is current; R20 updated.

<!-- fr:journal kind=finding scope=spec id=s10-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s10 -->
### s10-resolved · finding [fixed] · resolves s10: Drift-check inputs undefined

§G: cursors read from each batch branch over REST; incompatibility is a different `fr` major; no recorded versions → reported only; artifact readability is left to fr's own migration gate. R17 narrowed accordingly; Test Plans 11-12.

<!-- fr:journal kind=finding scope=spec id=s11-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s11 -->
### s11-resolved · finding [fixed] · resolves s11: The first write edits the tracked .gitignore; workspace undefined

R4 and §B: `.git/info/exclude`, never a tracked file; workspace = git toplevel or `--workspace` (required outside a clone); the READ_ONLY_COMMANDS rationale is updated; Test Plan 4.

<!-- fr:journal kind=finding scope=spec id=s12-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s12 -->
### s12-resolved · finding [fixed] · resolves s12: Pushing refs/fr/triage/* through the cloud git proxy is unmeasured

§B names it an owed measurement; Test Plan 16 pushes and fetches the scope's ref through the cloud git proxy before merge.

<!-- fr:journal kind=finding scope=spec id=s13-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s13 -->
### s13-resolved · finding [fixed] · resolves s13: The lease's duration and self-renewal are unspecified

R9 and §D: duration = three wake intervals plus the Routine's period (90 min default); host holder is `host:<host id>`, stable across pid changes; the same holder renews its own expired lease; Test Plan 8.

<!-- fr:journal kind=finding scope=spec id=s14-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s14 -->
### s14-resolved · finding [fixed] · resolves s14: Test Plan 2's GraphQL list is incomplete; R8 export and R16 untested

Test Plan 2 lists every GraphQL-backed call incl. writes and `issue view --json`; Test Plan 7 adds the export refusal; Test Plan 11 adds the run kind's stamp, migration, validator and chain.

<!-- fr:journal kind=finding scope=spec id=s15-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s15 -->
### s15-resolved · finding [fixed] · resolves s15: fr-claude-cloud package location; some herdr-only parts already optional

§F: `packages/fr-claude-cloud`, with its version surface, mypy entry, import-direction entry and contract test; the 'become optional' list narrowed to `ADOPT_LIST_RUNNER` and the wave grouping (batch_drive.py:457).

<!-- fr:journal kind=finding scope=spec id=s16-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s16 -->
### s16-resolved · finding [fixed] · resolves s16: R19/§H rest on a premise spare-preload disproved, and their fallback (re-home) cannot help

Background rewritten from the discoveries; R19 and §H now take the agents from the repo (`agents` artifact kind, d9), the worker's first step checks the two agent types and ends BLOCKED with a needs_action naming the artifact instead of re-homing; hooks are defence in depth with their presence an owed measurement in Test Plan 17; R18's rationale no longer assumes skills cannot refresh. Test Plans 13, 17, 18.

<!-- fr:journal kind=finding scope=spec id=s17-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s17 -->
### s17-resolved · finding [fixed] · resolves s17: §H's setup script, done as described, is the silent half-install that setup-script measured

§H names the setup script's rsync install and the seeding of installed_plugins.json and settings.json; R19 requires install.sh to fail rather than warn and exit 0; Test Plan 13 covers it.

<!-- fr:journal kind=finding scope=spec id=s18-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s18 -->
### s18-resolved · finding [fixed] · resolves s18: Environment set by the setup script likely never reaches the session; FR_HOST_ID 'restored into its workspace' has no mechanism

R3 and §A: forge.api comes from `~/.config/fr/forge.yaml`, written by the setup script, never an export. R11 and §B Identity: the brief carries the host id and every wake writes it to `~/.config/fr/host-id` when missing. Test Plans 3 and 6 check a fresh shell.

<!-- fr:journal kind=finding scope=spec id=s19-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s19 -->
### s19-resolved · finding [fixed] · resolves s19: forge.api is said to resolve from 'the host's scope.yaml', but scope.yaml is per scope and the run path has none

§A: `resolve()` takes no scope; order FR_FORGE_API, `~/.config/fr/forge.yaml`, graphql; scope-durable.yaml's value is written to the host file on restore only when absent; §B makes `forge_api`/`state_repo` optional ScopeConfig fields. Test Plan 3.

<!-- fr:journal kind=finding scope=spec id=s20-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s20 -->
### s20-resolved · finding [fixed] · resolves s20: The gh commands fr tells agents to run (pr create/edit/ready, issue close/edit) are GraphQL-backed and outside R1

R1 includes FORGE_COMMANDS; §A gives them a github-rest spelling via `gh api` routes, named in briefs when rest is selected; Test Plans 2 and 17.

<!-- fr:journal kind=finding scope=spec id=s21-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s21 -->
### s21-resolved · finding [fixed] · resolves s21: 'Raise on a 403' conflicts with GhClient methods whose contract is None on any failure

§A: per-method contract: pr_for_branch and issues_enabled keep None, every other method raises on 403; pr_for_branch derives owner/repo from the checkout's origin; R1 says so; Test Plan 2 tests both sets.

<!-- fr:journal kind=finding scope=spec id=s22-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s22 -->
### s22-resolved · finding [fixed] · resolves s22: Pending requests, re-home records and session ids are not in REF_FILES, so they are lost on a fresh container

R5 and §B REF_FILES add requests.yaml, sessions.yaml and rehomes.yaml; §F and §G point at them; Test Plans 5, 9 and 12 restore them.

<!-- fr:journal kind=finding scope=spec id=s23-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s23 -->
### s23-resolved · finding [fixed] · resolves s23: The driver's self-re-home strands it behind its own lease

R9 and §D: the holder is `cloud:<host id>`, which a re-homed driver keeps; Test Plans 8 and 12.

<!-- fr:journal kind=finding scope=spec id=s24-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s24 -->
### s24-resolved · finding [fixed] · resolves s24: Lease default does not match its own formula (3x5 + 60 = 75, not 90)

R9 and §D: 3 × 5 + 60 = 75 minutes, computed from the configured values; Test Plan 8 asserts the computation.

<!-- fr:journal kind=finding scope=spec id=s25-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s25 -->
### s25-resolved · finding [fixed] · resolves s25: No rule says how a cloud scope's batches reach the claude-cloud runner when the repo config says herdr

R10 and §E: the driver adapter supplies the runner, overriding the repo's launch.runner default; an explicit foreign launch.runner is reported, not dispatched; the cloud driver ignores post_merge and post_merge_restart; Test Plan 9 runs one repo config with two scopes.

<!-- fr:journal kind=finding scope=spec id=s26-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s26 -->
### s26-resolved · finding [fixed] · resolves s26: Privacy guard: no source for the state repo's visibility, and the lease push runs before any collect

R8 and §C: the state repo's visibility is read with GET repos/{state_repo} before every push and export, unknown refuses; with no facts the keys' repos are read the same way; the lease push goes through the check (§E step 1); Test Plan 7.

<!-- fr:journal kind=finding scope=spec id=s27-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s27 -->
### s27-resolved · finding [fixed] · resolves s27: Stale and mismatched cross-references between the design and the Test Plan

§B now cites Test Plan 16, which also pushes to a state repo the session did not start with; R4 and Test Plan 4 use the git common dir's info/exclude; Test Plan 13 covers R19's agent check.

<!-- fr:journal kind=finding scope=spec id=s28-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s28 -->
### s28-resolved · finding [fixed] · resolves s28: The new runner package's obligations list misses surfaces fr-herdr is pinned in

§F's obligations add the root dependencies, the coverage source and the scaffold POST_CREATE runner-package list (test_runner_package_lists.py).

<!-- fr:journal kind=finding scope=spec id=s29-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s29 -->
### s29-resolved · finding [fixed] · resolves s29: R16 records a plugin version with no named source, and nothing reads it

R16 and §G drop the plugin version: it is lockstepped with fr's and the loaded version is unreadable from inside a session; the agents a worker uses are checked through the `agents` artifact's stamp instead.

<!-- fr:journal kind=finding scope=spec id=s30-resolved created=2026-10-08T12:14:06+00:00 state=fixed resolves=s30 -->
### s30-resolved · finding [fixed] · resolves s30: Two wake sources are assumed, not measured

§E lists PR-activity wakes and the Routine firing into the existing session as owed measurements; R11 says so; Test Plan 17 observes each once.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-07-cloud-triage-p2 created=2026-10-08T12:17:53+00:00 -->
### phase-split-2026-10-07-cloud-triage-p2 · decision · ask: state in the workspace, on a ref, behind the privacy guard (R4-R8)

Its own reviewable ask: where a scope's state lives and how it survives a container, independent of the forge backend beyond reading visibility.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-07-cloud-triage-p3 created=2026-10-08T12:17:54+00:00 -->
### phase-split-2026-10-07-cloud-triage-p3 · decision · ask: the lease and the driver adapter (R9-R13)

Its own ask: one driver per scope and the pass/record split of the drive loop.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-07-cloud-triage-p4 created=2026-10-08T12:17:55+00:00 -->
### phase-split-2026-10-07-cloud-triage-p4 · decision · ask: the claude-cloud runner (R14-R15)

Its own ask and its own package: the mailbox runner and the status mapping.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-07-cloud-triage-p5 created=2026-10-08T12:17:57+00:00 -->
### phase-split-2026-10-07-cloud-triage-p5 · decision · ask: versions and drift (R16-R18)

Its own ask: the run kind's 9 -> 10 migration and re-homing on an incompatible major.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-07-cloud-triage-p6 created=2026-10-08T12:17:58+00:00 -->
### phase-split-2026-10-07-cloud-triage-p6 · decision · ask: workers in the cloud (R19-R21)

Its own ask: the agents artifact kind (d9), setup and install hardening, the worker brief, cloud post_merge and the skill.

<!-- fr:journal kind=decision scope=spec id=tier-2026-10-07-cloud-triage-p3 created=2026-10-08T12:18:00+00:00 -->
### tier-2026-10-07-cloud-triage-p3 · decision · hard: the lease is a concurrency path every driver relies on

Compare-and-swap ownership across hosts and cloud sessions, and the shared pass function the host loop moves onto; a mistake strands or doubles drivers.

<!-- fr:journal kind=decision scope=spec id=tier-2026-10-07-cloud-triage-p5 created=2026-10-08T12:18:01+00:00 -->
### tier-2026-10-07-cloud-triage-p5 · decision · hard: a run-kind migration every cursor goes through

Moves the run kind's current_version 9 -> 10 and migrates this repo's cursors; artifact-versioning rules apply.

<!-- fr:journal kind=decision scope=spec id=tier-2026-10-07-cloud-triage-p6 created=2026-10-08T12:18:02+00:00 -->
### tier-2026-10-07-cloud-triage-p6 · decision · hard: a new artifact kind every fr-enabled repo will carry

Registers the agents kind with its stamp, validator and re-render path, and changes fr init and install.sh for every consumer repo.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-07-cloud-triage-p4-1 created=2026-10-08T12:19:48+00:00 -->
### phase-split-2026-10-07-cloud-triage-p4-1 · decision · review-size: the claude-cloud runner is a new workspace package

Supersedes phase-split-2026-10-07-cloud-triage-p4. Its requirements (R14, R15) are also cited by the broad end-to-end row that phases 3 and 6 link, so self-review counts them as shared. Folded into phase 3 it would add a whole new package (~1100 lines, with its own version surface, lockfile and CI entries) to a ~1400-line hard concurrency phase, too large for one review.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-07-cloud-triage-p6-1 created=2026-10-08T12:19:49+00:00 -->
### phase-split-2026-10-07-cloud-triage-p6-1 · decision · review-size: the agents artifact kind and the worker setup are a separate ~1000-line change

Supersedes phase-split-2026-10-07-cloud-triage-p6. R19-R21 are also cited by the broad end-to-end row that phases 3 and 4 link. Folded into an earlier phase it would add a new artifact kind (registry, stamp, validator, re-render path, wheel data and tripwire), install.sh, the worker brief and the skill with its three mirrors to a phase already near 1400 lines.

<!-- fr:journal kind=discovery scope=spec id=slow-suite created=2026-10-08T13:48:20+00:00 -->
### slow-suite · discovery · The full suite takes ~20 minutes in a 4-core cloud container; branch pushes run no CI

Measured 2026-10-08 during phase 1: `uv run pytest -q --no-cov -n auto` in this cloud container (4 cores) ran for over 20 minutes, against ~2.5 minutes on a 12-core host (AGENTS.md). And .github/workflows/ci.yml triggers on `push: [main]` and `pull_request` only, so the branch's pushes before a PR existed ran no CI at all; a draft PR does trigger it (no `types:` filter).

<!-- fr:journal kind=decision scope=spec id=d10-ci-evidence created=2026-10-08T13:48:21+00:00 -->
### d10-ci-evidence · decision · Operator decision, round 10: CI as test evidence, in this spec

Operator, 2026-10-08, after slow-suite: open the draft PR now so every push runs CI (derio-net/super-fr#1088, opened before deliver at the operator's request), and add to THIS spec a requirement letting fr accept a green CI run on HEAD as test evidence (R22, §I), rather than filing it separately or keeping local suites only.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-07-cloud-triage-p2-1 created=2026-10-08T13:50:13+00:00 -->
### phase-split-2026-10-07-cloud-triage-p2-1 · decision · risk-first: CI as test evidence (R22) lands before the remaining phases

Supersedes phase-split-2026-10-07-cloud-triage-p2. Phases were renumbered on 2026-10-08 (d10): the new phase 2 is R22, placed right after the skeleton so phases 3-7 can prove themselves with the PR's CI instead of a ~20-minute local suite in this container (discovery slow-suite).

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-07-cloud-triage-p3-1 created=2026-10-08T13:50:14+00:00 -->
### phase-split-2026-10-07-cloud-triage-p3-1 · decision · ask: state in the workspace, on a ref, behind the privacy guard (R4-R8)

Supersedes phase-split-2026-10-07-cloud-triage-p3 after the renumbering (was phase 2).

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-07-cloud-triage-p4-2 created=2026-10-08T13:50:16+00:00 -->
### phase-split-2026-10-07-cloud-triage-p4-2 · decision · ask: the lease and the driver adapter (R9-R13)

Supersedes phase-split-2026-10-07-cloud-triage-p4-1 after the renumbering (was phase 3).

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-07-cloud-triage-p5-1 created=2026-10-08T13:50:17+00:00 -->
### phase-split-2026-10-07-cloud-triage-p5-1 · decision · review-size: the claude-cloud runner is a new workspace package

Supersedes phase-split-2026-10-07-cloud-triage-p5 after the renumbering (was phase 4; reason as phase-split-2026-10-07-cloud-triage-p4-1).

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-07-cloud-triage-p7 created=2026-10-08T13:50:20+00:00 -->
### phase-split-2026-10-07-cloud-triage-p7 · decision · review-size: the agents artifact kind and the worker setup are a separate ~1000-line change

Was phase 6 before the renumbering (reason as phase-split-2026-10-07-cloud-triage-p6-1's original text).

<!-- fr:journal kind=decision scope=spec id=tier-2026-10-07-cloud-triage-p2 created=2026-10-08T13:50:21+00:00 -->
### tier-2026-10-07-cloud-triage-p2 · decision · hard: changes the test-evidence gate every phase and delivery relies on

R22 adds a second way to satisfy fr's tests evidence; a mistake would let CI vouch for a tree it did not test.

<!-- fr:journal kind=decision scope=spec id=tier-2026-10-07-cloud-triage-p4 created=2026-10-08T13:50:23+00:00 -->
### tier-2026-10-07-cloud-triage-p4 · decision · hard: the lease is a concurrency path every driver relies on

Was tier-2026-10-07-cloud-triage-p3 before the renumbering.

<!-- fr:journal kind=decision scope=spec id=tier-2026-10-07-cloud-triage-p7 created=2026-10-08T13:50:24+00:00 -->
### tier-2026-10-07-cloud-triage-p7 · decision · hard: a new artifact kind every fr-enabled repo will carry

Was tier-2026-10-07-cloud-triage-p6 before the renumbering.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-07-cloud-triage-p6-2 created=2026-10-08T13:50:37+00:00 -->
### phase-split-2026-10-07-cloud-triage-p6-2 · decision · ask: versions and drift (R16-R18)

Supersedes the earlier phase-split-2026-10-07-cloud-triage-p6 entries after the renumbering (this was phase 5).

<!-- fr:journal kind=decision scope=spec id=renumber-2026-10-07-cloud-triage-phases created=2026-10-08T13:50:39+00:00 -->
### renumber-2026-10-07-cloud-triage-phases · decision · Plan phases renumbered for R22: old 2-6 are now 3-7

2026-10-08, decision d10: the CI-evidence phase is inserted as phase 2, so old phase N is now N+1. Journal decisions written before this keep their old numbers: tier-2026-10-07-cloud-triage-p3 (lease) is now phase 4 (re-recorded as tier-2026-10-07-cloud-triage-p4), tier-2026-10-07-cloud-triage-p5 (run-kind migration) is now phase 6, still hard and still covered by tier-2026-10-07-cloud-triage-p6's id (whose text names the agents kind, now phase 7, re-recorded as tier-2026-10-07-cloud-triage-p7); tier-2026-10-07-cloud-triage-p6 therefore now stands for phase 6's hard tier (a migration every cursor goes through). The phase-split entries with -1/-2 suffixes record each phase's reason under its new number.

<!-- fr:journal kind=review scope=spec id=spec-review-3 created=2026-10-08T13:53:45+00:00 -->
### spec-review-3 · review · independent spec review of R22/§I: 8 findings

Reviewer a2f206dc267b3224f (fr-spec-reviewer, dispatched by this session), 2026-10-08, over R22, §I and Test Plan 19 only. Findings s31-s38, all in scope, all fixed in the spec. Verified: run_cmd.py:1922-1934, :2691, :2845-2875, :2878-2929, :2961-3069; run/code_tree.py:61,:71; fr/git.py; services_cmd.py; ci.yml:4-7; fr-goal SKILL.md:111-112.

<!-- fr:journal kind=finding scope=spec id=s31 created=2026-10-08T13:54:06+00:00 state=open review_scope=in -->
### s31 · finding [open] (reviewer: in scope) · CI on a pull_request tests HEAD merged into base, and a conflicting PR leaves ci waiting forever

check: codebase. evidence: §I; ci.yml:4-7,:21 (checkout of refs/pull/N/merge). The witness claimed a tree CI never ran; a conflicting PR runs no pull_request workflow.

<!-- fr:journal kind=finding scope=spec id=s31-resolved created=2026-10-08T13:54:07+00:00 state=fixed resolves=s31 -->
### s31-resolved · finding [fixed] · resolves s31: CI on a pull_request tests HEAD merged into base, and a conflicting PR leaves ci waiting forever

R22 and §I: the witness records the CI sha and the base sha it merged with, stated as such; step 4 refuses with no open PR or a CONFLICTING one.

<!-- fr:journal kind=finding scope=spec id=s32 created=2026-10-08T13:54:09+00:00 state=open review_scope=in -->
### s32 · finding [open] (reviewer: in scope) · 'every check green, at least one present' accepts a sha the test workflow never ran on

check: codebase. evidence: R22; acceptance-report.yml, pinned-clis.yml; ci.yml ci-ok. A fast unrelated check satisfied the rule; skipped counted as success.

<!-- fr:journal kind=finding scope=spec id=s32-resolved created=2026-10-08T13:54:10+00:00 state=fixed resolves=s32 -->
### s32-resolved · finding [fixed] · resolves s32: 'every check green, at least one present' accepts a sha the test workflow never ran on

§I: only gate checks count (.fr/ci.yaml gate_checks, else required checks, else refused); this repo declares ci-ok; a skipped or absent gate refuses.

<!-- fr:journal kind=finding scope=spec id=s33 created=2026-10-08T13:54:12+00:00 state=open review_scope=in -->
### s33 · finding [open] (reviewer: in scope) · Requiring every check couples phase test evidence to non-test gates

check: codebase. evidence: ci.yml coverage, validate-artifacts, change-fragment; acceptance-report.yml.

<!-- fr:journal kind=finding scope=spec id=s33-resolved created=2026-10-08T13:54:13+00:00 state=fixed resolves=s33 -->
### s33-resolved · finding [fixed] · resolves s33: Requiring every check couples phase test evidence to non-test gates

§I: non-gate checks are ignored; ci-ok aggregates the CI jobs the repo itself chose to gate on.

<!-- fr:journal kind=finding scope=spec id=s34 created=2026-10-08T13:54:15+00:00 state=open review_scope=in -->
### s34 · finding [open] (reviewer: in scope) · Binding to HEAD's exact sha forces a push and a CI wait after every fr bookkeeping commit

check: consistency. evidence: R22; record commits; code_tree excludes fr artifact trees.

<!-- fr:journal kind=finding scope=spec id=s34-resolved created=2026-10-08T13:54:16+00:00 state=fixed resolves=s34 -->
### s34-resolved · finding [fixed] · resolves s34: Binding to HEAD's exact sha forces a push and a CI wait after every fr bookkeeping commit

§I step 3: the CI sha is the nearest pushed first-parent ancestor with HEAD's code tree (at most 50), recorded in the witness.

<!-- fr:journal kind=finding scope=spec id=s35 created=2026-10-08T13:54:18+00:00 state=open review_scope=in -->
### s35 · finding [open] (reviewer: in scope) · No GhClient method reads checks by sha

check: codebase. evidence: ghclient.py:225-235; real_ghclient.py:402-424.

<!-- fr:journal kind=finding scope=spec id=s35-resolved created=2026-10-08T13:54:19+00:00 state=fixed resolves=s35 -->
### s35-resolved · finding [fixed] · resolves s35: No GhClient method reads checks by sha

§I: new GhClient.commit_checks(repo, sha) -> {name, workflow, status, conclusion, url}, latest per (workflow, name) via filter=latest and latest-per-context statuses, on both GitHub clients and the fake; glab/tea raise UnsupportedForgeOperation.

<!-- fr:journal kind=finding scope=spec id=s36 created=2026-10-08T13:54:20+00:00 state=open review_scope=in -->
### s36 · finding [open] (reviewer: in scope) · Waiting for CI has a wake-up only in the cloud

check: consistency. evidence: §I; fr-goal SKILL.md:106 idle guard.

<!-- fr:journal kind=finding scope=spec id=s36-resolved created=2026-10-08T13:54:22+00:00 state=fixed resolves=s36 -->
### s36-resolved · finding [fixed] · resolves s36: Waiting for CI has a wake-up only in the cloud

§I Waiting: pending exits 75, not an idle point; fr-goal tells a host orchestrator to re-run the resolve every 2 minutes for at most 45, then report blocked.

<!-- fr:journal kind=finding scope=spec id=s37 created=2026-10-08T13:54:23+00:00 state=open review_scope=in -->
### s37 · finding [open] (reviewer: in scope) · Plugin prose that ci contradicts goes beyond fr-goal §8

check: consistency. evidence: fr-goal SKILL.md:88,:103; fr-phase-executor.md:125,133-142.
