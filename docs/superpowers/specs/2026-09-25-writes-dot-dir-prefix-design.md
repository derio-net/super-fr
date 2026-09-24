# deliver `tests=` gate: match a log under a dot-directory

- **Date:** 2026-09-25
- **Status:** designed
- **Origin:** gh#606 (found delivering #604, journal finding dl-f1)
- **Goal:** `fr run resolve … --step deliver --evidence tests=<log>` accepts a
  log that the orchestrator's own `Bash` command wrote, when the log's
  relative path starts with a dot-directory such as `.fr-deliver/tests.log`.

## 1. Problem

`deliver` checks that the orchestrator wrote the `tests=` log itself
(`fr.commands.run_cmd`, the `tests` evidence check, which calls
`fr.run.telemetry.orchestrator_wrote_since`). That function asks
`_writes(command, log)` (`packages/fr/src/fr/run/telemetry.py:888`) whether a
main-thread `Bash` command's `>`, `>>` or `tee` target names the log. `log` is
the resolved absolute path. A relative target is suffix-matched against it:

```python
elif str(log).endswith("/" + target.lstrip("./")) or log.name == target:
```

`str.lstrip("./")` removes a **set of characters**, not a prefix, so
`.fr-deliver/tests.log` becomes `fr-deliver/tests.log`. That can never be a
suffix of `…/.fr-deliver/tests.log`, so the gate refuses with "no command of
YOURS wrote it" even though the orchestrator did write the log.

The same stripping is also accidentally lenient. `../x.log` becomes `x.log`,
which matches any log whose name is `x.log`.

## 2. Design (operator decision: segment-wise strip)

Compare **path segments**, not strings:

1. An absolute target matches only when it equals `log`. This is unchanged.
2. A relative target is parsed as `PurePosixPath(target).parts`. That already
   drops `.` segments and repeated slashes. Leading `..` segments are then
   removed. The command's cwd is not in the transcript, so a parent hop cannot
   be resolved. Keeping the rest of the path is the existing leniency, stated
   deliberately rather than kept by accident.
3. The target matches when the remaining segments, which must not be empty,
   are the trailing segments of `log.parts`.

Consequences:

- `.fr-deliver/tests.log`, `./.fr-deliver/tests.log` and `tests.log` all match
  `/repo/.fr-deliver/tests.log`.
- `x.log`, `./x.log` and `../x.log` still match `…/x.log`, as they do today.
- `fr-deliver/tests.log` does not match `…/.fr-deliver/tests.log`, and
  `foo/tests.log` does not match `…/xfoo/tests.log`. The string `endswith`
  needed its `"/"` guard to get this right; segment comparison gets it
  without one.
- A `..` in the middle of the path (`a/../b.log`) is not collapsed, so it does
  not match. This case is rare and fails closed.

Out of scope: an absolute target reached through a symlink, such as `/tmp/…`
against a `resolve()`d `/private/tmp/…` on macOS. This change does not cause
it. Also out of scope is gh#607 (a backgrounded suite cannot satisfy the gate).

## 3. Test Plan

1. Unit (`tests/unit/test_run_telemetry.py`): a captured `Bash` command
   writing `.fr-deliver/tests.log` yields its run window for the resolved
   `…/.fr-deliver/tests.log`. This test is red before the fix.
2. Unit: the segment rules in §2, both the matches and the non-matches,
   pinned directly on `_writes`.
3. Live, before merge: this change's own `deliver` names
   `--evidence tests=.fr-deliver/tests.log`, written by foreground suite
   chunks, and is resolved through the worktree's `uv run fr`. The run
   cursor records it. There is no post-merge step (operator decision).
