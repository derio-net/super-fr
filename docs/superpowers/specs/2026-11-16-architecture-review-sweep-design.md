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
   costly parts. No module is split in this PR. A no-growth line budget on the five files
   lands here.
5. One short fragment is added to the existing architecture page.
6. Verification is the `candidate` strategy, with CI tests as the contract for each row.

## Requirements

R1. A report at `docs/superpowers/audits/2026-11-16-architecture-review.md` covers the six categories of #1318 (duplicated contracts, duplicated mechanisms, seam violations, oversized modules, dead or vestigial code, test-suite duplication and cost) and names the commit it was checked against. Each finding has an id, a category, a severity, where it is defined and who reads it, whether the copies disagree today, the proposed fix, the guard that stops it coming back, the files the fix touches, and its tracking reference (an issue, or this PR for the four clusters landed here).
R2. The report lists every item of the audit (F01–F09 and the cursor race) and of the supplement (R01–R07, G01, and each row of its "preserve" table) with its status re-checked at the report's commit. No claim is copied forward unchecked: an item the run could not re-check is marked as not re-checked, with the reason.
R3. The report lists F01–F04 with their issues (#1499, #1500, #1419, #1501) as behaviour fixes outside the refactor lane. This PR changes none of the behaviour they describe.
R4. For each of F05, F06, F07, F09 and the cursor race that is still present at the report's commit, the run looks for an existing issue by that finding's own terms, and files a new issue only when none exists. The report names the issue for each. The search is per finding, never a sweep of the backlog.
R5. The report holds a decomposition plan for each of the five modules: a responsibility map with line ranges, the existing package each cluster belongs in, the slice order with a size for each slice, what each slice must preserve, and the guards that must be widened in the same change. Every line range, count and "no production caller" claim taken from the brainstorm's reviews is re-checked against the code before it is written. The three side findings (the `plan_ops.tick` and `complete_phase` duplicates of the record engine, the raw `write_text` calls in `plan_ops.py`, the import from `triage_batch_cmd` in `triage_kanban_cmd.py`) are re-checked and listed with their status.
R6. The report designs the costly parts, each with a preservation contract: a typed verdict that `run_cmd.py`'s evidence verifiers return in place of printing and exiting; a ports object through which the triage driver receives its clock, client, runner and output, so that tests' patches of the command module keep working; the garbage-collection part of `isolation/local.py` with its subclass override points; and the retirement of `plan_ops.tick` and `complete_phase`, stated as a behaviour change that needs its own contract.
R7. Every piece of sweep work this PR does not land has an issue linked from #1318: one per remaining consolidation cluster (R04, R05, R06), one per module for its cheap slices, and one per costly-part design. Each issue states the preserved behaviour, the callers to migrate, the guard, and the files it shares with other open work. Where an open issue already covers the work (#1286 for the strict YAML loader, #1174 for the import cycle), the run comments there and links it, and files no second issue.
R8. The package-boundary guard (`tests/unit/test_import_direction.py`) reads imports from the syntax tree. It reports a sibling-package import in every form: several names on one `import` line, an aliased import, a `from` import, and an import nested in a function, class or `try`. For each sanctioned soft point it proves that no `fr_dispatch` import is at module level, replacing the substring checks. The test file carries planted-source cases for each form and for a soft point that breaks the rule. No file under `packages/` changes for this requirement.
R9. Gate annotations derive from `fr.gates`. `fr.gates` gains a `PostMergeGate` type holding exactly `tester` and `devops`, and `POST_MERGE_GATES` is computed from it. `ExitBlock.gates`, `StepGate`, the step tag pattern in `fr/spec.py` and the strategy manifest's gate field take their values from `Gate` and `PostMergeGate`. The values each one accepts and rejects, its error text and any schema it emits are unchanged. The workflow manifest's `gate: operator` is a different concept and stays as it is. A test ties each annotation to the vocabulary and fails when a value is added to one side only.
R10. The cloud adapter's session-status type is `fr_dispatch`'s `SessionStatus`; the name `FrStatus` stays importable as an alias. The remote-state mapping is unchanged. `BoardStatus` in `fr` stays a separate literal, because `fr` must not import `fr_dispatch`, and one test asserts that all three names hold the same values. A second test asserts that `fr.acceptance.report.STATUS_LABEL` has a label for every acceptance status and no other key.
R11. One function, `fr.triage.timestamps.parse_aware`, reads an aware timestamp: it returns `None` for a missing, empty, malformed or naive value and keeps the offset of an aware one. The four readers named in Background are removed and their callers use it; what each caller does with `None` is unchanged. A table test covers those cases, and a syntax-tree scan fails when another function under `packages/*/src` has the same body.
R12. A tripwire holds a line budget for each of the five modules named in Background. It fails when a module has more lines than its budget, and it fails when a budget exceeds its module's line count by more than 50, so a budget follows its module down. Each budget starts at the module's line count on this branch. The failure message says to move the new code into the module the report names, or to change the budget in the same diff with the reason in the PR.
R13. The architecture page gains one authored fragment, `docs/triage/derio-net--super-fr/architecture/decomposition.html`, listed in that page's manifest after `pipeline.html`. It states, in a few paragraphs and one table, the five modules, what stays in each, the seams and the guards on them, and links to the report. It carries no text from outside this repo. A test proves that every fragment the repo's architecture manifest names exists and passes `validate_fragment`.
R14. The PR changes no behaviour. Every existing test passes unchanged, except tests that pinned a removed duplicate by name, which follow the name. The PR adds one `patch` change fragment, rewrites nothing under `docs/superpowers/implemented/`, and regenerates any generated mirror it affects with the sync scripts.
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

`_imports_of` parses each file with `ast` and walks every `Import` and `ImportFrom` node,
returning the root module of each imported name with whether the node is at module level.
The existing offender tests keep their assertions and read the new data. The soft-point
test asserts, per file in `_SOFT_POINTS`, that every `fr_dispatch` import node is nested
(not a direct child of the module) and that the install message is present. `_SOFT_POINTS`
itself is unchanged. Entry-point loading by name (`importlib.metadata`) stays allowed; the
guard does not judge dynamic imports, and the report says so.

Planted cases are source strings parsed by the same helper: `import os, fr_cncd`;
`import fr_cncd as c`; `from fr_cncd import x`; an import inside a function; an import
under `try`; and a soft point with a module-level `from fr_dispatch import …`.

### C. Gate vocabulary, R01 (R9)

`fr/gates.py`:

```python
PostMergeGate = Literal["tester", "devops"]
POST_MERGE_GATES: frozenset[str] = frozenset(get_args(PostMergeGate))
```

`triage/model.py` types the remap as `Gate | Literal["none"]`. `spec.py` sets
`StepGate = PostMergeGate` and builds `_TAG_RE` from `get_args(PostMergeGate)`.
`verification/model.py` types the field as `Literal["none"] | PostMergeGate`.

`fr.gates` imports only `typing`, so no import cycle is possible. Before changing each
site, the implementer captures what it emits today (the validation error for a bad value,
and any JSON schema or sorted listing that prints the values) in a test, then changes the
annotation and keeps that test green. If a member order appears in output, the annotation
is written so the order is kept. `PRE_MERGE_HOLD_GATES` is not touched.

The guard test asserts, in process: the remap's accepted set equals `GATES | {"none"}`;
`get_args(StepGate)`, the tag pattern's alternatives and the strategy field's accepted set
minus `none` each equal `POST_MERGE_GATES`; and a helper that compares an annotation to a
vocabulary fails on a synthetic annotation with one extra value.

### D. Session status, R02 (R10)

`fr_claude_cloud/mailbox.py` imports `SessionStatus` from `fr_dispatch.protocols` (the
adapter already depends on `fr_dispatch`) and sets `FrStatus = SessionStatus`. `STATE_MAP`
and `map_state` are unchanged. The existing equality test in `test_import_direction.py`
gains the third name. The `STATUS_LABEL` coverage test compares its keys with
`get_args(fr.acceptance.model.Status)`; if the two differ today, that is a finding for the
report and a behaviour question, not something this PR changes silently.

### E. Triage timestamps, R03 (R11)

New module `packages/fr/src/fr/triage/timestamps.py` with `parse_aware(stamp)`, the body
the four copies share. It imports only `datetime`, so every triage module and the command
module can import it. The four private functions are deleted and their call sites renamed;
no caller's handling of `None` moves. Readers elsewhere that treat a naive time as UTC
(usage, debt) have a different contract and are not migrated; the report lists them under
"duplicates to keep".

The scan test parses each file under `packages/*/src`, normalises each function body
(docstring dropped, names kept) and fails when a function other than `parse_aware` has the
owner's body. It reads source only and starts no process.

This lands before any extraction from `triage_batch_cmd.py`, so later slices do not move
the same helper.

### F. Line budget (R12)

`tests/unit/test_tripwire_module_budget.py` holds one table, path to budget, for the five
modules. It counts physical lines. Two assertions per module: `lines <= budget`, and
`budget - lines <= 50`. The second makes an extraction PR lower the budget, and keeps the
first meaningful. The 50-line slack lets ordinary edits that shorten a file pass without a
budget change.

The budget is a review trigger for five named files, not a ceiling for the codebase. The
report states that as the answer to the issue's third open question.

### G. Architecture fragment (R13)

A hand-written HTML fragment in the style of the page's other fragments: a heading, a
short introduction, one table (module, lines, what stays, what moves and where, the guard),
and a link to the report on GitHub. It uses the page's CSS variables and no script. The
manifest gains the entry `decomposition.html` after `pipeline.html`.

`tests/unit/test_triage_architecture.py` gains a test that resolves the repo's own
architecture manifest and validates every fragment it names. The rendered page is not
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

- import-guard-reads-syntax-tree: none — CI test: planted sources with a multi-name, aliased, `from`, nested and `try` import of a sibling package are each reported, and a soft point with a module-level `fr_dispatch` import fails
- gate-annotations-follow-vocabulary: none — CI test: the triage remap, the step tag and the strategy gate field accept exactly the values `fr.gates` defines, and the comparison fails on a synthetic annotation with an extra value
- session-status-one-vocabulary: none — CI test: `SessionStatus`, `BoardStatus` and the cloud adapter's `FrStatus` hold the same values, the adapter's state mapping tests pass unchanged, and `STATUS_LABEL` covers every acceptance status
- triage-timestamps-one-reader: none — CI test: `parse_aware` returns `None` for missing, empty, malformed and naive input and keeps a `Z` and a non-zero offset; a scan finds no second function with its body
- hotspot-modules-cannot-grow: none — CI test: the tripwire's check fails on a module over its budget and on a budget more than 50 lines above its module, and passes for the five modules as committed
- architecture-page-shows-decomposition: none — CI test: every fragment the repo's architecture manifest names exists and passes `validate_fragment`

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
documentation upkeep. None is product behaviour, so none has a row; they are checked by
spec review, the PR review and `fr docs check`.

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
