# Runbook — v2 demo recording (single arm, OpenCode + GitLab)

The **shape** of the run. Identities (GitLab host, group, project, namespace) are
third-party and live in an operator-local env file outside this repo, alongside
the executable command sequence and the recording assets
(`.claude/rules/third-party-privacy.md`). Nothing here should ever contain a
real value.

Revised 2026-09-22 against fr 4.14.5 and the OpenCode work merged since the
first draft.

## Configuration: the real install, not a clean room

The first draft pointed `XDG_CONFIG_HOME` at an empty directory, as the bc88
comparison did. That is wrong for this run: **`fr` and OpenCode both resolve
skills, agents, plugins and `models.yaml` through `XDG_CONFIG_HOME`**
(`fr.models.xdg_config_home`, shared by `fr.opencode_agents` so the two never
diverge). An empty one yields a session with no `/fr-init`, no `/fr-goal` and no
agents — the same silent failure as an earlier arm whose skill copy "didn't
take".

bc88 needed a clean room to make two arms comparable. This is one arm, and the
listener will run her *real* install — so the run uses it too. Only
`XDG_DATA_HOME` is isolated, for a clean `opencode.db` to measure from (copy
`auth.json` into it). What the run mutates — `models.yaml` and the installed
agent files — is snapshotted first and restored at teardown, the method PR #539
used and proved byte-identical.

## Launch from a plain terminal

`env | grep '^CLAUDE_'` must print nothing. **#537**: ambient `CLAUDE_*`
variables made fr record the *orchestrating Claude Code session* as the holder
of an OpenCode dispatch. Launching via Claude Code's `!` prefix reproduces it.

## The recording starts pristine — `fr-init` is IN it

No `.devcontainer` in the clone, clean tree. `fr-init` scans, interviews,
scaffolds and builds on camera, and declares `backend: gitlab` through
`fr init scaffold --backend gitlab` — which also installs a versioned `glab` in
the container. That key's absence is what made fr assume GitHub before #487, so
the interview asking for it is where the GitLab story becomes visible.

**Waits are shown as waits**, compressed hard with the compression labelled on
screen. Pre-pulling base image layers is legitimate and unlabelled.

## Tiers: pre-bound, genuinely different (route A)

**#538 (open)**: with every tier unbound, fr-goal on OpenCode never asked the
model-per-tier question — the condition is a check the model has to remember,
and it didn't. So filming the question as onboarding (route B) is not reliable
until #538 is fixed.

Pre-bind each tier to a **different** model with `fr models set`, which
materialises into the installed agent and names the file it wrote. Same-model
bindings show three labels resolving to one model and prove nothing.

Subagent dispatch itself is proven: #494's post-merge run (PR #539) dispatched a
phase to `fr-phase-executor-mechanical`, the tier its plan declared, with its own
usage and every tool call under the child.

## Identity inverts from bc88

bc88's bug was the work identity landing on a public open-source commit. Here
commits go to the employer's GitLab, so the work identity is correct, supplied
by the `includeIf` for the work path. Assert `user.email` in the clone.

## Preflight — assertions, not steps

Each line below failed silently in some earlier run:

- `fr-goal` and `fr-init` skills present in the **real** OpenCode config;
- `opencode agent list` shows all four `fr-phase-executor*` agents;
- `glab auth status`, plus a real API read of the fork;
- tier bindings resolve to three different models;
- clone pristine, identity is the work one, `origin` pushable, `upstream` not.

## Measurement — read `opencode.db`, not the cursor

Two corrections from live runs:

- **Token totals.** `tokens_input` is *uncached only* (#509); alone it
  under-reports ~20×. Total input is `tokens_input + tokens_cache_read +
  tokens_cache_write`.
- **Which tier ran.** `dispatch-holder-identity / opencode` is `partial` (#537):
  the task tool blocks and only returns the child session id with the result, so
  fr's cursor cannot name the holder while the unit is held, and records the
  manifest's agent id rather than the tier that ran. The `session` table's
  `agent` and `model` columns are the source of truth.

Wall time is the db's session span. **Cast length is not runtime** — the TUI
repaints about once a second, so `--idle-time-limit` never engages.

## Take acceptance

A take is discarded and re-recorded unless:

- both question gates fired — `fr-init` interviewed, and `/fr-goal` asked its
  batch and ended the turn. `operator-gate / opencode` is only **advisory**, so
  this can silently not happen; it remains the highest-risk moment;
- at least one phase dispatched: a `session` row with `parent_id` set and a
  **tiered** `fr-phase-executor-<tier>` agent (a bare name means the tier failed
  to resolve), on the model bound to that tier;
- a check genuinely failed and was recovered;
- the merge request exists on the fork;
- annotation offsets were noted live.

## Known limits — film them honestly

- **The OpenCode plugin is not delivered by `install.sh`.** Its README says
  "install the package (once published) or vendor this directory" and add it to
  the repo's `opencode.json`. So this run has **no edit-gate backstop** and **no
  idle adapter** on OpenCode. The isolation itself — worktree and container —
  still happens through `fr`; only the backstop against a wandering agent is
  absent. A listener who runs `install.sh` gets exactly this.
- `operator-gate / opencode: advisory` — above.
- #538 — why tiers are pre-bound.

## Assets never enter this repo

Casts, renders and stills stay outside it. super-fr is a Skill cloned onto every
consumer machine, so a committed binary inflates every install permanently. A
terminal recording against a third-party GitLab also shows its host, namespace
and project in prompts, git output and MR URLs — a second reason the cast is
never committed and the rendered deck stays internal.
