# fr-herdr

The `herdr` runner accepts run-unit work with Claude or OpenCode. OpenCode
uses an explicit `provider/model`, for example `openai/gpt-6.1-sol`.
Run dispatch/drive from inside a herdr pane (`HERDR_ENV=1`). Control sessions
start in the stable primary checkout, even when called from a linked worktree;
the brief reaches branch work through fr isolation.

`fr-herdr restart-idle` previews eligible panes; `--yes` acts and repeatable
`--exclude <pane>` protects named panes. Claude keeps its existing `--resume`
behavior. Managed OpenCode batch, conflict and close-out sessions start **fresh**
in the same pane under the same name/model, using durable fr state, not the old
session id or initial goal. Delivered cursors HOLD for operator review/Ready/merge;
current conflict handbacks take precedence. Close-out uses pickup/merge gates.
Running units must be explicitly reconciled before redispatch.

Descriptors live in `~/.cache/fr/herdr` (`FR_HERDR_CACHE_DIR` overrides), keyed by
the inherited server socket and pane. Missing, corrupt or non-active descriptors,
busy/self/excluded panes, drafts, overlays, unknown processes/models and unsupported
input layouts are skipped without input. Observation supports the captured OpenCode
1.18.35 and 2.1.4 default-theme full TUI captures, not arbitrary versions/themes/mini mode.

Before the first brief, OpenCode readiness waits within the existing 30-second
budget for unknown startup layout or the narrowly captured empty V2 metadata frame
(grey border, no agent/model row, default new-session title and known footer).
That frame is **never accepted as ready**. Every observation rechecks the live
identity, selected session/model, `--auto`, cwd and status; a changed foreground PID
refuses. Only the unchanged strict input parser can admit submission. Drafts,
visible overlays and complete-but-grey prompts still refuse; timeout sends no
brief. Launch keeps `--no-focus`; no input or focus action settles the UI.
This handles a known premature startup refusal, not proof of a historical failure's
cause or a completed client-live walk.

An OS-backed nonblocking pane lock excludes concurrent mutations.
Before input, an independent process verifies that the filesystem actually
enforces the lock. Unsupported shared filesystems refuse; choose a reliable local cache.
OpenCode uses plain `exit` (Claude uses `/exit`), verifies a foreground shell and its cwd, confirms
the target model, then submits recovery with observed uptake. Failures never close
the tab or destroy transcripts/worktrees. Inspect the surviving source, target or
shell using the report's checkpoint and recovery instructions. A non-active
descriptor prevents automatic retry and blind resubmission. Scripted candidate
tests do not discharge the operator-owned live Ready walk (Refs #1089).

`fr triage batch replace <id> --harness opencode --model provider/model --reason
<why>` previews audited fresh replacement in either direction (omit harness for
model-only). `--yes` acts; an explicit model is required on harness change.
It preserves dispatch/branch/PR/reservation and pane/name. Scope then pane
ownership spans pending descriptor, batch attempt, runner checkpoints, batch
success/launch and descriptor activation. Ordinary edits stay frozen.

On partial failure inspect the surviving source/target/shell; `replace <id>
--repair --reason <inspection> --yes` reconciles both stores without exit, launch
or duplicate prompt. Target kind/model alone never proves uncertain submission.
Details and the disposable operator walk: `docs/herdr-control-sessions.md`.

For a **positively absent** control pane, `batch replace <id> --recover --harness
opencode --model provider/model --reason <why>` previews a fresh herdr-allocated
pane. Explicit `--yes` acts; same-model recovery is allowed. Select the exact
scope/state (`--repo` or `--org`, optional `--dir`) and primary `--checkout`.
Original dispatch/history and existing workspace/run/dirty work stay intact.
Global pane/tab/agent observations refuse surviving/reused/ambiguous ownership.
Server/item/source-keyed durable intent precedes allocation; uncertain allocation
is discovered by explicit `--repair`, never allocated again automatically.
Successful effective ownership includes actual new pane and fresh session id.

Recovered OpenCode starts with `--auto` in acknowledge/report-only **HOLD**.
HOLD precedes conflicts and all cursor continuation, survives managed restart,
and needs a separate operator instruction to release work. No gate is answered
and no running unit is claimed/abandoned automatically. Repair launches/sends
nothing and requires persisted uptake plus matching session identity to certify
success. The disposable actual-client walk is **post-merge Tester, walk-owed**;
automated fake-backed scenarios are not a live pass. See the control-session guide
for refusal, checkpoint and inspection details.
