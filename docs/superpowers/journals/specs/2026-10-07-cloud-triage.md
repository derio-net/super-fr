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
