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

## Tiers: pre-bound, and none equal to the session model

**#538 (open)**: with every tier unbound, fr-goal on OpenCode never asked the
model-per-tier question. So filming it as onboarding (route B) is unreliable
until that is fixed; pre-bind instead.

**Tiering is already proven** — #560 recorded a live OpenCode run where three
declared tiers each dispatched to their tier agent and each ran on *its own*
binding, pairwise distinct, none on the session model. This run therefore
**shows** tiering rather than owing evidence for it.

Take #560's method as a constraint on the bindings: **no tier may be bound to
the model the session itself runs on.** Its predecessor run bound all three
tiers to the session model, so its rows could not tell a correct tiered dispatch
from a broken untiered one — the proof rested on the agent *name* alone. Pick
three models that differ from each other **and** from the session model, or the
same ambiguity returns on camera.

### Declare the session model, and probe everything before trusting it

**Bind the session's own model as the `orchestrator` tier.** It is never
dispatched to, but `fr run start` and `advance` warn when the session runs on
something else — so #560's "no tier equals the session model" becomes a
declared value fr checks, not a sentence in this runbook.

**Probe every bound model live before recording.** On 2026-09-23 the entire
gpt-5.6 generation had been retired from Copilot — each answered `The requested
model is not supported` — while `opencode models` still listed all three, even
after `--refresh`. The list is a catalogue, not a statement of what the provider
will serve. And `fr models set` accepts any string and materialises it, so a
retired model surfaces only when a phase is dispatched to it: the operator had a
`standard` agent bound to a dead model with no signal from anything.

A changed session model also resets the gate evidence. Attempt 1's question
gates fired on the old model; whether a new one follows the same *advisory*
prose is unmeasured, and has to be watched as closely as the first time.

## Identity inverts from bc88

bc88's bug was the work identity landing on a public open-source commit. Here
commits go to the employer's GitLab, so the work identity is correct, supplied
by the `includeIf` for the work path. Assert `user.email` in the clone.

## Preflight — assertions, not steps

Each line below failed silently in some earlier run:

- **the installed `fr` matches the repo** — the surfaces move fast; re-run
  `install.sh` when it does not;
- **the plugin is delivered** — `fr-opencode-plugin` present in the OpenCode
  plugins directory (since #563, 4.17.0);
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

**Artifacts live in the workspace, not the clone.** After `fr isolation up`
the spec, plan and run cursor are written into the fr worktree — reading the
base clone finds nothing. They are also *uncommitted* there, so an
`fr isolation down` plus `git worktree remove` destroys the cursor and the run
cannot be resumed ("no run state at …"). Commit or copy before any down/up cycle.

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
- **the model was not auto-continued after asking its questions** — if it was,
  the idle adapter answered past the operator and the take is void (and the
  observation is worth an issue);
- `resolve` demanded `reviewer=` and `tests=`, and recorded its evidence as
  *unverified* rather than claiming otherwise;
- annotation offsets were noted live.

## The plugin is delivered now — and one risk goes live with it

**#563 landed (4.17.0).** `install.sh` delivers `fr-opencode-plugin` to
`~/.config/opencode/plugins/`, so a consumer's OpenCode now carries both the
edit gate and the idle adapter. Two consequences, opposite in sign.

**The Security beat became real on this harness.** Parity footnote [2]: all
file-writing tools are gated including nested arguments and patch-body targets;
the delivered copy is loaded by the real binary and refuses a base-clone edit in
CI (`tests/integration/test_opencode_plugin_live.py`). `bash` remains ungated
(#436) — a known gap, not a bypass, and worth saying out loud rather than
filming around.

**The idle adapter is now active, and unproven.** Footnote [3]: on
`session.idle` the plugin sends the next command back into the session; that a
plugin-originated prompt actually *executes* is **not live-proven**. It was
harmless while nothing delivered it. It is not harmless now, because **the
operator gate works by ending the turn — which is exactly `session.idle`.** If
the model is auto-continued straight after asking its questions, that is the
adapter answering past the operator, and the take is void. Watch for it, and
record it either way: this run is the first real chance to see the behaviour.

## Evidence the run must now produce (#536)

`fr-goal`'s first post-#508 run broke seven contracts while reporting success,
and #536's fixes mean `fr run resolve` now demands real evidence. Its own Test
Plan names *"the next real fr-goal run"* as the live check — this one.

- **The session binds itself.** `fr run start` / `fr isolation up` record the
  ambient session id (C4 — the old matcher only recognised a bare `fr`).
- **An unasked gate is refused.** `resolve` wants an answered question since the
  gate paused; the bypass is `--no-questions --reason`, and it is journaled.
- **`reviewer=` must name a separately dispatched subagent** — never the phase's
  implementer, never a phase executor.
- **`tests=` must be a log the orchestrator itself wrote during `deliver`**,
  with the log's bytes inside that command's run window, hashed onto the cursor.
- **The model recorded is the served model**, not the alias typed (C3).

**Expect loud degradation on OpenCode, and do not read it as failure.**
Transcripts cannot be read there, so `reviewer=` is checked only against the
implementer set, the gates stay advisory, and evidence is recorded as
*unverified*. Seeing that said plainly is the correct outcome; seeing it claimed
as verified would be the bug.

## Remaining limits

- `operator-gate / opencode: advisory` — nothing can mechanically block, so both
  question gates can still silently not fire. Still the highest-risk moment.
- `bash` is ungated by the edit gate.
- The idle adapter's behaviour is unproven, as above.

## Assets never enter this repo

Casts, renders and stills stay outside it. super-fr is a Skill cloned onto every
consumer machine, so a committed binary inflates every install permanently. A
terminal recording against a third-party GitLab also shows its host, namespace
and project in prompts, git output and MR URLs — a second reason the cast is
never committed and the rendered deck stays internal.
