# Triage batch board — design

**Date:** 2026-10-05
**Slug:** `2026-10-05-triage-batch-board`
**Status:** design (fr-goal, autonomous)
**Repo:** `derio-net/super-fr` (single-repo change)

## Background

`fr triage render` writes `triage.html`, the backlog board: tiers, waves,
needs-you and a Batches section of flat cards (`fr/triage/render.py`
`_batches`). Once batches are dispatched — by hand or by `fr triage batch
drive` — the operator's live question changes from "what should we work on"
to "where is each batch right now, and which session do I look at". The
triage page answers neither well: it is a long page, it is only as fresh as
the last `fr triage render`, and nothing on it leads to a session.

What exists to build on:

- A batch's stage is derived, never stored: `fr.triage.batch.derive_batch_stage`
  gives `proposed | dispatched | pr-open | merged | partial | abandoned |
  cancelled`; `dependency_state` gives each `after` entry's state; the close-out
  lifecycle is read from `CloseoutEvent` (`batch_drive.closeout_event`,
  `is_finished`).
- `fr.triage.views.drive_snapshot(facts, judgements)` builds the driver's
  `Snapshot` from facts alone, and `batch_drive.drive_pass` turns it into the
  ordered actions the driver would take — a per-batch "what happens next".
- A batch session is a herdr tab labelled with its item id
  (`batch_item_id` → `<repo>/run/batch-<id>`); a close-out session's label is
  `closeout_item_id`. `herdr tab list` reports every tab's `tab_id`,
  `workspace_id` and `agent_status` (`idle | working | blocked | done |
  unknown`), and `herdr tab focus <tab_id>` / `herdr workspace focus <id>`
  switch to it. Tab ids are allocated at creation and recorded nowhere fr
  reads, so "jump to the session" must resolve label → tab when it runs.
- `fr_dispatch.protocols.SessionCloser` is the precedent for an OPTIONAL
  runner capability declared beside `Runner`, never inside it, and checked
  with `isinstance`. `fr` reaches runners only through `fr_dispatch`
  (`triage_batch_cmd.load_runner`, a `find_spec`-guarded soft point); `fr`
  never imports `fr_herdr` (`tests/unit/test_import_direction.py`).
- `drive` holds `<state dir>/drive.lock` while it runs and re-collects facts
  every pass (`triage_cmd.collect_into`).
- `fr.triage.components` holds the shared colour tokens and the phone gutter.

## Requirements

R1. `fr triage board` (same `--repo` / `--org` / `--dir` options as `fr triage render`) writes `board.html` into the triage state directory from `facts.json` and `judgements.yaml`, without collecting; with no batches it still writes a page that says there are none.
R2. The board shows exactly one card per batch in `judgements.yaml`, in one of six columns, left to right: **Proposed** (never dispatched, every `after` dependency satisfied or none), **Waiting** (never dispatched, some `after` dependency not yet satisfied), **Running** (stage `dispatched`), **PR open** (stage `pr-open`), **Closing out** (stage `merged` and not finished), **Done** (finished, or stage `cancelled`, `abandoned` or `partial`). A Done card for `cancelled`, `abandoned` or `partial` carries that word as a pill; a Waiting card whose dependency is unsatisfiable is marked blocked. Each column header shows its card count; within a column, cards sort by wave (no wave last), then batch id.
R3. A collapsed card shows the batch id, title, wave, member count, the session status pill (R7), the next-action hint (R6) and, while the batch has a dispatch event and is not Done, a jump button.
R4. A card expands in place to show: its member issues (title linked to the forge, issue stage); its PR (link, draft or ready, check counts, mergeable state, review decision) when it has one; its lifecycle (wave, each `after` dependency with its state, branch, reserved version, runner, harness, model, skill, rationale); its event timeline (every dispatch, cancel, post_merge and closeout event, oldest first, with its time); and, when a close-out was started, a second jump button for the close-out session. Expanding works with scripts off.
R5. A jump button copies the command `fr triage batch focus <batch-id>` (plus `--closeout` for the close-out session's button), carrying the scope options the board was rendered with, to the clipboard, and confirms the copy on the button; where the clipboard is unavailable the command is shown selected for a manual copy. The command text is always visible on the expanded card.
R6. Each card carries a one-line next-action hint taken from the actions the driver would take for that batch on the same facts (`drive_pass` over `drive_snapshot`): e.g. "dispatch next", "waits on <batch>", "merge ready", "CI failing", "close-out due", or, from R7, "needs you: session blocked"; a batch with no action reads "nothing to do".
R7. When the board is rendered, each batch with a dispatch event, and each started close-out, shows the live status of its session — `working`, `blocked`, `idle`, `done`, `unknown`, or `no session` — asked of the runner named in its latest dispatch (or closeout) event through an optional runner capability. A runner without the capability, one that cannot be loaded or passes no preflight, or a status read that fails, shows `unknown` with one page-level note saying why; rendering never fails on it. A `blocked` session highlights its card as needing the operator.
R8. `fr triage batch focus <batch-id> [--closeout]` switches the operator's terminal to that batch's (or its close-out's) live session through the runner named in the latest dispatch (or closeout) event, and exits 0. It refuses with exit 2 and a one-line reason when the batch is unknown, has no such event, the runner lacks the focus capability or fails its preflight, or holds no live session for the item.
R9. The herdr runner implements both capabilities: status from `herdr tab list` (every workspace, matching the tab label to the item id; several tabs → the busiest of `blocked`, `working`, `idle`, `done`, `unknown`), and focus as `herdr workspace focus <workspace>` then `herdr tab focus <tab>` for the first matching tab.
R10. The page re-reads itself on a timer — every 30 seconds by default, set with `fr triage board --refresh <seconds>`, `0` turning it off — and keeps which cards are expanded and the scroll position across the reload. The page shows when it was rendered and when its facts were collected.
R11. `fr triage batch drive --yes` re-renders `board.html` after every pass, so the board follows each state change the driver makes or sees. A board that fails to render prints one warning and never fails or stops the drive.
R12. `fr triage board --watch [--interval <seconds>]` (default 60) re-collects facts and re-renders the board every interval until interrupted. It refuses, exit 2, while a live `drive` holds the state directory's lock, saying the drive keeps the board fresh.
R13. `triage.html` links to `board.html` from its Batches section whenever there are batches.
R14. Every forge- or judgement-sourced string on the board is escaped, none reaches a `<script>` element, and the copied command is built only from the validated batch id and scope options.
R15. The board follows the triage pages' look: the shared colour tokens in light and dark, a 16px side gutter, and no horizontal page scroll at phone width — the columns stack vertically below 720px.

## Design

### A. Protocol (`fr_dispatch.protocols`)

Two new optional protocols beside `SessionCloser`, each `runtime_checkable`,
neither part of `Runner`:

```python
SessionStatus = Literal["working", "blocked", "idle", "done", "unknown", "absent"]

class SessionInspector(Protocol):
    def session_statuses(self, items: Sequence[WorkItem]) -> dict[str, SessionStatus]:
        """Status of each item's live session by item id; `absent` when none."""

class SessionFocuser(Protocol):
    def focus(self, item: WorkItem) -> bool:
        """Switch the operator to the item's session; False when there is none."""
```

`absent` renders as "no session" (R7). Raising is a failed read / focus.

### B. herdr runner (`fr_herdr`)

`HerdrRunner.session_statuses` calls `_list_tabs()` once and maps each item id
to the busiest status of its tabs (R9 order); a value outside herdr's five is
`unknown`. `HerdrRunner.focus` lists tabs, takes the first whose label is the
item id, runs `herdr workspace focus <workspace_id>` then `herdr tab focus
<tab_id>`, returns True; no tab → False. Both go through `_run_herdr`, so the
existing fake covers them. Conformance lines join the `TYPE_CHECKING` block.

### C. Board model (`fr.triage.board`, pure)

```python
Column = Literal["proposed", "waiting", "running", "pr-open", "closing-out", "done"]

@dataclass(frozen=True)
class Card: batch, column, stage, blocked, hint, status, closeout_status, pr, members, ...

def column_of(batch, facts, judgements, finished: bool) -> Column
def build_board(facts, judgements, statuses: Mapping[str, SessionStatus]) -> Board
```

- `column_of` is R2's table: no events → `proposed`/`waiting` by
  `dependency_state` over `after`; else by `derive_batch_stage`, with
  `merged` split by `batch_drive.is_finished` (archives from the facts the
  same way `drive_snapshot` reads them).
- The hint (R6) runs `drive_pass(drive_snapshot(facts, judgements))` once and
  keeps the first action per batch, phrased by a small table keyed on
  `Action.kind`; a `blocked` session status overrides it.
- No clock, no I/O: `statuses` is an input, so `build_board` is unit-testable
  with plain facts.

### D. Board page (`fr.triage.board_render`, pure)

`render_board(board, *, scope_args, rendered_at, refresh) -> str`, following
`render.py`'s rules (module-constant CSS/JS, `html.escape` everywhere, no
facts text in `<script>`). Cards are `<details>` elements (R4, scripts off),
`id="card-<batch id>"`. The constant script: copy buttons
(`navigator.clipboard.writeText`, falling back to selecting the visible
`<code>`), the refresh timer (`location.reload()`), and expanded/scroll state
saved to `localStorage` keyed by the page path, every access in `try/catch`.
The refresh interval reaches the script as a `data-refresh` attribute on
`<body>`, an integer the renderer formats itself. `rendered_at` is passed in
by the command (the renderer reads no clock).

### E. Commands (`fr.commands.triage_board_cmd`, new; `triage_batch_cmd`)

- `fr triage board [--refresh N] [--watch [--interval N]] [--open]`:
  `_load_state`, then `_session_statuses(judgements, facts)`, then
  `build_board` + `render_board`, written atomically to `board.html`.
  `--watch` checks the drive lock (refuse, R12), then loops
  `collect_into` + render + sleep. `_session_statuses` groups the dispatched
  items by runner name, loads each runner through the existing soft point,
  and fills `unknown` with a note on any `ImportError`, preflight message,
  missing capability or exception (R7).
- `fr triage batch focus <batch-id> [--closeout]` in `triage_batch_cmd.py`,
  reusing its `load_runner`, `batch_item_id` / `closeout_item_id` and the
  probe `WorkItem` shape `drive` uses for closing sessions (R8).
- `_Driver.run_pass` ends (when acting) with a guarded call to the same
  render function the board command uses (R11).
- The scope options echoed into the copied command are `--repo <owner/repo>`
  or `--org <org>` as given, and `--dir <path>` when overridden.

### F. Triage page and skill

`render._batches` gains a link to `board.html` (R13). The `fr-triage` skill
names `fr triage board` and `fr triage batch focus` where it describes
batches and the driver; the OpenCode and Hermes mirrors are regenerated.

## Non-goals

- No server and no push channel: freshness is the drive's re-render plus the
  page's reload (operator decision).
- No issue-level cards; members appear inside their batch's card.
- No actions from the page other than copying a command: the board never
  dispatches, merges or closes anything.
- No focus capability for vk or cncd runners.

## Automated verification (CI)

Unit level, herdr faked at `_run_herdr`; board model and page from fixture
facts/judgements:

- `column_of` for every row of R2's table, including unsatisfiable `after`,
  partial and archived close-outs; card counts and ordering.
- Hints: one fixture per `drive_pass` action kind, and the blocked override.
- Page: every R4 section present on a full fixture; escaping of hostile
  titles; no facts text inside `<script>`; deterministic bytes for the same
  inputs; refresh attribute; `<details>` markup.
- `_session_statuses`: unknown + note for a missing runner, a failed
  preflight, a runner without the capability and a raising one.
- herdr runner: status precedence across several tabs, `absent`, unknown
  values; focus calls `workspace focus` then `tab focus`; no tab → False.
- `focus` command: each refusal of R8, and success.
- drive: board written after an acting pass; a raising render warns once and
  the pass still completes.
- `--watch` refusal under a live lock.
- A browser check of the page: collapsed and expanded cards in light and dark,
  phone width stacking, copy confirmation.

## Test Plan (post-merge, operator-driven)

1. Inside herdr, with a drive running over at least two batches, open
   `board.html`: cards sit in the right columns, move as the drive acts
   (within one pass plus one refresh), and expanded cards stay expanded
   across reloads.
2. Click a running batch's jump button, paste into a herdr pane: the terminal
   switches to that batch's tab, in its wave workspace.
3. While a session waits on a permission prompt, its card shows `blocked` and
   the "needs you" hint after the next render.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-10-05-triage-batch-board | `derio-net/super-fr` | `2026-10-05-triage-batch-board` | — |
