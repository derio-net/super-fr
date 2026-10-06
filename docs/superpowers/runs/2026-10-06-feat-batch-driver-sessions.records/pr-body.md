Batch `driver-sessions` changes three things:
- After a merge, the wave driver restarts the idle Claude sessions so they load the new plugins (#964).
- It reports, on the board too, a batch or close-out session that has sat idle with nothing to show for it (#1029).
- The herdr-only constraint is documented (#878).

Closes derio-net/super-fr#964
Closes derio-net/super-fr#878
Closes derio-net/super-fr#1029

## Summary

**`fr-herdr restart-idle`** (#964) is a new console script in `fr-herdr`, put on PATH beside `fr` by `install.sh`.
- It restarts idle Claude panes in place: `/exit`, then `claude <kept flags> --resume <id>`. The pane, tab, label and herdr agent name all stay the same.
- It never sends a key to a pane it should not touch: a busy pane, an unsent draft, background shells or agents, no transcript, unknown launch flags, its own pane, or an excluded pane.
- Claude's faint prompt suggestion is told apart from a typed draft through `pane read --ansi`. This was captured live.
- Each pane's status is re-read just before it is restarted.
- It prints one line per pane and a summary. It is a dry run unless `--yes` is given. One failed pane never stops the run.
- Every herdr surface it parses was captured live (`tests/fixtures/herdr/restart/`, with a README).

**Driver restart** (#964): opt in with `post_merge_restart: idle` in `.fr/triage.yaml`. super-fr's own config turns it on.
- Once per pass in which that repo's `post_merge` succeeded, the driver asks the close-out's runner to restart idle sessions. This goes through a new optional `SessionRestarter` protocol, so fr never imports fr_herdr.
- The restart runs in the pass's `finally`, so a pass that aborts after `post_merge` still restarts.
- It never holds a close-out and never ends the drive.
- Facts schema 5 → 6, for the two new config keys.

**Idle sessions** (#1029): one pure rule, `batch_drive.idle_session`, is read by both the driver and the board. A session is reported when all of these hold:
- the runner says it is `idle` or `done`;
- it was dispatched, or its close-out started, at least `idle_session_minutes` ago (default 60);
- there is no PR, or for a close-out no archive PR.

The driver warns once per process, with a paste-ready `fr triage batch focus` command. The board marks the card *needs you* and says why. `fr.run.liveness.is_idle` is not reused: it judges run cursors, which the driver does not hold (spec §D).

**#878**: kept as documented-only, as decided. The herdr runner's refusal now says to run `drive`/`dispatch` from a herdr pane, and the fr-triage skill states this, along with the new settings and verb.

Spec: `docs/superpowers/specs/2026-10-06-driver-sessions-design.md`
Plan: `docs/superpowers/plans/2026-10-06-driver-sessions/`

## Decisions (one question round)

1. #878: document only. The runner keeps refusing outside herdr.
2. The restart covers every idle Claude pane, not only batch sessions.
3. The verb is a `fr-herdr` console script.
4. The driver opts in through the `post_merge_restart` config key.
5. The idle rule is stateless, with a 60-minute default.
6. Verification: a `candidate` walk, plus a post-merge `live` row for the in-place restart.

## Operator gates

```
brainstorm: operator gate answered by the operator
```

## Test Plan

- post-merge — operator-driven, row `herdr-restart-idle-live`:
  1. Inside herdr, run `fr-herdr restart-idle` (a dry run) and check the per-pane lines against `herdr agent list`.
  2. Run `fr-herdr restart-idle --yes`.
  3. Check that each `ok` pane resumed the same session id, in the same tab, with the same label and launch flags, and that a pane holding a draft was skipped and left untouched.

## Out-of-scope findings to file

p3-r8 and p3-r9 (below) predate this change. Whether to file them is your call at merge.

## Acceptance

- **Debt (`fr acceptance status`):** ci 366, skipped 34, not-implemented 26, scheduled 1. This PR adds no skipped or not-implemented debt. Five of its six rows are `ci`. The sixth is the post-merge live row.
- **Rows added since `origin/main`,** each with a defense:
  - `herdr-restart-idle` — the operator-facing safety contract of the new verb; candidate-walked against a fake herdr.
  - `herdr-restart-idle-live` — in-place resume can only be proven on real panes; post-merge.
  - `drive-post-merge-restart` — the business promise that sessions run merged code after a drive merges.
  - `drive-idle-session-report` — the driver no longer waits forever on a silent session (#956's second half).
  - `board-idle-session` — the operator sees the stuck session on the board, with the reason (visual evidence taken at deliver).
  - `herdr-outside-refusal` — the herdr-only constraint is stated where the operator meets it.
- **Visual:** fresh screenshots of the three `board-idle-session` states, taken on the delivered branch and opened.
- **Explainers:** no page describes the wave driver or the herdr runner, so none is updated.

## Ready checklist (operator)

- [ ] CI green
- [ ] Explicit review ok
- [ ] No commits since the ok (fr's own `chore(fr):` record commits do not count)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

<!-- rendered by fr for run 2026-10-06-feat-batch-driver-sessions; edit above this line only -->

## Findings

- `sr-1` (spec) — install.sh never puts fr-herdr on PATH: uv's entry points go to a private bin dir and only `fr` is symlinked — **fixed**
- `sr-2` (spec) — The draft check reads Claude's prompt-suggestion ghost text as an unsent draft — **fixed**
- `sr-3` (spec) — The run strategy is `candidate`, but no Verification row is candidate-walked — **fixed**
- `sr-4` (spec) — The Test Plan names only the live row; CI tests are missing — **fixed**
- `sr-5` (spec) — The design depends on herdr surfaces the repo has never called or captured — **fixed**
- `sr-6` (spec) — The transcript check can pass for a session `claude --resume` cannot find from the pane's cwd — **fixed**
- `sr-7` (spec) — The restart runs synchronously inside each _close_out, restarting every pane k times per pass — **fixed**
- `sr-8` (spec) — 'once per dispatch' and 'once per drive' vs the warned set dying at every exec-restart — **fixed**
- `sr-9` (spec) — The board's `now` is ambiguous, and build_board's signature change is missing — **fixed**
- `sr-10` (spec) — views.needs_you labels every drive_pass warn 'failing-ci' — **fixed**
- `sr-11` (spec) — The R7 focus command omits scope options — **fixed**
- `sr-12` (spec) — Spec names do not match code: _snapshot, FACTS Literal, test path, protocol list — **fixed**
- `sr-13` (spec) — Restart preflight items unspecified; lazy import of fr_herdr.restart after post_merge mixes versions — **fixed**
- `sr-14` (spec) — kept_args drops other launch flags silently — **fixed**
- `p1-r1` (plan, phase 1) — restart_idle classified every pane from one initial agent list, so a pane that turned working during earlier serial restarts still got /exit — **fixed**
- `p1-r2` (plan, phase 1) — has_draft failed open when no line started exactly with the prompt glyph — **fixed**
- `p1-r3` (plan, phase 1) — only the first input line was checked, so a multi-line draft with an empty first line was missed — **fixed**
- `p1-r4` (plan, phase 1) — the named relaunch did not retry agent_pane_busy like the runner does — **fixed**
- `p1-r5` (plan, phase 1) — only HerdrError was caught, so an OSError or non-dict herdr answer aborted the run and lost the resume line — **fixed**
- `p1-r6` (plan, phase 1) — spec §A/R2 were not amended for the live discoveries — **fixed**
- `p1-r7` (plan, phase 1) — a lone background subagent was caught only by one captured panel glyph — **fixed**
- `p1-r8` (plan, phase 1) — the resume confirmation could accept a stale pre-exit agent-list entry — **fixed**
- `p1-r9` (plan, phase 1) — the relaunch and resume line assumed the shell cwd equals the claude cwd — **fixed**
- `p1-r10` (plan, phase 1) — HERDR_PANE_ID was not recorded and the tab list shape was never captured — **fixed**
- `p1-r11` (plan, phase 1) — install.sh passed --with-executables-from unconditionally, failing older uv — **fixed**
- `p2-r1` (plan, phase 2) — the owed restart lived only in memory while the post_merge event was persisted, so a pass aborted after post_merge lost it for good — **fixed**
- `p2-r2` (plan, phase 2) — the preflight-refusal test found the probe by a call-count heuristic and never asserted the refusal was reported — **fixed**
- `p2-r3` (plan, phase 2) — 'reported once per driver process' was untested across passes — **fixed**
- `p2-r4` (plan, phase 2) — no test that a recorded close-out, or one whose post_merge is not owed, does not restart — **fixed**
- `p3-r1` (plan, phase 3) — a cancelled batch with a leftover idle session was warned and flagged needs-you — **fixed**
- `p3-r2` (plan, phase 3) — 'has sat idle for N min' reported minutes since dispatch, not idle duration — **fixed**
- `p3-r3` (plan, phase 3) — the close-out unfinished test lived only in the driver; the board read only open archive PRs — **fixed**
- `p3-r4` (plan, phase 3) — threshold was >= while the spec said 'older than' — **fixed**
- `p3-r5` (plan, phase 3) — card printed raw ISO collected_at, wrapping mid-date — **fixed**
- `p3-r6` (plan, phase 3) — a runner load failure in the idle probe warned 'its sessions are not closed' — **fixed**
- `p3-r7` (plan, phase 3) — weak tests (raise case, non-status param, tautological failing-ci test, probe cost) — **fixed**

## Out-of-scope findings

- `p3-r8` (plan, phase 3) — the card front shows the batch session's pill, so an idle close-out card reads the wrong session's status — **out-of-scope**
- `p3-r9` (plan, phase 3) — the fr-triage skill says 'six lifecycle columns'; the board has seven — **out-of-scope**

## Pre-merge verification owed

None.

## Post-merge verification owed

- `herdr-restart-idle-live` — A restarted pane resumes the same Claude session id in the same pane and tab, with the same label, herdr agent name and --model, and a pane at the exit dialog is reported, never answered — restarting real Claude panes in place (same session id, tab, label, model) needs the operator's live herdr with real sessions; no pre-merge strategy may touch them.

## Tests

Full suite run at delivery — `driver-sessions-deliver-suite.log@d5fe3d3574ec`.

## Proportionality

```text
proportionality: merge-base 580430d4d78bc29d31e4deb08701993306196959

## Unreferenced new files

- .changes/feat-batch-driver-sessions.yaml
- packages/fr-herdr/src/fr_herdr/cli.py

## Out-of-plan touches

- packages/fr/src/fr/triage/components.py
- tests/integration/test_install_atomic.py
- tests/integration/test_scenarios.py

## Size

4406 lines changed (+4278 -128; fr artifacts excluded) against an estimate of 2350 (1.9×).

## Phases

3 agentic phases serve 9 of 9 requirements (R1, R2, R3, R4, R5, R6, R7, R8, R9).
```

## Cost

| step | turns | cost |
|---|---:|---:|
| brainstorm | 37 | — |
| spec-review | 43 | — |
| plan | 9 | — |
| plan-review | — | — |
| implement | 458 | — |
| journal-check | — | — |
| deliver | — | — |
| (outside run) | 18 | — |
| **total** | | — |

Sessions: 1 read, 0 unavailable.

_Dollars are `—`: no cost recorded yet. A harness may write a session's cost only when the session ends (Claude Code does). `fr run cost 2026-10-06-feat-batch-driver-sessions` reads it afterwards._
