# Journal: 2026-10-11-fr-small-fixes

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-12T15:09:26+00:00 input=true -->
### operator-brief · discovery · Batch fr-small-fixes dispatch brief (verbatim)

/fr-goal fr small fixes: tracker close state, models errors, skill column count

Batch `fr-small-fixes` of derio-net/super-fr: 4 issues, delivered as ONE pull request.

## super-fr#1102: tracker/github.py:114 passes state='closed' in lower case; both clients accept only OPEN/CLOSED
`packages/fr/src/fr/tracker/github.py:114` still `edit_issue_state(repo, number, state="closed")`; both clients accept only OPEN/CLOSED, so moving a tracker item to done raises.

## super-fr#1057: fr models check: dead-binding reason keeps trailing ')]))' from the wrapped provider error
`packages/fr/src/fr/bindings/probe.py:49` `_NOT_FOUND` still `[^"\\\n]*`, so the displayed reason keeps `)]))`. Cosmetic; verdict correct.

## super-fr#1055: corrupt models.yaml crashes fr run start after save
Corrupt `models.yaml` raises from `load_models` (`packages/fr/src/fr/models.py:56`) before any guard. Loud, pre-existing.

## super-fr#1066: the fr-triage skill says 'six lifecycle columns'; the board has seven
Skill and both mirrors (`.opencode/skills/fr-triage/SKILL.md:101`) still say six lifecycle columns; `kanban.py:62-72` `COLUMN_TITLES` has seven (Partial added by gh#985).

## Why these belong together
Four small independent fixes; #1102 makes every tracker close raise.

## Delivery rules
- Work on branch `feat/batch-fr-small-fixes`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#1102
  Closes derio-net/super-fr#1057
  Closes derio-net/super-fr#1055
  Closes derio-net/super-fr#1066
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

Coordinator rule (relayed mid-session): targeted tests only locally; any full or large suite through `bash ~/.cache/fr/coord/testslot.sh -- <cmd>`; prefer CI (`tests: ci`); never mark the PR ready, never merge.

<!-- fr:journal kind=decision scope=spec id=d1-models-error-scope created=2026-10-12T15:09:26+00:00 -->
### d1-models-error-scope · decision · #1055 reaches every models.yaml reader

Operator chose: load_models wraps YAML parse errors in ModelsError naming the file; `fr run start` warns after the save and exits 0; advance, resolve's chained advance and `fr models …` refuse with one `fr: <path>: …` line, exit 2. Not taken: guard run start only; treat a corrupt file as empty. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d2-board-columns-tripwire created=2026-10-12T15:09:26+00:00 -->
### d2-board-columns-tripwire · decision · #1066 names the columns and adds a tripwire, defensively

Operator chose name + tripwire, adding: the columns may change (another issue is in flight), so program defensively. Verified: #1107 adds two columns (nine) and #1151 renames the skill paragraph's lead. So the skill lists titles without a count, the docstring names neither, and the test reads COLUMN_TITLES live, finds the paragraph by content, and refuses a stated count (spec §D). decider: operator.

<!-- fr:journal kind=decision scope=spec id=d3-strict-fake created=2026-10-12T15:09:26+00:00 -->
### d3-strict-fake · decision · #1102 fixes the call site and makes FakeGhClient strict

Operator chose: state="CLOSED" at the call site, and FakeGhClient.edit_issue_state raises ValueError on anything but OPEN/CLOSED, like the real clients. Not taken: call site only; case-normalising the real clients. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d4-probe-trim created=2026-10-12T15:09:26+00:00 -->
### d4-probe-trim · decision · #1057 strips trailing brackets rather than narrowing the regex

Operator chose: keep the regex, rstrip a trailing run of `)`/`]`/whitespace, so a parenthesis inside the provider's own message survives. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d5-light-shape-verification-none created=2026-10-12T15:09:26+00:00 -->
### d5-light-shape-verification-none · decision · Light path, one agentic phase; verification none, tests: ci

Operator chose fr-goal-light with one agentic phase, `## Verification` = `strategy: none` with a reason per row, and the full suite proven by CI on the PR (`tests: ci`). decider: operator.
