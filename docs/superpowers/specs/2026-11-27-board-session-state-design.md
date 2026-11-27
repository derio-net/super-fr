# Batches page: who each card waits for, lane owners, time per column

Issue: derio-net/super-fr#1731. Batch `board-session-state`.

## Background

The Batches page (`fr triage batches`, written by
`packages/fr/src/fr/commands/triage_kanban_cmd.py:411` `write_board`, which both the
board command and the wave driver call: `triage_batch_cmd.py:5879`,
`triage_drive_loop.py:465`) puts every batch in one column. The column comes from
`fr.triage.kanban.column_of` (`kanban.py:444`), and the four Needs-you lanes from
`fr.triage.lanes.lane_of` (`lanes.py:33`). A card then shows its session's status
(`BoardStatus`, `kanban.py:74`, read live by `read_sessions`,
`triage_kanban_cmd.py:289`) and one hint line (`kanban.py:743-774`).

What the operator cannot see today:

- **Who the card waits for.** "Running" holds both an agent that is working and one that
  sits at an idle prompt while its background shells run. "PR open" holds both a PR
  whose CI runs and one the driver will queue on its next pass. The hint says some of
  this, in different words per case, and never as one answer to "whose turn is it".
  The herdr runner already knows how to tell an idle Claude prompt with background work
  from a really idle one: `fr_herdr.restart.has_background_work` (`restart.py:221`), used
  today only to refuse a restart (`restart.py:269`, `replacement.py:123`).
- **Who owns a Needs-you lane.** A lane says "Needs you · Reviewer", but not who that is.
- **How long a card has been where it is**, and so where a wave loses its time. Columns
  are derived from facts on every render and nothing records when a card entered one;
  session states have no timestamps at all.

This works without Stations (the planned multi-operator surface) and helps orchestrate
waves today.

## Requirements

R1. Every card on the Batches page names the one party it waits for, from a closed set of six: `you` (the operator, with the lane's role when the card is in a Needs-you lane or held for the operator's approval label), `agent` (its front session works, or is idle below the idle threshold with no PR yet), `background` (its front session sits at an idle prompt while background shells, monitors or subagents run), `ci` (its PR's checks are pending), `queue` (the wave driver or merge queue acts next: dispatch, queueing, the in-flight cap, landing), `dependency` (a batch it is `after` is not yet satisfied). Only a card in the `Done` column waits for no one and shows no wait; a card in a Tester or DevOps lane, a Closing-out card and an Obsolete card (which waits for the operator's `batch cancel`) each show one.
R2. The wait never moves a card: `lanes.lane_of` and `kanban.column_of` stay the only decision of a card's column, and the wait is derived after the column, by one pure function with a fixed precedence (Design §A).
R3. `background` is read only from a runner that can say it. A new optional `fr_dispatch` protocol, `SessionActivity`, beside `SessionInspector`, returns the item ids whose session is idle with background work. The herdr runner implements it: for each item whose status is `idle` or `done`, it reads the visible screen of each Claude agent pane in the item's tabs (one `herdr pane read` per such pane) and asks `fr_herdr.restart.has_background_work`. Another agent kind, another runner, or a failed read reports no background; a failed read adds one page note.
R4. Each repo's `.fr/triage.yaml` may name an owner per Needs-you lane: `lane_owners: {developer: [<login>], reviewer: [...], tester: [...], devops: [...]}`. The key is display-only: it is not a guarded key (`config.protection.GUARDED_TRIAGE_KEYS`), so it is read under quiet and stealth from an unprotected configuration branch too, and an unknown lane key under it never refuses the repo's config: it is ignored and named in one page note. Each Needs-you column header shows its owners (`owner: @a, @b`) or `owner: unassigned`; in a scope of several repos whose owners differ it shows them per repo. A card in a Needs-you lane names the lane's owners in its wait line. Adding the key moves `FACTS_SCHEMA` from 20 to 21.
R5. A dwell ledger, `dwell.json` in the scope's state directory, carried by the state ref (`state_ref.REF_FILES`), records per batch the column and the wait party it was last seen in and since when, plus the closed intervals before that. Each `write_board` observes the board at the render time: a column or wait that differs from the ledger's closes the open interval at that time (its start is the later of the two `since` times) and restarts the changed `since`. A state the ledger first saw already under way is marked first-seen (its time is "at least"); a restarted `since` is not first-seen; a closed interval keeps the mark of its start. A batch absent from the board is dropped, and each batch keeps its last 200 intervals, marking itself truncated when it drops one. The ledger has ONE writer: `write_board` stores it only when no live driver holds `drive.lock`, or when it runs inside that driver; any other render observes in memory and stores nothing. A fetch of the state ref adopts the ref's `dwell.json` over a local one and never refuses over it. An unreadable ledger is an empty one plus one page note, never a crash; the ledger is written atomically.
R6. Each card shows one dwell line: `in <column> <duration> · waits for <party> <duration>`, durations as `45m`, `3h 12m` or `2d 4h`, prefixed `≥` when the state is first-seen. A card with no wait (R1) shows only its column time.
R7. The Batches page has a "Time per wave" section: one block per wave, and one for the batches with no wave, giving the time its batches spent per column and per wait party (closed intervals plus open ones up to the render time), and for each column the batch that spent longest there. A total that a first-seen interval or a truncated batch contributes to is prefixed `≥`. Waves the cutoff hides (`cutoff_hidden_waves`) are hidden there too.
R8. `build_board` and `render_board` stay pure: the wait is computed inside `build_board` from what it is handed (the background set included), the render reads no clock, and only `write_board` reads and writes the ledger.

## Design shape

```
packages/fr-dispatch/src/fr_dispatch/protocols.py
  + class SessionActivity(Protocol)            # session_background(items) -> frozenset[str]   (R3)
packages/fr-herdr/src/fr_herdr/runner.py
  ~ HerdrRunner                                # + session_background: idle/done tabs → Claude panes
                                               #   → `pane read` → restart.has_background_work  (R3)
packages/fr/src/fr/triage/
  + waits.py                                   # Party, Wait, wait_of(...)  — pure, ordered rules (R1, R2)
  + dwell.py                                   # Ledger model, load/observe/store, card_dwell,
                                               #   wave_time  — observe() pure, clock passed (R5-R7)
  ~ model.py                                   # TriageConfig.lane_owners; FACTS_SCHEMA 20 → 21 (R4)
  ~ kanban.py                                  # Card.wait; ColumnView.owners; build_board(background=) (R1, R4, R8)
  ~ kanban_render.py                           # wait + dwell line on the card, owner in lane
                                               #   header, "Time per wave" section (R4, R6, R7)
  ~ state_ref.py                               # REF_FILES += "dwell.json" (R5)
packages/fr/src/fr/commands/triage_kanban_cmd.py
  ~ read_sessions → SessionReads.background    # asks SessionActivity, notes a failure (R3)
  ~ write_board                                # load ledger → observe(board, now) → store only as
                                               #   the one writer → render (R5, R8)
packages/fr/src/fr/triage/state_ref.py
  ~ fetch_state                                # dwell.json: the ref's copy wins, never a clash (R5)
docs/explainers/fr-triage.md                   # waits, lane_owners, dwell line, Time per wave
docs/explainers/fr-dispatch.md                 # SessionActivity beside SessionNotes
docs/reference/dispatch-lifecycle.md           # SessionActivity in the optional-protocol list
docs/herdr-control-sessions.md                 # the board's background read (one pane read per idle Claude pane)
```

## Design

### A. The wait (`fr/triage/waits.py`)

```python
Party = Literal["you", "agent", "background", "ci", "queue", "dependency"]

@dataclass(frozen=True)
class Wait:
    party: Party
    role: Literal["developer", "reviewer", "tester", "devops"] | None  # set for `you` in a lane
```

`wait_of` takes what `kanban._card` already computes: the column and stage, the lane
verdict, `needs_you`, `Card.front` and the front session's status (`BoardStatus | None`),
whether the front session's item id (`batch_item_id`, or `closeout_item_id` when the front
is the close-out) is in the background set, the PR's `checks` (which may be `None`), the
driver's actions and the queued, ready and awaiting sets, whether the batch is in the
default selection, and each `after` dependency's `dependency_state`. It returns a
`Wait | None`. First match wins:

| # | Condition | Wait |
|---|---|---|
| 1 | the column is `done` | None |
| 2 | `needs_you` (a blocked session, a merge stop, a lane, an idle session past the threshold, a held archive) | `you`, role = the lane's role (`needs-developer` → developer …), else None |
| 3 | the stage is `obsolete` (it waits for `batch cancel`) | `you` |
| 4 | the batch is in the awaiting set (green, held for the operator's `approved-fr`) | `you`, role reviewer |
| 5 | an `after` dependency is `unsatisfiable` or `unknown` (`Card.blocked`: re-plan or cancel) | `you` |
| 6 | an `after` dependency is not `satisfied` | `dependency` |
| 7 | the column is `proposed` and the batch is not in the default selection (the driver never takes it) | `you` |
| 8 | front status `working` | `agent` |
| 9 | front status `idle` or `done`, and the front item id is in the background set | `background` |
| 10 | an open PR with `(checks or {}).get("pending", 0) > 0` | `ci` |
| 11 | the batch has a driver action, or is queued or ready, or sits in `proposed` (selected) or `waiting` | `queue` |
| 12 | front status `idle` or `done` | `agent` (still its turn: below the idle threshold, row 2 did not fire) |
| 13 | otherwise (front status `absent`, `unknown` or `None`) | `queue` (the driver re-dispatches or replaces a lost session, or flags it stale) |

`blocked` never reaches a row after 2, because a blocked session is always `needs_you`.
The wait is set on `Card.wait` after the column and hint are decided; it changes neither
(R2). Every row has its own test, with the close-out front for rows 8, 9 and 12.

### B. Background (`SessionActivity`)

`fr_dispatch.protocols.SessionActivity.session_background(items) -> frozenset[str]` is an
optional protocol, like `SessionNotes` (`protocols.py:163`); `tests/unit/test_import_direction.py`
keeps `fr` free of an `fr_herdr` import, so the board learns of it only through the
protocol. `HerdrRunner.session_background` lists tabs and agents once, keeps the items
whose `_status_of` is `idle` or `done`, and for each agent of kind `claude` in those tabs
reads `pane read <pane> --source visible --ansi` and asks `restart.has_background_work`.
`read_sessions` asks it only of a runner that implements it, after `session_statuses`, and
returns the union in a new `SessionReads.background`. A raise costs one note,
`runner <name> could not read background work: <reason>`, and no background.

### C. Lane owners

`TriageConfig.lane_owners: LaneOwners = LaneOwners()`, a model with four `list[str]`
fields (default empty) and `ignored: list[str]`: a `mode="before"` validator moves any
other key under `lane_owners` into `ignored`, so a typo (`review:`) never refuses the
repo's `.fr/triage.yaml` and its queue, `post_merge` and other keys; the board prints one
note per repo naming the ignored keys. The key stays out of
`config.protection.GUARDED_TRIAGE_KEYS` (`protection.py:61`): it runs nothing and trusts
no one, so an unprotected configuration branch may set it. `ColumnView.owners` holds, for a Needs-you column, a mapping repo →
logins built from the facts' per-repo config for the repos of the scope;
`kanban_render._column` prints it under the title. The card's wait line reads
`waits for you · reviewer (@a, @b)`. `FACTS_SCHEMA` moves to 21 with its comment, like 20
before it; `test_triage_model.py` pins the number.

### D. The dwell ledger (`fr/triage/dwell.py`)

```json
{"schema": 1,
 "batches": {"<batch id>": {
   "column": "pr-open", "column_since": "<ISO>", "column_first_seen": false,
   "wait": "ci", "wait_since": "<ISO>", "wait_first_seen": false,
   "intervals": [{"column": "running", "wait": "agent", "start": "<ISO>", "end": "<ISO>"}]}}}
```

Each interval also carries `first_seen` (its start was a first sighting), and each
batch `truncated` (it dropped an interval to the cap).

`observe(ledger, board, now) -> Ledger` is pure. For each card it compares column and
wait party (`None` for no wait) with the entry: equal keeps the entry; different appends
the open interval `(column, wait, start = max(column_since, wait_since), end = now,
first_seen = the first_seen of whichever since is the start)` and restarts each changed
`*_since` at `now` with its `*_first_seen` cleared. A new batch starts with both
`*_since = now` and both `*_first_seen = true`. Intervals are capped at the last 200 per
batch (`truncated = true` once one is dropped). Batches absent from the board are dropped. `card_dwell(entry,
now)` and `wave_time(ledger, board, now)` turn it into the card line and the wave section.
`load` returns `(Ledger, note | None)`; `store` writes through `write_text_atomic`.
`write_board` runs load → `build_board` → `observe` → `store` → `render_board(dwell=…)`,
and stores only as the ledger's one writer: when `drive.lock` names no live driver
(`live_driver`, the check the watch already makes at `triage_kanban_cmd.py:561`), or when
the caller is that driver (the driver's `_write_board`, `triage_batch_cmd.py:5875`, and the
supervisor's, `triage_drive_loop.py:465`, pass `writer=True`). Otherwise it observes in
memory, so the page still shows fresh durations, and leaves the file alone.

`state_ref.fetch_state` (`state_ref.py:255`) treats `dwell.json` as observation, not
authored state: it never counts as a clash, and a moved ref's copy overwrites the local
one. A fetch costs at most the transitions one host saw since its last push; the driver
pushes the state every pass, so that is at most one pass.

Precision is the observation cadence. The driver renders the page on each pass that is not
essential-only (an essential-only paced pass keeps the last board,
`triage_batch_cmd.py:5813-5816`); the watch renders only after a collect
(`triage_kanban_cmd.py:630-632`) and not at all while a driver holds the lock. Under quota
pacing the gap between observations can be several pass intervals: a transition is dated
at the next observation, never earlier, and a state shorter than one gap may go unseen.

### E. Rendering

The card summary gains the dwell line under the hint (`.dwell`, muted). The wait party is
a pill, `wait-<party>`, coloured like the existing status pills (`you` takes `--sev-1`).
The "Time per wave" section follows the queue section: per wave a `<details>` with a
table, rows the columns and parties with time, columns `total` and `longest (batch)`;
carrying `data-cutoff-hidden` when its wave is hidden.

## Verification

gate: developer
- batch-card-waits-for: none — CI unit tests over `wait_of`'s table and the card, plus fr-goal's browser checks at review and deliver over a page rendered from fixture state
- batch-card-background-wait: none — CI unit tests over `HerdrRunner.session_background` with captured screens and over `read_sessions` with a fake runner
- batch-lane-owners: none — CI unit tests over the config model and the column header, plus fr-goal's browser checks at review and deliver
- batch-dwell-ledger: none — CI unit tests drive `observe` with a fake clock and assert intervals, first-seen, pruning, the cap and the unreadable-file note
- batch-card-dwell-line: none — CI unit tests plus fr-goal's browser checks at review and deliver
- batch-wave-time-summary: none — CI unit tests plus fr-goal's browser checks at review and deliver
- batch-background-live: live — only a real herdr with a Claude session running a background shell shows the screen this reads; the unit tests read captured screens

## Test Plan

- [ ] post-merge — operator-driven: with the wave driver running on a live herdr, start a background shell in a dispatched Claude batch session and leave it at its prompt; the next Batches page shows that card `waits for background`, and after the shell ends, `waits for agent` (row `batch-background-live`).

## Risks

- `FACTS_SCHEMA` 21 may collide with another open branch that moves it; the later one to
  merge renumbers, as earlier bumps did.
- Observation gaps under quota pacing date a transition late (Design §D); the `≥` marks
  only first sightings, not late dating.
- One `pane read` per idle Claude pane per render costs wall clock on a large wave; it is
  bounded by the number of idle panes and runs only where the herdr runner is loaded.
