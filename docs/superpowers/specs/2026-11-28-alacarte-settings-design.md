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

- Every shipped or repo-authored workflow shape resolves (`fr.workflow.resolve.resolve_workflow`),
  and `fr run start` (`commands/run_cmd.py:1321`, re-resolved in the workspace at `:1373`), a
  brainstorm record's `shape:` rebind (`fr.run.steps.rebind_shape`, `run/steps.py:482`) and
  `fr run adopt` (`run/adopt.py:928`, also reached from `fr migrate artifacts`,
  `commands/migrate_cmd.py:328`) start a run on any of them. A repo cannot withdraw one.
- `fr.record.pr_body.REQUIRED_SECTIONS` (`record/pr_body.py:85`) is a fixed tuple of nine headings;
  `render_pr_body` (`record/pr_body.py:1560`) renders each, and `deliver` refuses a live body that
  lacks any (`run/deliver.py:332`).
- The `placement` key's description still says "stealth is not yet served"
  (`settings/model.py:273`), and `_repo_file`'s refusal (`settings/load.py:280-295`) still names the
  `fr` branch's root `settings.yaml` as quiet's switch, though S1 moved it to `.fr/settings.yaml`
  on `fr-config`.
- `git.push: ask` / `git.pr: ask` make `fr push` (`commands/push_cmd.py:199`) and `fr pr create`
  (`commands/pr_cmd.py:146`) wait for a verified operator approval
  (`fr.git_policy.ask.require_approval`); on a harness whose transcript fr cannot read the request
  always refuses (`git_policy/ask.py:245-259`). Under stealth the loader forces the forge keys to
  stealth's own values (`QUIET_FORGE`) and reports an explicit contrary value as `contrary`
  (refused by `fr settings check` as `stealth-forge-explicit` and by `fr run start` through
  `check_settings`), but leaves `git.push` and `git.pr` at whatever the tracking file says, `auto`
  by default. Two other readers of those keys exist: `config/change.py:229` (`pr_policy`, the
  configuration-change PRs `fr settings init`/`sync` open on the configuration branch) and
  `settings/check.py:52-74` (`push-ask-with-driven-triage`).

## Requirements

R1. Settings schema 3 adds `workflows.disabled`, a list of shape names (default empty), and `forge.pr_sections` (R4). A file whose raw data names `workflows` or `forge.pr_sections` at all, an empty list or mapping included, declares `schema: 3`, and is refused naming the key otherwise. fr reads schemas 1, 2 and 3.
R2. `fr run start <shape>`, a brainstorm record's `shape:` rebind and `fr run adopt` (including the adopt `fr migrate artifacts` performs) refuse a disabled shape, naming `workflows.disabled` and the shapes still available. Under stealth the check reads the tracking space's settings, so it runs in the workspace. A run already started on a shape later disabled keeps going: `advance`, `resolve` and `reshape` never refuse on it, and `adopt --supersede` of an existing run is allowed when the shape it resolves is that run's own shape.
R3. `fr settings check` refuses a `workflows.disabled` entry that names no shape fr can resolve (shipped or the repo's own), and a list that disables every shape.
R4. `forge.pr_sections` holds three on|off keys, default on: `proportionality` (`## Proportionality`), `cost` (`## Cost`) and `settle` (`## PR settle`). No other heading is configurable; any other key is refused with a message naming the three.
R5. A section turned off is rendered nowhere: neither in `pr-body.md` nor in the durable `<run-id>.pr-body.md`, and `deliver` does not require it on the live PR. Its figures stay reachable through their own commands (`fr plan proportionality`, `fr run cost`, `fr pr settle`), and the settle check at `deliver` still runs as `git.settle` says.
R6. The `placement` key's description and `_repo_file`'s refusal say what is true: `.fr/settings.yaml` may only say `repo`; quiet is switched on by `.fr/settings.yaml` on `fr-config`; stealth is chosen per run and reads its settings from `<target-dir>/.fr/settings.yaml` on the tracking repo's `<branch>-config`. `fr settings init` renders that text, renders a list default as a YAML list, and under stealth shows `git.push` and `git.pr` at `ask`.
R7. Under stealth, the effective `git.push` and `git.pr` are `ask` whatever the tracking settings file says, and `fr settings show` reports their source as `stealth`. A tracking file that sets either one explicitly to `auto` is refused by `fr settings check` and `fr run start`, as an explicit contrary forge key is. Under stealth, `push-ask-with-driven-triage` names the driven `.fr/triage.yaml` keys as the only fix, since `git.push` is not the operator's to change there.
R8. Under stealth, writes of fr's state to the tracking repo keep being pushed on every write without asking, and the configuration-change PRs fr opens on the tracking repo's configuration branch follow the tracking file's own `git.pr` (default `auto`), not the forced value. Only `fr push` of the product branch and `fr pr create` are forced to ask.
R9. Under stealth, `fr push` asks only when it would add code to the target: with no product commit to push it pushes nothing, asks nothing and exits 0. Each push that does add code asks for its own approval, settle-fix pushes included.
R10. Under stealth, the fr-goal and fr-debugging skills push no code before `deliver`: a phase executor never pushes, and a phase's suite evidence is a local log, never `tests: ci`. The first code push is at `deliver`'s open, and `fr pr create` asks for its own approval. The skills state the costs: until that push the phases' code exists only on the host that wrote it, so a cross-host `--resume` before `deliver` does not carry it; and on a harness whose transcript fr cannot read, a stealth run cannot push or open its PR through fr and stops at `deliver`'s open.

## Design shape

```
packages/fr/src/fr/
  settings/
    model.py        ~ SCHEMAS (1,2,3); Workflows{disabled}; Forge.pr_sections{proportionality,cost,settle}
                      before-validator: raw presence -> schema 3 (R1); pr_sections key refusal names the three (R4)
                      _strict_int message; placement description (R6)
    load.py         ~ _stealth forces git.push/git.pr = ask, contrary += git.* (R7); keeps the tracking
                      file's own git.pr for config-change PRs (R8); _repo_file text (R6)
    check.py        + unknown-disabled-shape, every-shape-disabled (R3)
                    ~ stealth-forge-explicit also reports git.push / git.pr; driven-triage text under stealth (R7)
    render.py       ~ list defaults as YAML lists; stealth git keys at ask; schema hint 1, 2, 3 (R6)
  config/change.py  ~ pr_policy reads the unforced git.pr under stealth (R8)
  workflow/
    resolve.py      + discover_names (moved from commands/workflow_cmd.py:_discover_names)
    available.py    + refuse_disabled(name, repo_root) -> None — the one disabled check (R2)
  commands/
    workflow_cmd.py ~ imports discover_names
    run_cmd.py      ~ start: refuse_disabled before isolation (repo, quiet) or in the workspace (stealth)
    push_cmd.py     ~ under stealth: no code pending -> no ask, push nothing (R9)
  run/steps.py      ~ rebind_shape calls refuse_disabled
  run/adopt.py      ~ calls refuse_disabled unless superseding a run onto its own shape
  record/pr_body.py ~ PR_SECTION_HEADINGS; required_sections(settings); render skips an off section (R4, R5)
  run/deliver.py    ~ reads required_sections(settings)
plugins/super-fr/skills/
  fr-goal/SKILL.md      ~ stealth: no per-phase push, deliver-open push asks, the two costs (R10)
  fr-debugging/SKILL.md ~ the same rule (R10)
  (OpenCode and Hermes mirrors regenerated; docs pages in §F)
tests/scenarios/alacarte-settings.sh   + the candidate walk (+ its test in tests/integration/test_scenarios.py)
```

## Design

### A. Schema 3 (R1, R4)

`SCHEMAS = (1, 2, 3)`, `SCHEMA_VERSION = 3`, `schema_: Literal[1, 2, 3]`; `_strict_int`'s message
and `render.py`'s schema hint name 1, 2 and 3. A new `Workflows(_Closed)` section holds
`disabled: list[str] = []`; a new `PrSections` under `Forge` holds three `OnOffType` fields.
Presence is a raw-data question, so it is a `mode="before"` model validator on `Settings` in
`model.py` (no import of `load._present`, which would cycle): when the raw mapping has a
`workflows` key, or its `forge` mapping has a `pr_sections` key, and `schema` is not 3, it raises
`<key> needs schema: 3`. `PrSections` also has a `mode="before"` validator that refuses an unknown
key with `unknown key <k>; allowed: cost, proportionality, settle`, so the closed model's generic
"extra inputs" never reaches the operator. Settings is not a registered artifact kind, so there
is no stamp bump or migration: the schema number is the compatibility signal an older fr refuses
on ("newer than this fr understands").

### B. Disabled workflows (R2, R3)

`fr.workflow.resolve.discover_names(repo_root, shipped_dir)` is `workflow_cmd._discover_names`
moved, so `fr workflow check` and the new check read one list. `fr.workflow.available` holds
`refuse_disabled(name, repo_root) -> None`, which reads `load_settings(repo_root)` and raises
`WorkflowError("workflow <name> is disabled by this repo's settings (workflows.disabled); available:
<names>")`. Callers:

- `fr run start`: before isolation is ensured under repo and quiet (a disabled shape provisions
  nothing); under stealth the base clone has no marker yet and would read the target's ignored
  file, so the check runs in the workspace beside the manifest re-resolve (`run_cmd.py:1373`),
  where settings are already checked for stealth (`:1384`).
- `rebind_shape`, before it returns a manifest.
- `adopt_run`, unless it supersedes an existing run and the resolved shape name equals the old
  run's (`old_state.workflow` before `@`). A `--supersede` with no existing run is a plain adopt
  and is checked; `fr migrate artifacts`'s adopt goes through the same function.

`advance`, `resolve` and `reshape` do not call it. `fr settings check` gains two checks: each
disabled name must be in `discover_names` (`unknown-disabled-shape`), and the remaining list must
not be empty (`every-shape-disabled`).

### C. PR-body sections (R4, R5)

`PR_SECTION_HEADINGS = {"proportionality": "## Proportionality", "cost": "## Cost", "settle": "##
PR settle"}`. `pr_body.required_sections(settings)` is `REQUIRED_SECTIONS` minus the headings of the
off keys; `REQUIRED_SECTIONS` stays the full tuple. `render_pr_body` reads the settings once and
skips an off section's heading and body; the durable copy is the same render. `deliver`'s required
set is `required_sections(...)` plus the historical heading when the run has any. `settle: off`
removes only the section; the deliver settle check (`git.settle`) is untouched.

### D. Placement text and init rendering (R6)

The `placement` description and `_repo_file`'s quiet message are corrected. `render.py`'s
`_scalar` renders a list as a YAML flow list (`[]`, `[a, b]`), so an uncommented `#disabled: []`
parses; under stealth its header prose and `_stealth_forge` also show `git.push: ask` and
`git.pr: ask`.

### E. Stealth confirmation (R7–R10)

`_stealth` in `settings/load.py` updates `git` with `push: ask, pr: ask` beside the forge keys,
marks both sources `stealth`, adds `git.push` / `git.pr` to `contrary` when the tracking file sets
them explicitly to `auto`, and keeps the tracking file's own `git.pr` on `EffectiveSettings` as
`config_pr` (the unforced value). `config/change.py`'s `pr_policy` reads `config_pr` when it is set,
so configuration PRs on the tracking repo are not forced to ask (R8). `stealth-forge-explicit`
reports `contrary`, so both git keys are refused with the forge ones; `push-ask-with-driven-triage`
under stealth says that stealth forces `git.push: ask` and that the fix is removing the driven
`.fr/triage.yaml` keys.

`fr push` computes `unpushed` before the ask. Under stealth (`outside_repo(...) == STEALTH`), when
`_code_pending` is false it prints `nothing to push to <remote>` and exits 0 without a request; with
code pending it asks as today and consumes the approval after the push, so the next code push asks
again (R9). `fr pr create` is unchanged: it already asks under `git.pr: ask`, and `deliver`'s ask
gate (`run/deliver.py:214-245`) then accepts only the PR `fr pr create` recorded, now for every
stealth run. State pushes to the tracking repo go through `fr.placement.stealth`'s own pusher,
which reads no settings (R8, pinned by a test).

The skills (R10): fr-goal's stealth bullet, §5 and §6 gain "under stealth no executor pushes, phase
evidence is a local log, and the branch is pushed first at `deliver`'s open, where `fr push` asks";
the resume sentence gains its limit; the Hermes limit is stated once. fr-debugging's stealth
bullet gains the same rule. Both mirrors are regenerated (`scripts/sync-opencode.py`,
`scripts/sync-hermes.py`).

### F. Docs

`docs/reference/workflow-shapes.md` (covers `fr/workflow/**`, `run_cmd.py`) gains the disabled
list; `docs/explainers/01-fr-goal.md` and `docs/explainers/fr-debugging.md` (cover their skills)
gain the stealth confirmation and its two costs; `fr docs check` decides what else is owed.

## Verification

strategy: candidate
- s2-workflows-disabled: candidate — the scenario installs the candidate, disables a shape in a fixture repo's settings and sees `fr run start` refuse it while another shape starts
- s2-pr-sections: candidate — the scenario turns `cost` and `proportionality` off and renders a fixture run's PR body without them
- s2-stealth-confirm: candidate — the scenario reads a stealth fixture's effective settings (`git.push`/`git.pr` ask, source stealth) and sees `fr push` print an approval request instead of pushing, and push nothing without asking when no code is pending
gate: developer

## Test Plan

- pre-merge — CI: `tests/unit/test_settings_model.py` and `tests/unit/test_settings_check.py` pin
  schema 3, the two new sections, the raw-presence refusal (an empty `workflows: {}` included), the
  `pr_sections` key refusal naming the three, and the two new checks (R1, R3, R4); a
  `tests/unit/test_settings_cmd.py` test renders init with a list default and the corrected text
  (R6) (rows `s2-workflows-disabled`, `s2-pr-sections`).
- pre-merge — CI: `tests/unit/test_workflow_available.py` pins the refusal at `run start` (repo and
  stealth, the stealth check reading the tracking settings), rebind, plain adopt, `--supersede`
  with no run and onto another shape, and that `advance`/`resolve`/`reshape` and a same-shape
  `adopt --supersede` do not refuse (R2) (row `s2-workflows-disabled`).
- pre-merge — CI: `tests/unit/test_pr_body_sections.py` renders a body with each key off, checks
  `deliver`'s required set, and that `settle: off` still leaves the deliver settle check in force
  (R5) (row `s2-pr-sections`).
- pre-merge — CI: `tests/unit/test_settings_stealth.py` pins stealth's forced `ask`, its source, the
  contrary refusal and the driven-triage wording; a test pins that a stealth state write and a
  configuration-change PR proceed without a request, and that `fr push` with no code pending asks
  nothing (R7, R8, R9) (row `s2-stealth-confirm`).
- pre-merge — CI: a skill-prose test asserts the stealth sentences of R10 in both canonical
  SKILL.md files (the mirror tripwires carry them to the mirrors) (row `s2-stealth-confirm`).
- pre-merge — candidate: `tests/scenarios/alacarte-settings.sh`, run by its own test in
  `tests/integration/test_scenarios.py` (all three rows).

## Out of scope

- #1657 (issues filed by a split become sub-issues): a candidate for S2 in the epic, not in this
  batch.
- Allowed-placement lists and retiring the `placement` key (operator decision, round 1 Q4).
- Making the review-bearing sections (findings, owed verification, manual operations, owed
  actions) optional (operator decision, round 1 Q2).
- `fr placement move` pushing product-side branches without reading `git.push`: an operator-typed
  move, outside D7's `fr push` and `fr pr create` (review s-r1-13).
- S3 and S4 of epic #1652.
