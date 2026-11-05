# Repo feature settings — design

**Date:** 2026-11-04
**Slug:** `2026-11-04-repo-feature-settings`
**Status:** design (fr-brainstorming, standalone)
**Repo:** `derio-net/super-fr` (single-repo change, two plans)

## 1. Background

super-fr assumes every repo it works in wants the whole paper trail: spec,
plan folder, journals, run cursor, acceptance matrix, Test Plan, gate labels,
fr-rendered PR body, `chore(fr):` commits, and pushes and draft PRs opened
without asking. Four situations make that wrong:

1. **Shared or third-party repos.** Teammates do not use super-fr, and fr's
   files, commits, labels and PR sections are noise to them, or leak process
   detail.
2. **Lighter process.** The full ceremony costs more than it returns in a small,
   throwaway, docs-only or infra repo.
3. **Different conventions.** The repo already keeps specs, tests or acceptance
   somewhere else.
4. **Forge-side quiet.** Labels, tracker issues, comments and PR-body sections
   are the most visible traces of all.

Today no setting addresses any of this. Two read-only surveys of the code
(2026-11-04) found:

- **Env vars.** The only skips are `FR_SKIP_MIGRATION` and `FR_SKIP_IDENTITY`.
- **The one partial knob.** `tracking: none` (the tracking service in
  `.devcontainer/fr-profiles.yaml`, read by `fr.services.resolve.resolve_tracking`)
  turns off three things: label sync (`fr/verification/labels.py`), awaiting-live
  labelling (`fr/run/closeout.py`) and backfill trackers (`fr/gatebackfill/apply.py`).
  It leaves the PR body, comments and every in-repo trace alone.
- **Paths.** About 44 modules hardcode `docs/superpowers/…` or
  `docs/acceptance/…`, as do the shell hooks. The registry locators
  (`fr.artifacts.registry`) are read only by migration, the trigger and
  `fr validate artifacts`.
- **The edit gate's detection.** It decides a repo is fr-enabled from a
  devcontainer profile or the existence of `docs/superpowers/plans/`
  (`plugins/super-fr/hooks/lib/fr-isolation-decision.sh`).

## 2. Philosophy analysis — which features may be quieted, and how

Each artifact does two jobs at once:

- it is the pipeline's **working memory**: the spec is the contract, the plan
  feeds the phase executors, and the journals carry handoffs and the review
  evidence;
- it is a **durable trace** in the product repo's history.

"Quiet" can therefore mean three different things:

- **off**: the artifact does not exist.
- **elsewhere**: it exists, but in the operator's own state repo, never in the
  product repo.
- **muted**: it exists, but no forge write or PR section shows it.

Here is how each feature sits against the pipeline today:

| Feature | Role | Absent today | Off is… |
|---|---|---|---|
| Acceptance matrix | A registry beside the pipeline | Degrades everywhere: self-review warns, the PR body says `None.`, debt reports it unavailable | **Coherent**: a policy the repo may decline |
| Test Plan | Post-merge owed steps, the archive hold | Never refused; only a near-miss heading is refused | **Coherent**: a policy |
| Gates | Close-out holds, labels | No gate lines means nothing holds | **Coherent**, except that a plan with ops forces `devops` |
| Spec | The contract: nothing after brainstorm reads anything else | The emit gate and spec-review evidence refuse | **Breaking**: fr-goal could not run |
| Plan folder | The phase executors' input; `fr apply` needs it on `origin/HEAD` | `implement`'s `needs: [spec, plan]` refuses | **Breaking** |
| Journals | The only proof that a phase was reviewed (`journal-check`, `review` and `findings` evidence) | The review gates refuse | **Breaking** |
| Run state | The cursor, the step records, the usage file | `fr run` has nothing to drive | **Breaking** |

**Decision.** The memory kinds may move *elsewhere* but never be *off*, and that
rule is structural: the schema cannot express it. The policy kinds may also be
*off*. An `off` is always reported as "disabled by repo setting" and never
rendered as "none", because a quiet repo must not read as a repo with nothing
owed.

Things that stay unsettable, by design:

- **Marking a PR ready and merging it.** Both stay the operator's (#814).
- **Force-pushing.** A squash folds only commits that are not yet pushed.
  Already-pushed history is pinned by the DevOps gate's `head_oid`, by the
  operator's review-ok guard and by `tests: ci`.

### Squash and the evidence chain

fr's evidence binds to **code trees**, not commits: suite logs and
`tests: reuse` through `fr/run/code_tree.py`, walks through
`fr/verification/walk.py`. Journals and step records are file contents, not
history. A squash keeps the final tree, so it orphans no evidence.

The only conflict is with history that is already pushed, which is why the one
squash mode is `squash-unpushed`.

## Requirements

R1. A repo's super-fr settings are read from two layers:

- a committed `.fr/settings.yaml`;
- an operator-side entry keyed by the repo's normalized `origin` URL, under
  `~/.config/fr/settings.d/`.

The operator-side entry overrides the committed one key by key. A key missing
from both takes its documented default, and every default is today's behaviour.

R2. `fr settings init` writes `.fr/settings.yaml`, or with `--operator` the
operator-side entry. Every key appears commented out at its default value, with
a comment stating its allowed values, what the default does, and what the
non-default trades away.

`fr settings show` prints the effective settings and each key's source
(`default`, `repo` or `operator`). With `--json`, it prints them for skills.

R3. The settings schema is closed. Every fr command that reads settings refuses
the following, naming the file and the key:

- an unknown key;
- an unknown value;
- a schema version newer than this `fr`.

`fr settings check` reports the same errors and exits non-zero.

R4. Each artifact kind takes one mode:

| Kinds | Allowed modes |
|---|---|
| `spec`, `plan`, `journals`, `runs` (the cursor, step records and usage files) | `repo` or `elsewhere` |
| `acceptance`, `test_plan`, `gates` | `repo`, `elsewhere` or `off` |

`off` for a memory kind is refused by the schema.

R5. `fr settings check` and `fr run start` refuse incoherent settings, naming the
conflict:

- `gates: off` in a repo whose live plan carries manual operations. `devops`
  cannot be off while ops exist, and `fr plan self-review` refuses such a plan
  under `gates: off`.
- `home` set in the committed layer.
- An `elsewhere` mode while no operator-side `home` is set.
- Changing an artifact kind's mode while a live run has artifacts of that kind
  in the other place.

R6. Under `acceptance: off`:

- fr writes no matrix, no reports, no matrix rule file and no matrix CI.
- `fr acceptance init`, `add` and `set-status` refuse, naming the setting.
- A step record carrying an `acceptance:` section is refused, naming the
  setting.
- Brainstorm presents no rows.
- Every surface that reports the matrix says "disabled by repo setting": self-review,
  PR body, `fr debt`, proportionality, `fr acceptance status` and the
  SessionStart nag.

R7. Under `test_plan: off`:

- The brainstorm writes no `## Test Plan`.
- `fr plan self-review` refuses a spec that carries one, naming the setting.
- Close-out and archive owe no Test Plan outcomes.
- The matrix staleness guard does not require rows that cite a Test Plan.

R8. Under `gates: off`:

- No gate is computed, labelled or held.
- `fr plan self-review` refuses a spec whose `## Verification` carries a `gate:`
  line, naming the setting.
- Verification strategies and walks still run: turning gates off does not turn
  verification off.

R9. `forge.labels`, `forge.comments` and `forge.issues` each take `on` (the
default) or `off`. Under `off`, fr makes no such forge write anywhere:

- label sync, gate-pass labels and awaiting-live labels;
- gate-pass comments;
- issues filed by `fr journal file` and `fr archive`, the debt issue, and
  backfill trackers.

A leftover that would have been filed stays recorded in the journal, and
`deliver` accepts it as recorded, as it does under `tracking: none`.

R10. `forge.pr_body` is `full` (the default) or `minimal`. Under `minimal`:

- The live PR carries only a plain summary: no fr marker, no fr section, no cost
  or proportionality table.
- fr renders the full body to the run's records.
- `deliver`'s required-section gate checks that rendered copy, and checks the
  live body only for the absence of fr markers.

R11. `git.push` and `git.pr` each take `auto` (today's behaviour) or `ask`.
Under `ask`, every push or PR creation fr performs is an operator gate on the
run cursor. It proceeds only on an operator answer given after the gate opened.
Marking a PR ready and merging it are not settable, and stay the operator's.

R12. A new `fr push` command performs every push fr-driven work makes. The
skills call it instead of bare `git push`, and it applies R11, R13 and R14 in
one place.

R13. `git.history` is `keep` (the default) or `squash-unpushed`. Under
`squash-unpushed`, `fr push`:

- folds the commits not yet on the remote branch into one commit before
  pushing;
- never rewrites a pushed commit and never force-pushes;
- leaves the code tree unchanged, so tree-keyed evidence stays valid.

R14. `git.commit.with_issue` and `git.commit.without_issue` are commit-subject
templates over a closed placeholder set: `{type}`, `{scope}`, `{summary}` and
`{issue}`. An unknown placeholder is refused, and so is `{issue}` in the
without-issue template.

- fr's own commits use them.
- The dispatch briefs and `fr pickup` carry them to the agents.
- `fr push` refuses to push an unpushed commit whose subject does not match the
  template that applies: with-issue when the run is tied to an issue.
- Under `squash-unpushed`, fr composes the squashed subject from the template
  itself.

R15. Every path fr reads or writes for an artifact kind is resolved through one
resolver, keyed by kind and by the effective mode. This covers the Python
modules, the shell hooks and the shipped CI templates. A tripwire refuses a new
hardcoded artifact path outside it.

R16. Under `elsewhere`, an artifact kind lives in the operator's state repo:
`home`, set operator-side only, in a directory per product repo.

- fr fetches it before reading and pushes it after writing.
- No file of that kind, and no `chore(fr):` commit for it, reaches the product
  repo.
- The privacy guard (`fr.triage.privacy.leak_risk`) refuses a state repo that is
  more visible than the product repo.

R17. A repo with effective settings from either layer counts as fr-enabled for
the isolation edit gate and the bash guard, beside the existing profile and
plans signals. The edit gate therefore still protects a base clone whose plans
live elsewhere.

R18. Every shipped skill that would write, nag about or render a quieted
feature reads the effective settings (`fr settings show --json` or its brief),
instead of assuming the defaults.

R19. Delivery is two plans, two PRs:

- **Plan 1:** R1–R14 and R18. Here the schema accepts `elsewhere`, but
  `fr settings check` and `fr run start` refuse it as "not yet available".
- **Plan 2:** R15–R17, which lifts that refusal.

## 3. Design

### A. The settings file and its layers (R1–R3)

```yaml
# .fr/settings.yaml — every key optional; missing = default (today's behaviour)
schema: 1
artifacts:
  spec:        repo        # repo | elsewhere
  plan:        repo        # repo | elsewhere
  journals:    repo        # repo | elsewhere
  runs:        repo        # repo | elsewhere   (cursor, step records, usage)
  acceptance:  repo        # repo | elsewhere | off
  test_plan:   repo        # repo | elsewhere | off   (elsewhere = the spec's home)
  gates:       repo        # repo | elsewhere | off   (elsewhere = gate state in home, not labels)
forge:
  labels:   on             # on | off
  comments: on             # on | off
  issues:   on             # on | off
  pr_body:  full           # full | minimal
git:
  push:    auto            # auto | ask
  pr:      auto            # auto | ask   (always a draft; ready/merge are never fr's)
  history: keep            # keep | squash-unpushed
  commit:
    with_issue:    "{type}({scope}): {summary} (#{issue})"
    without_issue: "{type}({scope}): {summary}"
# home: <owner/repo>       # operator-side ONLY — refused in this file
```

- **Module.** A new `fr/settings/` package: `model.py` (a closed pydantic model,
  `extra="forbid"`, with `schema_version`), `load.py` (the two layers, merge with
  provenance), `check.py` (R5's coherence rules as data), and `render.py` (the
  commented `init` output, generated from the model's field docs so that the
  comments cannot drift from the schema).
- **CLI.** `commands/settings_cmd.py`.
- **The operator layer** is `~/.config/fr/settings.d/<host>--<owner>--<repo>.yaml`,
  keyed by the normalized `origin` remote. A repo with no remote has no operator
  layer.
- **Trigger exemption.** `settings` joins `READ_ONLY_COMMANDS`: `init` writes
  only its own file, never a registered artifact.
- **Is `.fr/settings.yaml` an artifact?** No. It is configuration like
  `.fr/triage.yaml`, so it is not a registry kind, and its `schema` key is
  validated by the loader.

### B. Policy off (R6–R8)

Each `off` is applied at the place that already handles the feature's absence:

- the matrix loaders and `record/apply.py`'s `_acceptance_writes`;
- `spec.py`'s Test Plan reader;
- `verification/exit.py`'s gate computation.

A single `fr.settings.disabled(repo_root, feature)` predicate is the one
question each site asks. What changes is the *reporting*: every "None."/silent
branch these sites take for an absent feature is split into "absent" and
"disabled by repo setting".

### C. Forge quiet (R9–R10)

`forge.labels`, `forge.comments` and `forge.issues` extend the three existing
`tracking: none` checks, and add the sites that check does not cover today:

- gate-pass comments;
- `fr journal file` and archive filing;
- `fr debt issue`;
- the awaiting-live and close-out commands that the triage driver runs.

`tracking: none` keeps meaning all three are off. Each site asks one predicate,
`fr.settings.forge_allows(repo_root, "labels")`.

`pr_body: minimal` changes `_deliver_pr_gate` (`commands/run_cmd.py`):

- It renders `pr-body.md` as today.
- It checks `REQUIRED_SECTIONS` against the rendered file.
- It reads the live body back only to refuse an fr marker in it.

### D. Push, PR, history, templates (R11–R14)

- **`fr push`** (`commands/push_cmd.py`) is the one push path. It:
  1. resolves the run from the branch;
  2. under `push: ask`, refuses unless the run's open `push` gate was answered
     by the operator after it opened, printing the gate to answer;
  3. under `squash-unpushed`, soft-resets to the remote branch's tip and commits
     once, with a templated subject, refusing if the remote is not an ancestor
     of HEAD;
  4. checks every unpushed subject against the template;
  5. runs `git push`.

  The skills (fr-goal §6/§8, fr-debugging, fr-execute) switch from `git push`
  to `fr push`.
- **PR creation** stays where the skills already do it. Under `pr: ask`, the
  `deliver` brief (and `tests: ci`'s early draft) carries an operator gate to
  answer before `gh pr create --draft` runs. `deliver` then refuses a PR opened
  before that answer.
- **The operator gate** reuses the cursor's existing operator-gate machinery,
  the same predicate `brainstorm` uses (`operator_answered_since`), as a
  per-push gate record in the step record. It adds no new step id: a new step
  would drift every live run's shape.
- **fr's own commits** go through `records_commit.commit_records` and
  `artifacts/commit.commit_paths`, which take the subject from the template
  with `type=chore` and `scope=fr`. The migrate gate's
  `chore(fr): migrate …` uses the same path.

### E. Elsewhere (R15–R17, plan 2)

- **The resolver.** A new `fr.artifacts.paths` resolver is the only producer of
  an artifact path. `ArtifactKind.locator` becomes its repo-mode output, and the
  ~44 hardcoded constants are replaced by calls to it.
- **Shell hooks** get the same answers from `fr settings paths --shell`, cached
  per session.
- **The state repo backend** reuses `fr/triage/state_ref.py`'s mechanics:
  fetch-before-read, a compare-and-swap push after every write, and the privacy
  guard. Each product repo gets its own directory,
  `<host>--<owner>--<repo>/docs/superpowers/…`, so that the layout under it
  mirrors repo mode and archive, migration and validation work on it
  unchanged.
- **Dispatch.** `fr apply`'s reachability gate reads `elsewhere` artifacts on
  the state repo's default branch instead of `origin/HEAD`.
- **Detection (R17).** The isolation decision script adds a third fr-enabled
  signal: a `.fr/settings.yaml`, or an operator-side entry for this remote.

### F. Skills and mirrors (R18)

The fr-goal, fr-brainstorming, fr-plan, fr-execute, fr-debugging and
fr-acceptance skills each gain one short clause: "read
`fr settings show --json` (or the brief's `settings`); a feature `off` is not
written, and is reported as disabled". Both mirror generators,
`sync-opencode.py` and `sync-hermes.py`, are re-run.

## 4. Non-goals

- **Adapters to external systems** (Jira, test-case tools, ADR directories). For
  the "different conventions" case, the repo turns the feature `off` and keeps
  its own system. An adapter is a later spec.
- **A setting that marks a PR ready, merges it or force-pushes.**
- **Relocating archived artifacts** under `docs/superpowers/implemented/`.
  `elsewhere` applies to new and live artifacts; an archive stays where it was
  written.
- **A `fr settings move` that relocates a live run's artifacts.** R5 refuses
  the mode change instead.

## 5. Artifacts, versions, mirrors

- **No registered artifact kind changes shape in plan 1.** `.fr/settings.yaml`
  is configuration, not a kind.
- **Plan 2** changes no shape either. It changes where a kind lives, and the
  registry's locators become the resolver's repo-mode output.
- **Change fragments.** Each PR adds a `minor` fragment.
- **Explainers.** `docs/explainers/01-fr-goal.md` gains a "Quiet repos"
  paragraph. Regenerate the `.html`, per the explainers-currency rule.

## Verification

strategy: candidate
gate: repo-settings-quiet-repo-live=tester
- repo-settings-quiet-repo-live: live — only a real forge and a real fr-goal run in a quiet repo show that no fr label, comment, issue or PR-body section lands; walked after release

## Test Plan

_(post-merge, operator-driven)_

1. [tester] In a scratch repo on a real forge, set operator-side
   `forge: {labels: off, comments: off, issues: off, pr_body: minimal}` and
   `git: {push: ask, pr: ask, history: squash-unpushed}`. Run a small `/fr-goal`
   to delivery, then confirm:
   - fr asked before each push and before the PR;
   - the pushed branch shows one commit per push, matching the template;
   - the PR has no fr labels, comments or marker sections;
   - no issue was filed.

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
