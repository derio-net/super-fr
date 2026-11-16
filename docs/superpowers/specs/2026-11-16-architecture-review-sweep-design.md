# Architecture review and the first guarded consolidations — design

super-fr#1318, delivered as one PR on `feat/gh-1318`. This run is stage 1 of the issue
(the review) plus the first small part of stage 2 (the sweep). The rest of the sweep is
filed as issues for later runs.

## Background

#1318 asks for a review of `packages/*/src` for duplicated contracts, duplicated
mechanisms, seam violations, oversized modules, dead code and test-suite cost, followed by
a refactoring sweep with one PR per finding cluster, each with a guard that stops the
duplication from coming back.

Three inputs already exist on the issue, each pinned to a different commit:

- **The full engineering audit** (`f0a45b5b`, v8.0.0): findings F01–F09 and one unverified
  risk (two `fr run` commands racing on one cursor).
- **The duplication and seams supplement** (`a4281f85`, v8.0.3): seven consolidation
  clusters R01–R07, one guard correction G01, and a table of apparent duplicates that
  encode different policies and must stay separate.
- **The bug index** (`33e12d67`): F01–F04 are reproduced defects, tracked as #1499, #1500,
  #1419 and #1501. They change behaviour, so they stay out of #1318's refactor PRs.

None of the three is in the repo, and none was checked against the commit this run starts
from. Checks made during the brainstorm, at `39f06125`:

- The supplement's claims for G01, R01, R02 and R03 hold. `fr.gates` already defines
  `Gate`, `GATES` and `POST_MERGE_GATES`; the hand-written copies are `ExitBlock.gates`
  (`triage/model.py:519`), `StepGate` and `_TAG_RE` (`spec.py:564–565`) and the strategy
  gate literal (`verification/model.py:75`). `FrStatus` (`fr_claude_cloud/mailbox.py:44`)
  is a third copy of `SessionStatus`. The four identical aware-timestamp readers are
  `_parse_at` (`commands/triage_batch_cmd.py:3611`), `_parse_time` (`triage/batch.py:222`),
  `_aware` (`triage/check.py:375`) and `_parse` (`triage/views.py:83`).
  `tests/unit/test_import_direction.py` reads imports with a line regex.
- F02, F05 and F07 are still present: `run/model.py:600` calls `write_text`,
  `commands/run_cmd.py:6490` runs `shell=True` with no timeout, and
  `plugins/super-fr/hooks/fr-isolation-required.sh` calls bare `jq`.
- Four read-only reviews of the five largest modules (`commands/run_cmd.py` 8,862 lines,
  `commands/triage_batch_cmd.py` 7,343, `isolation/local.py` 3,164, `plan_ops.py` 2,545,
  `triage/batch_drive.py` 2,130) found that each has a part that moves cheaply along an
  existing seam and a part that is costly for a nameable reason. About 7,800 lines can move
  in roughly 15 small or medium slices. The reviews' line ranges and counts are unverified
  reviewer output; R5 requires the report to re-check them.

The operator's decisions, recorded in the spec journal:

1. This run delivers the report and lands G01, R01, R02 and R03.
2. The report reconciles the audit and the supplement with the current code.
3. F05, F06, F07, F09 and the cursor race are re-checked, and an issue is filed for each
   one still present and not already tracked. No fix lands here.
4. The report plans the decomposition of the five modules, including a design for the
   costly parts. No module is split in this PR. The no-growth line budget on the five
   files (R12) is the agent's reading of that answer: the operator was told and did not
   object, and was not asked about the budget's rules.
5. One short fragment is added to the existing architecture page.
6. Verification is the `candidate` strategy, with CI tests as the contract for each row.

## Requirements

R1. A report at `docs/superpowers/audits/2026-11-16-architecture-review.md` covers the six categories of #1318 (duplicated contracts, duplicated mechanisms, seam violations, oversized modules, dead or vestigial code, test-suite duplication and cost) and names the commit it was checked against. Each finding has an id, a category, a severity on the audit's scale (P0 emergency, P1 release blocker, P2 next maintenance cycle, P3 planned maintainability work), where it is defined and who reads it, whether the copies disagree today, the proposed fix, the guard that stops it coming back, the files the fix touches, and its tracking reference (an issue, or this PR for the four clusters landed here).
R2. The report lists every item of the audit (F01–F09 and the cursor race) and of the supplement (R01–R07, G01, and each row of its "preserve" table) with its status re-checked at the report's commit. No claim is copied forward unchecked: an item the run could not re-check is marked as not re-checked, with the reason.
R3. The report lists F01–F04 with their issues (#1499, #1500, #1419, #1501) as behaviour fixes outside the refactor lane. This PR changes none of the behaviour they describe.
R4. For each of F05, F06, F07, F09 and the cursor race that is still present at the report's commit, the run looks for an existing issue by that finding's own terms, and files a new issue only when none exists. The report names the issue for each. The search is per finding, never a sweep of the backlog.
R5. The report holds a decomposition plan for each of the five modules: a responsibility map with line ranges, the existing package each cluster belongs in, the slice order with a size for each slice, what each slice must preserve, and the guards that must be widened in the same change. Every line range, count and "no production caller" claim taken from the brainstorm's reviews is re-checked against the code before it is written. The three side findings (the `plan_ops.tick` and `complete_phase` duplicates of the record engine, the raw `write_text` calls in `plan_ops.py`, the import from `triage_batch_cmd` in `triage_kanban_cmd.py`) are re-checked and listed with their status.
R6. The report designs the costly parts, each with a preservation contract: a typed verdict that `run_cmd.py`'s evidence verifiers return in place of printing and exiting; a ports object through which the triage driver receives its clock, client, runner and output, which preserves what the driver's tests assert about output and effects and states whether the tests' patch locations move or stay; the garbage-collection part of `isolation/local.py` with its subclass override points; and the retirement of `plan_ops.tick` and `complete_phase`, stated as a behaviour change that needs its own contract.
R7. Every piece of sweep work this PR does not land has an issue linked from #1318: one per remaining consolidation cluster (R04, R05, R06; R04's is the same-loader extraction only, cross-linked with #1286, which keeps the backend switch), one per module for its cheap slices, and one per costly-part design. Each issue states the preserved behaviour, the callers to migrate, the guard, and the files it shares with other open work. Where an open issue already covers the work (#1174 for the import cycle), the run comments there and links it, and files no second issue.
R8. Every check in the package-boundary guard (`tests/unit/test_import_direction.py`) reads imports from the syntax tree, the two `fr.triage` checks included. It reports a forbidden import in every form: several names on one `import` line, an aliased import, a `from` import (`from fr import triage` among them), and an import nested in a function, class, `if` or `try`. For each sanctioned soft point it proves that every `fr_dispatch` import is either inside a function body or under `if TYPE_CHECKING:`, and that the file calls `importlib.util.find_spec("fr_dispatch")` and carries the install message. A source file the guard cannot parse fails the guard. The test file carries planted-source cases for each form and for a soft point that breaks the rule; its existing planted fixtures are rewritten as valid source. No file under `packages/` changes for this requirement.
R9. Gate annotations derive from `fr.gates`. `fr.gates` gains a `PostMergeGate` type holding exactly `tester` and `devops`, and `POST_MERGE_GATES` is computed from it. `ExitBlock.gates`, `StepGate`, the step tag patterns in `fr/spec.py` and `fr/ops/stub.py` and the strategy manifest's gate field take their values from `Gate` and `PostMergeGate`. The values each one accepts and rejects, its error text and any schema it emits are unchanged. The workflow manifest's `gate: operator` is a different concept and stays as it is. A test ties each annotation to the vocabulary and fails when a value is added to one side only.
R10. The cloud adapter's session-status type is `fr_dispatch`'s `SessionStatus`; the name `FrStatus` stays importable as an alias. The remote-state mapping is unchanged. `BoardStatus` in `fr` stays a separate literal, because `fr` must not import `fr_dispatch`, and the tests assert that `FrStatus` is the same object as `SessionStatus` and that `BoardStatus` holds the same values. A second test asserts that `fr.acceptance.report.STATUS_LABEL` has a label for every acceptance status and no other key.
R11. One function, `fr.triage.timestamps.parse_aware`, reads an aware timestamp: it returns `None` for a missing, empty, malformed or naive value and keeps the offset of an aware one. The four readers named in Background are removed and their callers use it; what each caller does with `None` is unchanged. A table test covers those cases. A syntax-tree scan, with local names normalised, fails when another function under `packages/*/src` has the same body, and is itself tested on a planted copy and a planted renamed copy.
R12. A tripwire holds a line budget for each of the five modules named in Background. It fails when a module has more lines than its budget, and it fails when a budget exceeds its module's line count by more than 400, so an extraction lowers the budget. Each budget starts at the module's line count on this branch rounded up to the next multiple of 100. The failure message says to move the new code into the module the report names, or to change the budget in the same diff with the reason in the PR. The two bounds, the starting headroom and the 400 figure are design choices of this spec, not operator decisions.
R13. The architecture page gains one authored fragment, `docs/triage/derio-net--super-fr/architecture/decomposition.html`, listed in that page's manifest after `pipeline.html`. It states, in a few paragraphs and one table, the five modules, what stays in each, the seams and the guards on them, and links to the report. It carries no text from outside this repo. A test proves that the repo's architecture manifest names no missing file, that every fragment it names passes `validate_fragment`, and that `decomposition.html` is among them, directly after `pipeline.html`.
R14. The PR changes no behaviour. Every existing test passes unchanged, with two exceptions: tests that pinned a removed duplicate by name follow the name, and `tests/unit/test_import_direction.py` is rewritten as R8 says, keeping every existing assertion's meaning. The PR adds one `patch` change fragment, rewrites nothing under `docs/superpowers/implemented/`, and regenerates any generated mirror it affects with the sync scripts.
R15. `AGENTS.md` names `fr.triage.timestamps`, `PostMergeGate` and the line-budget tripwire where it describes those areas, and every page whose `covers:` paths this PR changes is edited or re-stamped so `fr docs check` passes.

## Design

### A. The report (R1–R7)

One Markdown file, written by this run from the code at the branch's base commit. It is not
an artifact kind and has no reader in `fr`. Its sections, in order:

1. **Scope and method.** The commit, what was read, what was run, and the limits. It
   answers the issue's first open question: area reviewers plus one reconciliation pass.
2. **Status of earlier findings.** One table for the audit (F01–F09 and the cursor race) and
   one for the supplement (R01–R07, G01), with columns: item, earlier commit, status now
   (`present`, `fixed in <ref>`, `landed in this PR`, `not re-checked: <why>`), and
   tracking reference. This is R2, R3 and R4.
3. **Findings by category.** The six categories of the issue. Each finding uses the fields
   of R1. Category 3 lists, per seam, the tripwire that guards it or the fact that none
   does. Category 5 states what was proved removable and what was not; a grep hit is not
   proof. Category 6 uses the committed `.test_durations` only as recorded weights, never as
   current wall-clock.
4. **Duplicates to keep.** The supplement's table (default-branch and root readers, atomic
   writers, marker checks, schema numbers, legacy readers), each re-checked, each with the
   policy difference that makes it a non-duplicate.
5. **Decomposition plan.** One subsection per module (R5), then the four costly-part
   designs (R6).
6. **Order and conflicts.** Which clusters touch the same files, and the order that follows.
7. **Issues filed.** The list for R7, with numbers.

Issue writes go through `gh` and are made once, after the report text is final. Each new
issue body is written to a file first and follows `.claude/rules/third-party-privacy.md`.
An issue is filed only for work this PR leaves undone.

### B. The import-direction guard, G01 (R8)

One helper parses a source text with `ast` and walks every `Import` and `ImportFrom`
node. For each it returns the full dotted module, the names a `from` import takes, and the
node's position: inside a function body, under `if TYPE_CHECKING:`, or anywhere else
(module level, including a module-level `if`, `try`, `with` or class body, all of which run
at import time). A relative import is resolved against the file's package. A `SyntaxError`
is not caught: an unparseable file fails the test that read it.

Every existing test reads this helper. The sibling-offender tests compare root modules as
before. The two `fr.triage` checks drop `_FR_TRIAGE_IMPORT_RE` and match `fr.triage` as a
dotted prefix, plus `triage` among the names of a `from fr import …`. The soft-point test
asserts, per file in `_SOFT_POINTS`: every `fr_dispatch` import is inside a function body
or under `if TYPE_CHECKING:` (two soft points have such a block today,
`triage_kanban_cmd.py:76` and `triage_batch_cmd.py:298`); the tree holds a call
`importlib.util.find_spec("fr_dispatch")`; and the install message is present.
`_SOFT_POINTS` itself is unchanged. Entry-point loading by name (`importlib.metadata`)
stays allowed; the guard does not judge dynamic imports, and the report says so.

The existing fixtures in `test_a_third_fr_dispatch_import_is_refused` are a bare indented
import line, which is not valid Python. They become the same import inside a `def`.

Planted cases are source strings read by the same helper: `import os, fr_cncd`;
`import fr_cncd as c`; `from fr_cncd import x`; an import inside a function; an import
under `try`; `import os, fr.triage` and `from fr import triage` for the triage checks; and,
for a soft point, a module-level `from fr_dispatch import …`, the same under a
module-level `try`, and the same under a module-level `if` that is not `TYPE_CHECKING`.

### C. Gate vocabulary, R01 (R9)

`fr/gates.py`:

```python
PostMergeGate = Literal["tester", "devops"]
POST_MERGE_GATES: frozenset[str] = frozenset(get_args(PostMergeGate))
```

`triage/model.py` types the remap as `Literal["none", Gate]`, and
`verification/model.py` types the field as `Literal["none", PostMergeGate]`. The nested
form is required: Python flattens it into one `Literal` in today's order, while a union of
two literals is validated branch by branch. Run during spec review on this branch's
pydantic: the union form reports two errors for a bad value (the first reading
`Input should be 'none'`) and emits an `anyOf` schema; the nested form reports the one
error and the `enum` schema the field has today.

`spec.py` sets `StepGate = PostMergeGate` and builds `_TAG_RE` from
`get_args(PostMergeGate)`; `ops/stub.py` builds the tag part of `_LEAD_RE` the same way.
`StepGate`'s member order changes from (`devops`, `tester`) to (`tester`, `devops`).
`Step` is a dataclass and nothing reads that order, and an alternation matches the same
strings in either order.

Two other places name the two gates and stay hand-written: the ordered tuple in
`triage/lanes.py:78` (Tester first, by rule) and help text in
`commands/journal_cmd.py:219`. The report lists both under "duplicates to keep".

`fr.gates` imports only `typing`, so no import cycle is possible. Before changing each
site, the implementer captures what it emits today (the validation error for a bad value,
and any JSON schema or sorted listing that prints the values) in a test, then changes the
annotation and keeps that test green. If a member order appears in output, the annotation
is written so the order is kept. `PRE_MERGE_HOLD_GATES` is not touched.

The guard test asserts, in process: the remap's accepted set equals `GATES | {"none"}`;
`get_args(StepGate)`, the strategy field's accepted set minus `none`, and the set of tags
each of the two tag patterns matches (every member of `GATES` tried as a tag) each equal
`POST_MERGE_GATES`; and a helper that compares an annotation to a
vocabulary fails on a synthetic annotation with one extra value.

### D. Session status, R02 (R10)

`fr_claude_cloud/mailbox.py` imports `SessionStatus` from `fr_dispatch.protocols` (the
adapter already depends on `fr_dispatch`) and sets `FrStatus = SessionStatus`. `STATE_MAP`
and `map_state` are unchanged. The existing equality test in `test_import_direction.py`
keeps comparing `BoardStatus` with `SessionStatus` by value. A new assertion checks
`FrStatus is SessionStatus`: after the alias a value comparison could not fail, and what
can regress is a separate literal coming back. The `STATUS_LABEL` coverage test compares
its keys with `get_args(fr.acceptance.model.Status)`; the two hold the same nine statuses
today.

### E. Triage timestamps, R03 (R11)

New module `packages/fr/src/fr/triage/timestamps.py` with `parse_aware(stamp)`, the body
the four copies share. It imports only `datetime`, so every triage module and the command
module can import it. The four private functions are deleted and their call sites renamed;
no caller's handling of `None` moves. Readers elsewhere that treat a naive time as UTC
(usage, debt) have a different contract and are not migrated; the report lists them under
"duplicates to keep".

The scan is a function from source text to the functions whose body matches the owner's.
It drops the docstring and renames parameters and local variables by order of first use, so
a copy with other variable names still matches. The test runs it over every file under
`packages/*/src` and expects only `parse_aware`; it also runs it on a planted copy and on a
planted copy with renamed variables, and expects each to be reported. It reads source only
and starts no process.

The scan finds copies, not other implementations of the same contract. Two exist today
with a different body: `_pr_time` (`commands/triage_batch_cmd.py:2042`) and
`_created_since` (`triage/collect.py:1106`). This PR does not change them; the report
lists each with whether it has the same contract and what should happen to it.

This lands before any extraction from `triage_batch_cmd.py`, so later slices do not move
the same helper.

### F. Line budget (R12)

`tests/unit/test_tripwire_module_budget.py` holds one table, path to budget, for the five
modules, and one check function over (lines, budget) that the tests call both on the real
files and on planted numbers. It counts physical lines. Two assertions per module:
`lines <= budget`, and `budget - lines <= 400`.

Starting budgets are the line counts rounded up to the next 100: 8,900, 7,400, 3,200,
2,600 and 2,200 at the branch's base. (`main` added 60 lines to `run_cmd.py` while the
branch was open, so its budget lands as 9,000 by the same rule.) That gives each module between 36 and 70 lines of headroom, so an
ordinary PR that adds a few lines changes no budget and two such PRs do not conflict on the
table. The lower bound is wide for the same reason: several PRs that each trim a module
cannot together push the budget out of range, while an extraction slice (the report's
small slices move a few hundred lines, and the medium ones more) must lower it.

Two PRs can still pass alone and fail together on `main`: each adds lines within the
headroom and their sum exceeds it. No budget scheme avoids that. The headroom makes it
rare, the failure message names the one-line fix, and the report states the cost: once the
headroom of `run_cmd.py` is used, a feature that adds to it must move code out or raise
the budget in its own diff.

The budget is a review trigger for five named files, not a ceiling for the codebase. The
report states that as the answer to the issue's third open question.

### G. Architecture fragment (R13)

A hand-written HTML fragment in the style of the page's other fragments: a heading, a
short introduction, one table (module, lines, what stays, what moves and where, the guard),
and a link to the report on GitHub. It uses the page's CSS variables and no script. The
manifest gains the entry `decomposition.html` after `pipeline.html`.

`tests/unit/test_triage_architecture.py` gains a test that resolves the repo's own
architecture manifest and asserts three things: `missing` is empty (`resolve_manifest`
records an absent file there and does not raise), every resolved fragment passes
`validate_fragment`, and `decomposition.html` is in `fragments` and directly after
`pipeline.html` in `order`. The rendered page is not
committed; `fr triage architecture render` is run once during implementation to see the
fragment in place.

### H. Order inside the PR

1. G01, so the later moves are made under the stronger guard.
2. R01, R02, R03, each as its own commit with its guard.
3. The line-budget tripwire.
4. The report, written last so its "landed in this PR" rows and line counts are true, then
   the fragment, then the issues.

Known overlap with open work: #1419 (`isolation/types.py`) and #1500 (`run/model.py`) are
not touched. `triage/model.py` and `triage_batch_cmd.py` are edited by a few lines each; a
conflict with a concurrent batch is resolved by rebasing this branch.

## Verification

strategy: candidate
gate: developer

- import-guard-reads-syntax-tree: none — CI test: planted sources with a multi-name, aliased, `from`, nested and `try` import of a sibling package or of `fr.triage` are each reported, and a planted soft point with an `fr_dispatch` import at module level, under a module-level `try` or under a plain `if` fails
- gate-annotations-follow-vocabulary: none — CI test: the triage remap, both step tag patterns and the strategy gate field accept exactly the values `fr.gates` defines, and the comparison fails on a synthetic annotation with an extra value
- session-status-one-vocabulary: none — CI test: the cloud adapter's `FrStatus` is `SessionStatus` itself, `BoardStatus` holds the same values, the adapter's state mapping tests pass unchanged, and `STATUS_LABEL` covers every acceptance status
- triage-timestamps-one-reader: none — CI test: `parse_aware` returns `None` for missing, empty, malformed and naive input and keeps a `Z` and a non-zero offset; the copy scan reports a planted copy and a planted copy with renamed variables, and finds none in the source
- hotspot-modules-cannot-grow: none — CI test: the tripwire's check fails on a module over its budget and on a budget more than 400 lines above its module, and passes for the five modules as committed
- architecture-page-shows-decomposition: none — CI test: the repo's architecture manifest names no missing file, every fragment it names passes `validate_fragment`, and `decomposition.html` is resolved directly after `pipeline.html`

The walk runs the candidate smoke only (install, version, status in a fresh fixture).
Nothing is owed after merge.

## Acceptance rows

| Row | Requirement | Claim |
|---|---|---|
| `import-guard-reads-syntax-tree` | R8 | The package-boundary guard reports a sibling-package import in any import form. |
| `gate-annotations-follow-vocabulary` | R9 | Every gate annotation accepts exactly the gates `fr.gates` defines. |
| `session-status-one-vocabulary` | R10 | The dispatch protocol, the board and the cloud adapter agree on the session statuses, and every acceptance status has a report label. |
| `triage-timestamps-one-reader` | R11 | Triage reads aware timestamps through one function with one stated behaviour. |
| `hotspot-modules-cannot-grow` | R12 | The five largest modules cannot grow past their recorded size without a visible budget change. |
| `architecture-page-shows-decomposition` | R13 | The architecture page's authored fragments, the decomposition fragment among them, are valid. |

R1–R7 produce a document and issues, R14 is the no-behaviour-change constraint and R15 is
documentation upkeep. None is product behaviour, so none has a row. The report and the issues are checked by
the lens review before `deliver` and by the PR review, and R15 by `fr docs check`.

## Non-goals

- Fixing F01–F04 (#1499, #1500, #1419, #1501) or any of F05, F06, F07, F09 and the cursor
  race.
- Splitting any of the five modules, or moving any function out of them other than the
  four timestamp readers.
- R04 (strict YAML loader), R05 and R06 (test helpers), R07 (orchestration slices). They are
  filed, not landed.
- A shared git abstraction, a shared atomic writer, or a single "valid workspace" check.
  The report records why each set of readers is not a duplicate.
- A line ceiling for modules other than the five.
- Refreshing the audit's score or re-running its mutation and workload measurements.
- Committing a rendered architecture page.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-16-architecture-review-sweep | `derio-net/super-fr` | `2026-11-16-architecture-review-sweep` | — |
