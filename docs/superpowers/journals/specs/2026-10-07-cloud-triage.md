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
