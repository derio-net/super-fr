# Herdr control sessions

Configure a batch's `launch.harness` as `claude` or `opencode`; OpenCode's
`launch.model` is an explicit provider/model. Run dispatch/drive inside herdr.
The control session lives in the stable primary checkout, not the branch workspace
that close-out can remove. Branch work still uses fr isolation.

`post_merge_restart: idle` uses the same eligibility as `fr-herdr restart-idle
--yes`. Preview without `--yes` first. Claude resumes; managed OpenCode recovers
fresh from durable cursors, records and journals. Never restart the initial goal.
Delivered drafts HOLD; current handbacks require matching branch head and live
mergeability. Close-out pickup retains delivery/merge gates.

Drafts and command overlays can report idle, so status alone is insufficient.
Caller/excluded panes and unknown layouts/processes are skipped; the runner never
clears drafts or answers dialogs. Failed restarts leave non-active descriptors and
recovery instructions. Inspect the pane before manually recovering it; never
blindly resend a brief with uncertain uptake. See
[`fr-herdr`](../packages/fr-herdr/README.md) for cache/observation limits.

Audited replacement is the separate implementation phase; no replacement CLI is
claimed here. The operator-owned client-live walk remains required before Ready,
independently of scripted installed-candidate evidence (Refs #1089).
