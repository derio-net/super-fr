# Event-driven, à la carte super-fr — architecture, and S1: configuration homes

**Date:** 2026-11-19 (brainstormed 2026-11-19 to 2026-11-24)
**Slug:** `2026-11-19-event-driven-a-la-carte`
**Status:** design (fr-brainstorming, standalone)
**Repo:** `derio-net/super-fr`
**Tracking:** epic #1652; this spec builds S1 (#1653). S2 #1654, S3 #1655 and S4 #1656 each get
their own spec, written from Part I. Related: #1657 (split tracking), #1651 (cncd).

This document has two parts. **Part I** is the architecture the operator settled for the whole
epic: vocabulary, decisions and the order of the sub-projects. It is not built by this spec and
holds no requirements; S2 to S4 cite it. **Part II** is S1, the only part this spec builds:
`## Requirements`, `## Design`, `## Verification` and `## Test Plan` belong to S1 alone.

## Background

The operator asked for two things (spec journal entry `brief`):

- **À la carte:** a repo composes the process it wants in its own configuration: which workflows
  exist, which PR-body sections it wants (not everybody wants Proportionality or Cost), where fr's
  memory lives (repo, quiet, stealth), and more.
- **Event-driven:** the handoffs between agents and gates become explicit events. Role agents
  (a Product Owner who brainstorms, an Architect who does wayfinding, a Tester who mans the tester
  gate, an Orchestrator who drives waves) pick a ticket up, do their part and pass it on. Today one
  session does too much.

The operator's constraint: a broker service must not become a hard requirement. A single portable
session that runs the whole workflow must keep working.

What exists today (read 2026-11-24 on this branch):

- `.fr/settings.yaml` is already a closed-schema settings file (spec
  `2026-11-04-repo-feature-settings`), read from the default branch under `repo`. Under `quiet` the
  switch and settings are the **root** `settings.yaml` of the `fr` branch
  (`fr.artifacts.paths.SWITCH_SETTINGS`); under `stealth` they are `<target-dir>/settings.yaml` in
  the tracking clone (`fr.placement.stealth.TARGET_SETTINGS`).
- Every other `.fr/` file (`ci.yaml`, `docs.yaml`, `lenses.yaml`, `triage.yaml`, `ops.yaml`,
  `debt.yaml`, `candidate-install`) is read from the **product checkout** in every placement.
- Five kinds of repo configuration live under `docs/superpowers/`, beside fr's memory:
  `workflows/`, `verifications/`, `models.yaml`, `trackers.yaml`, `plan-config.yaml`
  (`fr.artifacts.paths.REPO_CONFIG_KINDS`). None is a registered artifact kind.
- `.devcontainer/fr-profiles.yaml` is the registered `profiles` kind (version 2).
  `.fr-isolation-allow` is read only by the edit-gate hooks (`hooks/lib/fr-isolation-decision.sh`,
  `fr-opencode-plugin/src/marker.ts`), never by Python.
- super-fr's shipped defaults have three different homes and two mechanisms: workflows
  (`plugins/super-fr/workflows/` → wheel `fr/workflows/`, kept by hand-`cp` and a tripwire),
  verifications (same, `fr/verifications/`) and lenses (`plugins/super-fr/lenses/` → wheel
  `fr/lens_manifests/`, kept by `scripts/sync-lenses-data.py`). One shared resolver
  (`fr/_shipped.py`) and one env var per kind.
- Triage state's working copy is `<clone>/.fr/triage-state/<scope>/`; its durable copy, the orphan
  branch `refs/heads/fr-triage/<scope-id>`, exists only once a `state_repo` was chosen
  (`fr.triage.state_ref.decide_state_repo`, asked on first collect).

# Part I — Architecture (S1 to S4)

## Vocabulary

- **Space.** Where a run's state lives and its configuration is read: the remote's feature
  branches under `repo`, the `fr` branch under `quiet`, the tracking branch under `stealth`. A
  triage scope's space is its `fr-triage/<scope-id>` branch.
- **Repo configuration.** What an fr-enabled repo declares about its own process. It lives in
  `.fr/` at the root of its space and travels with the space, into stealth too.
- **Shipped defaults.** What super-fr provides: code, and default workflows, verification
  strategies, lenses and (S4) stations. Repo configuration overrides them.
- **Station.** A role that does steps: Product Owner, Architect, Tester, DevOps, Orchestrator.
  Declared abstractly in repo configuration.
- **Binding.** A host's statement that a runner (harness, model, profiles) staffs a station. Lives
  in the host file, outside every repo.
- **Staffing.** `solo`: one session runs the workflow and runs each step's agent as a subagent.
  `stations`: a Router hands each step to its station.
- **Router.** The mechanical decider of handoffs. A port with adapters; one per space.

## Decisions

Recorded as spec journal entry `operator-decisions-r1`.

| # | Decision |
|---|---|
| D0 | Each workflow step declares the station that does it; a step boundary is a commit, pushed per placement. Ad-hoc flows (fr-debugging, …) become workflows. A mechanical Router decides handoffs: a port, whose first adapter sits beside the wave driver, with a Local Router for stealth and room for a future service. |
| Split | The repo declares stations; a host file binds them to runner, harness and model. A future Coordinator node may hold the bindings of several runner nodes. |
| D1 | Every runner a station binds provides `SessionMessenger`. Whether a runner can take a message no longer decides continue-or-fresh. |
| D2 | Two staffings: `solo` (today's fr-goal, generalised) and `stations`. |
| D3 | One Router per space; station and Router configuration live in that space's `.fr/`. |
| D4 | Runs register implicitly: the cursor in the space, watched through `fr_dispatch`'s `Source`. |
| D5 | One Router per space, held by a lease; a host may run several Routers. |
| D6 | Stealth uses a Local Router on its tracking space. |
| D7 | Stealth: state is pushed to the tracking repo on every write; code reaches the target (`fr push`, `fr pr create`) only after the operator explicitly confirms, whatever `git.push` says. |
| D8 | cncd cannot be bound to a station; its retirement is #1651. |
| D9 | A station session handles one ticket. |
| D10 | A host-wide admission ledger (`HostCapacity`: session slots plus sampled load and memory, oldest waiter first) is shared by every Router and wave driver on the host. A full host spills over to a fallback binding the host file names when the space is pushed; else the step waits and raises a Need after a set time. Stealth always waits. |
| D11 | The devcontainer profile is the unit of access: a station names a profile; a profile declares its network reach; a binding lists the profiles its host can enter; a bounded reach probe runs at admission. `fr hosts check` refuses a binding or fallback that cannot satisfy its station. |
| D12 | `.fr/` holds repo configuration only and follows the space. |
| D13 | super-fr's shipped defaults get one home. |
| D14 | Triage state follows the unit under triage; its branch is the wave-driver Router's space. |
| D15 | A repo scope's triage branch lives in that repo; an org scope's in the org's state repo; a stealth repo's in its tracking repo; a repo may name a state repo in `.fr/settings.yaml`. The privacy guard is unchanged. |

## Sub-projects

| # | Issue | Builds | Needs |
|---|---|---|---|
| S1 | #1653 | Configuration homes: D12, D13, D14, D15 (this spec). | — |
| S2 | #1654 | À la carte settings: available workflows, required PR-body sections (`fr.record.pr_body.REQUIRED_SECTIONS` becomes configurable), placement choices with stealth settings read from its space, and D7. #1657 is a candidate. | S1 |
| S3 | #1655 | Every flow is a workflow: fr-debugging and the other ad-hoc flows as manifests, each step declaring its station, the step boundary as a commit, `staffing: solo`. | S1, S2 |
| S4 | #1656 | Stations and the Router: D1 to D6, D9 to D11, the host file, `staffing: stations`. | S3 |

A Coordinator node or external broker is later and out of the epic.

# Part II — S1: configuration homes

## Requirements

R1. Every repo-configuration file fr reads lives under one `.fr/` directory at the root of the run's space: the product checkout under `repo`, the `fr` branch under `quiet`, and `<target-dir>/` in the tracking clone under `stealth`.
R2. One module resolves the configuration root and every reader of repo configuration goes through it: the space's working directory for working-tree reads, and the space's default ref for reads at the default branch (`origin/<default>` under `repo`, `origin/fr` under `quiet`, the tracking ref under `stealth`). A test fails when any other module names a `.fr/` path.
R3. Under `quiet` the switch and settings are `.fr/settings.yaml` on the `fr` branch; under `stealth` they are `<target-dir>/.fr/settings.yaml`. Every reader of the switch, including the edit-gate hooks on every harness, recognises it there.
R4. Under `quiet` and `stealth` the other `.fr/` files (`ci.yaml`, `docs.yaml`, `lenses.yaml`, `triage.yaml`, `ops.yaml`, `debt.yaml`, `candidate-install`) are read from the space. A product checkout's own `.fr/` is then ignored, and fr says so once per command, naming the file.
R5. The repo's workflow overrides and own workflows live in `.fr/workflows/<name>.yaml`, its verification strategies in `.fr/verifications/<name>.yaml`, its model bindings in `.fr/models.yaml`, its trackers in `.fr/trackers.yaml` and its plan format in `.fr/plan-config.yaml`. `fr settings paths` names the new locations.
R6. The devcontainer profile declarations live in `.fr/profiles.yaml`. The `.devcontainer/<profile>/` directories stay where they are.
R7. The base-clone edit allowlist lives in `.fr/isolation-allow`, with the same glob rules, read by the edit gate on every harness.
R8. `fr migrate artifacts --yes`, and the CLI-entry gate in the contexts that migrate, moves each file of R3 and R5 to R7 from its old path with `git mv` and commits the moves as one `chore(fr): migrate` commit. When both the old and the new path exist, it refuses that file and names both.
R9. For one minor release after S1 ships, a reader that finds a file only at its old path uses it and prints one notice naming `fr migrate artifacts --yes`; the hooks accept the old path without a notice. From the next minor release the old path is refused with the same remedy.
R10. super-fr's shipped defaults have one home: `plugins/super-fr/defaults/<kind>/` for `workflows`, `verifications` and `lenses`, one wheel copy at `fr/defaults/<kind>/`, one sync script with a check mode, and one test that fails on drift. A repo's `.fr/` entry of the same name wins over the shipped one.
R11. One environment variable, `FR_SHIPPED_DEFAULTS_DIR`, points the resolver at another defaults tree. `FR_SHIPPED_WORKFLOWS_DIR`, `FR_SHIPPED_VERIFICATIONS_DIR` and `FR_SHIPPED_LENSES_DIR` keep working for the release of R9.
R12. `.fr/` holds configuration only. Triage's working state lives in the host cache, `~/.cache/fr/triage/<scope>/`. A scope whose state is still in `<clone>/.fr/triage-state/<scope>/` is moved there on its first use, unless a driver's `drive.lock` for that scope names a live process, in which case fr refuses and says to stop the driver first.
R13. Every triage scope keeps its durable state on its `fr-triage/<scope-id>` branch by default, with no question asked: a scope of one repo keeps it in that repo, an org scope in the org's state repo (chosen as today), and a repo under stealth in its tracking repo.
R14. A repo may name the state repo of its triage scope in `.fr/settings.yaml` as `triage.state_repo: <owner>/<repo>`, which wins over R13's default. A settings file that sets it declares `schema: 2`; a file without it may stay at `schema: 1`, and fr reads both.
R15. The triage privacy guard is unchanged: a private or internal repo's issue never reaches a public state repo, whichever rule chose it.
R16. Shipped manifests and repo configuration never live under `docs/superpowers/`; that tree holds fr's memory only.

## Design

### A. The configuration root (R1, R2, R4)

A new module `fr/config/space.py` is the one resolver. It builds on what decides the placement today
(`fr.artifacts.paths.space_for`) and answers two questions:

- `config_dir(repo_root) -> Path`: the `.fr/` of the space's working tree. Under `repo` it is
  `<product checkout>/.fr`, under `quiet` `<fr worktree>/.fr` (the worktree at
  `~/.cache/fr/worktrees/<main checkout>/fr`), under `stealth` `<tracking clone>/<target-dir>/.fr`.
- `read_at_default(repo_root, rel) -> str | None`: the file's text at the space's default ref, read
  by commit the way `fr.settings.load` reads `settings.yaml` today.

Every reader listed in the inventory below moves onto it. The readers of `.fr/docs.yaml`, `lenses.yaml`,
`ops.yaml`, `debt.yaml` (working tree today), `.fr/ci.yaml` and `triage.yaml` (by commit today) keep
the kind of read they do; only the root changes. When the placement is `quiet` or `stealth` and the
product checkout also has a `.fr/`, `space.py` prints one line to stderr naming the ignored files,
the way `settings/load.py` already does for `.fr/settings.yaml`.

`tests/unit/test_tripwire_config_space.py` scans `packages/*/src` for the literal `.fr/` and the
old paths of R5 to R7, and fails outside `fr/config/space.py`, `fr/artifacts/paths.py` and the
migration modules. This makes the rule structural: a new reader cannot pick the wrong root.

Consequence under `quiet` and `stealth`: the product's CI cannot read `.fr/docs.yaml` or
`.fr/ci.yaml`, so fr's CI gates (`fr docs check`, `fr acceptance check`) do not run in the product's
CI there. That follows from the placement: such a product carries no fr. A repo that wants those
gates in CI uses `repo`.

### B. The switch and the settings (R3)

`paths.SWITCH_SETTINGS` becomes `.fr/settings.yaml`, and `stealth.TARGET_SETTINGS` becomes
`<target-dir>/.fr/settings.yaml`. `quiet.read_switch`, `settings/load.py` and the edit-gate readers
(`hooks/lib/fr-isolation-decision.sh` at its two `cat-file -p refs/remotes/origin/fr:settings.yaml`
reads, the OpenCode plugin's switch reader, the Hermes hook through the same library) read the new
path first and, during R9's release, the old one when the new one is absent. If both exist and their
`placement` lines differ, the switch is refused, as an unreadable switch is today.

**This is a guard change.** The edit gate decides whether a write to the `fr` worktree is allowed,
so its PR gets an independent adversarial review before merge, of the hook library and the plugin
alike.

### C. The moved files (R5 to R7)

| From | To | Kind |
|---|---|---|
| `docs/superpowers/workflows/<name>.yaml` | `.fr/workflows/<name>.yaml` | new kind `workflow-config` |
| `docs/superpowers/verifications/<name>.yaml` | `.fr/verifications/<name>.yaml` | new kind `verification-config` |
| `docs/superpowers/models.yaml` | `.fr/models.yaml` | new kind `models-config` |
| `docs/superpowers/trackers.yaml` | `.fr/trackers.yaml` | new kind `trackers-config` |
| `docs/superpowers/plan-config.yaml` | `.fr/plan-config.yaml` | new kind `plan-config` |
| `.devcontainer/fr-profiles.yaml` | `.fr/profiles.yaml` | `profiles`, 2 → 3 |
| `.fr-isolation-allow` | `.fr/isolation-allow` | new kind `isolation-allow` |
| `<fr branch>/settings.yaml`, `<target-dir>/settings.yaml` | `.fr/settings.yaml` in the space | new kind `settings-location` |

`fr.artifacts.paths._TABLE` moves the five rows to `.fr/`; `REPO_CONFIG_KINDS` leaves the module,
because `.fr/` is not below an artifact tree and `placement_bound` already treats it as repo
configuration. `fr settings paths --shell` exports the new values under the same variable names.

Hard-coded copies of the old paths move too: `scripts/validate-plans.sh` and its wheel copy
`fr/data/validate-plans.sh` (the `FR_PLAN_CONFIG_FILE` fallback), `scripts/sync-opencode.py`'s
`AGENTS_MODELS_REL`, `fr/migrate.py`'s plan-config path, `fr/ops/gate.py`'s `PROFILES_FILE`, and
`stealth.FR_OWNED_PATHS`, which keeps the old entries so stealth still refuses them in a target.

### D. Migration (R8, R9)

The artifact framework migrates only registered kinds, and only `profiles` is one. S1 registers the
others with **the location as the stamp**: `read_stamp` answers 1 when the file is at its old
locator and 2 when it is at its new one. The 1 → 2 hop is a `SchemaMigration` that runs `git mv`,
builds nothing in memory and changes no byte, so the crash window the versioning rule describes
cannot leave a half-written file: either the move happened or it did not. `profiles` gets its 2 → 3
hop the same way, keeping its `schema_version` stamp inside the file and moving the file.

Each kind's validator is the reader it already has: `fr workflow check`, `fr verification check`,
`load_models`, the trackers loader, the plan-config loader, `validate_profiles`, and a glob-syntax
check for `isolation-allow`. `fr validate artifacts` runs them at the new path.

R9's transition is one function, `space.legacy_path(rel)`, used by every reader through
`space.py`: it returns the old path when only the old one exists and prints one notice per command.
At the next minor release a one-line change turns the notice into a refusal. That change is filed as
a follow-up issue under #1653 when S1 merges.

### E. One home for shipped defaults (R10, R11, R16)

`plugins/super-fr/defaults/` holds `workflows/`, `verifications/` and `lenses/`, moved with
`git mv` from their three current directories. `scripts/sync-defaults-data.py` (replacing
`sync-lenses-data.py` and the two hand-`cp` hints) copies the tree to `packages/fr/src/fr/defaults/`
and has `--check`. `tests/unit/test_tripwire_shipped_defaults.py` replaces the three per-kind
tripwires and keeps each one's own assertions (each workflow passes `fr workflow check`, the four
strategies keep their `when`/`driver`, the four lenses exist). `fr/_shipped.py` resolves
`<root>/<kind>/` for every kind, in the order repo `.fr/<kind>/` > `FR_SHIPPED_DEFAULTS_DIR` >
the per-kind variable (R11) > wheel > marketplace. `install.sh`'s rsync already copies the whole
plugin, so it needs no change; `test_install_copies_workflows.py` and `_lenses.py` follow the
new path, and a verifications case is added.

The agents data (`fr/agents/`) and `fr/harness/parity.yaml` stay where they are: the first is the
source of a rendered artifact kind with its own pin, the second is internal and never overridden.

### F. Triage state (R12 to R15)

**Working copy.** `fr.triage.model.state_dir` returns `~/.cache/fr/triage/<scope>/` (or `--dir`),
the directory `drive.lock` already uses. On first use it moves an existing
`<clone>/.fr/triage-state/<scope>/` there, then drops the `info/exclude` line. A `drive.lock` in the
old directory whose pid is alive refuses the move.

**Durable copy by default.** `decide_state_repo` gains a first rule: when the scope is one repo, its
state repo is that repo, taken without asking (the privacy guard passes trivially, the visibility is
the same). An org scope keeps today's choice and question. A repo under stealth uses its tracking
repo. `.fr/settings.yaml`'s `triage.state_repo` wins over all three; `fr.settings.model` gains the
`triage` section and accepts `schema: 1 | 2`, refusing `triage` under `schema: 1`.

A repo's `docs/triage/` export (this repo's reviewed copy, configured by `.fr/triage.yaml`
`export.path`) is unchanged. It is an export, not state.

**Not changed:** the scope id still hashes the host id (`scope_config.py`), so two hosts triaging one
repo use two branches. That conflicts with "the branch is the scope's space" (D14) once S4 makes it
a Router's space. S1 files it as an issue under #1656 instead of changing it here.

### Inventory of readers that move

From the 2026-11-24 survey of this branch: `fr/workflow/resolve.py`, `commands/workflow_cmd.py`,
`artifacts/validate.py`, `triage/ledger.py` (`EXIT_INPUTS`); `fr/verification/resolve.py`,
`commands/verification_cmd.py`; `fr/models.py`, `commands/models_cmd.py`, `commands/run_cmd.py`,
`commands/triage_batch_cmd.py`, `scripts/sync-opencode.py`; `fr/tracker/model.py`;
`fr/repair.py`, `fr/plan_config.py`, `commands/repair_cmd.py`, `commands/repos_cmd.py`,
`fr/migrate.py`, `validate-plans.sh` (two copies); `isolation/types.py` (`profiles_config`, which
feeds `services/resolve.py` and every `resolve_services` caller), `isolation/scaffold.py`,
`artifacts/profiles_services.py`, `artifacts/structure.py`, `ops/gate.py`, `ops/profile.py`;
`hooks/lib/fr-isolation-decision.sh`, `fr-opencode-plugin/src/marker.ts`; and the `.fr/*.yaml`
readers of §A. Prose: `fr-init`, `fr-isolation`, `fr-goal` skills, the `fr-isolation-required`
rule and their generated mirrors.

## Non-goals

- Everything in S2 to S4.
- Where `.devcontainer/<profile>/` lives under stealth.
- The host-independent triage scope id (filed, see §F).
- Retiring cncd (#1651).

## Verification

strategy: candidate
- s1-config-root: candidate — a scenario installs the candidate and runs fr in a fixture repo under each placement
- s1-switch-moved: candidate — the scenario's quiet and stealth fixtures read the switch at the new path, and the hook suite runs on the candidate's hooks
- s1-migration: candidate — a scenario migrates a fixture repo holding every old path
- s1-shipped-defaults: candidate — the installed candidate resolves every shipped workflow, strategy and lens from the one tree
- s1-triage-state-home: candidate — a scenario collects a fixture scope and finds its state in the cache and on its branch
gate: developer

## Test Plan

- pre-merge — CI: `tests/unit/test_config_space.py` pins `config_dir` and `read_at_default` under
  repo, quiet and stealth and the ignored-product notice (R1, R2, R4), and
  `tests/unit/test_tripwire_config_space.py` fails a `.fr/` path named outside the resolver (R2)
  (row `s1-config-root`).
- pre-merge — CI: `tests/unit/test_placement_quiet.py` and `test_settings_load.py` read the switch
  and settings at `.fr/settings.yaml` and at the old path during the transition, and refuse two that
  disagree; the hook suites (`tests/hooks/`) and `bun test` in `packages/fr-opencode-plugin` do the
  same for the edit gate (R3, R9) (row `s1-switch-moved`).
- pre-merge — CI: per-kind migration tests move each old path with `git mv`, commit once, refuse
  when both paths exist, and read the old path with one notice (R5 to R9), and the hop-by-hop chain
  test covers `profiles` 1 → 3 (row `s1-migration`).
- pre-merge — CI: `tests/unit/test_tripwire_shipped_defaults.py` checks the one tree against its
  wheel copy and every manifest's own check; resolver tests cover the order and the aliases
  (R10, R11, R16) (row `s1-shipped-defaults`).
- pre-merge — CI: triage tests cover the cache working copy, the move from `.fr/triage-state/`, the
  live-lock refusal, the default state repo per scope kind, `triage.state_repo` with `schema: 2`,
  and the privacy guard on each (R12 to R15) (row `s1-triage-state-home`).
- pre-merge — candidate: `tests/scenarios/` gains a configuration-homes scenario that installs the
  candidate, migrates a fixture repo holding every old path, and runs `fr settings paths`,
  `fr workflow check` and `fr verification list` under repo, quiet and stealth fixtures (rows
  `s1-config-root`, `s1-switch-moved`, `s1-migration`, `s1-shipped-defaults`,
  `s1-triage-state-home`).
