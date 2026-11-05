# Repo feature settings and artifact placements — design

**Date:** 2026-11-04
**Slug:** `2026-11-04-repo-feature-settings`
**Status:** design (fr-brainstorming, standalone)
**Repo:** `derio-net/super-fr` (single-repo change, three plans)

## 1. Background

super-fr assumes every repo it works in wants the whole paper trail, all of it
on the feature branch:

- spec, plan folder, journals, run cursor;
- the acceptance matrix with three committed reports;
- a Test Plan;
- gate labels and an fr-rendered PR body;
- `chore(fr):` commits, and pushes and draft PRs opened without asking.

Four situations make that wrong, and the operator named all four:

- **Shared or third-party repos.** Teammates don't use super-fr. fr's files,
  commits, labels and PR sections are noise to them, or leak process detail.
- **Lighter process.** The ceremony costs more than it returns.
- **Different conventions.** The repo keeps specs, tests or acceptance
  elsewhere.
- **Forge-side quiet.** Labels, issues, comments and PR sections are the most
  visible traces of all.

Two read-only surveys of the code (2026-11-04) found:

- **No setting addresses this.** The only env skips are `FR_SKIP_MIGRATION` and
  `FR_SKIP_IDENTITY`.
- **One partial knob exists.** `tracking: none`, the tracking service in
  `.devcontainer/fr-profiles.yaml`, read by
  `fr.services.resolve.resolve_tracking`, silences three things:
  - label sync (`fr/verification/labels.py`);
  - awaiting-live labels (`fr/run/closeout.py`);
  - backfill trackers (`fr/gatebackfill/apply.py`).

  It leaves the PR body, comments and every in-repo trace alone.
- **Artifact paths are hardcoded.** About 44 modules and the shell hooks
  hardcode `docs/superpowers/…` or `docs/acceptance/…`. The registry locators
  (`fr.artifacts.registry`) are read only by migration, the trigger and
  `fr validate artifacts`.
- **The edit gate's detection depends on those paths.** It calls a repo
  fr-enabled when it has a devcontainer profile or a `docs/superpowers/plans/`
  directory (`plugins/super-fr/hooks/lib/fr-isolation-decision.sh`).
- **Every feature edits the matrix.** It is one shared `matrix.yaml`, and its
  three reports are committed renders that every feature regenerates.
  github.com shows a committed `.html` as source, so only `report_linked.md`
  ever rendered for a browsing reader.

## 2. Philosophy analysis

Each artifact does two jobs:

- it is the pipeline's **working memory**: the spec is the contract, the plan
  feeds the phase executors, and the journals are the only proof a phase was
  reviewed;
- it is a **durable trace** in the product repo.

The surveys sort the features accordingly:

| Feature | Absent today | May be off? |
|---|---|---|
| Acceptance matrix | Degrades everywhere: self-review warns, the PR body says `None.`, debt reports it unavailable | **Yes**: a policy a repo may decline |
| Test Plan | Never refused; only a near-miss heading is | **Yes**: a policy |
| Gates | No gate lines means nothing holds | **Yes**, except that a plan with ops forces `devops` |
| Spec, plan, journals, run state | fr-goal's emit, `needs` and review-evidence gates refuse | **No**: fr-goal cannot run without them |

The decisions that follow from this:

1. **Memory kinds are never off.** They may only be *placed* elsewhere, and
   the settings schema has no key for turning them off. The invariant is
   structural: it fails at authoring time, not mid-run.
2. **A policy kind that is off is reported, never silent.** It shows as
   "disabled by repo setting", never as "none", because a quiet repo must not
   read as a repo with nothing owed.
3. **Some things are never settable:** marking a PR ready, merging it, and
   force-pushing.
4. **Squash only touches what is not yet pushed.** fr's evidence binds to code
   trees, not commits:
   - suite logs and `tests: reuse` through `fr/run/code_tree.py`;
   - walks through `fr/verification/walk.py`.

   A squash keeps the tree, so it orphans none of that evidence. What it
   cannot do is rewrite pushed history, which three things pin: the DevOps
   gate's `head_oid` (`fr/ops/gate.py`), the operator's review-ok guard, and
   `tests: ci`.
5. **Placement must travel with the work.** A placement that lives on one
   host fails on the next one: a fresh host would see no settings and
   silently write traces into the repo meant to stay clean. So every
   placement's switch and settings live with its artifacts, and there is no
   host-local settings layer.

## Requirements

### Placements and settings

R1. Every artifact fr writes has one of three placements:

| Placement | Where the artifacts live |
|---|---|
| `repo` (the default; today's behaviour) | the feature branch |
| `quiet` | one long-lived branch named `fr` in the same remote, each feature under its own unique path |
| `stealth` | a branch of a separate tracking repo; nothing reaches the target repo |

One path resolver, keyed by kind and placement, produces every artifact path.
It covers the Python modules, the shell hooks and the shipped CI templates, and
a tripwire refuses a hardcoded artifact path outside it.

R2. Settings live with the placement, and there is no host-local layer:

| Placement | Settings file |
|---|---|
| `repo` | an optional committed `.fr/settings.yaml` on the default branch |
| `quiet` | `settings.yaml` at the root of the `fr` branch |
| `stealth` | the tracking repo, one file per target |

A key missing from the file takes its documented default, and every default is
today's behaviour.

R3. Each settings command works on the active placement's file:

- `fr settings init` writes that file with every key present but commented out
  at its default, with a comment giving its allowed values, what the default
  does, and what the non-default trades away. `init --quiet` creates the `fr`
  branch; `init --stealth` needs `--tracking` and `--target`.
- `fr settings show` prints the effective settings and each key's source.
  `--json` prints them for skills.
- `fr settings check` validates the file.

R4. The settings schema is closed. Every fr command that reads settings refuses
the following, naming the file and the key:

- an unknown key;
- an unknown value;
- a schema version newer than this `fr`.

The policy kinds `acceptance`, `test_plan` and `gates` take `on` or `off`. The
memory kinds have no key at all.

R5. `fr settings check` and `fr run start` refuse incoherent settings, naming
the conflict:

- `gates: off` when a live plan carries manual operations;
- any forge key other than quiet under `stealth`, which forces forge quiet.

`fr plan self-review` also refuses a plan that carries ops under
`gates: off`.

### Policy off

R6. Under `acceptance: off`:

- fr writes no matrix fragment, no report and no matrix CI.
- `fr acceptance add` and `set-status`, and any record's `acceptance:`
  section, are refused, naming the setting.
- Brainstorm presents no rows.
- Self-review, the PR body, `fr debt`, proportionality, `fr acceptance status`
  and the SessionStart nag all say "disabled by repo setting".

R7. Under `test_plan: off`:

- The brainstorm writes no `## Test Plan`.
- `fr plan self-review` refuses a spec that carries one, naming the setting.
- Close-out and archive owe no Test Plan outcomes.
- The matrix staleness guard does not require rows that cite a Test Plan.

R8. Under `gates: off`:

- No gate is computed, labelled or held.
- `fr plan self-review` refuses a spec whose `## Verification` has a `gate:`
  line, naming the setting.
- Verification strategies and walks still run.

### Forge quiet

R9. `forge.labels`, `forge.comments` and `forge.issues` each take `on` (the
default) or `off`. Under `off`, fr makes no forge write of that kind
anywhere:

- labels: label sync, gate-pass labels, awaiting-live labels;
- comments: gate-pass comments, the report comment;
- issues: `fr journal file` and archive filing, the debt issue, backfill
  trackers.

A leftover that would have been filed stays recorded in the journal, and
`deliver` accepts it as recorded, as it does under `tracking: none`.
`tracking: none` keeps meaning all three are off.

R10. `forge.pr_body` is `full` (the default) or `minimal`. Under `minimal`:

- The live PR carries only a plain summary, with no fr marker, fr section,
  cost table or proportionality table.
- fr renders the full body into the run's records.
- `deliver`'s required-section gate checks that rendered copy, and checks the
  live body only for the absence of fr markers.

### Git policy

R11. `git.push` and `git.pr` each take `auto` (today's behaviour) or `ask`.
Under `ask`, every push or PR creation is an operator gate on the run cursor,
and it proceeds only on an operator answer given after the gate opened.
Marking a PR ready and merging it are not settable.

R12. A new `fr push` command performs every push fr-driven work makes. The
skills call it instead of bare `git push`, and it applies R11, R13 and R14 in
one place.

R13. `git.history` is `keep` (the default) or `squash-unpushed`. Under
`squash-unpushed`, `fr push`:

- folds the commits not yet on the remote branch into one commit before
  pushing;
- never rewrites a pushed commit and never force-pushes;
- leaves the code tree unchanged.

R14. `git.commit.with_issue` and `git.commit.without_issue` are subject
templates over a closed placeholder set: `{type}`, `{scope}`, `{summary}` and
`{issue}`. An unknown placeholder is refused, and so is `{issue}` in the
without-issue template.

- fr's own commits use the templates.
- The dispatch briefs and `fr pickup` carry them to the agents.
- `fr push` refuses an unpushed commit whose subject does not match the
  template that applies.
- Under `squash-unpushed`, fr composes the subject itself.

R15. Every shipped skill that writes, nags about or renders a configurable
feature reads the effective settings (`fr settings show --json`, or its
brief) instead of assuming the defaults.

### Acceptance model (every placement)

R16. Acceptance rows live in per-feature fragments, and each row is owned by
the feature that created it. A later feature that changes existing behaviour
changes an existing row only by appending an amendment record to its own
fragment, never by writing to another feature's fragment. The amendment
operations are:

- `reword`;
- `set-status`;
- `add-level`;
- `drop-level`;
- `retire`.

R17. The effective matrix is never stored. It is the fold of the fragments of
merged features, in merge order; a branch's view also includes its own pending
amendments. An abandoned feature's amendments never apply.

Each amendment names the row revision it was based on. An amendment whose base
is no longer the row's effective revision is refused by `fr acceptance check`
and by `deliver` until it is re-amended against the new revision.

R18. Rows reference fr artifacts logically (`spec:<slug>#R<n>`,
`plan:<slug>`), resolved through R1's resolver. Code references keep
`<repo>:<path>#<test>`. A placement move therefore never rewrites a row.

R19. `fr migrate artifacts --yes` migrates an existing repo to the fragment
model:

- It splits `docs/acceptance/matrix.yaml` into fragments by origin spec.
  Rows without exactly one origin go to a `legacy` fragment.
- It converts path references into logical ones.
- It removes the committed reports.

This is a shape change for the `matrix` kind: it ships a stamp bump, a frozen
reader for the old shape, and a structure validator.

R20. Reports are derived, never committed:

- `fr acceptance report [--open]` renders them locally.
- The README's "Viewing the acceptance report" section and `fr --help` name
  that command.
- The CI that fr scaffolds publishes a job summary on every PR (GitHub), or an
  exposed artifact (GitLab), and publishes the HTML report to Pages from the
  default branch.
- The README carries a link or badge to that published report.

R21. Before scaffolding Pages publishing or a Pages badge, fr checks that the
published site would be no more visible than the repo: either the repo is
public, or the forge reports access-controlled Pages. If neither holds, fr
scaffolds no Pages job, points the README badge at the latest default-branch
CI run instead, and prints which case it chose and why.

R22. `forge.report_comment` takes `off` (the default) or `on`. When on, CI
keeps one PR comment carrying the Markdown report. It requires
`forge.comments: on`, and it is refused under `quiet` and `stealth`.

### Quiet and stealth

R23. Under `quiet`:

- **The switch.** The `fr` branch on `origin` carries a root `settings.yaml`
  with `placement: quiet`. A branch named `fr` without that file is ignored.
- **Fail closed on the switch.** fr checks `origin` for the switch before any
  write, and refuses to write if `origin` is unreachable.
- **Append-only updates.** Every update to the `fr` branch is one commit that
  touches only that feature's path, never rewriting or deleting it.
- **Atomic with the code.** When the `fr` branch and the feature branch both
  move, they are pushed together with `git push --atomic`.
- **Nothing on the product branches.** No fr artifact and no `chore(fr):`
  commit reaches the default branch or any feature branch.

R24. A stealth run is chosen per run, never by repo settings. There are two
ways to start one:

- invoke fr-goal or fr-debugging with `mode=stealth`, naming the tracking repo
  and branch;
- start from the tracking repo with `mode=stealth`, naming the local target
  repo.

The target needs no `.fr/settings.yaml`.

fr refuses, before any write, when the tracking repo or branch is missing or
unreachable. No fr file, commit or forge write reaches the target. The privacy
guard (`fr.triage.privacy.leak_risk`) refuses a tracking repo that is more
visible than the target. The run is resumed from the tracking repo, which
records the target's remote and branch.

R25. Archiving depends on the placement:

- under `quiet` and `stealth`, it appends a `merged: <sha>` record to the
  feature's path and moves nothing;
- under `repo`, it keeps `implemented/`.

R26. The isolation edit gate and the bash guard treat a repo as fr-enabled in
two more cases, beside the profile and plans signals:

- it carries a valid `fr` branch switch;
- a live stealth run's pipeline sentinel names it as its target.

### Moving between placements

R27. `fr placement move --to repo|quiet|stealth [--tracking <repo>@<branch>]`
moves a whole repo, including archived features and the shared artifacts of
live runs. `--run <id>` moves a single stealth run.

- **Steps.** Copy, then verify, then switch, then remove. Verify means the
  destination's folds (matrix, journal states) and `fr validate artifacts`
  equal the source's.
- **Restartable.** Every step is idempotent and resumable after a crash.
- **History is not erased.** A move out of `repo` removes the files from the
  default branch through a PR, and prints that git history still holds them.
- **Precondition.** A move is refused while any workspace has uncommitted
  work.

R28. A feature branch whose artifacts do not match the repo's current placement
must migrate before it can merge.

- **Migration.** The CLI-entry artifact gate migrates such a branch in a valid
  workspace, as its own commit, exactly as it migrates a stale stamp.
- **Refusal.** Until then, `fr push` and `deliver` refuse it. Where fr's CI
  exists, so does the `validate-artifacts` job.

### Delivery

R29. Three plans, three PRs:

| Plan | Scope | Requirements |
|---|---|---|
| 1 | Settings core in `repo` placement | R2–R15, `repo` only |
| 2 | The acceptance model and derived reports | R16–R22 |
| 3 | The resolver, quiet, stealth and moves | R1, R23–R28 |

Until plan 3 lands, the schema accepts `quiet` and `stealth`, but
`fr settings check` refuses them as "not yet available".

## 3. Design

### A. Settings (R2–R5)

```yaml
# .fr/settings.yaml (repo) · <fr branch>/settings.yaml (quiet) · <tracking>/<target-id>/settings.yaml (stealth)
schema: 1
placement: repo            # repo | quiet | stealth   (must match where this file lives)
artifacts:                 # policy kinds only — spec/plan/journals/runs have no key: never off
  acceptance: on           # on | off
  test_plan:  on           # on | off
  gates:      on           # on | off
forge:
  labels:   on             # on | off
  comments: on             # on | off
  issues:   on             # on | off
  pr_body:  full           # full | minimal
  report_comment: off      # off | on   (needs comments: on; refused under quiet/stealth)
git:
  push:    auto            # auto | ask
  pr:      auto            # auto | ask   (always a draft; ready/merge are never fr's)
  history: keep            # keep | squash-unpushed
  commit:
    with_issue:    "{type}({scope}): {summary} (#{issue})"
    without_issue: "{type}({scope}): {summary}"
```

- **Module.** A new `fr/settings/` package:
  - `model.py`: a closed pydantic model, `extra="forbid"`;
  - `load.py`: placement discovery (R23/R24), then the one file;
  - `check.py`: R5's rules, as data;
  - `render.py`: `init`'s commented output, generated from the field docs so
    the comments cannot drift from the schema.
- **Trigger exemption.** `settings` joins `READ_ONLY_COMMANDS`, because `init`
  writes only its own file.
- **Callers ask predicates, not files.** `fr.settings.disabled(root, feature)`
  and `fr.settings.forge_allows(root, kind)` are the only questions callers
  ask.

### B. Policy off and forge quiet (R6–R10)

- **Where off applies.** Each `off` is applied where the feature's absence is
  already handled:
  - the matrix loaders and `record/apply.py` `_acceptance_writes`;
  - `spec.py`'s Test Plan reader;
  - `verification/exit.py`.

  Every branch that today prints "None." or stays silent for an absent feature
  is split into "absent" and "disabled by repo setting".
- **Where forge quiet applies.** The forge keys extend the three existing
  `tracking: none` checks to the sites that check misses: gate-pass comments,
  `fr journal file`/archive filing, `fr debt issue`, and the triage driver's
  close-out commands.
- **`pr_body: minimal`** changes `_deliver_pr_gate` (`commands/run_cmd.py`) to
  check `REQUIRED_SECTIONS` against the rendered `pr-body.md` instead of the
  live body.

### C. Git policy (R11–R14)

- **`fr push`** (`commands/push_cmd.py`) runs, in order:
  1. Resolve the run from the branch.
  2. Under `push: ask`, require an operator answer given after the per-push
     gate opened.
  3. Under `squash-unpushed`, soft-reset to the remote tip and commit once,
     refusing unless the remote tip is an ancestor of HEAD.
  4. Check every unpushed subject against the template.
  5. Under `quiet`, push the `fr` branch atomically with the feature branch.
  6. Push.

  fr-goal §6/§8, fr-debugging and fr-execute switch from `git push` to
  `fr push`.
- **The ask gates reuse what exists.** `push: ask` and `pr: ask` use the
  cursor's existing operator-answer predicate (`operator_answered_since`), as
  gate entries in the step record. No new step id is added, because a new step
  would drift every live run's shape.
- **fr's own commits.** `records_commit.commit_records` and
  `artifacts/commit.commit_paths` take their subject from the template, with
  `type=chore` and `scope=fr`.

### D. Acceptance fragments (R16–R22)

- **Repo-placement layout.** Fragments sit at
  `docs/acceptance/features/<spec-slug>.yaml`. Each holds the rows the feature
  created and the amendments it made:

  ```yaml
  schema_version: 1
  feature: 2026-11-04-repo-feature-settings
  rows:
    - {id: repo-settings-layered, capability: …, acceptance: …, origin: [spec:2026-11-04-repo-feature-settings#R2], …}
  amendments:
    - {row: acceptance-pipeline-rows, op: reword, base: 7, acceptance: …, why: …}
  ```
- **The fold.** It runs over features in merge order. That order comes from
  `git log --first-parent` of the default ref, or from the `merged:` records
  under quiet and stealth.
- **Revisions.** A row's revision is the count of amendments applied to it.
- **One fold, many callers.** `fr acceptance check`, `status`, `report`,
  `debt`, self-review, the PR body and close-out all read `fold()`, never a
  file.
- **The migration.** `matrix_fragments` gets a frozen `MatrixV<n>` reader,
  splits the existing matrix by origin spec, converts references, deletes the
  three reports, and reports its counts.
- **The rule file follows.** The repo-local `.claude/rules/acceptance-matrix.md`
  and the scaffolded rule are rewritten to match.
- **CI templates.** `fr/acceptance/ci.py`'s templates gain the per-PR summary
  or artifact step, the default-branch Pages job, and a README badge,
  generated only after the R21 visibility check.

### E. Placements (R1, R23–R28)

- **The resolver.** A new `fr.artifacts.paths` resolver replaces the hardcoded
  constants, and `ArtifactKind.locator` becomes its `repo` output. The shell
  hooks read `fr settings paths --shell`, cached per session.
- **Quiet reads and writes the `fr` branch through a second worktree**
  (`~/.cache/fr/worktrees/<repo>/fr`). The resolver returns paths into it, so
  validation and the folds work unchanged.
- **Stealth reuses the triage state machinery** (`fr/triage/state_ref.py`):
  fetch-before-read and a compare-and-swap push. Each target gets its own
  directory, `<host>--<owner>--<repo>/`, laid out exactly like quiet's.
  Ordering: the code is pushed first, and the state records the product head
  it describes. On resume, fr reconciles the two:
  - they are equal → proceed;
  - the branch is ahead → the last step's bookkeeping was lost; redo that step;
  - the state is ahead → refuse, naming the missing SHA.
- **Moves and drift.** `fr placement move` (`commands/placement_cmd.py`)
  implements R27. Branch drift (R28) is a fifth condition in
  `fr.artifacts.trigger`, sharing its contexts table, its no-commit-on-default
  rule and its own-commit rule.

## 4. Non-goals

- **Adapters to external systems** (Jira, test-case tools, ADR directories).
  For the "different conventions" case, the repo turns the feature `off`.
- **A host-local settings layer.**
- **A setting that marks a PR ready, merges it, or force-pushes.**
- **Moving a stealth run between two tracking repos.**

## 5. Artifacts, versions, mirrors

- **Plan 1** changes no artifact shape. `.fr/settings.yaml` is configuration,
  not a registered kind.
- **Plan 2** changes the `matrix` kind's shape (R19): a stamp bump, a
  migration, a frozen reader and a validator, and it runs
  `fr migrate artifacts --yes` on this repo in the same PR.
- **Plan 3** adds no kind. It changes where kinds live.
- **Every plan:**
  - adds a `minor` change fragment;
  - re-runs `sync-opencode.py` and `sync-hermes.py` after its skill edits;
  - updates `docs/explainers/01-fr-goal.md` and its `.html` (placements, quiet
    repos, derived reports).

## Verification

strategy: candidate
gate: repo-settings-quiet-repo-live=tester
- repo-settings-quiet-repo-live: live — only a real forge and real fr-goal runs in quiet and stealth placements show that no fr trace reaches the product repo or its forge; walked after release

## Test Plan

_(post-merge, operator-driven)_

1. [tester] **Quiet.** On a real forge, create a scratch repo and run
   `fr settings init --quiet` with:
   - `forge: {labels: off, comments: off, issues: off, pr_body: minimal}`;
   - `git: {push: ask, pr: ask, history: squash-unpushed}`.

   Run a small `/fr-goal` to delivery, then confirm:
   - fr asked before each push and before the PR;
   - the feature branch shows one templated commit per push and no fr files;
   - the `fr` branch holds the feature's directory;
   - the PR has no fr labels, comments or marker sections.
2. [tester] **Stealth.** From a tracking repo, run `/fr-goal mode=stealth`
   against a second scratch target. Interrupt it after phase 1, then resume it
   on another host from the tracking repo. Confirm that the target carries no
   fr file, commit or forge write, and that the run resumed where it stopped.

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
