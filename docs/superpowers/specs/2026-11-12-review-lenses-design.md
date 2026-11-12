# Review lenses — design

## 1. Goal

A phase's code review in the `fr-goal` flow is a general review today: the
dispatched reviewer is told to find what is wrong, incomplete or worse than it
needs to be, and nothing says which concerns it must look at. Security, test
depth, needless complexity and error handling are covered only when the reviewer
happens to think of them, and nothing records whether it did.

This feature gives the review named **lenses**. A lens is an id plus the
instruction text fr puts into the reviewer's brief. The plan says, per phase,
which lenses apply; the reviewer returns one line per lens naming the changed
files it examined and the findings it raised; fr refuses the review while a
declared lens is unaccounted for; and the pull request shows which lenses ran.

It is the first of four quality areas identified in the brainstorm. The other
three (a whole-change review before delivery, a reuse search at plan time, and a
reader's guide in the PR body) are separate specs and are not designed here.

## 2. Background (read from the code)

- **The flow.** `plugins/super-fr/workflows/fr-goal.yaml` runs `implement` as a
  grouped `for_each: phase` with two members, `implement-phase` and
  `review-phase`. `fr-goal-light.yaml` keeps the same `review-phase` member.
- **The review's evidence.** `review-phase` resolves `done` only with a
  `kind=review` plan-journal entry, a dispatched reviewer's id, and no open
  finding against the phase. `fr/run/review_return.py` already gives the
  reviewer an exact rule in the brief (`review_findings`), reads a fenced
  `review-findings` block out of its return, and `run_cmd.py` refuses the resolve
  when the block is missing, malformed or disagrees with the plan journal. Where
  fr cannot read the return the check is noted `unobserved=reviewer-return`.
- **The phase header.** `fr.types.PhaseHeader` is `extra="forbid"` and carries
  `tag` (`agentic` | `manual`), `files` (the globs the phase expects to touch,
  `*` spans `/`) and `estimate_lines`. `files` and `estimate_lines` were added as
  optional, defaulted fields with no stamp bump; a plan that uses them raises its
  `fr_version` floor instead, and `fr plan self-review` refuses a plan that uses
  them under a lower floor (`plan_ops.py`).
- **Plan-time checks.** `fr plan self-review` (`plan_ops.self_review`) is the
  deterministic `plan-review` step of both workflows.
- **Repo-over-shipped resolution.** Workflows and verification strategies ship
  under `plugins/super-fr/` with a generated copy in the `fr` wheel, and a repo
  may add or override them. Neither is mirrored to OpenCode or Hermes.
- **The PR body.** `fr/record/pr_body.py` renders the body at `deliver` from the
  cursor and the journals; under `forge.pr_body: minimal` the full render is
  kept in the durable `<run-id>.pr-body.md` only.
- **What is missing.** No file under `plugins/super-fr/` or `packages/fr/src/fr/`
  names a security, test-depth, complexity or error-handling concern for the
  code review. The refactor gate (`fr/record/gates.py`) checks that a refactor
  step exists, not what the code looks like after it.

The outside datapoint the operator supplied is an essay arguing that
agent-written code yields a fragile codebase. Its named failure modes are tests
that assert trivial behaviour or one user type, more helpers than the problem
needs, small quality issues (naming, test gaps) that accrue because review is
skimmed, and errors nobody instrumented. The four shipped lenses below are those
concerns plus security, which the operator added.

## Requirements

R1. fr ships four lenses: `security`, `tests`, `simplicity` and `errors`. Each has an id, a one-line title and the instruction text a reviewer is given.
R2. A repo may, in `.fr/lenses.yaml`, add a lens of its own, replace a shipped lens's title and instruction text, and disable a shipped lens. The repo's **effective lenses** are the shipped ones not disabled, with replacements applied, plus the repo's own.
R3. `fr lenses list` prints the effective lenses and where each comes from; `fr lenses show <id>` prints one lens's instruction text; `fr lenses check` fails a `.fr/lenses.yaml` that is unreadable, names an unknown key, disables or requires a lens that does not exist, or defines a lens with no instruction text. The three commands write nothing and run on a repository whose artifacts are stale.
R4. A plan phase header may carry `lenses` (the lens ids its review applies) and `lens_waivers` (lens id to a non-empty reason). In a plan whose `fr_version` floor is at or above the release that introduces lenses, `fr plan self-review` fails an agentic phase that neither applies nor waives every effective lens, that names a lens which is not effective, that both applies and waives one lens, or that waives one with an empty reason. Manual phases are exempt.
R5. `fr plan create` writes a floor that enables R4, and `fr plan self-review` fails a plan whose phases carry `lenses` or `lens_waivers` under a floor that an fr unable to parse them satisfies.
R6. `.fr/lenses.yaml` may hold path rules, each a list of path globs and the lenses those paths require. `fr plan self-review` fails an agentic phase whose `files` globs reach a path a rule names when the phase does not apply every lens that rule requires; a waiver does not satisfy a path rule.
R7. `fr run resolve` refuses a `review-phase` unit `done` when a file the phase changed matches a path rule and the phase does not apply a lens that rule requires. The refusal names the file, the rule and the lens, and says to add the lens to the plan phase and review again.
R8. The `review-phase` brief of a phase that applies lenses carries, for each applied lens, its instruction text, and the exact rule for the block the reviewer must return (R9). A phase that applies none carries no lens text.
R9. A reviewer of a phase that applies lenses ends its return with a fenced `review-lenses` block, one line per applied lens: the lens id, at least one file the phase changed that it examined under that lens, and the ids of the findings it raised under that lens or `none`.
R10. Where fr can read the reviewer's return, `fr run resolve` refuses the `review-phase` unit `done` while an applied lens has no line from any reviewer of the unit, a line names no file the phase changed, a line names a file the phase did not change, a line cites a finding id that the same reviewer's `review-findings` block does not list, or the block is malformed. Where fr cannot read the return, the check is noted unobserved exactly as the findings check is today.
R11. fr records the outcome of R10 on the unit as derived evidence that the orchestrator cannot pass: per applied lens, how many files were examined and which findings were raised.
R12. The PR body `deliver` renders carries a "Review lenses" section: per phase, each applied lens with the number of files examined and each finding raised under it with how it closed, and each waived lens with its reason. A change to `.fr/lenses.yaml` on the branch is stated in that section. Under `forge.pr_body: minimal` the section is in the durable render only.
R13. A plan whose floor is below the release that introduces lenses, and whose phases carry none, is reviewed exactly as today: no lens text in the brief, no lens block owed, and the PR body section says the plan predates review lenses. A run in flight when fr is upgraded is not stranded by this feature.
R14. The `fr-plan` skill tells the plan author to decide each phase's lenses and waivers, the `fr-goal` skill tells the orchestrator to put the brief's lens text into the reviewer's prompt verbatim, and an operator page documents lenses, `.fr/lenses.yaml` and the four shipped instruction texts.

## 3. Design

### 3.A The lens set

A lens manifest is one YAML file:

```yaml
lens: security
title: Security
brief: |
  <instruction text given to the reviewer>
```

Shipped manifests live in `plugins/super-fr/lenses/*.yaml`, with a generated
copy in the `fr` wheel, the arrangement verification strategies use (one
canonical directory, one tripwire for the copy, no OpenCode or Hermes mirror,
riding `install.sh`'s wholesale marketplace sync). New package `fr/lenses/`:
`model.py` (the manifest and config models, closed-world), `resolve.py`
(`effective_lenses(repo_root)`), `check.py`, `rules.py` (path rules) and
`review.py` (the brief text and the block parser, beside
`fr/run/review_return.py`, which it does not change).

The four shipped instruction texts say what to look for and what not to report:

- **security** — input that reaches a shell, a query, a path, a template or a
  deserialiser without validation; secrets or tokens written to logs, errors,
  artifacts or the forge; authorisation checks missing or made after the act;
  new dependencies and what they can reach; permissions wider than the change
  needs. Not general robustness.
- **tests** — whether the new tests would fail if the behaviour were wrong: a
  test that asserts what the code does line by line, one that covers only the
  easy input or one kind of user, a missing failure path, a mock standing in for
  the thing under test. Not coverage numbers.
- **simplicity** — a helper, layer, option or abstraction the change does not
  need; code that duplicates something the repo already has; names that do not
  say what the thing is; a function a reader cannot follow in one pass. Not
  style a formatter or linter owns.
- **errors** — a failure that is swallowed, turned into a default, or reported
  without what a person needs to act on it; a new failure path with no log or
  signal; a retry or fallback that hides the cause. Not input validation
  (security) or missing tests (tests).

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

`fr lenses` is a read-only group (`commands/lenses_cmd.py`) and joins
`fr.artifacts.trigger.READ_ONLY_COMMANDS`: it mutates no registered artifact.

### 3.B The phase header

Two optional, defaulted fields on `PhaseHeader`, omitted from written phase
files when empty:

```yaml
lenses: [security, tests]
lens_waivers:
  simplicity: "moves one constant; nothing to simplify"
  errors: "no new failure path: the phase only renames a flag"
```

They follow the `files` / `estimate_lines` precedent: no plan stamp bump, and a
plan that uses them raises its `fr_version` floor to the release that
introduces lenses (the predicted version: base plus this PR's fragment bump).
That floor is also the switch for the completeness rule (R4), so every plan
`fr plan create` writes from then on is held to it and every older plan is left
alone (R13).

`fr plan create` and `fr plan edit` accept the two fields. `self_review` gains
one check, `_check_lenses`, which reads the effective lenses and the path rules
once per plan.

**Reaching a path (R6).** A phase's `files` globs reach a rule's paths when a
tracked file at HEAD matches both a phase glob and a rule glob, or when a phase
glob, read as a literal path, matches a rule glob (the case of a file the phase
will create). This is a plan-time approximation on purpose; R7 is the exact
check.

### 3.C The review

**Brief.** `run_cmd._dispatch_brief` adds a `review_lenses` key beside
`review_findings` for a phase that applies lenses: each applied lens's title and
instruction text, then the block rule with the phase's lens ids filled in:

````
```review-lenses
security | src/auth/session.py, src/auth/token.py | p2-r1, p2-r3
tests | tests/test_session.py | none
```
````

With several reviewers, each returns lines only for the lenses its dispatch
prompt assigns; the unit needs every applied lens covered by at least one.

**The phase's changed files.** The files that differ between the commit in which
fr opened the phase's `implement-phase` unit and HEAD at the review's resolve,
fr's own artifacts (`docs/superpowers/**`, `docs/acceptance/**`) excluded, the
exemption `fr plan proportionality` already uses. fr commits the cursor when it
opens a unit, so that commit is in the branch's history; the plan settles how it
is located without changing the cursor's shape.

**Resolve.** In the order: R7 (path rules against the changed files), then R10
(the block). Both refuse through the existing `_return_refusal` path, before any
byte is written. R10 runs only where the return is readable; R7 needs only git
and always runs.

**Evidence (R11).** `review-phase` gains a derived evidence key, `lenses`, in
both shipped manifests: `security=2:p2-r1,p2-r3;tests=1:none`, or `none` for a
phase that applies no lens. Like `findings`, passing it is refused. An evidence
key is not a member id, so an in-flight cursor does not drift on it; the plan
confirms that against `_check_step_drift` and, if a unit already past review
lacks the key, reads it as `unevidenced (predates review lenses)`, the treatment
units from before the evidence gate already get.

### 3.D The PR body

`pr_body.py` gains `_review_lenses`, rendered after the findings sections:

| Phase | Lens | Files examined | Findings |
|---|---|---|---|
| 2 | security | 2 | p2-r1 fixed, p2-r3 fixed |
| 2 | tests | 1 | none |
| 2 | simplicity | waived | moves one constant; nothing to simplify |

Finding states come from the plan-journal fold. The table shows a count of files
rather than their names, to keep the body short; the reviewer's full lines are
in its return and the finding entries are in the journal. The section is not a
required section (`REQUIRED_SECTIONS` is unchanged), so an existing live PR is
not refused for lacking it.

### 3.E Skills and docs

- `fr-plan` SKILL: one paragraph under phase authoring — decide each lens per
  phase, apply or waive with a reason, `fr lenses list` shows the set.
- `fr-goal` SKILL §6: put `review_lenses` into the reviewer's prompt verbatim,
  as it already does `review_findings`.
- Both regenerated into the OpenCode and Hermes mirrors.
- `docs/review-lenses.md`: a published operator page (`covers:` the lens
  package, the shipped manifests and the two skills). `docs/explainers/01-fr-goal.md`
  gains the lens step in its review section.
- A change fragment, `minor`: a new CLI group and a new mandatory plan rule.

## 4. Decisions

Settled with the operator in the brainstorm:

1. Start with review lenses; the other three areas are later specs.
2. Lenses are chosen per phase in the plan, not applied wholesale and not one
   reviewer per lens: the judgement is made at authoring and review cost does
   not multiply.
3. Under-declaration is closed two ways: every lens is applied or waived with a
   reason, and a repo's path rules make a lens mandatory where a waiver is not
   accepted.
4. Four shipped lenses; a repo may add, replace and disable.
5. The reviewer's lines are tied to files the phase changed, fr checks them, and
   the PR shows the result.
6. Verified pre-merge on a candidate build; no post-merge row.

Made in the spec:

7. Path rules are checked twice, at plan time against `files` and at review
   against the real diff, because `files` is the author's forecast.
8. `.fr/lenses.yaml` is read from the branch, with the change surfaced on the PR,
   not from the default branch: a new repo could otherwise not introduce its
   first rule and use it in one PR.
9. The completeness rule keys on the plan's `fr_version` floor, so no plan in
   flight starts failing self-review.

## 5. Risks

- **A line that names a file proves little.** A reviewer can name a changed file
  and write `none` without reading it. The check raises the cost of an empty
  claim and makes the claim specific enough for the operator to doubt; it does
  not prove attention. Nothing cheaper than a second reviewer does.
- **Waivers become boilerplate.** A reason is free text. The spec reviewer and
  the operator read it; path rules are the part that cannot be argued away.
- **Plan-time glob matching is approximate.** A phase whose `files` are wrong
  passes R6 and is caught at R7, after the phase is implemented, which costs one
  more review. Accepted: R7 is exact.
- **Longer briefs.** Four instruction texts add a few hundred tokens to each
  review dispatch.
- **The unobserved case.** On a harness where fr cannot read a subagent's
  return, R10 is not enforced and the lens evidence reads unobserved. R7 and the
  plan-time rules still hold.

## Verification

strategy: candidate
- review-lenses-effective-set: candidate — scenario drives the installed `fr lenses list|show|check` over a fixture repo with and without `.fr/lenses.yaml`
- review-lenses-phase-must-declare: candidate — scenario: `fr plan self-review` over a plan with a silent phase, a waived phase and a complete one, and over an older-floor plan
- review-lenses-path-rules: candidate — scenario: a waived lens on a phase whose `files` reach a ruled path, and a review resolve after a phase touched one
- review-lenses-reviewer-return-checked: candidate — scenario: review resolves with a stubbed reviewer return that is complete, lacks a lens line, and names a file the phase did not change
- review-lenses-shown-on-pr: candidate — scenario: the rendered PR body of a fixture run with applied and waived lenses

## Test Plan

Nothing is owed after merge: every row is proven on a candidate build before it.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
