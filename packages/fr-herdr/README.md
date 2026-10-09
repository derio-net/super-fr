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
1.18.35 default-theme full TUI, not arbitrary versions/themes/mini mode.

An OS-backed nonblocking pane lock excludes concurrent mutations.
Before input, an independent process verifies that the filesystem actually
enforces the lock. Unsupported shared filesystems refuse; choose a reliable local cache.
OpenCode uses plain `exit` (Claude uses `/exit`), verifies a foreground shell and its cwd, confirms
the target model, then submits recovery with observed uptake. Failures never close
the tab or destroy transcripts/worktrees. Inspect the surviving source, target or
shell using the report's checkpoint and recovery instructions. A non-active
descriptor prevents automatic retry and blind resubmission. Scripted candidate
tests do not discharge the operator-owned live Ready walk (Refs #1089).
