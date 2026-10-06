# Driver sessions — idle sessions restart on new plugins; stuck sessions are reported

Batch `driver-sessions`: super-fr#964, super-fr#878, super-fr#1029, delivered as one PR.

## Background

The wave driver (`fr triage batch drive`, `packages/fr/src/fr/commands/triage_batch_cmd.py`)
runs the repo's `post_merge` after each merged batch (`_Driver._close_out`); super-fr's is
`./scripts/install.sh`, so the host gets the merged fr, hooks and skills. The driver re-execs
itself on the newly installed `fr` (gh#998, `restart_to`). Every **other** Claude session keeps
the plugins it loaded at start-up. During a long drive that means ~30 herdr tabs on stale
super-fr until the operator restarts each one by hand (#964). A one-off script restarted 28 of
35 panes in place on 2026-09-26; #964 records the procedure and the failure modes it met.

The herdr runner (`packages/fr-herdr/src/fr_herdr/runner.py`) refuses its preflight unless
`HERDR_ENV=1`, so the driver can only run inside a herdr session (#878). Every item the driver
dispatches carries a wave `group` (`batch_drive.wave_group`), so the `HERDR_WORKSPACE_ID` half
of that preflight never applies to drive items. herdr's CLI does answer from outside a session
(it falls back to the default socket). But herdr's own agent guidance is never to drive the
focused session from outside it, and the operator chose to keep the refusal and document it.

#1028 made the runner confirm that a brief was taken up. #956's second ask is still open
(#1029): a batch or close-out session that has sat idle with nothing to show for it is never
reported. Today the driver reports a close-out only when **no tab holds it**
(`_stale_closeout`, gh#1025). A tab that is alive but idle, with no PR, waits forever.

## Requirements

R1. `fr-herdr restart-idle` is a console script shipped by the `fr-herdr` package. It considers every pane that `herdr agent list` reports with `agent: claude`. It prints one line per pane: `ok`, `skip <reason>` or `fail <reason>`, plus the pane id and its tab label. A summary line follows. It is a dry run, printing what it would do, unless `--yes` is given. `--exclude <pane>` can be repeated.
R2. A pane is restarted only when all of these hold. Its status is `idle` or `done`. It has a recorded session id, and that session has a transcript on disk. Its input box holds no unsent draft. Its screen shows no background shells or agents. It is not the pane running the command, and it is not excluded. Any other pane is skipped with the reason, and no key is ever sent to it.
R3. A restart happens in place. It sends `/exit`, then waits at most 30 s for `claude` to leave the pane's foreground. If Claude's exit dialog appears (an unsent feedback draft), the pane is reported `fail exit-dialog`, and the restart neither answers the dialog nor waits out the timeout. Otherwise it relaunches `claude --resume <session-id>` in the same pane, keeping `--model` and the permission flags of the original argv. It then waits at most 90 s for the pane to run `claude` again on the same session id. The tab, its label, the pane and the herdr agent name are unchanged.
R4. One failed pane never stops the run. The command exits 0 when no pane failed, 1 when any pane failed, and 2 on a refusal.
R5. `fr-herdr restart-idle` runs only inside a herdr session (`HERDR_ENV=1`, `herdr` on PATH), the same rule as the runner's preflight. Outside, it refuses with exit 2. `scripts/install.sh` and `.fr/candidate-install` put `fr-herdr` on PATH beside `fr`.
R6. A repo opts in through `.fr/triage.yaml`'s `post_merge_restart: idle`. The default is `none`. After that repo's `post_merge` succeeds, the wave driver asks the close-out's runner to restart idle sessions, then starts the close-out. It prints one summary line, plus one line per failed pane. Neither a restart failure nor a runner that cannot restart holds the close-out or ends the drive. A runner that cannot restart is reported once per drive. The driver's own pane is never restarted. super-fr's own `.fr/triage.yaml` turns the option on.
R7. A batch session is reported when all of these hold: the runner reports it `idle` or `done`, its last dispatch is older than the repo's `idle_session_minutes`, and the batch has no PR. A close-out session is reported on the same terms when its close-out was recorded longer ago than that threshold and no archive PR is attributed to it. `idle_session_minutes` is set in `.fr/triage.yaml`; the default is 60. The driver reports each such session once per dispatch or close-out, names the item and how long it has sat, and prints the command that focuses it (`fr triage batch focus <batch> [--closeout]`). Reporting never ends the drive.
R8. The board (`fr triage board`) marks a card *needs you* for the session R7 would report, and the card says why.
R9. Outside herdr, the herdr runner still refuses. Its refusal says to run `fr triage batch drive` (and `dispatch`) from a herdr pane. The fr-triage skill states that constraint, and also the `post_merge_restart` and `idle_session_minutes` settings.

## Design

### A. `fr_herdr.restart` — the restart engine (R1–R5)

A new module in `fr-herdr`. It reaches herdr only through `runner._run_herdr`, the existing
seam that tests replace. Pure decisions are kept apart from the calls:

- `classify(agent, screen, argv, transcript_exists, self_pane, excluded) -> Skip | Plan` is
  pure, over one `agent list` entry, the pane's `pane read --source recent` text and the
  `pane process-info` argv. It checks R2 in a fixed order, and the first failing check names
  the reason: `not-claude` (filtered before listing), `status <s>`, `no-session`,
  `no-transcript`, `draft`, `background-work`, `self`, `excluded`.
  - Draft: the last line beginning `❯` carries text after the prompt.
  - Background work: the status line names running shells or agents. The patterns are
    taken from a **live capture**, never composed (fixtures under
    `tests/fixtures/herdr/restart/`, each with a README saying when and how it was
    captured).
- `kept_args(argv) -> list[str]` keeps `--model <m>`, `--permission-mode <m>` and
  `--dangerously-skip-permissions` from the original `claude` argv, and drops the rest
  (`--resume` and `--continue` in particular, which R3 replaces).
- The transcript lookup is a glob, `<CLAUDE_CONFIG_DIR or ~/.claude>/projects/*/<id>.jsonl`.
- `restart(pane, plan) -> Outcome` runs the sequence:
  1. `pane send-text /exit` and `enter`.
  2. Poll `pane process-info` and `pane read` until no `claude` runs in the foreground
     (30 s). If the screen shows the exit dialog ("unsent feedback draft"), stop at once
     with `fail exit-dialog`.
  3. Relaunch in the same pane:
     - `agent start <name> --kind claude --pane <p> -- <kept> --resume <id>` when the pane
       had a herdr agent name. This keeps `HerdrRunner.message` working, because it
       addresses agents by name.
     - `pane send-text "claude <kept> --resume <id>"` and `enter` when it had none.
  4. Poll `agent list` until the pane reports `agent: claude` with the same
     `agent_session` value (90 s).

  Each step's `HerdrError` becomes `fail <step>: <herdr's words>`.
- `restart_idle(*, yes, exclude) -> RestartReport` lists, classifies and restarts serially,
  so one pane at a time leaves the foreground. It catches each pane's failure and goes on.
  The caller's pane is `HERDR_PANE_ID`.

The console script is `fr_herdr.cli:main` (`[project.scripts] fr-herdr`). It is argparse
with one subcommand, `restart-idle`, and no Typer dependency: fr-herdr depends only on `fr`
and `fr-dispatch`. It prints the lines and exits per R4. Its refusal uses the same
`preflight` predicate as the runner (R5).

Install (R5): `scripts/install.sh` adds `--with-executables-from fr-herdr` to the
`uv tool install` of `fr`. `uv tool install --with` exposes only the main package's
scripts, so without this flag the console script would reach nobody's PATH.
`.fr/candidate-install` does the same, so a walk can run it.
`tests/unit/test_install_sh.py`-style drift guards pin both.

### B. `SessionRestarter` — the driver's reach (R6)

`fr_dispatch.protocols` gets a fifth optional protocol, beside `SessionCloser`,
`SessionInspector` and `SessionMessenger`. It is runtime-checkable and never part of
`Runner`:

```python
class SessionRestarter(Protocol):
    def restart_idle(self, *, exclude: Sequence[str] = ()) -> RestartSummary: ...
```

`RestartSummary` is a frozen dataclass in `fr_dispatch.protocols`: `ok`, `skipped`, and
`failed: tuple[tuple[str, str], ...]` holding (pane, reason) pairs. `HerdrRunner.restart_idle`
calls `fr_herdr.restart.restart_idle(yes=True, ...)`. fr never imports fr_herdr; it sees only
the protocol.

`_Driver._close_out` changes as follows. After `post_merge` succeeds and its event is
written, it checks the repo's config. When `facts.config_for(repo).post_merge_restart ==
"idle"`, it loads the close-out's runner (`self._try_runner`) and runs its `preflight`.
- A runner that is a `SessionRestarter` is called. The driver prints `restart: N ok, M
  skipped, K failed` and one `restart failed <pane>: <reason>` per failure.
- A runner that is not one is reported once: `runner <name> cannot restart sessions`.
- Any exception is caught and reported. The close-out then starts as before.

The restart runs before the close-out, so the close-out session (fresh anyway) never races
it. The driver's own pane is excluded by the engine (`HERDR_PANE_ID`), and a driver run from
a Claude pane's shell tool reads `working` anyway. The restart is synchronous: 10–20 s per
pane, measured. It is opt-in, so the repo accepts that pause.

### C. Config (R6, R7)

`TriageConfig` gains two fields:
- `post_merge_restart: Literal["none", "idle"] = "none"`
- `idle_session_minutes: int = Field(default=60, ge=1)`

`facts.json` carries the config through a full `model_dump`, so `FACTS_SCHEMA` moves 5 → 6
and `FACTS_READS` gains 6. A schema-5 reader then says "re-run collect" instead of "invalid
facts", the same reasoning as the `mirrors` bump. `facts.json` is a cache, not a registered
artifact, so no artifact migration is owed. super-fr's `.fr/triage.yaml` gets
`post_merge_restart: idle`.

### D. Idle sessions — one pure rule, two readers (R7, R8)

`batch_drive.idle_session(batch, *, status, has_pr, closeout, archive_attributed, now,
threshold) -> IdleSession | None` is pure, and the only definition. `IdleSession` holds the
item id, `since` and `minutes`.
- For the batch item: status `idle`/`done`, last dispatch older than the threshold, no
  batch PR.
- For the close-out item: status `idle`/`done`, close-out event older than the threshold,
  no attributed archive PR.

It is stateless, so it survives the driver's exec-restart (gh#998), and the board computes
it from the same inputs.

`fr.run.liveness.is_idle` is deliberately **not** reused, though #1029 suggested it. It
decides whether a *run cursor* is advanceable with nobody working. The driver holds no cursor
for a batch (the run lives on the batch branch, in the batch's workspace); it holds a session
status and forge facts. A second reading of the cursor from the driver would be a second
definition of the same thing, the defect #1029 meant to avoid.

**Driver.** `Snapshot` gains `idle: tuple[IdleSession, ...]`. Each pass, `_snapshot` probes
session statuses (one `session_statuses` per runner, soft: a runner that cannot load or
refuses is skipped, as `_sessions` does) only for candidates. A candidate is a selected
batch whose last dispatch is older than the threshold and that has no PR, or a recorded,
unfinished close-out older than the threshold. `drive_pass` emits `Action("warn", batch,
"<item> has sat <status> for <N> min with no PR|archive PR; focus it: `<focus command>`")`
with `head=f"idle-session\0{item}\0{event.at}"`. The `warned` set keeps it to once per
dispatch or close-out in a process, the same as every other warn. A warn never changes the
summary, so it never keeps a drive alive or ends one.

**Board.** `kanban._card` gets `now` and the repo's threshold passed in. The board keeps "no
clock", because the command supplies it. A card is `needs_you` when `idle_session` returns a
value for its batch or close-out item, and its detail line says `idle <N> min, no PR` (or
`no archive PR`). `views.needs_you` reads facts alone, with no session status, and is
unchanged.

### E. Outside herdr (R9)

`HerdrRunner.preflight`'s refusal text becomes: "not inside a herdr session (HERDR_ENV=1 is
unset): run `fr triage batch drive` / `dispatch` from a herdr pane — herdr is never driven
from outside it". The fr-triage skill (canonical `plugins/super-fr/skills/fr-triage/SKILL.md`,
mirrors regenerated by both sync scripts) gains a short "Runner constraints and session
upkeep" paragraph covering the herdr-only rule, `post_merge_restart` and
`idle_session_minutes`.

### Not in scope

- Driving herdr from outside a session (operator decision: document only).
- Restarting harnesses other than Claude Code.
- Restarting sessions on a schedule other than `post_merge`.
- Persisting "already reported" across driver restarts.

## Verification

The run is verified by its own `candidate` walk at `deliver`. The scenarios drive the
installed `fr-herdr` and `fr` against a fake `herdr` on PATH that replays live-captured JSON.
They never reach a real herdr or a forge.

strategy: candidate
- drive-post-merge-restart: none — the driver's post_merge path needs a forge and a merged batch, which no fresh fixture repo has; unit tests drive `_Driver._close_out` with a fake restarting runner in CI.
- drive-idle-session-report: none — a pass needs collected forge facts and a live runner; `drive_pass`/`idle_session` unit tests and a command-level test with a fake inspecting runner verify it in CI.
- board-idle-session: none — the board reads live session statuses from a runner; `kanban` unit tests plus the browser check of the rendered card verify it.
- herdr-outside-refusal: none — the refusal text is unit-tested on `HerdrRunner.preflight`, and the skill paragraph is pinned by a test over the canonical skill.
- herdr-restart-idle-live: live — restarting real Claude panes in place (same session id, tab, label, model) needs the operator's live herdr with real sessions; no pre-merge strategy may touch them.

## Test Plan

- post-merge — operator-driven: inside herdr, run `fr-herdr restart-idle` (dry run), check
  the per-pane lines against `herdr agent list`. Then run `fr-herdr restart-idle --yes` and
  check that each `ok` pane resumed the same session id, in the same tab, with the same label
  and `--model`, and that a pane with a draft was skipped and untouched
  (row `herdr-restart-idle-live`).
