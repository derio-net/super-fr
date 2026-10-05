## Summary

A live Kanban board of triage batches, refreshed by the wave driver or a timer, with a one-click "jump" that copies the command to switch to a batch's herdr session.

- **`fr triage board`** writes `board.html` beside `triage.html`: one card per batch in six lifecycle columns (Proposed · Waiting · Running · PR open · Closing out · Done). Each card shows its live herdr session status (`working`/`blocked`/`idle`/`done`, with "needs you" on a blocked session) and a next-action hint taken from what the driver would do. Cards expand in place to show member issues, PR and CI state, lifecycle, the event timeline and the close-out session.
- **Jump:** the button copies `fr triage batch focus <id> [--closeout] --repo … [--dir …]`. The new **`fr triage batch focus`** resolves the session's herdr tab by label when it runs, then focuses its workspace and tab.
- **Freshness:** `fr triage batch drive --yes` re-renders the board after every pass. `fr triage board --watch` re-collects and re-renders when no drive runs (it steps aside while a drive holds the lock). The page reloads itself every 30s (`--refresh N`, 0 = off) and keeps expanded cards and scroll position.
- **Runner seam:** `SessionInspector` and `SessionFocuser` are new optional protocols beside `SessionCloser`; herdr implements both. All `fr_dispatch` contact goes through a third soft point, `triage_kanban_cmd.py`; `fr.triage.kanban*` are pure.
- `triage.html` links the board once it exists, the `fr-triage` skill describes both new commands (OpenCode and Hermes mirrors regenerated), and `plural("batch")` now says "batches".

Spec: `docs/superpowers/specs/2026-10-05-triage-batch-board-design.md` · Plan: `docs/superpowers/plans/2026-10-05-triage-batch-board/`

## Decisions (operator, one question round)

d1 one card per batch · d2 lifecycle columns · d3 separate `board.html` via `fr triage board` · d4 drive re-renders + page timer + `--watch` · d5 jump copies a new `fr` verb · d6 live session status at render · d7 expanded: members, PR/CI, lifecycle, timeline, next-action hint.

## Operator gates

```text
brainstorm: operator gate answered by the operator
```

## Out-of-scope findings to file

- `p2-r6`: a `partial` batch sits in Done (d2) while its close-out still runs, so its hint can read "close-out due". This is intended: sr-4 keeps a partial card's hint, status and jump buttons live. Changing it would mean revisiting d2, so the operator decides whether to file it.

## Back-loaded manual phase

None — all three phases are agentic.

## Test Plan (post-merge — operator-driven)

1. Inside herdr, with a drive running over at least two batches, open `board.html`. Check that cards sit in the right columns, move as the drive acts (within one pass plus one refresh), and that expanded cards stay expanded across reloads.
2. Click a running batch's jump button and paste the command into a herdr pane. The terminal should switch to that batch's tab, in its wave workspace.
3. While a session waits on a permission prompt, check that its card shows `blocked` and the "needs you" hint after the next render.

## Acceptance

- **Rows added since `origin/main` (7, all from this spec, each cites its requirement):**
  - `triage-board-columns`, `-card-detail`, `-jump-focus`, `-session-status`, `-refresh` and `-untrusted-text` are now `ci`. Each states what the board does for an operator, and each is unit-tested and browser-checked where it carries `visual`.
  - `triage-board-live-herdr` is `not-implemented` with `verify: post-merge`. Only a real herdr session can prove the focus switch and the blocked status, which is the Test Plan above.
- **Acceptance debt:** `fr acceptance status` reports 320 ci, 31 skipped, 18 not-implemented and 1 scheduled. The only debt this PR adds is the post-merge row above. The warnings about archived wave-driver spec refs predate this PR.

## Notes

- Spec-review raised 11 findings and the three phase reviews raised 18; every in-scope finding is fixed (list below). One review fix caught a real regression via its own new tests: a successful render was clearing `--watch`'s collect warnings.
- Size is 1.4× the estimate. Most of the extra is tests: the review rounds added the precedence, lock and watch-robustness tests.
- Local full suite: 8616 passed, 105 skipped.

## Ready checklist (operator's)

- [ ] CI green
- [ ] explicit review ok (operator, on this PR)
- [ ] no commits since the ok (fr's own `chore(fr):` record commits excepted)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

<!-- rendered by fr for run 2026-10-05-feat-triage-kanban-board; edit above this line only -->

## Findings

- `sr-1` (spec) — §C/§E import fr_dispatch from forbidden modules and set up a command-module cycle — **fixed**
- `sr-2` (spec) — R6 hints cannot come from drive_pass alone; most cards would read 'nothing to do' — **fixed**
- `sr-3` (spec) — is_finished from facts is false: drive_snapshot reads no archives — **fixed**
- `sr-4` (spec) — partial in Done but the driver still runs its close-out; R3 hides its jump button — **fixed**
- `sr-5` (spec) — R11 hook: every pass vs when acting, stale judgements, missing scope args — **fixed**
- `sr-6` (spec) — _session_statuses failure modes misnamed: load_runner exits via typer.Exit; probe needs payload.group — **fixed**
- `sr-7` (spec) — Close-outs recorded with runner 'hand' not handled by R4/R7/R8 — **fixed**
- `sr-8` (spec) — --watch checks the drive lock only at start — **fixed**
- `sr-9` (spec) — herdr focus verbs have no captured evidence in the repo — **fixed**
- `sr-10` (spec) — Copied command echoes --dir unquoted — **fixed**
- `sr-11` (spec) — Ambiguities: R4 harness/model source, R13 dead link, untested R1/R10/R12/R13, --open not in requirements — **fixed**
- `p1-r1` (plan, phase 1) — probe_item duplicated _Driver._sessions WorkItem construction — **fixed**
- `p1-r2` (plan, phase 1) — load_runner/_fail/_try_load duplicated triage_batch_cmd's — **fixed**
- `p1-r3` (plan, phase 1) — focus/load exception text interpolated raw (multi-line, empty) — **fixed**
- `p1-r4` (plan, phase 1) — no test for the real load_runner -> _fail -> typer.Exit capture path — **fixed**
- `p1-r5` (plan, phase 1) — herdr precedence tests did not pin the whole order — **fixed**
- `p1-r6` (plan, phase 1) — protocol membership test vacuous without __protocol_attrs__ — **fixed**
- `p1-r7` (plan, phase 1) — probe annotated Any discarded WorkItem typing — **fixed**
- `p1-r8` (plan, phase 1) — matrix row cited only the focus CLI test — **fixed**
- `p2-r1` (plan, phase 2) — write_board reload test could never fail — **fixed**
- `p2-r2` (plan, phase 2) — unknown asserted via note text, not the card pill — **fixed**
- `p2-r3` (plan, phase 2) — board_command re-loaded state just to count batches — **fixed**
- `p2-r4` (plan, phase 2) — relative --dir copied verbatim — **fixed**
- `p2-r5` (plan, phase 2) — command wrap split tokens — **fixed**
- `p3-r1` (plan, phase 3) — live_driver and the drive disagreed on an unreadable lock — **fixed**
- `p3-r2` (plan, phase 3) — --watch ended on non-forge collect errors and unguarded render failures — **fixed**
- `p3-r3` (plan, phase 3) — opened = webbrowser.open(...) or True — **fixed**
- `p3-r4` (plan, phase 3) — drive_lock decided lock liveness inline, duplicating live_driver — **fixed**

## Out-of-scope findings

- `p2-r6` (plan, phase 2) — partial batch in Done shows a close-out hint — **out-of-scope**

## Post-merge verification owed

- `triage-board-live-herdr` — Inside herdr during a live drive, cards move columns as the drive acts, the pasted jump command switches to the batch's tab in its wave workspace, and a session waiting on a prompt shows blocked.

## Tests

Full suite run at delivery — `deliver-suite.log@4bf1c77aff11`.

## Proportionality

```text
proportionality: merge-base 109349659b0105d79d42f533d712359752dcbed4

## Unreferenced new files

- .changes/feat-triage-kanban-board.yaml

## Out-of-plan touches

- packages/fr/src/fr/triage/drive_lock.py
- tests/unit/triage_kanban_fixtures.py

## Size

3282 lines changed (+3177 -105; fr artifacts excluded) against an estimate of 2330 (1.4×).

## Phases

3 agentic phases serve 15 of 15 requirements (R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, R11, R12, R13, R14, R15).
- phase 1 — no ask of its own; split reason: risk-first: the unproven herdr focus verbs, the new runner protocols and the third fr_dispatch soft point land and are reviewed before the board builds on them
```

## Cost

| step | turns | cost |
|---|---:|---:|
| brainstorm | 26 | — |
| spec-review | 35 | — |
| plan | 10 | — |
| plan-review | — | — |
| implement | 283 | — |
| journal-check | — | — |
| deliver | — | — |
| (outside run) | 9 | — |
| **total** | | — |

Sessions: 1 read, 0 unavailable.

_Dollars are `—`: no cost recorded yet. A harness may write a session's cost only when the session ends (Claude Code does). `fr run cost 2026-10-05-feat-triage-kanban-board` reads it afterwards._
