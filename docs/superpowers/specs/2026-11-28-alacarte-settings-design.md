# À la carte settings — available workflows, PR-body sections, modes, stealth code-push confirmation

Issue: derio-net/super-fr#1654 (S2 of epic #1652). Depends on S1 (#1653, merged in #1696).

## Background

`.fr/settings.yaml` is the closed-schema settings file of spec
`2026-11-04-repo-feature-settings` (`packages/fr/src/fr/settings/model.py`). S1
(`2026-11-19-event-driven-a-la-carte`) moved it into the run's configuration space and reads
stealth's settings from the tracking space: `<target-dir>/.fr/settings.yaml` on
`<branch>-config` (`fr.settings.load._stealth`). The epic's operator, asked what "à la carte"
means, named three things: the workflows a repo offers, the PR-body components ("not everybody
wants to see Proportionality or Cost"), and the repo/quiet/stealth choices. Epic decision D7
adds one rule: under stealth, code reaches the target only after the operator confirms.

What the code does today:

- Every shipped or repo-authored workflow shape resolves (`fr.workflow.resolve.resolve_workflow`)
  and `fr run start` (`commands/run_cmd.py:1321`), a brainstorm record's `shape:` rebind
  (`fr.run.steps.rebind_shape`, `run/steps.py:482`) and `fr run adopt` (`run/adopt.py:928`) start
  a run on any of them. A repo cannot withdraw one.
- `fr.record.pr_body.REQUIRED_SECTIONS` (`record/pr_body.py:85`) is a fixed tuple of nine headings;
  `render_pr_body` (`record/pr_body.py:1560`) renders each, and `deliver` refuses a live body that
  lacks any (`run/deliver.py:332`).
- The `placement` key's description still says "stealth is not yet served"
  (`settings/model.py:273`), though stealth is served and `.fr/settings.yaml` may only say `repo`
  (`settings/load.py:_repo_file`).
- `git.push: ask` / `git.pr: ask` make `fr push` and `fr pr create` wait for a verified operator
  approval (`fr.git_policy.ask.require_approval`). Under stealth the loader forces the forge keys
  to stealth's own values (`QUIET_FORGE`) and reports an explicit contrary value as `contrary`
  (refused by `fr settings check` as `stealth-forge-explicit` and by `fr run start`), but leaves
  `git.push` and `git.pr` at whatever the tracking file says, `auto` by default.

## Requirements

R1. Settings schema 3 adds `workflows.disabled`, a list of shape names (default empty). A file that sets any key this spec adds declares `schema: 3`; fr reads schemas 1, 2 and 3, and a file that sets one without `schema: 3` is refused naming the key.
R2. `fr run start <shape>`, a brainstorm record's `shape:` rebind and `fr run adopt` of a plan or spec with no run refuse a disabled shape, naming `workflows.disabled` and the shapes still available. A run already started on a shape later disabled keeps going: `advance`, `resolve`, `reshape` and `adopt --supersede` of that run never refuse on it.
R3. `fr settings check` refuses a `workflows.disabled` entry that names no shape fr can resolve (shipped or the repo's own), and a list that disables every shape.
R4. Settings schema 3 adds `forge.pr_sections`, three on|off keys, default on: `proportionality` (`## Proportionality`), `cost` (`## Cost`) and `settle` (`## PR settle`). No other heading is configurable; the closed model refuses any other key, naming the three.
R5. A section turned off is rendered nowhere: neither in `pr-body.md` nor in the durable `<run-id>.pr-body.md`, and `deliver` does not require it on the live PR. Its figures stay reachable through their own commands (`fr plan proportionality`, `fr run cost`, `fr pr settle`), and the settle check at `deliver` still runs as `git.settle` says.
R6. The `placement` key's description says what is true: `.fr/settings.yaml` may only say `repo`; quiet is switched on by `.fr/settings.yaml` on `fr-config`; stealth is chosen per run and reads its settings from `<target-dir>/.fr/settings.yaml` on the tracking repo's `<branch>-config`. `fr settings init` renders that text.
R7. Under stealth, the effective `git.push` and `git.pr` are `ask` whatever the tracking settings file says, and `fr settings show` reports their source as `stealth`. A tracking file that sets either one explicitly to `auto` is refused by `fr settings check` and `fr run start`, as an explicit contrary forge key is.
R8. Under stealth, writes of fr's state to the tracking repo keep being pushed on every write without asking; only `fr push` of the product branch and `fr pr create` ask.
R9. Under stealth, the fr-goal and fr-debugging skills push no code before `deliver`: a phase executor never pushes, and a phase's suite evidence is a local log, never `tests: ci`. The first `fr push` is at `deliver`'s open and is an operator confirmation (the `ask` request), and `fr pr create` asks for its own.

## Design shape

```
packages/fr/src/fr/
  settings/
    model.py        ~ SCHEMAS (1,2,3); Workflows{disabled}; Forge.pr_sections{proportionality,cost,settle}
                      placement description (R6); schema-3 validator (R1)
    check.py        + unknown-disabled-shape, every-shape-disabled (R3)
                    ~ stealth-forge-explicit also reports git.push / git.pr (R7)
    load.py         ~ _stealth forces git.push/git.pr = ask, contrary += git.* (R7)
  workflow/
    available.py    + available_or_refusal(name, repo_root) — the one disabled check (R2)
  commands/run_cmd.py   ~ start calls it
  run/steps.py          ~ rebind_shape calls it
  run/adopt.py          ~ a new cursor calls it (not --supersede)
  record/pr_body.py     ~ required_sections(settings); render skips an off section (R4, R5)
  run/deliver.py        ~ reads required_sections(settings)
plugins/super-fr/skills/
  fr-goal/SKILL.md      ~ stealth: no per-phase push; deliver-open push is a confirmation (R9)
  fr-debugging/SKILL.md ~ the same rule for its one push (R9)
tests/scenarios/alacarte-settings.sh   + the candidate walk
```

## Design

### A. Schema 3 (R1)

`SCHEMAS = (1, 2, 3)`, `SCHEMA_VERSION = 3`. A new `Workflows(_Closed)` section with
`disabled: list[str] = []` and a new `PrSections(_Closed)` under `Forge` with three `OnOffType`
fields. The `Settings` model validator that already demands `schema: 2` for `triage.state_repo`
gains the same rule for schema 3: when the file sets a non-default `workflows.disabled` or any
`forge.pr_sections` key, `schema_ < 3` is refused naming the key (the check reads the raw data's
presence, as `_present` does, so an explicit `on` under schema 2 is refused too). Each field
carries its `description=`, from which `fr settings init` renders the comments. Settings is not a
registered artifact kind, so there is no stamp bump or migration: the schema number is the
compatibility signal an older fr refuses on ("newer than this fr understands").

### B. Disabled workflows (R2, R3)

`fr.workflow.available` holds one function, `refuse_disabled(name, repo_root) -> None`, raising
`WorkflowError` with the message `workflow <name> is disabled by this repo's settings
(workflows.disabled); available: <names>`. Available names are the shapes `fr workflow check`
discovers (repo then shipped, `commands/workflow_cmd.py:_discover_names`, moved into
`fr.workflow.resolve` so both read one list) minus the disabled ones. It reads
`load_settings(repo_root)`, so under quiet and stealth the list comes from the configuration
space. Callers: `run start` before isolation is ensured (a disabled shape provisions nothing, as a
typo'd one does), `rebind_shape` before it returns a manifest, and `adopt` only on the path that
creates a new cursor. `advance`, `resolve`, `reshape` and `adopt --supersede` do not call it.

`fr settings check` gains two checks: each disabled name must be in the discovered list
(`unknown-disabled-shape`), and the available list must not be empty (`every-shape-disabled`).

### C. PR-body sections (R4, R5)

`pr_body.required_sections(settings) -> tuple[str, ...]` is `REQUIRED_SECTIONS` minus the headings
of the off keys; `REQUIRED_SECTIONS` stays the full tuple (the docs and tests name it). The map
from key to heading is one constant, `PR_SECTION_HEADINGS`. `render_pr_body` reads the settings
once and skips an off section's heading and body; the durable copy is the same render, so it
drops them too. `deliver`'s required set is `required_sections(...)` plus the historical heading
when the run has any. Turning `settle` off removes only the section: the `settle` evidence and the
deliver settle check still follow `git.settle`.

### D. Placement text (R6)

The description is corrected in `settings/model.py`; `fr settings init`'s rendered comments follow.
No behaviour changes.

### E. Stealth confirmation (R7, R8, R9)

`_stealth` in `settings/load.py` updates `git` with `push: ask, pr: ask` beside the forge keys,
marks both sources `stealth`, and adds `git.push` / `git.pr` to `contrary` when the tracking file
sets them explicitly to `auto`. `fr settings check`'s `stealth-forge-explicit` (renamed in its
message only: "stealth's own values") and `fr run start`'s contrary refusal already read
`contrary`, so they refuse both. `fr push` and `fr pr create` need no change: they already read
`settings.git.push` / `settings.git.pr` and take the `ask` path, recording the approval in the
run's own journal, which under stealth lives in the tracking clone. State pushes to the tracking
repo are a different code path (`fr.placement.stealth`) that never reads `git.push` (R8, pinned by
a test).

Under `tests: ci` a phase executor would push to get CI; under stealth the executor cannot ask the
operator, so the skills say a stealth phase's suite evidence is a local log. fr-goal §5/§6 and §8
gain one stealth sentence each; fr-debugging's stealth bullet gains the same rule. Both mirrors
(`scripts/sync-opencode.py`, `scripts/sync-hermes.py`) are regenerated.

### F. Docs

`docs/reference/workflow-shapes.md` (covers `fr/workflow/**`, `run_cmd.py`) gains the disabled
list; `docs/explainers/01-fr-goal.md` and `docs/explainers/fr-debugging.md` (cover their skills)
gain the stealth confirmation; `fr docs check` decides what else is owed.

## Verification

strategy: candidate
- s2-workflows-disabled: candidate — the scenario installs the candidate, disables a shape in a fixture repo's settings and sees `fr run start` refuse it while another shape starts
- s2-pr-sections: candidate — the scenario turns `cost` and `proportionality` off and renders a fixture run's PR body without them
- s2-stealth-confirm: candidate — the scenario reads a stealth fixture's effective settings (`git.push`/`git.pr` ask, source stealth) and sees `fr push` print an approval request instead of pushing
gate: developer

## Test Plan

- pre-merge — CI: `tests/unit/test_settings_model.py` and `tests/unit/test_settings_check.py` pin
  schema 3, the two new sections, the schema-3 refusal and the two new checks (R1, R3, R4, R6)
  (rows `s2-workflows-disabled`, `s2-pr-sections`).
- pre-merge — CI: `tests/unit/test_workflow_available.py` pins the refusal at `run start`, rebind
  and adopt, and that `advance`/`resolve`/`reshape`/`adopt --supersede` of a started run do not
  refuse (R2) (row `s2-workflows-disabled`).
- pre-merge — CI: `tests/unit/test_pr_body_sections.py` renders a body with each key off and checks
  `deliver`'s required set (R5) (row `s2-pr-sections`).
- pre-merge — CI: `tests/unit/test_settings_stealth.py` pins stealth's forced `ask`, its source and the
  contrary refusal; a test pins that a stealth state write pushes without a request (R7, R8) (row
  `s2-stealth-confirm`).
- pre-merge — candidate: `tests/scenarios/alacarte-settings.sh` (all three rows).

## Out of scope

- #1657 (issues filed by a split become sub-issues): a candidate for S2 in the epic, not in this
  batch.
- Allowed-placement lists and retiring the `placement` key (operator decision, round 1 Q4).
- Making the review-bearing sections (findings, owed verification, manual operations, owed
  actions) optional (operator decision, round 1 Q2).
- S3 and S4 of epic #1652.
