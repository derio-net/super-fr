# deliver `tests=` gate accepts a backgrounded suite — design

**Date:** 2026-09-26
**Slug:** `2026-09-26-tests-window-background`
**Status:** design (fr-goal, autonomous; operator-decided batch `tests-window`)
**Repo:** `derio-net/super-fr` (single-repo change)
**Fixes:** gh#594 (root), gh#607 and gh#631 (duplicates)

## 1. Goal

`fr run resolve --step deliver --evidence tests=<log>` must accept a suite the
orchestrator ran the way super-fr's own brief tells it to — in the background
(`run_in_background`) — and a suite whose log path was held in a shell variable.
Today it refuses both, so a run that obeys the `long_commands` rule cannot
deliver.

### Non-goals

- Proving the command is a real test suite (the gate's documented limit,
  `orchestrator_wrote_since`'s docstring; `echo ok > log` still passes).
- OpenCode's `&` detach. Its rule (`long_commands.py`) detaches the suite with
  `(cmd; echo "exit=$?") > log 2>&1 &`; that command returns at once with exit 0,
  so `_opencode_wrote_since` has the SAME zero-length-window defect, and this
  change does NOT fix it: OpenCode has no completion event to end a window on,
  so it needs its own design (e.g. a witness-line contract). It stays refused and
  is filed as a follow-up. The `$VAR` fix lives in the shared `_writes`, so it
  does apply there.
- Resolving a variable set in an EARLIER tool call, or inherited from the
  environment (`$TMPDIR` as a target root is handled, §3.B; a bare unresolvable
  variable fails closed).

## 2. Background — verified against the code

`_verify_tests_log` (`run_cmd.py`) requires, where the transcript is readable,
that the log's mtime fall inside a `(tool_use, tool_result)` window of a
main-thread `Bash` command that wrote it (`orchestrator_wrote_since`,
`run/telemetry.py`). Two contradictions with the rest of the product:

1. **Background.** `harness/long_commands.py` tells Claude Code readers to
   `run_in_background` any suite over ~120 s. A backgrounded `Bash` returns its
   `tool_result` at once (`Command running in background with ID: <id>. Output is
   being written to: …`), long before the log is finished, so the log's mtime
   lands after the window and the gate refuses. Real transcript shape, captured
   from a Claude Code session (ids and paths redacted to shape):
   - tool_result record: `type: user`, block `tool_result`,
     `tool_use_id: <T>`, text starting `Command running in background with ID:`.
   - later, a `type: user` record with `origin.kind: task-notification` and
     `message.content` a string
     `<task-notification>…<tool-use-id><T></tool-use-id>…<status>completed</status>
     <summary>Background command "…" completed (exit code 0)</summary>…`;
     its `timestamp` is when the command finished.
2. **Variable target.** `_WRITE_TARGET` is syntactic over the literal command
   text; `L=$TMPDIR/full-suite.log; pytest > "$L" 2>&1` captures the target
   `$L`, which matches no path.

## 3. Design

### A. A backgrounded write's window ends at its task-notification

In `orchestrator_wrote_since`, a writing `Bash` call whose immediate
`tool_result` is the background acknowledgement (text begins
`Command running in background`) has no window yet. Its window is
`(tool_use timestamp, timestamp of the task-notification naming that tool_use
id)`, and only when the notification says it completed successfully:
`<status>completed</status>` and a summary that does not report a non-zero exit
code. Failed, killed, or never-notified (still running) → no window (fails
closed; the existing "no command of YOURS wrote it" refusal fires, and its text
gains a hint that a backgrounded suite counts once its notification arrived).
Notifications are matched by `tool-use-id` alone — never by task id or text
position — parsed out of the notification's `<tool-use-id>` tag (new code) and
looked up in the same `issued` map the foreground path fills. Both content
shapes are handled, for the acknowledgement's `tool_result.content` and for the
notification's `message.content`: a plain string, or a list of `text` blocks.

The acknowledgement is not `is_error`, so today it already yields a
zero-length window; that window is replaced, not added to.

### B. `$VAR` and `${VAR}` targets

`_WRITE_TARGET`'s path class admits `$`/`{`/`}` (it already does). `_writes`
resolves a variable target against assignments in the SAME command string
(`NAME=value`, optionally `export`, value bare or quoted, up to the next `;`,
`&&`, `||`, newline). Substitution repeats until stable (bounded). Any
variable still unresolved is then dropped when it LEADS the path
(`$TMPDIR/full-suite.log` → `full-suite.log`, matched by trailing segments like
every other relative target — the environment root is unknowable from the
transcript, exactly as the cwd is), and fails closed when it appears anywhere
else, is the whole target (`> $L` with no assignment in the command), or is a
command substitution (`> $(mktemp)`). An assignment must precede the redirect.
Residual weakness, stated as part of the gate's existing limit: a dropped
leading `$TMPDIR` makes `$TMPDIR/x.log` match any log ending in `x.log`.

### C. Docs

`long_commands.py`'s Claude Code line gains nothing to fix — its instruction is
now honoured. fr-goal §8's deliver sentence stays true. No skill copy changes,
so no mirror regeneration; a change fragment (patch) is still required for
`packages/*/src/**`.

## 4. Decisions

| id | decision | why |
|---|---|---|
| d1 | End the window at the task-notification keyed by `tool_use` id (#607's direction) | it is the only transcript event that says the backgrounded command finished, and it carries the id the write is already keyed on |
| d2 | Require `completed` and no non-zero exit for a background window | mirrors the foreground `is_error` rule: a failed run met no obligation |
| d3 | Resolve variables only within one command; drop a leading unresolvable variable | closed-world and syntactic like `_writes` today; cross-call state cannot be trusted |
| d4 | No new evidence key, no schema change | the gate's inputs are unchanged, only its recognition widens — not an artifact shape change |

## 5. Test Plan

Business-level: a run that follows the brief's own long-command rule can deliver.

1. **Background suite accepted (red→green, the reproduction).** A transcript
   with a backgrounded writing `Bash` (immediate acknowledgement, later
   task-notification `completed`) yields a window ending at the notification;
   a log whose mtime is inside it passes `_verify_tests_log`.
2. **Background refusals.** No notification yet, `failed` status / exit code ≠ 0,
   a notification for a different tool_use id, and a non-writing backgrounded
   command each yield no window.
3. **Variable targets (red→green).** `L=/x/t.log; pytest > $L`, `> "${L}"`,
   `export L=…`, chained reassignment, and `L=$TMPDIR/t.log` all match; a
   variable assigned nowhere in the command, mid-path, assigned only AFTER the
   redirect, or a `$(mktemp)` substitution does not; `> "$L" 2>&1` matches.
   The fixtures mirror the captured (redacted) records in §2, in both content
   shapes (string and text-block list).
4. **Non-regression.** Every existing `test_run_telemetry.py` window case and
   `test_run_tests_log_opencode.py` stays green.
5. Post-merge: none (nothing deploys); the change's own `deliver` is the live
   proof.

## 6. Acceptance rows

- `deliver-tests-log-background` — deliver's `tests=<log>` gate accepts a suite
  the orchestrator ran in the background, once its task-notification reports
  success (unit → `tests/unit/test_run_telemetry.py`).
- `deliver-tests-log-shell-variable` — the gate accepts a log whose path the
  writing command held in a shell variable (same file).

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-26-tests-window-background | `derio-net/super-fr` | `2026-09-26-tests-window-background` | — |
