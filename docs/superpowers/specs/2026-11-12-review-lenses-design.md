# Review lenses — design

## 1. Goal

A phase's code review in the `fr-goal` flow is a general review: the dispatched
reviewer is told to find what is wrong, incomplete or worse than it needs to be.
That stays. What the flow lacks is a review of the **whole feature** under a
named concern. Security, test depth, needless complexity and error handling are
looked at only when a phase reviewer happens to think of them, one phase at a
time, and nothing records whether anyone did.

This feature adds **lenses** and a **lens review**. A lens is an id plus the
instruction text a reviewer is given. During a run, any agent at any step may
add a lens to the feature when it sees a reason; a repo's path rules add one
when the feature changes a path they name. The lenses accumulate. Before
`deliver`, a new step dispatches one reviewer per accumulated lens over the
whole change; fr refuses the step while a lens is unaccounted for; and the pull
request shows which lenses ran, why, and what they found.

The per-phase review is not changed and is never handed a lens, so its freedom
to report anything is untouched.

Of the four quality areas the brainstorm identified, this covers review lenses
and most of the whole-change review. A reuse search at plan time and a reader's
guide in the PR body are separate specs and are not designed here.

## 2. Background (read from the code)

- **The flow.** `plugins/super-fr/workflows/fr-goal.yaml` runs `implement` as a
  grouped `for_each: phase` (`implement-phase`, `review-phase`), then
  `journal-check` (a `cli` step), then `deliver`. `fr-goal-light.yaml` has the
  same tail.
- **Review evidence.** `review-phase` resolves `done` only with a `kind=review`
  plan-journal entry, a dispatched reviewer's id, and no open finding against
  the phase. `fr/run/review_return.py` gives the reviewer an exact rule in the
  brief (`review_findings`) and parses a fenced `review-findings` block out of
  its return; `run_cmd.py` refuses the resolve when a reviewer's block is
  missing, malformed or disagrees with the plan journal, and supports several
  reviewers on one unit. Where fr cannot read the return the check is noted
  `unobserved=reviewer-return`.
- **Scope rule.** A reviewer tags each finding `in` (this change is wrong,
  incomplete or worse than it needs to be) or `out` (true, not caused by this
  change). The orchestrator fixes every in-scope finding and files the rest
  (`fr journal resolve --state out-of-scope`).
- **Journals.** `fr.journal.model.JournalEntry` is closed-world with a closed
  `kind` vocabulary; the `journal` artifact kind is at version 3, and each new
  entry kind so far moved it (2, 3). Every agent step of the flow emits a
  journal (`journal:spec` or `journal:plan`) through its step record.
- **Step drift.** `run_cmd._check_step_drift` refuses a run whose manifest
  gained or lost a step id since `fr run start`; `fr run reshape` inserts a new
  step pending and keeps every unit. Adding `journal-check` did exactly this.
- **Repo-over-shipped resolution.** Workflows and verification strategies ship
  under `plugins/super-fr/` with a generated copy in the `fr` wheel; a repo may
  add or override them. Neither is mirrored to OpenCode or Hermes.
- **The PR body.** `fr/record/pr_body.py` renders it at `deliver` from the
  cursor and the journals; under `forge.pr_body: minimal` the full render is
  kept in the durable `<run-id>.pr-body.md` only.
- **The diff.** `fr plan proportionality` already defines a feature's diff:
  `git merge-base HEAD <base>` to `HEAD`, with fr's own artifacts
  (`docs/superpowers/**`, `docs/acceptance/**`) exempt.

The outside datapoint the operator supplied is an essay arguing that
agent-written code yields a fragile codebase. Its named failure modes are tests
that assert trivial behaviour or one user type, more helpers than the problem
needs, code that "solves what fits in the context window" and misses long-term
issues, small quality issues that accrue because review is skimmed, and errors
nobody instrumented. The four shipped lenses are those concerns plus security,
which the operator added; reviewing the whole change at once answers the
context-window point.

## Requirements

R1. fr ships four lenses: `security`, `tests`, `simplicity` and `errors`. Each has an id, a one-line title and the instruction text a reviewer is given.
R2. A repo may, in `.fr/lenses.yaml`, add a lens of its own, replace a shipped lens's title and instruction text, and disable a shipped lens. The repo's **effective lenses** are the shipped ones not disabled, with replacements applied, plus the repo's own.
R3. `fr lenses list` prints the effective lenses and where each comes from; `fr lenses show <id>` prints one lens's instruction text; `fr lenses check` fails a `.fr/lenses.yaml` that is unreadable, names an unknown key, disables or requires a lens that does not exist, or defines a lens with no instruction text. The three commands write nothing and run on a repository whose artifacts are stale.
R4. Any agent step of a run, from brainstorm to the phase reviews and the lens review itself, may add an effective lens to the feature with a reason, through its step record or from the command line. Adding is all an agent can do: a lens once added is never removed, and adding one already present keeps both reasons. An addition naming a lens that is not effective, or carrying no reason, is refused. The briefs and prompts of the existing steps are otherwise unchanged; in particular a phase reviewer is given no lens text.
R5. Additions are recorded in the run's journals, in the spec journal before a plan exists and in the plan journal after, each naming the lens, the reason, and the step that added it. `fr lenses status` prints the lenses accumulated for the current run with their reasons.
R6. `.fr/lenses.yaml` may hold path rules, each a list of path globs and the lenses those paths require. A lens is part of a feature's lens set when any file the feature changed matches a rule that requires it, whether or not an agent added it.
R7. The feature's **lens set** is every lens an agent added plus every lens a path rule requires for the files the feature changed, computed from the branch as it stands when it is read. `fr lenses status` shows, for a lens a rule requires, the rule and one matching file.
R8. Both shipped workflows run a `lens-review` step after the last phase review's check and before `deliver`. Its brief names each lens in the set with its instruction text, the reasons recorded for it or the rule that requires it, and the exact rule for what a reviewer returns (R9). The orchestrator dispatches one reviewer per lens, each given only its own lens, over the feature's whole diff.
R9. A lens reviewer ends its return with a fenced `review-lens` block naming its lens and at least one file the feature changed that it examined, and with the findings block reviewers already return, each finding tagged in scope or out of scope. In-scope findings are fixed and out-of-scope findings are filed by the rules the phase reviews use.
R10. Where fr can read the reviewers' returns, `fr run resolve` refuses the `lens-review` step `done` while a lens in the set, as computed at that resolve, has no reviewer's block; a block names no file the feature changed or names a file it did not change; one reviewer's block names more than one lens; a returned finding is missing from the plan journal or carries another scope tag there; or a finding the lens review raised is still open. The refusal names the lens and, for a lens a rule requires, the rule and a matching file. Where fr cannot read a return, the check is noted unobserved exactly as the phase review's is today.
R11. fr records the outcome on the step as derived evidence that the orchestrator cannot pass: per lens, how many files were examined and which findings were raised. When the lens set is empty the step completes with that evidence reading `none`, and no reviewer is dispatched.
R12. The PR body `deliver` renders carries a "Review lenses" section: each lens in the set with why it is there (the steps that added it and their reasons, or the rule), the number of files examined, and each finding with how it closed. When the set was empty the section says that no lens was requested for this change. A change to `.fr/lenses.yaml` on the branch is stated in that section. Under `forge.pr_body: minimal` the section is in the durable render only.
R13. A run started before this feature is not lost: `fr run reshape` inserts `lens-review` pending into a run that has not yet delivered and keeps every unit, and a journal written before this feature, holding no lens addition, reads as an empty set.
R14. The `fr-goal`, `fr-brainstorming`, `fr-plan` and `fr-execute` skills and the phase-executor and spec-reviewer agents tell their reader that it may add a lens and how; the `fr-goal` skill tells the orchestrator to run the lens review, one reviewer per lens, with the brief's text verbatim; and an operator page documents lenses, `.fr/lenses.yaml` and the four shipped instruction texts.

## 3. Design

### 3.A The lens set a repo has

A lens manifest is one YAML file:

```yaml
lens: security
title: Security
brief: |
  <instruction text given to the reviewer>
```

Shipped manifests live in `plugins/super-fr/lenses/*.yaml`, with a generated
copy in the `fr` wheel: the arrangement verification strategies use (one
canonical directory, one tripwire for the copy, no OpenCode or Hermes mirror,
riding `install.sh`'s wholesale marketplace sync). New package `fr/lenses/`:
`model.py` (manifest and config, closed-world), `resolve.py`
(`effective_lenses`), `check.py`, `rules.py` (path rules), `accumulate.py`
(`lens_set`, R7) and `review.py` (the brief text and the block parser, beside
`fr/run/review_return.py`, which it reuses and does not change).

The four shipped instruction texts say what to look for across the whole
change, and where to send what does not belong to the lens:

- **security** — input that reaches a shell, a query, a path, a template or a
  deserialiser without validation; secrets or tokens written to logs, errors,
  artifacts or the forge; authorisation checks missing or made after the act;
  new dependencies and what they can reach; permissions wider than the change
  needs.
- **tests** — whether the new tests would fail if the behaviour were wrong: a
  test that restates the code, one that covers only the easy input or one kind
  of user, a missing failure path, a mock standing in for the thing under test.
  Not coverage numbers.
- **simplicity** — a helper, layer, option or abstraction the change does not
  need; code that duplicates something the repo already has, or that two phases
  each wrote; names that do not say what the thing is; a function a reader
  cannot follow in one pass. Not style a formatter or linter owns.
- **errors** — a failure that is swallowed, turned into a default, or reported
  without what a person needs to act on it; a new failure path with no log or
  signal; a retry or fallback that hides the cause.

Each text ends the same way: a problem seen outside the lens is still reported,
as an ordinary finding.

`.fr/lenses.yaml`, all keys optional, unknown keys refused:

```yaml
disable: [errors]
lenses:
  accessibility:
    title: Accessibility
    brief: |
      ...
  security:            # replaces the shipped text
    title: Security
    brief: |
      ...
require:
  - paths: ["src/auth/**", "**/migrations/*.sql"]
    lenses: [security]
```

It is read from the working tree at HEAD, like `.fr/docs.yaml` and
`.fr/ci.yaml`. A branch can therefore loosen it; R12 makes that visible on the
pull request, where the operator decides.

`fr lenses` (`commands/lenses_cmd.py`) has `list`, `show`, `check` and `status`,
all read-only, and joins `fr.artifacts.trigger.READ_ONLY_COMMANDS`.

### 3.B Adding a lens

An addition is a journal entry of a new kind, `lens`: the lens id in a header
token (`lens=<id>`), the reason as the body, the adding step recorded with it.
A new entry kind is a journal shape change: the `journal` kind moves to version
4 with a registered migration and a validator, as kinds 2 and 3 did, and this
repo's own journals are migrated in the same PR.

Two ways in, one writer (`fr.record.apply`):

- a step record's `journal:` section — `{kind: lens, lens: security, body:
  "<why>"}` — available to every agent step, since each already emits a journal;
- `fr journal add --kind lens --lens <id> --body "<why>"`, for work with no run.

The entry's id is assigned by fr (`lens-<id>-<n>`), so two agents adding the
same lens never collide. There is no resolution record for a `lens` entry:
nothing closes or withdraws it.

`lens_set(repo_root, run)` is the one definition of R7: the distinct lens ids
of every `lens` entry in the run's spec and plan journals, plus the lenses of
every path rule matched by a file in the feature's diff (the proportionality
diff, same exemptions), restricted to effective lenses. A journalled lens the
repo has since disabled is dropped with a warning naming it.

### 3.C The lens review

**The step**, in both shipped manifests, between `journal-check` and `deliver`:

```yaml
  - id: lens-review
    kind: agent
    skill:
      - superpowers:requesting-code-review
      - superpowers:receiving-code-review
    tier: standard
    needs: [spec, plan, journal:plan]
    emits: [journal:plan]
    evidence: [lenses, review, reviewer, findings]
```

**Advance.** With an empty set, `fr run advance` completes the step itself
(`lenses=none`) and moves on to `deliver`, as it does for a `cli` step. With a
non-empty set it prints a brief whose `lens_review` key holds, per lens: the
title and instruction text, the recorded reasons or the matching rule and file,
the letter that lens's reviewer uses in finding ids, the diff's merge-base, and
the return rule.

**Return.** One reviewer per lens. Each ends with:

````
```review-lens
lens: security
examined: src/auth/session.py, src/auth/token.py
```
````

and the existing `review-findings` block. Finding ids are `l<letter>-r<k>`, the
letter from the brief, so the existing parser needs one more accepted prefix and
its several-reviewers rule (no id returned twice) applies as it stands. Lens
findings are plan-journal findings with no phase.

**Resolve.** `lens_set` is computed again at resolve, so a lens added during
the review, or a path rule newly matched by a fix, is owed before the step
closes. The checks of R10 run through the existing refusal path, before any
byte is written. `review` and `reviewer` are held as on a phase review: a
`kind=review` plan-journal entry created after the step opened, and dispatch
ids this session dispatched after it opened. `findings` is derived: refused
while any `l…` finding is effectively open in the plan journal.

**Fixes.** The orchestrator receives the reviews as it does a phase review's:
each in-scope finding is fixed with a test or refuted with reasoning, each
out-of-scope finding is filed. Fixes are not sent back through the phase
reviews; the suite `deliver` runs covers them, and a fix that touches a ruled
path brings that lens into the set at resolve.

**Evidence (R11).** `lenses` reads `security=2:la-r1,la-r2;tests=5:none`, or
`none`. Passing it is refused.

**Drift (R13).** `lens-review` is a new step id, so a run started earlier is
refused by `_check_step_drift` until `fr run reshape <run-id> --yes` inserts it.
A run already at or past `deliver` is not reshaped and finishes on the shape it
started with.

### 3.D The PR body

`pr_body.py` gains `_review_lenses`, rendered after the findings sections:

| Lens | Why | Files examined | Findings |
|---|---|---|---|
| security | rule `src/auth/**` (src/auth/session.py) | 2 | la-r1 fixed, la-r2 out of scope (#1432) |
| tests | implement-phase 2: "the retry path is only tested with a mock" | 5 | none |

or the single line "No lens was requested for this change." Finding states come
from the plan-journal fold. The table shows a count of files; the reviewer's
own lines are in its return. The section is not added to `REQUIRED_SECTIONS`, so
an existing live PR is not refused for lacking it.

### 3.E Skills, agents and docs

- One short paragraph each in `fr-brainstorming`, `fr-plan`, `fr-execute`,
  `fr-goal` §6 (for the phase reviewer's prompt) and the `fr-phase-executor` and
  `fr-spec-reviewer` agents: you may add a lens with a reason when the work
  gives you one; `fr lenses list` shows the set. The spec reviewer is read-only,
  so it returns the suggestion and the orchestrator records it.
- `fr-goal` gains a section for `lens-review` between its §7 and §8.
- Mirrors regenerated (OpenCode, Hermes); the agents edit moves the `agents`
  kind per `AGENTS.md`.
- `docs/review-lenses.md`: a published operator page. `docs/explainers/01-fr-goal.md`
  gains the step.
- A change fragment, `minor`: a new CLI group, a new workflow step.

## 4. Decisions

Settled with the operator:

1. Start with review lenses; reuse search and the reader's guide are later specs.
2. Lenses are reviewed once, at feature level before `deliver`, by a review
   separate from the phase reviews. This replaced an earlier design that named
   lenses on each plan phase and had the phase reviewer account for them: the
   operator's concern was that concrete lenses would narrow a phase reviewer's
   attention.
3. Any agent at any step may add a lens; lenses accumulate.
4. The set is agent additions plus what the repo's path rules require for the
   files actually changed. An empty set dispatches no review and the PR says so.
5. One reviewer per lens.
6. Four shipped lenses; a repo may add, replace and disable.
7. Each reviewer names changed files it examined; fr checks; the PR shows it.
8. The usual in-scope and out-of-scope rules apply to lens findings.
9. Verified pre-merge on a candidate build; no post-merge row.

Made in the spec:

10. Additions are append-only with no removal: a lens that turns out not to
    matter costs one review that returns `none`, and a removable lens would
    need a waiver rule again.
11. `.fr/lenses.yaml` is read from the branch, with the change surfaced on the
    PR: a repo could otherwise not introduce its first rule and use it in one PR.
12. The set is recomputed at resolve, not frozen when the step opens.
13. Lens-review fixes are not re-reviewed.

## 5. Risks

- **Findings arrive late.** A problem in an early phase is found after later
  phases are built on it, so a fix can be larger than it would have been at
  that phase's review. Accepted in exchange for a reviewer that sees the whole
  change; an agent that suspects the problem early can still raise it as an
  ordinary finding at its own step.
- **Nobody adds a lens.** Agent judgement is the main source, and an agent under
  load may not stop to add one. Path rules are the part that does not depend on
  it, and the PR states an empty set.
- **A named file proves little.** A reviewer can name a file and return `none`
  without reading it. The check makes the claim specific enough to doubt; it
  does not prove attention.
- **Large diffs.** Each reviewer reads the whole feature diff. On a very large
  feature that is expensive per lens and may exceed what one context reads well.
- **Runs in flight need `fr run reshape`** after upgrading.
- **The unobserved case.** On a harness where fr cannot read a subagent's
  return, R10's block checks are not enforced; the set, the dispatch-id check
  and the open-finding check still are.

## Verification

strategy: candidate
- review-lenses-effective-set: candidate — scenario drives the installed `fr lenses list|show|check` over a fixture repo with and without `.fr/lenses.yaml`
- review-lenses-accumulate: candidate — scenario: lenses added from step records at two steps and from the command line, `fr lenses status`, a refused unknown lens, and a reshaped older run
- review-lenses-path-rules: candidate — scenario: a fixture run whose diff touches a ruled path with no agent addition, in `fr lenses status` and at the lens-review resolve
- review-lenses-reviewer-return-checked: candidate — scenario: lens-review resolves with stubbed reviewer returns that are complete, lack one lens, and name a file the feature did not change; and an empty set completing with no dispatch
- review-lenses-shown-on-pr: candidate — scenario: the rendered PR body of a fixture run with a rule lens, an agent lens, and of one with an empty set

## Test Plan

Nothing is owed after merge: every row is proven on a candidate build before it.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
