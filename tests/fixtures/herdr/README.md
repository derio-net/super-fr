# herdr CLI fixtures

- `tab-list.json` — captured live 2026-09-25 from `herdr tab list --workspace w2`
  (herdr's JSON envelope and tab objects as printed); the operator's tab labels
  are replaced with invented ones, the shape is unchanged.
- `tab-create.json` — NOT a live capture: creating a tab would have opened one
  in the operator's session. It is assembled from herdr's own documentation
  (`herdr --skill`: "`tab create` returns `.result.tab` and `.result.root_pane`")
  with a `tab` object shaped as captured by `herdr tab get` and a `root_pane`
  object shaped as captured by `herdr pane list`. `fr_herdr` reads only
  `.result.root_pane.pane_id` from it. Replace it with a real capture when one is
  taken (plan phase 4's live walk).
- `workspace-list.json`, `tab-list-all.json`, `workspace-create.json`,
  `tab-rename.json`, `workspace-close.json` — captured live 2026-10-05
  (herdr protocol 22) from `herdr workspace list`, `herdr tab list` (no
  `--workspace`: every workspace), `herdr workspace create --label
  fr-fixture-capture --cwd /tmp --no-focus`, `herdr tab rename <tab_id>
  fr-fixture-capture-tab` and `herdr workspace close <workspace_id>` (the
  scratch workspace was closed again). Redaction: every workspace label other
  than `super-fr` became `example-ws-<n>`, every tab label that was not a
  batch item id or a bare `|` became `example-tab-<n>`; shape unchanged.
- `workspace-focus.json`, `tab-focus.json` — captured live 2026-10-05 (herdr
  0.9.1) from `herdr workspace focus <focused workspace_id>` and `herdr tab focus
  <focused tab_id>` (focusing what was already focused, so nothing moved for the
  operator). Redaction: the tab label became `example-tab-1`; shape unchanged.
- `agent-start-pane-busy.json` — captured live 2026-10-06 (herdr 0.9.1, stderr of
  a failed `herdr agent start`): run straight after `herdr workspace create` in a
  scratch workspace, it lost the race to the new shell in 1 of 6 tries (gh#931).
  Only the pane id was changed, to match `tab-create.json`'s root pane.
- `agent-prompt-stalled.json` — NOT a live capture: the stall is
  timing-dependent and did not reproduce in 6 tries (gh#956). The code
  `agent_prompt_stalled` is herdr's documented one (`herdr agent prompt --help`,
  `herdr --skill`); the envelope is the shape of the captured `agent-start-pane-busy.json`
  and the message is invented. `fr_herdr` reads only `.error.code`.
- `workspace-list-adopt.json`, `tab-list-adopt.json`, `agent-list.json`,
  `tab-rename-adopt.json`, `agent-rename.json`, `tab-list-adopted.json`,
  `agent-list-adopted.json` — captured live 2026-10-06 (herdr 0.9.0) for batch
  adopt (spec 2026-10-06-triage-batch-adopt §E). A scratch workspace
  `fr-adopt-scratch` was created with `herdr workspace create --no-focus`, and
  `claude --model haiku` was started in its root pane with `herdr pane run` —
  NOT `herdr agent start`, so herdr detected an agent it did not launch (it
  carries no `name` and no `agent_session`). Then, in order: `herdr workspace
  list`, `herdr tab list`, `herdr agent list`, `herdr tab rename wT:t1
  derio-net/super-fr/run/batch-adopt-scratch`, `herdr agent rename wT:p1
  b-adopt-scratch-0000` (exit 0: herdr renames an agent it did not launch, and
  `herdr agent get b-adopt-scratch-0000` then resolves it by that name), and the
  two lists again (`-adopted`); the scratch workspace was closed afterwards. No
  other tab or agent was renamed, messaged or closed. Redaction: only the
  workspaces `w7`, `w9` and the scratch `wT` are kept; workspace labels became
  the bare repo name; tab labels without an issue ref or item id became
  `example-tab-<n>`; every agent `cwd` became `/work/<repo>` (the scratch one
  `/tmp/fr-adopt-scratch`), other agents' terminal titles became `claude`, and
  session ids became sequential placeholder UUIDs. Shape unchanged.
