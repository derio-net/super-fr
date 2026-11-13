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
  entry kind so far moved it (2, 3). Every agent step of the flow except
  `deliver` emits a journal through its step record, and an entry lands in the
  scope its step emits (`fr.workflow.artifacts.journal_scope`): on the light
  shape `spec-plan-review` runs after `plan` and still writes the spec journal.
  The record's `JournalItem` (`fr/record/model.py`) is closed-world too, and the
  `record` kind is at version 11.
- **Evidence targets.** `run_cmd._evidence_target` knows two targets: a phase
  unit against the plan journal, and a flat step against the spec journal. A
  flat step that emits `journal:plan` has none, and `review`, `reviewer` and
  `findings` are refused for it. `reviewer` holds one dispatch id. An evidence
  name must be in `_VERIFIABLE_EVIDENCE`, and a derived one in
  `DERIVED_EVIDENCE` and `_DERIVED_FROM`, or the resolve refuses it.
- **`advance` and agent steps.** `fr run advance` never completes a
  `kind: agent` step; it prints a brief and opens a dispatch, and only
  `fr run resolve` moves the cursor past it.
- **`.fr/ci.yaml`.** `fr/run/ci_evidence.declared_gates` reads it as the union
  of the default branch's copy and HEAD's: a branch can add a gate and never
  drop one its base declares.
- **Step drift.** `run_cmd._check_step_drift` refuses a run whose manifest
  gained or lost a step id since `fr run start`, wherever its cursor is.
  `fr run reshape` inserts a new step pending and keeps every unit, but only
  when the new step is after the cursor; otherwise it refuses and names
  `fr run adopt <plan-dir> --supersede`.
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
R3. `fr lenses list` prints the effective lenses and where each comes from; `fr lenses show <id>` prints one lens's instruction text; `fr lenses check` fails a `.fr/lenses.yaml` that is unreadable, names an unknown key, defines a lens whose id is not lower-case letters, digits and hyphens starting with a letter, defines a lens with no instruction text, disables or requires a lens that does not exist, or disables a lens that a path rule requires. The three commands write nothing and run on a repository whose artifacts are stale.
R4. Any agent step of a run, from brainstorm to the phase reviews and the lens review itself, may add an effective lens to the feature with a reason, through its step record or from the command line. Adding is all an agent can do: a lens once added is never removed, and adding one already present keeps both reasons. An addition naming a lens that is not effective, or carrying no reason, is refused. The briefs and prompts of the existing steps are otherwise unchanged; in particular a phase reviewer is given no lens text.
R5. An addition is recorded in the journal the adding step writes (the spec journal or the plan journal), naming the lens, the reason and, when it came through a step record, the step that added it. `fr lenses status` prints the lenses accumulated for the current run with their reasons.
R6. `.fr/lenses.yaml` may hold path rules, each a list of path globs and the lenses those paths require. The rules in force are those on the repository's default branch together with those on the branch: a branch can add a rule and cannot drop or weaken one its base holds, nor disable a lens a rule in force requires. A lens is part of a feature's lens set when any file the feature changed matches a rule in force that requires it, whether or not an agent added it.
R7. The feature's **lens set** is every lens an agent added plus every lens a path rule requires for the files the feature changed, computed from the branch as it stands when it is read. `fr lenses status` shows, for a lens a rule requires, the rule and one matching file.
R8. Both shipped workflows run a `lens-review` step after the last phase review's check and before `deliver`. Its brief names each lens in the set with its instruction text, the reasons recorded for it or the rule that requires it, and the exact rule for what a reviewer returns (R9). The orchestrator dispatches one reviewer per lens, each given only its own lens, over the feature's whole diff.
R9. A lens reviewer ends its return with a fenced `review-lens` block naming its one lens and at least one file the feature changed that it examined, and with a findings block whose ids carry the lens's id, each finding tagged in scope or out of scope. In-scope findings are fixed and out-of-scope findings are filed by the rules the phase reviews use.
R10. `fr run resolve` refuses the `lens-review` step `done` while a lens in the set, as computed at that resolve, has no reviewer named for it; a named reviewer is not an agent this session dispatched after the step opened; or a finding the lens review raised is still open. Where fr can read the reviewers' returns it also refuses while a named reviewer's return has no block for its lens, a block names no file the feature changed or names a file it did not change, or a returned finding is missing from the plan journal or carries another scope tag there. A refusal over a lens names it, prints that lens's instruction text and, for a lens a rule requires, the rule and a matching file. Where fr cannot read a return, those checks are noted unobserved, as the phase review's are today.
R11. fr records the outcome on the step as derived evidence that the orchestrator cannot pass: per lens, how many files were examined, or that the return was not observable, and which findings were raised. When the lens set is empty the step's brief says so and the step resolves with no reviewer dispatched and that evidence reading `none`.
R12. The PR body `deliver` renders carries a "Review lenses" section: each lens in the set with why it is there (the steps that added it and their reasons, or the rule), the number of files examined, and each finding with how it closed. When the set was empty the section says that no lens was requested for this change. A change to `.fr/lenses.yaml` on the branch is stated in that section. Under `forge.pr_body: minimal` the section is in the durable render only.
R13. A run started before this feature is not lost: `fr run reshape` inserts `lens-review` pending into a run whose cursor has not reached `deliver` and keeps every unit; a run already at `deliver` is carried onto the new shape by `fr run adopt <plan-dir> --supersede`, which keeps its units and evidence; and a journal written before this feature, holding no lens addition, reads as an empty set.
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
`fr/run/review_return.py`, whose finding-id grammar becomes a parameter so
both reviews share one parser).

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

Lens definitions, replacements and `disable` are read from the working tree
at HEAD. Path rules follow `.fr/ci.yaml`'s precedent
(`ci_evidence.declared_gates`): the rules in force are the union of the default
branch's `require:` and HEAD's, so one PR can add a repo's first rule and use
it, and no PR can remove a rule from under itself. `fr lenses check` refuses a
HEAD config that disables a lens a rule in force requires. The lenses a
feature is REVIEWED under follow the same precedent (`review_lenses`): a lens
effective on the default branch keeps the default branch's definition and
cannot be disabled by the branch under review, so the author of a change never
writes the instructions its own reviewer is given. A branch may add a lens and
use it at once; its change to an existing lens takes effect once merged, is
named in a warning, and R12 states any change to the file on the pull request.
With no remote, HEAD's rules are the rules in force, and
because there is then no feature diff to match, every one of them applies. A
remote whose default branch ref, its `.fr/lenses.yaml` or the merge-base cannot
be read in this checkout is a refusal that says what to fetch, never "no rules".

A lens id matches `^[a-z][a-z0-9-]*$`, so it is safe as a journal header token
and inside an entry or finding id.

`fr lenses` (`commands/lenses_cmd.py`) has `list`, `show`, `check` and `status`,
all read-only, and joins `fr.artifacts.trigger.READ_ONLY_COMMANDS`.

### 3.B Adding a lens

An addition is a journal entry of a new kind, `lens`. Its header carries
`lens=<id>` and, when it came through a step record, `step=<step-id>`, which fr
stamps from the record's own step (never supplied by the agent); `phase=` is
stamped from a phase unit as it is for other entries, and a `lens` entry in the
plan journal from a non-phase step is global. The entry's title is the reason,
one line; the body is optional detail. `lens` joins `_STAMPING_KINDS`, and the
model accepts `lens=` and `step=` on a `lens` entry only.

Two artifact shapes move, each with its stamp bump, registered migration and
validator in this PR, and this repo's own artifacts migrated in it:

- the `journal` kind, 3 to 4 (a new entry kind, as `owed` and `op` were);
- the `record` kind, 11 to 12: `JournalItem` gains an optional `lens` field,
  valid on `kind: lens` only.

Two ways in, one writer (`fr.record.apply`):

- a step record's `journal:` section — `{kind: lens, lens: security, title:
  "<why, one line>"}` — in every step that emits a journal. `deliver` emits
  none; by then the lens review is over.
- `fr journal add --scope <spec|plan> --slug <slug> --kind lens --lens <id>
  --title "<why>"`, with `--phase N` or `--global` under `--scope plan` as for
  any entry. This path records no step.

fr assigns the entry id (`lens-<id>-<n>`), so two agents adding one lens never
collide. A `lens` entry takes no resolution record: nothing closes or withdraws
it.

`lens_set(repo_root, run)` is the one definition of R7: the distinct lens ids
of every `lens` entry in the run's spec and plan journals, plus the lenses of
every rule in force matched by a file in the feature's diff (the
proportionality diff, same exemptions), restricted to effective lenses. A
journalled lens the repo (its default branch) has disabled is dropped with a
warning naming it; one only the branch disabled stays (§3.A). A lens a rule
requires cannot be disabled (§3.A), so `lens_set` refuses, naming the rule, the
lens and the file, when such a lens is not effective. No shipped lens set at
all is a broken install and a refusal, never an empty set.

### 3.C The lens review

**The step**, in both shipped manifests, between `journal-check` and `deliver`:

```yaml
  - id: lens-review
    kind: agent
    skill:
      - superpowers:requesting-code-review
      - superpowers:receiving-code-review
    tier: standard
    needs: [spec, plan]
    emits: [journal:plan]
    evidence: [lenses, review, reviewer, findings]
```

`journal:plan` is not in `needs`: `review-phase` both needs and emits it, so
naming it here is a cycle `fr workflow check` refuses (`lens-review ->
review-phase -> lens-review`). The step's place after `journal-check` orders
it, as `spec-review`'s place does for the spec journal. Only a flat step that
emits `journal:plan` and declares `lenses` is reviewed against the feature; any
other flat step declaring review evidence is refused, as before.

**Advance.** `fr run advance` is not changed: it prints the step's brief, as
for any agent step. The brief's `lens_review` key holds the set. For each lens:
its title and instruction text, the recorded reasons or the matching rule and
file, the diff's merge-base, and the return rule with that lens's finding-id
prefix. With an empty set the key says so, and the orchestrator resolves the
step at once with a record that names no review and no reviewer.

**Return.** One reviewer per lens. Each ends with:

````
```review-lens
lens: security
examined: src/auth/session.py, src/auth/token.py
```
````

and a `review-findings` block whose ids are `l-<lens>-r<k>` (`l-security-r1`).
The id carries the lens, so it does not move when the set grows and needs no
letter. `parse_review_findings` takes the id grammar as an argument: the phase
grammar stays its default, and the lens review passes
`^l-[a-z][a-z0-9-]*-r[1-9][0-9]*$`; `fr/lenses/review.py` holds the
`review-lens` parser and the lens version of the brief rule.

**A third evidence target.** `_evidence_target` gains a feature-level target
for a flat step that emits `journal:plan`: the plan journal, no phase. Each
consumer is routed through it:

- `review`: a `kind=review` plan-journal entry, global, created after the step
  opened. Not owed when the set is empty.
- `reviewer`: on this step the value is a map, one `<lens>=<dispatch-id>` per
  lens in the set, comma-separated. fr refuses a lens with no id, an id named
  for two lenses, and, where the session is readable, an id this session did
  not dispatch after the step opened. Not owed when the set is empty.
- `findings`, derived: the lens review's findings are the plan-journal
  findings whose id matches the lens grammar, journalled global. Refused while
  any is effectively open. Other plan findings are not this gate's.
- the returned-findings check: for each named reviewer whose return is
  readable, its `review-lens` block names the lens it was named for and files
  in the feature's diff, and every id in its findings block carries that lens
  and is journalled with the same scope tag.

**Resolve.** `lens_set` is computed again at resolve, so a lens added during
the review, or a rule newly matched by a fix, is owed before the step closes.
A refusal over such a lens prints its instruction text and return rule, which
is the brief for the reviewer still to be dispatched. Every check runs through
the existing refusal path, before any byte is written.

**Evidence (R11).** `lenses` is registered as derived (`DERIVED_EVIDENCE`,
`_VERIFIABLE_EVIDENCE`, `_DERIVED_FROM`, and a witness in
`_verified_evidence`), so the brief and the record template never list it as
owed and passing it is refused. It reads
`security=2:l-security-r1,l-security-r2;tests=5:none`, or `none` for an empty
set. Where a return is not readable the count is `unobserved`
(`security=unobserved:l-security-r1`, findings taken from the journal) and the
unit carries `unobserved=reviewer-return`.

**Fixes.** The orchestrator receives the reviews as it does a phase review's:
each in-scope finding is fixed with a test or refuted with reasoning, each
out-of-scope finding is filed. Fixes are not sent back through the phase
reviews; the suite `deliver` runs covers them, and a fix that touches a ruled
path brings that lens into the set at resolve.

**Drift (R13).** `lens-review` is a new step id, so a run started earlier is
refused by `_check_step_drift` until it is moved. With the cursor on or before
`journal-check`, `fr run reshape <run-id> --yes` inserts the step pending. With
the cursor on `deliver`, reshape refuses (the step is behind the cursor) and
the run is carried over with `fr run adopt <plan-dir> --supersede --yes`, which
then owes the lens review before `deliver`.

### 3.D The PR body

`pr_body.py` gains `_review_lenses`, rendered after the findings sections:

| Lens | Why | Files examined | Findings |
|---|---|---|---|
| security | rule `src/auth/**` (src/auth/session.py) | 2 | l-security-r1 fixed, l-security-r2 out of scope (#1432) |
| tests | implement-phase 2: "the retry path is only tested with a mock" | 5 | none |

or the single line "No lens was requested for this change." Finding states come
from the plan-journal fold. The table shows a count of files, or "not
observable" where fr could not read the return; the reviewer's own lines are in
its return. An addition made from the command line shows no step. The section is not added to `REQUIRED_SECTIONS`, so
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
11. Path rules are the default branch's together with the branch's, the rule
    `.fr/ci.yaml` already follows: a PR can add a rule and use it, and cannot
    remove one. Lens text is read from the branch and a change is stated on the
    PR.
12. The set is recomputed at resolve, not frozen when the step opens.
13. Lens-review fixes are not re-reviewed.
14. `fr run advance` keeps its rule of never completing an agent step: on an
    empty set the orchestrator resolves the step itself.
15. Lens finding ids carry the lens id, not a letter.

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
- **Runs in flight need `fr run reshape`** after upgrading, or
  `fr run adopt --supersede` when already at `deliver`.
- **The unobserved case.** On a harness where fr cannot read a subagent's
  return, R10's block checks are not enforced and the PR shows the files
  examined as not observable. That each lens has a named reviewer, the
  dispatch-id check where the session is readable, and the open-finding check
  still hold.

## Verification

strategy: candidate
- review-lenses-effective-set: candidate — scenario drives the installed `fr lenses list|show|check` over a fixture repo with and without `.fr/lenses.yaml`
- review-lenses-accumulate: candidate — scenario: lenses added from step records at two steps and from the command line, `fr lenses status`, a refused unknown lens, an older run reshaped before `deliver`, and one at `deliver` carried over by `adopt --supersede`
- review-lenses-path-rules: candidate — scenario: a fixture run whose diff touches a ruled path with no agent addition, in `fr lenses status` and at the lens-review resolve; a branch that drops a rule its base holds; and `fr lenses check` refusing a disabled lens a rule requires
- review-lenses-reviewer-return-checked: candidate — scenario: lens-review resolves with stubbed reviewer returns that are complete, lack one lens, and name a file the feature did not change; a reviewer named for a lens this session did not dispatch; and an empty set resolving with no reviewer
- review-lenses-shown-on-pr: candidate — scenario: the rendered PR body of a fixture run with a rule lens, an agent lens, and of one with an empty set

## Test Plan

1. [developer] No post-merge step exists: every row is proven on a candidate build before merge. At close-out, record this step as not applicable (`fr closeout outcome --step 1 --na`).

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-12-review-lenses | `derio-net/super-fr` | `2026-11-12-review-lenses` | — |
