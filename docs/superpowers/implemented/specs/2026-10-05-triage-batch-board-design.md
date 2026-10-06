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
  (`batch.py:224`) gives `proposed | dispatched | pr-open | merged | partial |
  abandoned | cancelled`; `dependency_state` (`batch.py:296`) gives each `after`
  entry's state; `closeout_state` (`batch.py:308`) gives `none | started |
  archived` from the events and the merged `chore/closeout-<branch>` PRs in the
  facts.
- `fr.triage.views.drive_snapshot(facts, judgements)` (`views.py:74`) builds
  the driver's `Snapshot` from facts alone, and `batch_drive.drive_pass`
  (`batch_drive.py:416`) turns it into the actions the driver would take. It
  emits an action only where the driver would ACT — nothing for a running
  session, a draft PR or pending CI — so it can inform a hint but cannot be
  the whole of one. The drive selects every batch with a wave, else all
  (`triage_batch_cmd._chosen`).
- A batch session is a herdr tab labelled with its item id
  (`batch_item_id` → `<repo>/run/batch-<id>`); a close-out session's label is
  `closeout_item_id`. A close-out the drive ADOPTED (done by hand, or already
  archived) is recorded with `runner: "hand"` and has no session.
  `herdr tab list` reports every tab's `tab_id`, `workspace_id` and
  `agent_status` (`idle | working | blocked | done | unknown`). `herdr tab
  focus <tab_id>` and `herdr workspace focus <workspace_id>` exist (their
  `--help` read 2026-10-05); tab ids are allocated at creation and recorded
  nowhere fr reads, so "jump to the session" must resolve label → tab when it
  runs.
- `fr_dispatch.protocols.SessionCloser` is the precedent for an OPTIONAL
  runner capability declared beside `Runner`, never inside it, and checked
  with `isinstance`. `fr` reaches `fr_dispatch` only from the soft points
  named in `tests/unit/test_import_direction.py` `_SOFT_POINTS`
  (`apply_cmd.py`, `triage_batch_cmd.py`), and never imports `fr_herdr`.
  `load_runner` reports a refusal as a red `error:` plus `typer.Exit`; the
  drive's `_try_runner` captures that and degrades to a warning.
- `drive` holds `<state dir>/drive.lock` while it runs (plan mode included)
  and re-collects facts every pass (`triage_cmd.collect_into`); `run_pass`
  loads facts and judgements once, before it acts.
- `fr.triage.components` holds the shared colour tokens and the phone gutter.

## Requirements

R1. `fr triage board` (same `--repo` / `--org` / `--dir` options as `fr triage render`, plus `--open` to open the page in a browser) writes `board.html` into the triage state directory from `facts.json` and `judgements.yaml`, without collecting; with no batches it still writes a page that says there are none.
R2. The board shows exactly one card per batch in `judgements.yaml`, in one of six columns, left to right: **Proposed** (never dispatched, every `after` dependency satisfied or none), **Waiting** (never dispatched, some `after` dependency not satisfied), **Running** (stage `dispatched`), **PR open** (stage `pr-open`), **Closing out** (stage `merged` and close-out not archived), **Done** (stage `merged` with close-out archived, or stage `cancelled`, `abandoned` or `partial`). A Done card for `cancelled`, `abandoned` or `partial` carries that word as a pill; a Waiting card with an unsatisfiable or unknown dependency is marked blocked. Each column header shows its card count; within a column, cards sort by wave (no wave last), then batch id.
R3. A collapsed card shows the batch id, title, wave, member count, the session status pill (R7), the next-action hint (R6) and a jump button whenever the batch has a dispatch event and its session status is not `no session`.
R4. A card expands in place to show: its member issues (title linked to the forge, issue stage); its PR (link, draft or ready, check counts, mergeable state, review decision) when it has one; its lifecycle (wave, each `after` dependency with its state, branch, reserved version, runner, harness, model, skill, rationale — harness and model from the batch's stored launch, else the repo's collected `defaults.launch` marked "(default)", else "—"); its event timeline (every dispatch, cancel, post_merge and closeout event, oldest first, with its time); and, when a close-out was started by a runner (not `hand`), the close-out session's status and a second jump button under the same rule as R3. Expanding works with scripts off.
R5. A jump button copies the command `fr triage batch focus <batch-id>` (plus `--closeout` for the close-out session's button), carrying the scope options the board was rendered with (`--repo` or `--org`, and `--dir` only when it was given), each argument shell-quoted, to the clipboard, and confirms the copy on the button; where the clipboard is unavailable the command is shown selected for a manual copy. The command text is always visible on the expanded card.
R6. Each card carries a one-line next-action hint, chosen in this order: a `blocked` session (R7) reads "needs you: session blocked"; else the first action the driver would take for that batch on the same facts (`drive_pass` over `drive_snapshot`, selecting the batches the drive selects by default — every batch with a wave, else all — at the drive's default in-flight cap), phrased per action kind (e.g. "dispatch next", "merge ready", "CI failing", "close-out due", "blocked: waits on <batch>", "held by the in-flight cap"); else a per-column fallback — Proposed "queued" (or "not driven" when outside the drive's selection), Waiting "waits on <batches not yet merged>", Running "session running, no PR yet", PR open "PR draft" / "CI pending" / "awaiting review", Closing out "archive PR pending" when a close-out was started and "close-out not recorded" when none was, Done "finished" or its pill word.
R7. When the board is rendered, each batch with a dispatch event, and each close-out started by a runner, shows the live status of its session — `working`, `blocked`, `idle`, `done`, `unknown`, or `no session` — asked of the runner named in its latest dispatch (or closeout) event through an optional runner capability. A runner that cannot be loaded, fails its preflight, lacks the capability, or raises shows `unknown` with one page-level note per runner saying why, and the render prints no error and never fails on it. A `blocked` session highlights its card as needing the operator.
R8. `fr triage batch focus <batch-id> [--closeout]` switches the operator's terminal to that batch's (or its close-out's) live session through the runner named in the latest dispatch (or closeout) event, and exits 0. It refuses with exit 2 and a one-line reason when the batch is unknown, has no such event, the close-out was done by hand, the runner cannot be loaded, lacks the focus capability or fails its preflight, or holds no live session for the item.
R9. The herdr runner implements both capabilities: status from `herdr tab list` (every workspace, matching the tab label to the item id; several tabs → the first present of `blocked`, `working`, `idle`, `done`, `unknown`; a status outside those five is `unknown`; no tab is `no session`), and focus as `herdr workspace focus <workspace_id>` then `herdr tab focus <tab_id>` for the first matching tab.
R10. The page re-reads itself on a timer — every 30 seconds by default, set with `fr triage board --refresh <seconds>`, `0` turning it off — and keeps which cards are expanded and the scroll position across the reload. The page shows when it was rendered and when its facts were collected.
R11. `fr triage batch drive --yes` re-renders `board.html` at the end of every pass, acting or not, from the facts that pass collected and the `judgements.yaml` as it stands after the pass's own writes, with the drive's scope options for the copied commands. (A pass's own forge effects — a PR it opened, a merge it made — show from the next pass's collect.) A board that fails to render prints one warning per cause and never fails or stops the drive.
R12. `fr triage board --watch [--interval <seconds>]` (default 60) re-collects facts the way `fr triage collect` does and re-renders the board every interval until interrupted. It refuses, exit 2, when a live `drive` holds the state directory's lock at start; when a drive takes the lock later, each iteration that finds it held skips its collect and render (the drive keeps the board fresh), saying so once.
R13. `triage.html` links to `board.html` from its Batches section when there are batches and `board.html` exists in the state directory.
R14. Every forge- or judgement-sourced string on the board is escaped, none reaches a `<script>` element, and the copied command is built only from the validated batch id and the scope options, each shell-quoted before it is HTML-escaped.
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
by R9's precedence. `HerdrRunner.focus` lists tabs, takes the first whose
label is the item id, runs `herdr workspace focus <workspace_id>` then `herdr
tab focus <tab_id>`, returns True; no tab → False. Both go through
`_run_herdr`, so the existing fake covers them. Conformance lines join the
`TYPE_CHECKING` block. Before building against the two focus verbs, their
live output is captured into `tests/fixtures/herdr/` (`tab-focus.json`,
`workspace-focus.json`) by focusing the tab and workspace that are already
focused — harmless — matching the existing fixture discipline; the help text
read 2026-10-05 is the argument evidence.

### C. Board model (`fr.triage.kanban`, pure, no `fr_dispatch` import)

```python
BoardStatus = Literal["working", "blocked", "idle", "done", "unknown", "absent"]
Column = Literal["proposed", "waiting", "running", "pr-open", "closing-out", "done"]

@dataclass(frozen=True)
class Card: batch, column, stage, blocked, hint, status, closeout_status, pr, members, launch, ...

def column_of(batch, facts, batches) -> Column
def build_board(facts, judgements, statuses: Mapping[str, BoardStatus], *, selected) -> Board
```

- `BoardStatus` is fr's own copy of `SessionStatus`; a test pins the two
  equal, the way `batch_item_id` is pinned to `run_item_id`. This keeps
  `fr.triage.kanban` free of any `fr_dispatch` import.
- `column_of` is R2's table: no events → `proposed` / `waiting` by
  `dependency_state` over `after`; else by `derive_batch_stage`, with
  `merged` split by `closeout_state(batch, facts) == "archived"`. A merged
  batch with no closeout event cannot be told apart offline from one closed
  out by hand before the drive saw it: it stays in Closing out with
  "close-out not recorded" (R6) until a drive pass adopts it (the drive
  records a `hand` close-out when it finds the archive done).
- The hint (R6) runs `drive_pass` once over `drive_snapshot(facts,
  judgements)` with `selected` set to the drive's default selection — moved to
  a pure `batch_drive.default_selection(batches)` that `_chosen` also calls —
  keeps the first action per batch, then falls back per column.
- No clock, no I/O: `statuses` is an input, keyed by item id.

### D. Board page (`fr.triage.kanban_render`, pure)

`render_board(board, *, scope_args, rendered_at, refresh, notes) -> str`,
following `render.py`'s rules (module-constant CSS/JS, `html.escape`
everywhere, no facts text in `<script>`). Cards are `<details>` elements (R4,
scripts off), `id="card-<batch id>"`. The command is
`shlex.join(["fr", "triage", "batch", "focus", id, *scope_args])`, then
HTML-escaped into the button's `data-command` and a visible `<code>`. The
constant script: copy buttons (`navigator.clipboard.writeText`, falling back
to selecting the `<code>`), the refresh timer (`location.reload()`), and
expanded/scroll state saved to `localStorage` keyed by the page path, every
access in `try/catch`. The refresh interval reaches the script as a
`data-refresh` integer attribute on `<body>`. `rendered_at` is passed in by
the command (the renderer reads no clock).

### E. Commands (`fr.commands.triage_kanban_cmd`, new soft point)

All `fr_dispatch` contact for the board lives in ONE new module,
`triage_kanban_cmd.py`, added to `_SOFT_POINTS` in
`tests/unit/test_import_direction.py` (with the same `find_spec` guard as
`triage_batch_cmd`). It imports from `triage_cmd` only (`triage_app`,
`batch_app`, `_scope`, `_load_state`, `collect_into`, option types), never
from `triage_batch_cmd`; `triage_batch_cmd` imports `write_board` from it.
The import is one-way, so there is no cycle. `triage_cmd` imports it last,
like the other triage command modules.

- `session_statuses(judgements, facts, *, prefix) -> (statuses, notes)`:
  builds probe `WorkItem`s exactly as the drive's `_sessions` does (item id,
  `unit="run"`, `payload.group = wave_group(prefix, wave)`), skips `hand`
  close-outs, groups by runner name, loads each runner with errors captured
  (the `_try_runner` pattern: `err_console.capture()`, catching `typer.Exit`
  and `Exception`), runs `preflight`, checks `isinstance(runner,
  SessionInspector)`, and degrades every failure to `unknown` plus one note.
  The drive's default workspace prefix is used outside the drive.
- `write_board(scope, target, *, scope_args, refresh, prefix) -> Path`:
  `_load_state` → `session_statuses` → `build_board` → `render_board`,
  written atomically to `board.html`.
- `fr triage board [--refresh N] [--watch [--interval N]] [--open]`. `--watch`
  refuses on a held lock at start; each iteration re-checks it (skip and say
  once while held), else `collect_into` as `fr triage collect` calls it, then
  `write_board`, then sleep.
- `fr triage batch focus <batch-id> [--closeout]` on `batch_app` (R8),
  building the same probe item and checking `SessionFocuser`.
- The scope args are `--repo <owner/repo>` or `--org <org>` as given, plus
  `--dir <path>` only when the operator passed one.

### F. Drive hook (`triage_batch_cmd`)

`_Driver` gains the scope args it was started with (including whether `--dir`
was given). At the end of every `--yes` pass, after its actions, it calls
`write_board` — which reloads `judgements.yaml` from disk, so the pass's own
dispatch and closeout events show — inside a guard that turns any exception
into one warning per distinct cause (the `read_failures` pattern).

### G. Triage page and skill

`render._batches` gains a link to `board.html` when the command tells it the
file exists (R13). The `fr-triage` skill names `fr triage board` and `fr
triage batch focus` where it describes batches and the driver; the OpenCode
and Hermes mirrors are regenerated.

## Non-goals

- No server and no push channel: freshness is the drive's re-render plus the
  page's reload (operator decision).
- No issue-level cards; members appear inside their batch's card.
- No actions from the page other than copying a command: the board never
  dispatches, merges or closes anything.
- No focus or status capability for vk or cncd runners.

## Automated verification (CI)

Unit level, herdr faked at `_run_herdr` with captured fixtures; board model
and page from fixture facts/judgements:

- `column_of` for every row of R2's table: unsatisfiable and unknown `after`,
  partial, a merged batch with no closeout event, one with a started close-out,
  one archived by event and one archived by a merged `chore/closeout-*` PR;
  card counts and ordering.
- Hints: one fixture per `drive_pass` action kind, every per-column fallback,
  "not driven" outside the default selection, and the blocked override.
- Page: R1's no-batches page; every R4 section on a full fixture, including
  the default-launch marking and a `hand` close-out without a button; R3's
  button rule (`absent` hides it, `unknown` keeps it); rendered and collected
  times; escaping of hostile titles; no facts text inside `<script>`; a
  hostile `--dir` shell-quoted then escaped; deterministic bytes for the same
  inputs; `data-refresh`; `<details>` markup; the `BoardStatus` pin.
- `session_statuses`: unknown + one note, and no `error:` output, for an
  unloadable runner, a failed preflight, a runner without the capability and
  a raising one; `hand` close-outs never probed; probe items carry the group.
- herdr runner: status precedence across several tabs, `absent`, an unknown
  value; focus calls `workspace focus` then `tab focus`; no tab → False.
- `focus` command: each refusal of R8, and success.
- drive: board written after an acting pass and after a non-acting pass;
  a dispatch event written by the pass appears on the board; a raising render
  warns once per cause and the pass still completes.
- `--watch`: refusal under a live lock at start; an iteration that finds the
  lock held skips; the default interval.
- `triage.html`: the board link present only when `board.html` exists.
- `test_import_direction`: `triage_kanban_cmd.py` is a soft point; nothing else
  new imports `fr_dispatch`.
- A browser check of the page: collapsed and expanded cards in light and dark,
  phone-width stacking, copy confirmation and the clipboard fallback, expanded
  cards kept across a reload.

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
