# fr small fixes — implementation plan

Spec: `docs/superpowers/specs/2026-10-11-fr-small-fixes-design.md` (R1–R7).

One agentic phase: four small, independent fixes, each a red → green → refactor
task, then a closing task for the release fragment, the acceptance rows and the
quality gate. One phase because every fix is a few lines and the whole diff
reviews comfortably in one pass (operator decision d5: light path).

- **Task 1 (#1102, R1–R2).** The GitHub tracker closes with `CLOSED`, and the test
  fake refuses any state the real clients refuse. That leniency is why the bug shipped.
- **Task 2 (#1057, R3).** Trim the OpenCode wrapper's `)]…` tail from the
  dead-binding reason. The regex stays, so a parenthesis inside the message survives.
- **Task 3 (#1055, R4–R6).** Invalid YAML becomes a `ModelsError` naming the file.
  `fr run start` warns after its save, and the other readers refuse with exit 2.
  None of them prints a traceback, and a broken config is never read as unbound.
- **Task 4 (#1066, R7).** Defensive, because the columns are moving (#1107 adds
  two, #1151 renames the skill paragraph's lead). The skill names the titles with
  no count, and the docstring names neither. A tripwire reads `COLUMN_TITLES` live
  and finds the paragraph by content.

No phase names a member issue as `tracking_issue`. Locally, run only the targeted
tests. CI on draft PR #1158 runs the full suite (`tests: ci`).
