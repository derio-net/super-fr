# S1: configuration homes (event-driven, à la carte epic)

**Date:** 2026-11-19 (brainstormed 2026-11-19 to 2026-11-24)
**Slug:** `2026-11-19-event-driven-a-la-carte`
**Status:** design (fr-brainstorming, standalone)
**Repo:** `derio-net/super-fr`
**Tracking:** #1653, sub-project S1 of epic #1652. The epic's architecture (vocabulary, operator
decisions D0 to D15, the order S1 to S4) lives in the epic issue and in this spec journal's entry
`operator-decisions-r1`; this spec builds S1 only and cites the decisions it implements (D12 to D15).

## Background

The epic answers the operator's brief (spec journal entry `brief`):

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
- Triage state's working copy is `<clone>/.fr/triage-state/<scope>/` (`fr.triage.model.state_dir`),
  with `drive.lock` always in `~/.cache/fr/triage/<scope>/` (`triage_cmd.drive_lock_dir`). Its durable
  copy, the orphan branch `refs/heads/fr-triage/<scope-id>`, is synced only when the scope has a
  `state_repo` and the state directory sits inside a git clone, whose object store the ref commits are
  built in (`triage_cmd._sync_with_ref`). A one-repo scope already gets that repo without a question
  (`state_ref.decide_state_repo`); a scope with several repos is asked once.
- Under `quiet`, fr pushes every state write straight to the `fr` branch, with no pull request. A
  forge rule that required pull requests there would stop fr itself, so content on `fr` is never
  reviewed. GitHub enforces branch rules on a private repo only on a paid plan; fr already recognises
  the free-plan refusal (`fr.real_ghrestclient._plan_lacks_rulesets`).

## Requirements

R1. Repo configuration lives in one `.fr/` directory at the root of the run's **configuration space**: the product checkout under `repo`; the `fr-config` branch under `quiet`; `<target-dir>/` on the tracking repo's `<branch>-config` branch under `stealth`. fr's memory stays where it is today (the product checkout, the `fr` branch, the tracking `<branch>`).
R2. One module resolves the configuration space, and every reader of repo configuration goes through it. It answers the working directory for working-tree reads and a ref for reads at a commit: the default branch under `repo`, the tip of the configuration branch under `quiet` and `stealth`. A test fails when other Python code builds a `.fr` path.
R3. Under `quiet` and `stealth`, a feature branch cannot change repo configuration: every read that compares a branch's `.fr/` with the default branch's reads the configuration branch's tip for both sides. A change to `.fr/` there is a pull request to the configuration branch.
R4. Under `quiet` and `stealth`, the product checkout's own `.fr/` is ignored except for `isolation-allow` (R8), and fr says so once per command, naming the ignored files.
R5. Under `quiet` the switch and settings are `.fr/settings.yaml` on `fr-config`; under `stealth` they are `<target-dir>/.fr/settings.yaml` on `<branch>-config`. Every reader of the switch, the edit-gate hooks on every harness included, recognises it there, and the edit gate treats the `fr-config` worktree and the stealth configuration clone as placement write targets, as it treats the `fr` worktree and the tracking clone today.
R6. Until the release named in R14, fr also keeps the old settings file (the root `settings.yaml` on `fr`, `<target-dir>/settings.yaml` on the tracking `<branch>`) identical to the new one, writing both together, so an older fr or older hooks still read the placement correctly. fr refuses to act when the two differ, and no reader writes either one: when the old file holds the bytes the new one held at an earlier commit of the configuration branch's first-parent history (a change merged and the old file has not followed yet), the refusal says so and names `fr settings sync`, which shows both refs, the configuration branch's tip and the commits between, and `fr settings sync --yes --expect <tip>`, which writes the old file only from that previewed tip.
R7. Configuration that runs commands or decides merges is **executable configuration**: `.fr/candidate-install`, the command keys of `.fr/triage.yaml` (`post_merge` and the version commands), `.fr/ops.yaml`, and `.fr/ci.yaml`'s `gate_checks`, `tests` and `fast_tier`. Under `quiet` and `stealth`, fr runs or gates on it only when the forge enforces a pull-request rule on the configuration branch, read from the forge's effective rules for that branch. Unprotected, `ci.yaml`'s three keys are ignored with the reason said once: `deliver` then owes a local full-suite log, and no brief carries a `fast_tier`. When the forge cannot enforce one (a GitHub free-plan private repo, a forge fr cannot read rules from) or the read fails, fr refuses that action and says why and what to change. Other configuration is read whether or not the branch is protected.
R8. The base-clone edit allowlist is `.fr/isolation-allow` in the working tree of the checkout it governs, under every placement, tracked or not, read by the edit gate on every harness as `.fr-isolation-allow` is today.
R9. The repo's workflow overrides and own workflows live in `.fr/workflows/<name>.yaml`, its verification strategies in `.fr/verifications/<name>.yaml`, its model bindings in `.fr/models.yaml`, its trackers in `.fr/trackers.yaml`, its plan format in `.fr/plan-config.yaml`, and its devcontainer profile declarations in `.fr/profiles.yaml`. The `.devcontainer/<profile>/` directories stay in the product checkout. `fr settings paths` prints the configuration-space locations.
R10. `fr migrate artifacts --yes`, and the CLI-entry gate in the contexts that migrate, moves each file of R5, R8 and R9 from its old path. Within one checkout it moves with `git mv` (a plain rename for an untracked allowlist) in one `chore(fr): migrate` commit. Under `quiet` and `stealth` it first commits each file to the configuration branch, pushes it, and only then removes it from the product in the product's migrate commit; a refused push removes nothing.
R11. Under `quiet`, the migration also moves a product checkout's existing `.fr/` files (`ci.yaml`, `docs.yaml`, `lenses.yaml`, `triage.yaml`, `ops.yaml`, `debt.yaml`, `candidate-install`) to `fr-config` the same way, so no configuration is lost by R4.
R12. When a file exists at both its old and its new path, the migration refuses that file and names both paths; it migrates the rest.
R13. Until the release named in R14, a reader that finds a file only at its old path, the shell readers (the hooks and `validate-plans.sh`) included, uses it and prints one notice per command naming `fr migrate artifacts --yes` (the hooks print nothing).
R14. S1 records the end of R6 and R13 as an `owed` journal entry naming the release that refuses old paths, filed as an issue under #1653; S1 does not build the refusal.
R15. super-fr's shipped defaults have one home: `plugins/super-fr/defaults/<kind>/` for `workflows`, `verifications` and `lenses`, one wheel copy at `fr/defaults/<kind>/`, one sync script with a check mode, and one test that fails on drift. A repo's `.fr/workflows/<name>.yaml` or `.fr/verifications/<name>.yaml` wins over the shipped file of that name; lenses keep `.fr/lenses.yaml` as their only repo override.
R16. One environment variable, `FR_SHIPPED_DEFAULTS_DIR`, points the resolver at another defaults tree. `FR_SHIPPED_WORKFLOWS_DIR`, `FR_SHIPPED_VERIFICATIONS_DIR` and `FR_SHIPPED_LENSES_DIR` keep working until the release named in R14.
R17. `.fr/` holds configuration only. Triage's working state lives in `~/.cache/fr/triage/<scope>/`, which is its own git repository, so it can build and push its state branch with no product clone.
R18. A scope whose working state is in `<clone>/.fr/triage-state/<scope>/` is moved to the cache on first use, its `merge/` worktrees pruned instead of moved. fr refuses the move while that scope's `drive.lock` names a live process. When the cache already holds an older copy of the scope, fr keeps the clone's copy and sets the cache's aside as `<scope>.pre-s1`; when a second clone holds a copy that differs from the cache's in any durable file, fr refuses and names both.
R19. Every triage scope keeps its durable state on its `fr-triage/<scope-id>` branch by default: a scope first collected from a stealth workspace uses that workspace's tracking repo; otherwise a scope of one repo uses that repo; otherwise (an org scope, a scope of several named repos) the state repo is chosen as today.
R20. For a scope of one repo, that repo may name the state repo in `.fr/settings.yaml` as `triage.state_repo: <owner>/<repo>`, which wins over R19 when the scope has no state repo yet. When the scope already records a different one, fr keeps the recorded one and `fr triage check` reports the mismatch. A settings file that sets the key declares `schema: 2`; a file without it may stay at `schema: 1`, and fr reads both.
R21. The triage privacy guard is unchanged: a private or internal repo's issue never reaches a public state repo, whichever rule chose it.
R22. Shipped defaults and repo configuration never live under `docs/superpowers/`, which holds fr's memory only.

## Design

### A. The configuration space (R1 to R4, R22)

A new module `fr/config/space.py` is the one resolver. It builds on `fr.artifacts.paths.space_for`,
which already decides the placement, and returns a `ConfigSpace`:

| Placement | Working directory | Ref for reads at a commit | Memory (unchanged) |
|---|---|---|---|
| `repo` | `<product checkout>/.fr` | `origin/<default>` | product checkout |
| `quiet` | `<fr-config worktree>/.fr` (`~/.cache/fr/worktrees/<main checkout>/fr-config`) | `origin/fr-config` | `fr` worktree |
| `stealth` | `<config clone>/<target-dir>/.fr` (`~/.cache/fr/worktrees/<repo>/stealth--<slug>-config`, on `<branch>-config`) | `origin/<branch>-config` in that clone | tracking clone |

It offers three reads: `dir()` for working-tree readers, `at_default(rel)` for readers at the
default branch, and `at_pair(rel, base, head)` for readers that compare a branch with its base. Under
`repo`, `at_pair` reads the two commits it is given, as today; under `quiet` and `stealth` it reads
the configuration branch's tip for both (R3).

**Readers that move onto it** (the 2026-11-24 survey and the spec review):

- working tree: `docs/load.py` (`.fr/docs.yaml`), `lenses/resolve.py` (`.fr/lenses.yaml`),
  `ops/load.py` (`.fr/ops.yaml`), `debt/engine.py` (`.fr/debt.yaml`), `verification/rows.py`
  (`.fr/triage.yaml`), `verification/walk.py` (`.fr/candidate-install`, run), `services/resolve.py`
  and `isolation/types.py`'s `profiles_config` (and so every `resolve_services` caller),
  `isolation/scaffold.py`, `artifacts/profiles_services.py`, `artifacts/structure.py`,
  `ops/gate.py`, `ops/profile.py`, `fr/models.py`, `commands/models_cmd.py`, `commands/run_cmd.py`
  and `commands/triage_batch_cmd.py` (model bindings), `tracker/model.py`, `fr/repair.py`,
  `fr/plan_config.py`, `commands/repair_cmd.py`, `commands/repos_cmd.py`, `fr/migrate.py`,
  `workflow/resolve.py`, `commands/workflow_cmd.py`, `verification/resolve.py`,
  `commands/verification_cmd.py`, `artifacts/validate.py`, `triage/ledger.py` (`EXIT_INPUTS`);
- at the default branch: `settings/load.py`, `settings/check.py`, `ops/gate.py` (triage.yaml at
  a fresh `origin/<default>`), `triage/queue_exec.py` (`.fr/ci.yaml`), `triage/gitseam.py`
  (`.fr/triage.yaml` commands, `.fr/candidate-install` at a ref), `lenses/resolve.review_lenses`;
- at a pair: `run/ci_evidence.py` (`.fr/ci.yaml` at base and HEAD), `lenses/rules.py`
  (`require:` of both), `record/pr_body.py` (a branch that changed `.fr/lenses.yaml`);
- path tables: `fr.artifacts.paths` — `kind_dir`, `search_roots` and `settings_cmd`'s
  `paths_answers` route the moved kinds through `space.dir()`, so `fr settings paths` prints the
  configuration space under every placement, never `<fr worktree>/features/<id>/.fr/…`;
- forge-side readers of another repo (`triage/collect.py`, `settings/remote.py`,
  `tracker/github.py`): read `.fr/<file>` at `fr-config` through the forge when that branch carries a
  quiet switch, else at the default branch;
- named only: `triage_batch_cmd.SERVICE_PATHS`, `run/observed.py` (the shipped-verifications env
  var), `stealth.FR_OWNED_PATHS` (keeps the old entries, so a stealth target still refuses them).

When the placement is `quiet` or `stealth` and the product checkout has a `.fr/`, `space.py` prints
one line to stderr naming the ignored files, except `isolation-allow` (R4, R8).

**The tripwire** `tests/unit/test_tripwire_config_space.py` parses every Python module under
`packages/*/src` with `ast`, as `test_import_direction.py` does, and fails on a **path
construction** that names `.fr` or an old path of R9 outside `fr/config/space.py`,
`fr/artifacts/paths.py` and the migration modules: a string literal that starts `.fr/` or equals
`.fr` used as an argument of `Path(...)`, an operand of `/`, or an argument of `open`, `read_text`,
`show_at_commit` or a `git show` argument list. Literals in messages (`print`, `typer.echo`, an
exception's arguments, f-strings) and non-Python data are not path constructions and are not
scanned.

Under `quiet` and `stealth` the product's CI cannot read `.fr/`, so fr's CI gates (`fr docs
check`, `fr acceptance check`) do not run in the product's CI there. That follows from the
placement: such a product carries no fr.

### B. The configuration branch, the switch and the older reader (R5, R6)

Under `quiet`, `fr-config` is an orphan branch beside `fr`; its tree is `.fr/`. Under `stealth`,
`<branch>-config` is an orphan branch of the tracking repo whose tree is `<target-dir>/.fr/`. fr
creates either one, with the configuration it holds, at the migration (§D) or at `fr settings init`
under that placement, and opens a pull request for every later change: a change to repo
configuration is reviewed, as it is under `repo`. The pull request's branch is
`fr-config-change/<slug>`, cut from the configuration branch's tip (under stealth, on the tracking
repo), and fr writes no old file for it until it merges.

`paths.SWITCH_REF` becomes `refs/remotes/origin/fr-config` with `SWITCH_SETTINGS =
".fr/settings.yaml"`; `stealth.TARGET_SETTINGS` becomes `<target-dir>/.fr/settings.yaml` on
`<branch>-config`. `quiet.read_switch`, `settings/load.py` and the edit-gate readers
(`hooks/lib/fr-isolation-decision.sh` at its two `cat-file -p refs/remotes/origin/fr:settings.yaml`
reads, `fr-opencode-plugin/src/marker.ts` at its switch reads, the Hermes hook through the shared
library) read the new switch first and the old one when the new is absent (R13). The edit gate's
step 4 adds two write targets recognised by structure, never by name: the linked worktree at
`~/.cache/fr/worktrees/<main checkout>/fr-config` with HEAD on `refs/heads/fr-config` and the switch
reading `placement: quiet`, and the stealth configuration clone a valid stealth workspace's marker
names.

**Older readers (R6).** An fr below S1, or an older plugin's hooks, read only the root
`settings.yaml` on `fr` (or `<target-dir>/settings.yaml`). Without it they would read `repo` and
write artifacts to product branches. So until R14's release fr writes the old file too, with the
same bytes, when it creates the configuration branch (configuration branch first, then the memory
branch), and brings it in step after every reviewed change. Every new reader compares the two and refuses, naming both, when they
differ; the hooks deny, as they do for an unreadable switch. After a reviewed change merges, the
old file lags by one merge. A reader still refuses then, since a push straight to an unprotected
configuration branch looks the same, but says the old file is an earlier version and names `fr
settings sync`: it previews both refs, the configuration branch's tip and its commits since, each
with its second parent and marked as a merge of a change branch only when that parent is a fetched
`fr-config-change/*` tip (information for the operator, never an authorization), and with `--yes
--expect <tip>` writes the old file, refusing when the tip moved since the preview (fetching first,
retrying a refused push). The hooks name the same command, the preview first.

**This is a guard change.** The edit gate decides which writes reach the `fr`, `fr-config` and
stealth clones, so its PR gets an independent adversarial review before merge, of the hook library,
the OpenCode plugin and the Hermes hook.

### C. Executable configuration and protection (R7)

`fr/config/protection.py` answers one question: does the forge enforce a pull-request rule on the
configuration branch? On GitHub it reads `GET repos/<repo>/rules/branches/<branch>` through the
forge adapter and answers **enforced** only when the effective rules include `pull_request` with
`required_approving_review_count` of at least 1, `non_fast_forward` and `deletion` (review p3-r3). fr
reads the branch's rules, not who may bypass them: a ruleset with bypass actors still reads as
enforced, so the operator keeps the configuration branch's bypass lists empty, and every refusal
and every claim of protection says so. A 403
that `_plan_lacks_rulesets` recognises, a 404, an empty rule list, an unreadable answer, and a
forge whose adapter cannot read rules (GitLab, Gitea today) answer **not enforced**, each with its
reason. The answer is cached for the command, never on disk.

Each executor of executable configuration asks it first under `quiet` and `stealth`:
`verification/walk.py` (runs `candidate-install`), the driver's `post_merge` and version commands
(`triage/gitseam.py`), the ops probes and the ops gate (`ops/`), and the queue's `gate_checks`
(`triage/queue_exec.py`). **Not enforced** refuses that action with the reason and the fix
("protect `fr-config` with a ruleset requiring pull requests with at least one approving review;
keep its bypass list empty; GitHub needs a public repo or a paid plan for a private one"). Each runs exactly the reviewed tip (review p3-r2): it fetches the
configuration branch first (a failed fetch refuses), a blob read reads that fetched tip, and a
reader of the configuration checkout's files refuses a checkout that is dirty or not at that tip,
naming the difference and the remedy. Under `repo` nothing changes: the default branch's protection is the
repo owner's business today, and S1 does not change it (see Non-goals).

### D. The moved files and their migration (R8 to R13)

| From | To (configuration space unless noted) | Kind |
|---|---|---|
| `docs/superpowers/workflows/<name>.yaml` | `.fr/workflows/<name>.yaml` | new `workflow-config` |
| `docs/superpowers/verifications/<name>.yaml` | `.fr/verifications/<name>.yaml` | new `verification-config` |
| `docs/superpowers/models.yaml` | `.fr/models.yaml` | new `models-config` |
| `docs/superpowers/trackers.yaml` | `.fr/trackers.yaml` | new `trackers-config` |
| `docs/superpowers/plan-config.yaml` | `.fr/plan-config.yaml` | new `plan-config` |
| `.devcontainer/fr-profiles.yaml` | `.fr/profiles.yaml` | `profiles`, 2 → 3 |
| `.fr-isolation-allow` | `.fr/isolation-allow` in the **same checkout** | new `isolation-allow` |
| root `settings.yaml` on `fr`; `<target-dir>/settings.yaml` | `.fr/settings.yaml` on the configuration branch (old file kept, §B) | new `settings-location` |
| product `.fr/*` under `quiet` (R11) | the same names on `fr-config` | new `quiet-config` |

`fr.artifacts.paths._TABLE` moves the five rows to `.fr/`; `REPO_CONFIG_KINDS` leaves the module.
Hard-coded copies move too: `scripts/validate-plans.sh` and `fr/data/validate-plans.sh` (their
`FR_PLAN_CONFIG_FILE` fallback tries the new path, then the old one), `scripts/sync-opencode.py`'s
`AGENTS_MODELS_REL`, `fr/migrate.py`'s plan-config path and `ops/gate.py`'s `PROFILES_FILE`.

**Location-stamped kinds.** The artifact framework migrates only registered kinds, and only
`profiles` is one. S1 registers the others with **the location as the stamp**, which needs four
framework changes, each with its own tests:

1. `ArtifactKind.locators`: the old and the new locator; the old one gives version 1, the new one
   version 2. `read_stamp(path)` answers from which locator matched.
2. `write_version` is a no-op for these kinds: the move is the stamp.
3. A `SchemaMigration(..., relocates=True)` hop returns the destination; the runner stages the
   rename (`PlannedAction.moved_to`), accepts the source path being gone afterwards, and validates
   the file at its destination. Unlike `retires`, a relocating hop may be any hop of the chain.
4. A cross-space hop (R10, R11) writes the destination in the configuration space's checkout,
   commits and pushes it there first, and only then stages the product-side deletion; a refused
   push leaves the product file byte-identical and is that artifact's failure.

`profiles` 2 → 3 relocates the file and writes `schema_version: 3` into it, so it changes bytes:
it is built in memory and written once (`write_text_atomic`). Crash window: a `.fr/profiles.yaml`
carrying `schema_version: 2` with no old file is a relocation that did not stamp; the hop recognises
it and finishes the stamp. Both files present is R12's refusal. The hop-by-hop chain test covers
1 → 3.

`isolation-allow` moves in its own checkout: `git mv` when tracked, a plain rename when not (no
commit then), in the product checkout under every placement.

Each kind's validator is the reader it already has: `fr workflow check`, `fr verification check`,
`load_models`, the trackers loader, the plan-config loader, `validate_profiles`, the settings model,
and a glob-syntax check for `isolation-allow`. `fr validate artifacts` runs them at the new path.

**The transition (R13).** `space.legacy(rel)` returns the old path when only the old one exists and
prints one notice per command; `validate-plans.sh` and the hooks keep a two-path lookup. R14's
`owed` entry names the release that turns both into a refusal.

### E. `fr init scaffold` and `fr isolation up` under quiet and stealth (R9)

`.devcontainer/<profile>/` stays in the product; its declaration `.fr/profiles.yaml` is in the
configuration space. Under `quiet`, `fr init scaffold` commits the profile directory in the
product's commit and the declaration in a pull request to `fr-config`; `fr isolation up` reads the
declaration through `space.dir()`. Under `stealth`, the declaration goes to `<branch>-config` and
the profile directory is the operator's to add to the product (a stealth target carries no fr file,
and `.devcontainer/<profile>/` is not one).

### F. One home for shipped defaults (R15, R16)

`plugins/super-fr/defaults/` holds `workflows/`, `verifications/` and `lenses/`, moved with
`git mv` from their three current directories. `scripts/sync-defaults-data.py` replaces
`sync-lenses-data.py` and the two hand-`cp` hints, copies the tree to `packages/fr/src/fr/defaults/`,
and has `--check`. `tests/unit/test_tripwire_shipped_defaults.py` replaces the three per-kind
tripwires and keeps their assertions (each workflow passes `fr workflow check`; the four strategies
keep their `when` and `driver`; the four lenses exist; byte equality; importlib reachability).
`fr/_shipped.py` resolves `<root>/<kind>/` in the order: repo `.fr/<kind>/<name>.yaml` (workflows
and verifications only), `FR_SHIPPED_DEFAULTS_DIR/<kind>`, the per-kind variable (R16), the wheel,
the marketplace. Lenses take no repo directory: `.fr/lenses.yaml`'s disable and replace entries stay
their only repo override, and `review_lenses` keeps its default-branch-text rule. `install.sh`'s
rsync copies the whole plugin and needs no change; `test_install_copies_workflows.py` and
`test_install_copies_lenses.py` follow the new path, and a verifications case is added.
`fr/agents/` and `fr/harness/parity.yaml` stay where they are.

### G. Triage state (R17 to R21)

**The cache is a git repository.** `fr.triage.model.state_dir` returns `~/.cache/fr/triage/<scope>/`
(or `--dir`). The first use runs `git init` there, with an `info/exclude` that ignores everything:
the repository exists only to hold the state ref's objects and its remote, the state repo's URL.
`_sync_with_ref`, `push_now` and `local_tree` take this repository as "the clone that holds the
objects", so syncing no longer needs a product clone. `drive.lock` is already in this directory.

**The move (R18).** On first use, when `<clone>/.fr/triage-state/<scope>/` exists:

1. `drive.lock` in the cache directory (`drive_lock_dir`) naming a live pid refuses, with "stop the
   driver first". The check reads the cache directory, which every fr version writes the lock to.
2. When the cache directory already holds files (a host that triaged before cloud triage), it is
   renamed `<scope>.pre-s1`, and the clone's copy moves in.
3. `merge/` is not moved: its worktrees are registered in the product clone, so fr runs
   `git worktree remove --force` on each, then `git worktree prune`; the queue recreates them.
4. The `info/exclude` line `STATE_EXCLUDE` is removed from the clone.
5. A later use from another clone that still holds `.fr/triage-state/<scope>/` compares its durable
   files (`REF_FILES`) with the cache's: identical, it is removed; different, fr refuses and names
   both directories.

An fr below S1 on the same host still writes the clone's directory. Mixed fr versions on one host
are not supported; rule 5 makes the mix loud instead of silent.

**Default state repo (R19).** `decide_state_repo` gains one rule ahead of today's: when the
scope is first collected from a workspace whose marker records `placement: stealth`, its state repo
is the marker's tracking repo. The one-repo rule (already in the code) and the several-repo question
follow unchanged; with the cache repository, the one-repo default now always syncs. A group scope is
a scope of several named repos and takes the question, as today.

**The override (R20).** For a one-repo scope, collect reads `.fr/settings.yaml`'s
`triage.state_repo` through the forge from that repo's configuration space. It applies when
`scope-durable.yaml` records no state repo; a different recorded one is kept, and `fr triage check`
gains a `state repo mismatch` set naming both. `fr.settings.model` gains the `triage` section,
accepts `schema: 1 | 2`, and refuses `triage` under `schema: 1`; an fr below S1 refuses a
`schema: 2` file with its existing "newer than this fr" message.

**Unchanged:** the privacy guard (`privacy.py`); the scope id, which hashes the host id (filed for
S4 under #1656, decision `q-scope-id-s4`); and the `docs/triage/` export, an export configured by
`.fr/triage.yaml` `export.path`, not state.

### H. Prose and pages

Pages whose `covers:` or text name a moved path: `docs/explainers/01-fr-goal.md`,
`docs/explainers/index.md`, `docs/explainers/why-fr.md`, `docs/explainers/fr-triage.md`,
`docs/explainers/fr-isolation.md`, `docs/reference/workflow-shapes.md`,
`docs/reference/components.md`, `docs/review-lenses.md`, `docs/verification-strategies.md`, and
`AGENTS.md`. Skills and rules: `fr-init`, `fr-isolation`, `fr-goal`, the `fr-isolation-required`
rule (both copies) and their OpenCode and Hermes mirrors. The deny messages naming
`.fr-isolation-allow` (`hooks/fr-isolation-required.sh`, `hooks/hermes/fr-isolation-required.sh`,
`fr-opencode-plugin/src/index.ts`) move together, so the harnesses keep the same text.

## Non-goals

- Everything in S2 to S4 of epic #1652.
- Checking the default branch's protection under `repo` (the same free-plan gap exists there; it is
  filed as an out-of-scope finding, not built here).
- A host-independent triage scope id (filed for S4).
- The refusal of old paths (R14 records it as owed).
- Retiring cncd (#1651).

## Verification

strategy: candidate
- s1-config-root: candidate — a scenario installs the candidate and runs fr in fixture repos under each placement
- s1-switch-moved: candidate — the scenario's quiet and stealth fixtures read the switch on the configuration branch, keep the old file in step, and the hook suites run on the candidate's hooks
- s1-executable-config-protection: candidate — a scenario with a stub forge answering enforced, free-plan 403 and unreadable runs a walk under quiet
- s1-migration: candidate — a scenario migrates fixture repos holding every old path under each placement
- s1-shipped-defaults: candidate — the installed candidate resolves every shipped workflow, strategy and lens from the one tree
- s1-triage-state-home: candidate — a scenario collects a fixture scope and finds its state in the cache repository and on its branch
gate: developer

## Test Plan

- pre-merge — CI: `tests/unit/test_config_space.py` pins `dir`, `at_default` and `at_pair` under
  repo, quiet and stealth, the ignored-product notice and the `fr settings paths` answers (R1 to R4,
  R9), and `tests/unit/test_tripwire_config_space.py` fails a `.fr` path construction outside the
  resolver and passes a message naming one (R2, R22) (row `s1-config-root`).
- pre-merge — CI: `tests/unit/test_placement_quiet.py` and `tests/unit/test_settings_load.py` read
  the switch on `fr-config` and the old file, write both in step and refuse two that differ;
  `tests/unit/test_hooks_isolation_required.py` and `tests/unit/test_isolation_decision_core.py`
  cover the hook library's new switch read, the `fr-config` worktree and stealth configuration clone
  as write targets, and the old-path fallback (the Hermes hook sources the same library), and
  `bun test` in `packages/fr-opencode-plugin` covers the plugin (R5, R6, R8, R13) (row
  `s1-switch-moved`).
- pre-merge — CI: `tests/unit/test_config_protection.py` answers enforced, not enforced (free-plan
  403, 404, no `pull_request` rule, unreadable, non-GitHub forge) from captured REST fixtures, and
  each executor refuses with the reason under quiet and runs under repo (R7) (row
  `s1-executable-config-protection`).
- pre-merge — CI: framework tests for location-stamped kinds and relocating hops (locators, no-op
  stamp, staged rename, validation at the destination, cross-space ordering with a refused push);
  per-kind migration tests under each placement, R12's refusal, the untracked allowlist, the
  profiles 1 → 3 chain and its crash window, and the quiet `.fr/` move (R10 to R12); the notice
  readers (R13) and the owed entry (R14) (row `s1-migration`).
- pre-merge — CI: `tests/unit/test_tripwire_shipped_defaults.py` and resolver tests for the order,
  the aliases and lenses taking no repo directory (R15, R16) (row `s1-shipped-defaults`).
- pre-merge — CI: triage tests for the cache repository syncing with no product clone, the move and
  each of its five rules, the stealth-workspace default, the one-repo default, the override and the
  mismatch set, `schema: 2`, and the privacy guard on each (R17 to R21) (row
  `s1-triage-state-home`).
- pre-merge — candidate: `tests/scenarios/` gains a configuration-homes scenario that installs the
  candidate, migrates fixture repos holding every old path under repo, quiet and stealth (with local
  bare remotes), and runs `fr settings paths`, `fr workflow check`, `fr verification list` and a
  triage collect against them (every row above).

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-24-s1-configuration-homes | `derio-net/super-fr` | `2026-11-24-s1-configuration-homes` | — |
