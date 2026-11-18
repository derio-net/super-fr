# Architecture review and the first guarded consolidations — plan

Spec: `docs/superpowers/specs/2026-11-16-architecture-review-sweep-design.md` (super-fr#1318).
One PR on `feat/gh-1318`, two agentic phases, no manual phase.

## What this plan delivers

- **Phase 1** lands five source-level changes that alter no behaviour, each with a guard
  that is shown to fail on a planted violation: the import-direction guard reads the syntax
  tree (G01); gate annotations derive from `fr.gates` (R01); the cloud adapter uses the
  dispatch protocol's session status (R02); one `fr.triage.timestamps.parse_aware` replaces
  four identical readers (R03); and a line budget holds the five largest modules.
- **Phase 2** writes the review itself: a report under `docs/superpowers/audits/`, one
  fragment on the architecture page, and an issue for every piece of work the PR leaves
  undone.

## Why two phases

The two halves are different asks. Phase 1 is fully specified code work, reviewable as a
diff against existing tests. Phase 2 is a document that needs design judgement (four
costly-part designs) and re-verification across the codebase, and it must be written after
phase 1 so its "landed in this PR" rows and line counts are true.

## Rules both phases follow

- **No behaviour change.** Existing tests pass unchanged; the one test file rewritten is
  `tests/unit/test_import_direction.py`, and every assertion in it keeps its meaning. If a
  step cannot be done without changing behaviour, stop and record a finding.
- **Capture before you change.** For the gate annotations, pin today's error list and
  schema in a test first. Use the nested form `Literal["none", Gate]`; the union form
  changes pydantic's error list and schema (measured during spec review).
- **Every guard fires.** A guard test that can only pass is not done; each has a planted
  case that it reports. The feature carries the `tests` lens for this reason.
- **Unverified inputs.** The plan-journal discoveries `review-run-cmd`,
  `review-triage-batch`, `review-isolation-local` and `review-plan-ops` are the brainstorm's
  module reviews. Their line ranges and counts were not checked. Phase 2 confirms each
  against the code before using it.
- **Out of scope.** F01–F04 (#1499, #1500, #1419, #1501) and F05–F09 are not fixed here. No
  module is split. `_pr_time`, `_created_since`, `triage/lanes.py` and the journal help text
  are listed in the report and not changed.
- **Forge writes** happen only in phase 2 task 6, after the report text is final, from
  body files, following `.claude/rules/third-party-privacy.md`.

## Verification

Strategy `candidate`, gate `developer`. Every acceptance row is `verify: none` with a CI
test named in the spec's `## Verification` section. The walk runs the candidate smoke only.
Nothing is owed after merge.
