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
R2. A pane is restarted only when all of these hold:
  - its status is `idle` or `done`;
  - it has a recorded session id, and that session's transcript exists under the project directory of the pane's own working directory;
  - the screen shows Claude's input box (a pane with no box, such as an overlay, is `no-prompt`), and the box holds no unsent draft on any of its lines (Claude's faint prompt suggestion is not a draft);
  - it shows no background work: running shells or monitors on the status line, or a subagent in the agent panel (`← 1 agent` is on every idle status line and is not evidence; only a count above one is);
  - a foreground `claude` process is found in the pane (else `no-process`);
  - its launch argv carries no flag outside the kept set;
  - it is not the pane running the command, and it is not excluded.

  Any other pane is skipped with the reason, and no key is ever sent to it. Each pane is judged at its own turn on a fresh read of its status, because a pane can turn `working` while earlier panes are being restarted; a pane that has left `agent list` by then is skipped `gone`. A pane whose own state cannot be read (a herdr error, an unreadable transcript path) is skipped `unreadable: <why>`; no failure of one pane, of whatever kind, stops the run (R4).
R3. A restart happens in place. It sends `/exit`, then waits at most 30 s for `claude` to leave the pane's foreground. If Claude's exit dialog appears (an unsent feedback draft), the pane is reported `fail exit-dialog`, and the restart neither answers the dialog nor waits out the timeout. Otherwise it relaunches `claude <kept flags> --resume <session-id>` in the same pane and waits at most 90 s for the pane to run `claude` again on the same session id. The tab, its label, the pane, the herdr agent name and every kept launch flag are unchanged. A pane that fails after `/exit` was sent is reported with the exact command that resumes it by hand.
R4. One failed pane never stops the run. The command exits 0 when no pane failed, 1 when any pane failed, and 2 on a refusal.
R5. `fr-herdr restart-idle` runs only inside a herdr session (`HERDR_ENV=1`, `herdr` on PATH), the same rule as the runner's preflight. Outside, it refuses with exit 2. After `scripts/install.sh`, `fr-herdr` is on PATH beside `fr`, through the same managed, atomically swapped link. After `.fr/candidate-install`, it is in `<prefix>/bin`.
R6. A repo opts in through `.fr/triage.yaml`'s `post_merge_restart: idle`. The default is `none`. In a drive pass where that repo's `post_merge` succeeded at least once, the wave driver asks the runner of the close-out it started to restart idle sessions, once, at the end of the pass. It prints one summary line, plus one line per failed pane. Neither a restart failure nor a runner that cannot restart holds a close-out or ends the drive. A runner that cannot restart is reported once per driver process. The driver's own pane is never restarted. super-fr's own `.fr/triage.yaml` turns the option on.
R7. A batch session is reported when all of these hold: the runner reports it `idle` or `done`, its last dispatch is older than the repo's `idle_session_minutes`, and the batch has no PR. A close-out session is reported on the same terms when its close-out was recorded longer ago than that threshold and no archive PR is attributed to it. `idle_session_minutes` is set in `.fr/triage.yaml`; the default is 60. The driver reports each such session once per driver process. The report names the item and how long it has sat, and gives a paste-ready command that focuses it (`fr triage batch focus <batch> [--closeout]` plus the drive's own scope options). Reporting never ends the drive.
R8. The board (`fr triage board`) marks a card *needs you* for the session R7 would report, judged at render time, and the card says why. The board's "Needs you now" list never shows an idle session as failing CI.
R9. Outside herdr, the herdr runner still refuses. Its refusal says to run `fr triage batch drive` (and `dispatch`) from a herdr pane. The fr-triage skill states that constraint, and also the `post_merge_restart` and `idle_session_minutes` settings and `fr-herdr restart-idle`.

## Design

### A. `fr_herdr.restart` — the restart engine (R1–R5)

A new module in `fr-herdr`. It reaches herdr only through `runner._run_herdr`, the existing
seam that tests replace. `runner.py` imports it **at module top level**, never lazily.
`post_merge` rebuilds the tool env in place (`uv tool install --force`), and a lazy import
would then load the new `restart.py` beside the old `runner.py` (sr-13).

The herdr surfaces it parses are recorded from live herdr 0.9.1, never composed. Fixtures
go under `tests/fixtures/herdr/restart/`, each with a README saying when and how it was
captured, with home paths redacted. They cover:
- `agent list`, which carries per pane `agent`, `agent_status`, `agent_session.value`,
  `name` (the key is absent for an unnamed pane, never null), `pane_id` and `tab_id`;
- `tab list`, whose `tabs[]` carry `tab_id` and `label` (the pane line's tab label);
- `pane process-info`, where `foreground_processes[].argv` is the `claude` launch argv;
- `pane read --source visible --ansi`, which prints raw terminal text (not a JSON
  envelope, so `_run_herdr` returns it as `{"raw": <text>}`; a non-object JSON answer is
  wrapped the same way, so every answer is a dict);
- the `HERDR_PANE_ID` environment variable, which is set in every herdr pane.

These were seen live while this spec was written. The exit dialog's text ("You have 1
unsent feedback draft · Enter to review & send · Esc to discard and exit") is quoted from
#964's live report, and its fixture README says so.

Pure decisions are kept apart from the calls:

- `classify(agent, screen, argv, cwd, transcript_exists, self_pane, excluded) -> Skip |
  Plan` is pure. It checks R2 in a fixed order, and the first failing check names the
  reason: `status <s>`, `no-session`, `no-process`, `no-transcript`, `unknown-flag <flag>`,
  `no-prompt`, `draft`, `background-work`, `self`, `excluded`. (Non-Claude panes are filtered out before
  classification and not listed.)
  - **Input box.** The live prompt is the last line that begins with `❯` (after any SGR
    codes) and sits directly under a horizontal rule: an earlier `❯` is the echo of a past
    message. The box runs from that line down to the next rule. No live prompt is `skip
    no-prompt`: with nothing to judge the draft by, the pane is never restarted.
  - **Draft.** Any text in the box that is not rendered faint (SGR 2): on the prompt line
    after the prompt, or on any continuation line (a draft can begin on a later line while
    the first is empty). Claude Code draws its prompt suggestion faint, right after the
    prompt: captured live, it is `❯\xa0\x1b[0m\x1b[2m<text>`. A plain-text read cannot tell a
    suggestion from typed input, which would wrongly skip nearly every pane (sr-2). The
    fixtures hold a suggestion, a real draft, a multi-line draft and an empty prompt.
  - **Background work.** Below the prompt: the status line names running shells or monitors
    (`N shell(s)`, `N monitor(s)`), the agent panel lists a subagent (a `◯` row), or the
    status line says `← N agents` with N above one. `← 1 agent` is on the status line of
    every idle Claude, fresh sessions included, so it is NOT evidence. A lone background
    subagent was captured live: herdr reports it `working` (so the status check already
    skips it) and the screen shows the `◯` panel row and `← 1 agent`. herdr reports
    `done`, not `idle`, for a settled pane with background shells, hence both statuses
    qualify.
- `kept_args(argv) -> list[str] | UnknownFlag`. It keeps these flags with their values:
  `--model`, `--permission-mode`, `--dangerously-skip-permissions`, `--add-dir`,
  `--settings`, `--mcp-config`, `--plugin-dir`, `--agent`. It drops `--resume`/`-r`,
  `--continue`/`-c` and `--session-id`, which R3 replaces. Any other flag, or any
  positional argument, makes the pane `skip unknown-flag <flag>`. A resumed session never
  silently loses a launch flag (sr-14).
- **Transcript.** The file is `<CLAUDE_CONFIG_DIR or ~/.claude>/projects/<slug>/<id>.jsonl`,
  where `<slug>` is the pane's foreground `claude` process cwd with every character outside
  `[A-Za-z0-9]` replaced by `-`. That is the directory `claude --resume` searches when it
  is relaunched from. It is never a glob across every project (sr-6). The pane's shell
  can be in another directory than the `claude` process was (claude `cd`s, or was started
  from elsewhere), so the restart reads the shell's cwd from `pane process-info` once
  claude has left; when it differs, the relaunch is preceded by `cd <claude cwd>`, and the
  by-hand `resume:` line carries the same `cd <cwd> && ` prefix (unless the shell is
  known to be there already).
- `restart(pane, plan) -> Outcome` runs the sequence:
  1. `pane send-text /exit` and `enter`.
  2. Poll `pane process-info` and `pane read` until no `claude` runs in the foreground
     (30 s). That `process-info` also gives the shell's cwd (the foreground process whose
     pid is `shell_pid`). If the exit dialog shows, stop at once with `fail exit-dialog`. If the 30 s
     run out, stop with `fail exit-timeout`. No further key is sent in either case.
  3. Relaunch in the same pane:
     - `agent start <name> --kind claude --pane <p> -- <kept> --resume <id>` when the pane
       had a herdr agent name. This keeps `HerdrRunner.message` working, because it
       addresses agents by name.
     - `pane send-text "claude <kept> --resume <id>"` and `enter` when it had none.
     - herdr accepted the pane's own name again right after `/exit` when probed live
       (the registration is released with the agent), and refuses only when ANOTHER pane
       holds the name (`agent_name_taken`); that refusal is the trigger for the send-text
       path. Both are pinned by captured fixtures.
     - The named start is retried while herdr answers `agent_pane_busy` (the pane's shell
       is not at its prompt yet), exactly as the runner's own starts are: one retry
       helper in `fr_herdr._herdr`, used by both.
  4. Poll until the pane runs a `claude` in the foreground (`pane process-info`) AND
     `agent list` reports it with the same `agent_session` value (90 s). The process check
     is what keeps a stale pre-exit `agent list` entry from passing as the relaunch.

  Each step's failure, of whatever type (a `HerdrError`, or an `OSError` from the
  filesystem), becomes `fail <step>: <the message>`; the `resume:` line survives it. Every failure after step 1
  adds `resume: claude <kept> --resume <id>`, the command the operator runs to resume the pane.
- `restart_idle(*, yes, exclude) -> RestartReport` lists, classifies and restarts serially,
  so one pane at a time leaves the foreground. It catches each pane's failure and goes on.
  The caller's pane is `HERDR_PANE_ID`, which herdr sets in every pane's environment
  (captured: `w36:p4`-shaped, the pane id as `agent list` reports it).

The console script is `fr_herdr.cli:main` (`[project.scripts] fr-herdr`). It is argparse
with one subcommand, `restart-idle`, and no Typer dependency: fr-herdr depends only on `fr`
and `fr-dispatch`. It prints the lines and exits per R4. Its refusal uses the same predicate
as the runner's preflight (R5).

**Install (R5, sr-1).** `uv tool install --with` exposes only the main package's scripts, so
both installers add `--with-executables-from fr-herdr` when `uv tool install --help` lists the flag (an older uv refuses the whole install over an unknown one); without it, the script the `--with` package leaves in the tool env's bin is linked all the same.
- `scripts/install.sh` installs into the private `$HOME/.local/share/fr/uv-bin` and links
  only `fr` onto PATH, so `--with-executables-from` alone would leave `fr-herdr` off PATH.
  It therefore manages a second link, `fr-herdr`, beside `fr`'s. That link is created
  only when `fr-herdr` was installed, and it is swapped the same way through the staged
  rebuild (gh#938): staged copy first, then uv's env.
- `.fr/candidate-install` already installs into `<prefix>/bin`, which is on the walk's PATH.
- Drift guards in `tests/integration/test_install_sh.py` pin the flag and the second link.
  `tests/integration/test_runner_package_lists.py` is checked for a literal that must
  follow.

### B. `SessionRestarter` — the driver's reach (R6)

`fr_dispatch.protocols` gets a fifth optional protocol, beside `SessionCloser`,
`SessionInspector`, `SessionFocuser` and `SessionMessenger`. It is runtime-checkable and
never part of `Runner`:

```python
class SessionRestarter(Protocol):
    def restart_idle(self, *, exclude: Sequence[str] = ()) -> RestartSummary: ...
```

`RestartSummary` is a frozen dataclass in `fr_dispatch.protocols`: `ok`, `skipped`, and
`failed: tuple[tuple[str, str], ...]` holding (pane, reason) pairs. `HerdrRunner.restart_idle`
calls `fr_herdr.restart.restart_idle(yes=True, ...)`. fr never imports fr_herdr; it sees only
the protocol.

**Once per pass, not per close-out (sr-7).** `post_merge` runs once per merged batch's
close-out (`_Driver._close_out`). A pass that closes out k batches would otherwise restart
every idle pane k times, each time at 10–20 s per pane (measured) and up to 120 s for a
failing pane. So `_close_out` only records, after a successful `post_merge` in a repo whose
`post_merge_restart` is `idle`, the runner name of the close-out it started; it makes no
restart call itself.

At the end of `run_pass`, before the exec-restart check, the driver restarts once per
recorded runner:
- It loads the runner with `self._try_runner` and runs `preflight` on the close-out probe
  item, `probe_item(repo, batch, closeout=True, prefix=...)`, the probe `_sessions` already
  builds (sr-13).
- A `SessionRestarter` is called. The driver prints `restart: N ok, M skipped, K failed`
  and one `restart failed <pane>: <reason>` per failure.
- A runner that is not a `SessionRestarter`, or that refuses, is reported once per driver
  process.
- Any exception is caught and reported.

The close-outs this pass started are fresh sessions and load the merged plugins on their
own. The restart is for every other session, so it runs after them. A failed restart never
makes `--once` exit non-zero, because it is upkeep, not the drive's work. The driver's own
pane is excluded by the engine (`HERDR_PANE_ID`), and a driver run from a Claude pane's
shell tool reads `working` anyway. The pause is bounded by panes × 120 s per pass with a
restart, and the option is opt-in.

### C. Config (R6, R7)

`TriageConfig` gains two fields:
- `post_merge_restart: Literal["none", "idle"] = "none"`
- `idle_session_minutes: int = Field(default=60, ge=1)`

`facts.json` carries the config through a full `model_dump`. So `FACTS_SCHEMA` moves 5 → 6,
`FACTS_READS` gains 6, `Facts.schema_`'s `Literal[3, 4, 5]` and its default move with them,
and the comment above `FACTS_SCHEMA` records why. A schema-5 reader then says "re-run
collect" instead of "invalid facts", the same reasoning as the `mirrors` bump. `facts.json`
is a cache, not a registered artifact, so no artifact migration is owed. super-fr's
`.fr/triage.yaml` gets `post_merge_restart: idle`.

### D. Idle sessions — one pure rule, two readers (R7, R8)

`batch_drive.idle_session(...) -> IdleSession | None` is pure, and the only definition.
Its inputs are the batch, `status`, `has_pr`, the close-out event, `archive_attributed`,
`now` and `threshold`. `IdleSession` holds the item id, the batch id, whether it is the
close-out, `since` and `minutes`.
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

**Driver.** `Snapshot` gains `idle: tuple[IdleSession, ...] = ()`. Each pass,
`_Driver.snapshot` probes session statuses only for candidates:
- a selected batch whose last dispatch is older than the threshold and that has no PR;
- a recorded, unfinished close-out older than the threshold.

The probe is one `session_statuses` per runner, and soft: a runner that cannot load or
refuses is skipped, as `_sessions` does. `drive_pass` emits `Action("warn", batch,
"<item> has sat <status> for <N> min with no PR|archive PR; focus it: <command>")` with
`head=f"idle-session\0{item}\0{event.at}"`. The command is `shlex.join(["fr", "triage",
"batch", "focus", batch, *(["--closeout"] if closeout else []), *self.scope_args])` (sr-11),
carried in from the driver the way `dedupe_command` is. The `warned` set keeps the warn to
once per driver process, the same as every other warn. A warn never changes the summary, so
it never keeps a drive alive or ends one.

`views.drive_snapshot`, which feeds the board's "Needs you now" list and the card hints, never
fills `Snapshot.idle`. `views.needs_you` turns every `warn` into a `failing-ci` need, so a
test pins that `drive_snapshot(...).idle == ()` (sr-10).

**Board.** `build_board` and `kanban._card` gain `now: datetime`. `_card` already reads
`facts.config_for(repo)`, so the threshold comes from there. `write_board` passes the
**wall clock**: session status is read live at render time, and the minutes must be real.
"No PR" comes from the collected facts. So a PR opened after the last collect reads as
"no PR" until the next collect, which the board's `--watch` loop already runs (`recollect`).
The card shows that window instead of hiding it: its line says `idle <N> min, no PR as of
<collected_at>` (sr-9). A card is `needs_you` when `idle_session` returns a value for its
batch or close-out item, and its detail line says why (`no PR` or `no archive PR`).

### E. Outside herdr (R9)

`HerdrRunner.preflight`'s refusal text becomes: "not inside a herdr session (HERDR_ENV=1 is
unset): run `fr triage batch drive` / `dispatch` from a herdr pane — herdr is never driven
from outside it". The fr-triage skill (canonical `plugins/super-fr/skills/fr-triage/SKILL.md`,
mirrors regenerated by both sync scripts) gains a short "Runner constraints and session
upkeep" paragraph covering the herdr-only rule, `post_merge_restart`,
`idle_session_minutes` and `fr-herdr restart-idle`.

### Not in scope

- Driving herdr from outside a session (operator decision: document only).
- Restarting harnesses other than Claude Code.
- Restarting sessions on a schedule other than `post_merge`.
- Persisting "already reported" across driver restarts: reports are once per driver process.

## Testing

Each requirement maps to the tests that pin it (all in CI):

- **R1, R2, R4.** `tests/unit/test_fr_herdr_restart.py`: `classify` over every live-captured
  fixture (suggestion vs draft, background work, `unknown-flag`, `self`, `excluded`,
  no transcript), `kept_args`, dry run vs `--yes`, and one failed pane not stopping the run.
- **R3.** The restart sequence against a fake `_run_herdr`: exit dialog, exit timeout,
  named start, the name-collision fallback, the resume timeout, and the resume-by-hand line.
- **R5.** The CLI's exit codes and its refusal outside herdr, plus the install drift
  guards in `tests/integration/test_install_sh.py`.
- **R6.** `_Driver` tests with a fake restarting runner: once per pass, and never holding a
  close-out or ending the drive.
- **R7.** `idle_session` and `drive_pass` unit tests; a command-level test with a fake
  inspecting runner; the `drive_snapshot` pin.
- **R8.** `kanban` card tests; the browser check of the rendered card.
- **R9.** The preflight text, and a test over the canonical fr-triage skill.
- **Config.** The `FACTS_SCHEMA` bump: a schema-6 file round-trips, and a schema-5 file
  still loads.

## Verification

The run is verified by its own `candidate` walk at `deliver`. The scenario drives the
installed `fr-herdr` against a fake `herdr` on PATH that replays the live-captured JSON. It
never reaches a real herdr or a forge.

strategy: candidate
- herdr-restart-idle: candidate — `tests/scenarios/herdr-restart-idle.sh` runs the installed `fr-herdr restart-idle` against a fake herdr: the dry-run lines and summary, skips without keys sent, exit codes, and the refusal outside herdr.
- drive-post-merge-restart: none — the driver's post_merge path needs a forge and a merged batch, which no fresh fixture repo has; unit tests drive `_Driver` with a fake restarting runner in CI.
- drive-idle-session-report: none — a pass needs collected forge facts and a live runner; `drive_pass`/`idle_session` unit tests and a command-level test with a fake inspecting runner verify it in CI.
- board-idle-session: none — the board reads live session statuses from a runner; `kanban` unit tests plus the browser check of the rendered card verify it.
- herdr-outside-refusal: none — the refusal text is unit-tested on `HerdrRunner.preflight`, and the skill paragraph is pinned by a test over the canonical skill.
- herdr-restart-idle-live: live — restarting real Claude panes in place (same session id, tab, label, model) needs the operator's live herdr with real sessions; no pre-merge strategy may touch them.

## Test Plan

Only what no pre-merge strategy can exercise. The CI tests are listed under `## Testing`.

- post-merge — operator-driven: inside herdr, run `fr-herdr restart-idle` (dry run), check
  the per-pane lines against `herdr agent list`. Then run `fr-herdr restart-idle --yes` and
  check that each `ok` pane resumed the same session id, in the same tab, with the same label
  and launch flags, and that a pane with a draft was skipped and untouched
  (row `herdr-restart-idle-live`).

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-10-06-driver-sessions | `derio-net/super-fr` | `2026-10-06-driver-sessions` | — |
