# Drive manages its herdr sessions — design

**Date:** 2026-10-05
**Slug:** `2026-10-05-drive-herdr-sessions`
**Status:** design (fr-goal, autonomous; batch `drive-close-tabs`)
**Repo:** `derio-net/super-fr` (single-repo change)
**Issues:** super-fr#918, super-fr#919

## Background

`fr triage batch drive` (spec `implemented/specs/2026-10-02-wave-driver-design.md`)
dispatches every batch and every close-out through a runner. With the herdr
runner (`packages/fr-herdr/src/fr_herdr/runner.py`) each one is a tab labelled
with its item id, opened in ONE workspace, the driver's own
`HERDR_WORKSPACE_ID` (`HerdrRunner.dispatch`, `tab create --workspace`).
Nothing ever closes those tabs: the wave-driver spec held that the runner
cannot see whether a session ended, so a merged archive PR is treated as the
end and the tabs are left. A two-batch wave left four idle tabs (#918), and a
multi-wave drive piles every session into the operator's working workspace
(#919).

Two facts, checked against herdr itself (protocol 22, `herdr api schema
--json`) on 2026-10-05, change the premise:

- `herdr tab list` reports every tab's `agent_status`, one of `idle`,
  `working`, `blocked`, `done`, `unknown` (`AgentStatus` enum). The runner
  CAN see whether a session is working.
- `herdr tab list` without `--workspace` lists the tabs of every workspace;
  `herdr workspace create --label --cwd --no-focus` returns the new
  `workspace`, its first `tab` and that tab's `root_pane`; `herdr workspace
  close <id>`, `herdr tab close <id>` and `herdr tab rename <TAB_ID>
  <LABEL>` exist.

The runner protocol (`packages/fr-dispatch/src/fr_dispatch/protocols.py`,
`Runner`) is a structural `Protocol` implemented by `vk`, `cncd` and `herdr`
without inheritance. A new required method would break the two runners that
have no sessions to close, so closing is an optional capability, and the wave
is a payload hint (`WorkItem.payload`, documented in
`fr_dispatch/work_item.py`) that a runner without the concept ignores.

## Requirements

R1. When `fr triage batch drive` dispatches a batch, the batch's session opens in a runner group named `<prefix>-wave-<n>` for the batch's wave `n`, or `<prefix>-no-wave` for a batch with no wave; with the herdr runner a group is a herdr workspace with that label, created when no workspace carries that label and reused while one does (a wave workspace R9 closed is created again by a later dispatch into it).
R2. `drive` takes `--workspace-prefix <text>`; without it the prefix is `drive`. An empty prefix is refused.
R3. A batch's close-out session opens in the group of the batch's CURRENT wave, wherever the batch's own session is (a batch dispatched by hand, or re-waved after dispatch, can sit elsewhere).
R4. The group travels to the runner as an optional `group` key in the work item's payload. A runner without the concept ignores it. A batch dispatched by hand with `fr triage batch dispatch` carries no group and opens where it does today (the herdr runner's own workspace).
R5. The herdr runner finds a live dispatch by its tab label in ANY workspace, so a live item is never dispatched twice because its tab sits in a wave workspace or was moved by hand.
R6. The runner protocol gains an optional close capability — close the sessions of one item, reporting `closed`, `busy` or `absent`. A runner that does not offer it is never asked, and its behaviour is unchanged.
R7. Once a batch is finished — its close-out event records a merged archive PR (driver-merged or adopted as archived), or an archive PR attributed to its close-out is merged — the driver closes the batch's session and its close-out session, when its runner offers the close capability and holds them live. `--keep-sessions` turns this off.
R8. The driver closes only its own items' sessions (a herdr tab whose label is the item id) and never one whose herdr agent status is `working` or `blocked`: that one is left and tried again on the next pass, if the drive runs one: a drive that is otherwise done does not wait for it, and a later drive closes it. `idle`, `done` and `unknown` are closable.
R9. When a closed item's tab is the only tab of its herdr workspace, and that workspace's label is the item's group and it is not the runner's own (`HERDR_WORKSPACE_ID`), the workspace is closed instead of the tab, so an emptied wave workspace does not linger. Any other workspace — one of the operator's, a tab moved there by hand — only loses the tab.
R10. Closing never holds or fails the drive: a busy session, a runner's preflight refusal or a failed close is reported once per cause, does not count as work remaining, and does not change the exit code; neither does a close that succeeded (a pass that only closed sessions is not a pass that acted). A runner that cannot be loaded for the close probe is the same: reported once, skipped.

## Design

### A. Protocol (`fr_dispatch`)

- `work_item.py` docstring: `group` joins `checkout` as an optional run-unit
  payload key — "the runner group (a herdr workspace) the item's session
  belongs to; a runner without groups ignores it". `RUN_PAYLOAD_KEYS` stays
  the six required keys.
- `protocols.py`: a second, optional protocol beside `Runner`:

  ```python
  CloseOutcome = Literal["closed", "busy", "absent"]

  @runtime_checkable
  class SessionCloser(Protocol):
      def close(self, item: WorkItem) -> CloseOutcome: ...
  ```

  `closed`: the item's sessions are gone now. `busy`: at least one is still
  working; nothing was closed. `absent`: the runner holds nothing for it.
  Raising is a failed close. `Runner` itself is unchanged, so vk and cncd
  need no edit (R6).
- `testing.py`: `check_close_contract(runner, item)` — the runner is a
  `SessionCloser`, and closing an item it does not hold returns `absent`.
  herdr's suite runs it.

### B. herdr runner (`fr_herdr`)

- `existing_dispatches` lists tabs with `herdr tab list` (no `--workspace`)
  and matches labels against item ids (R5).
- `dispatch` with `payload["group"]`:
  1. `herdr workspace list`; the first workspace whose `label` equals the
     group is used.
  2. If none, `herdr workspace create --label <group> --cwd <checkout>
     --no-focus`; its first tab is renamed to the item id (`herdr tab
     rename`) and its root pane hosts the agent, so no unlabelled tab is left
     behind. A failure after the workspace exists closes the workspace before
     re-raising, as a failed `tab create` already closes its tab (review
     r2p-f9).
  3. Otherwise `tab create --workspace <that id>` as today.
  Without a group, today's path: the runner's own workspace (R4). The
  rename is `herdr tab rename <tab_id> <item id>`; a failed rename is a
  failed dispatch (the workspace is closed), never an unlabelled tab.
- `preflight` requires `HERDR_WORKSPACE_ID` only when an item has no group.
- `close(item)`: one `tab list`; the tabs labelled `item.id`. None →
  `absent`. Any with `agent_status` in {`working`, `blocked`} → `busy`,
  nothing closed (R8). Otherwise each tab is closed with `tab close`, except
  a tab that is the only tab of its workspace when that workspace's label
  (`workspace list`) equals `item.payload["group"]` and it is not
  `self.workspace_id`: that workspace is closed with `workspace close` (R9).
  Returns `closed`.

### C. Driver (`fr.triage.batch_drive`, pure)

- `wave_group(prefix, wave) -> str`: `<prefix>-wave-<n>` / `<prefix>-no-wave`.
- `is_finished(batch, stage, archives) -> bool`: landed, with a close-out
  event whose `archived` is set, or an attributed archive PR in state
  `MERGED` (the two cases where step 3 of `drive_pass` already says "the
  batch is finished"). Step 3 uses it, so the two readings cannot drift.
- `Snapshot` gains `close_sessions: bool` and `sessions: frozenset[str]` —
  the batch and close-out item ids of finished batches that a closing runner
  holds live.
- `drive_pass` step 5, **Close**: for each selected finished batch with an
  item in `sessions`, an `Action("close", …)`. It adds nothing to the
  summary: closing is never work remaining (R10).

### D. Driver (`fr.commands.triage_batch_cmd`, effects)

- `--workspace-prefix` (default `drive`, empty refused) and
  `--keep-sessions` on `batch drive`.
- `dispatch_batch(..., group=None)`: the driver passes
  `wave_group(prefix, batch.wave)`; `batch dispatch` passes none (R4). It
  lands in `_work_item`'s payload when set.
- `_closeout_item` carries `wave_group(prefix, batch.wave)` (R3).
- Snapshot: unless `--keep-sessions` (and only with `--yes`), the driver
  probes each finished selected batch's items: the batch item against the
  runner its last `DispatchEvent` names, the close-out item against the
  runner its `CloseoutEvent` names, skipping `hand` (an adopted close-out has
  no session). Each probe item carries `group = wave_group(prefix,
  batch.wave)`. Probes are grouped per runner, one `preflight` and one
  `existing_dispatches` call each, as `_existing` does. Loading a runner
  goes through a non-exiting variant of `load_runner`: a load failure, a
  runner that is not a `SessionCloser`, or a preflight refusal skips that
  runner, the first two silently for a non-closer and the rest reported
  once — never the close-out probe's exit 2 (R10).
- `_act("close")`: `runner.close(item)` for each of the batch's live items.
  Outcome line: `closed …`, `busy, retried next pass: …`, or the failure.
  It returns `did=False` whatever happened, so `--once` exits as it would
  without it (R10). A failure or a busy outcome is printed once per batch
  and cause (the `warned` set), never sets `failed_write`.

### E. Skill prose

`plugins/super-fr/skills/fr-triage/SKILL.md`'s driver paragraph names the
wave workspaces, `--workspace-prefix`, session closing and
`--keep-sessions`; the OpenCode and Hermes mirrors are regenerated
(`scripts/sync-opencode.py`, `scripts/sync-hermes.py`).

## Non-goals

- No session closing for `fr triage batch dispatch` run by hand, and no
  closing in runners other than herdr.
- No new judgements event and no schema bump: closing is idempotent and
  re-derived each pass from the runner's own listing.
- No moving of tabs already open when a drive starts.

## Automated verification (CI)

Unit level, herdr faked at `_run_herdr` with its JSON fixtures:
`drive_pass` emits `close` for a finished batch with a live item and none
under `--keep-sessions`, and its summary is unchanged by it; `is_finished`
covers both readings; `wave_group` and the empty-prefix refusal; a driver
dispatch and close-out carry the group, a hand `batch dispatch` none;
`existing_dispatches` finds a tab in another workspace; `close` returns
`closed`/`busy`/`absent`, closes a lone tab's group workspace but never the
runner's own nor a workspace of another label; the probe skips `hand`, a
non-closer runner and a load failure without exiting 2; a close outcome
never changes the exit code; `check_close_contract` passes for herdr.

## Test Plan (post-merge, operator-driven)

1. Inside herdr, drive two small batches in different waves (`--yes`, default
   prefix): each opens in `drive-wave-<n>`, created on first dispatch; the
   close-out of each opens beside its batch.
2. After each archive PR merges, the batch's and close-out's tabs close on
   the next pass, and the emptied wave workspace closes; a tab still working
   is left, and closed by a later pass or a later drive.
3. `--keep-sessions` on a further drive leaves finished tabs open.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-10-05-drive-herdr-sessions | `derio-net/super-fr` | `2026-10-05-drive-herdr-sessions` | — |
