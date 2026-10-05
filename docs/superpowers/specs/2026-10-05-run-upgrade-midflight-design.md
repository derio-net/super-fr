# A run started on an older fr can be finished after an upgrade — design

**Issue:** derio-net/super-fr#891 · **Branch:** `feat/batch-run-upgrade-midflight` ·
**Run:** `2026-10-05-feat-batch-run-upgrade-midflight`

## Background

A `fr-goal` run that spans an `fr` upgrade cannot be finished today. `fr migrate
artifacts --yes` brings the cursor *file* up to date, but three gates then close in
sequence:

1. **Shape drift refuses every cursor operation.** When the shipped shape gained or lost
   a step since `fr run start` (live case: `fr-goal@1` gained `journal-check`),
   `_resolve_manifest_for_state` → `_check_step_drift`
   (`packages/fr/src/fr/commands/run_cmd.py:743`, `:765`) raises for `advance`,
   `resolve` — and for `gates` (`run_cmd.py:6407`), which is read-only and is the
   source `deliver` copies verbatim into the PR body's "Operator gates" section.
2. **`adopt` will not supersede.** `adopt_run` (`packages/fr/src/fr/run/adopt.py:595`)
   refuses when `fr.archive.find_run_for_plan` (`packages/fr/src/fr/archive.py:409`)
   finds a run for the plan, and points at the two commands that just refused. The only
   way out is deleting the run file by hand, which loses what it recorded — notably
   `StepRecord.answered_by` on `brainstorm`, so `fr run gates` then reports
   "provenance not recorded" for a gate the operator did answer.
3. **The evidence gate cannot accept a review older than the cursor.** Adoption leaves
   every completed phase's `review-phase` member `pending` (`build_run_state`,
   `adopt.py:370`). Resolving it needs `reviewer=<id>`, and `_verify_reviewer`
   (`run_cmd.py:2105`) refuses any id this session did not dispatch since the unit
   opened. A review that genuinely happened before the cursor existed can only be
   resolved `failed` (false), with fabricated evidence, or by re-running the review.

The run's artifacts are fine throughout; this is purely about the cursor. The cursor's
schema does not change in this design: `UnitRecord.evidence` is already
`dict[str, str]` (`packages/fr/src/fr/run/model.py:220`), and every new fact below is
either a value in that map or a rewrite of `steps` within the existing model.

## Requirements

R1. `fr run reshape <run-id>` previews moving a drifted run onto the current version of
its shape, and `--yes` applies it: every recorded step and unit is kept, a step added
ahead of the cursor is inserted `pending`, and a step removed that never left `pending`
is dropped.

R2. `fr run reshape` refuses, naming the step and changing nothing, when an added step
falls at or behind the cursor, when a removed step had left `pending` or is the cursor,
when a grouped step that has left `pending` changed its members, or when the shape's
schema version changed; the refusal names `fr run adopt --supersede` as the way on.

R3. The shape-drift refusal printed by every mutating `fr run` command names
`fr run reshape <run-id>` as the way forward.

R4. The read-only `fr run` commands — `gates` above all, plus `status`, `check` and
`cost` wherever they resolve the manifest — answer from a drifted cursor, printing one
warning that names the drift and `fr run reshape`, instead of refusing.

R5. `fr run adopt` over a plan that already has a run refuses, naming both
`fr run reshape <existing>` and `fr run adopt --supersede`.

R6. `fr run adopt --supersede` replaces the plan's existing run with a freshly adopted
cursor, carrying forward from the old one every fact still meaningful in the current
shape: gate clearance and `answered_by`, emitted artifacts, every unit's attempts and
evidence, and a `done` review member's state. The old run file is removed in the same
commit, whose message names the superseded run.

R7. A `review-phase` unit may be resolved `done` with `reviewer=historical`, accepted
only when its `review` evidence entry was created before the run itself started; the
review-entry and findings checks apply unchanged.

R8. `fr run adopt` (with or without `--supersede`) marks a complete phase's review
member `done`, with evidence `review=<id>`, `reviewer=historical` and the derived
`findings`, when the plan journal holds a `kind=review` entry for that phase and no
finding against it is still open; otherwise the member stays `pending` and adopt prints
why. When every phase ends up reviewed, the cursor lands on the step after the group.

R9. A historical review reads as such everywhere a review is reported: `fr run status`
and `fr run check` say "reviewed before this cursor existed (journal `<id>`) — reviewer
not observed", never as debt and never as a failure, and the PR body `deliver` renders
lists every historically-reviewed phase.

R10. The `fr-goal` skill's in-flight and stranded-run recovery prose (§ header paragraph
and §7), the shipped `fr-goal.yaml` comment that describes the stranded-run recovery,
and the `01-fr-goal` explainer describe reshape, `--supersede` and historical review
instead of moving a run file aside by hand.

## Design

### A. `fr run reshape` (R1–R3)

A new subcommand in `run_cmd.py`, dry-run by default like `fr apply` and `fr migrate
artifacts`. A pure function `reshape(state, manifest) -> RunState` (new module
`fr/run/reshape.py`, so it is testable without the CLI) does the work and raises
`ReshapeError` for every refusal; the command prints the diff (`added: …; removed: …`)
and, with `--yes`, saves through `save_run_state` and commits through
`_note_record_write`, the same path every other cursor write takes.

Rules, in order — the first that fails refuses, and nothing is written:

1. The manifest's `schema_version` must equal the recorded `@<schema>`. A schema change
   alters the step grammar itself; reshaping across it is not a list edit. (R2)
2. **Removed** steps (recorded, absent from the manifest) are dropped iff their record
   is `pending` and the step is not `state.cursor`. Otherwise the run did work there
   that the new shape cannot represent. (R2)
3. **Added** steps (in the manifest, not recorded) are inserted `pending` iff their
   manifest index is strictly greater than the cursor's. A step added at or behind the
   cursor would never run — the cursor only moves forward — so the run passed a check
   the new shape requires; refusing is the honest answer, and `adopt --supersede`
   rebuilds from disk. (R2)
4. **Grouped members** changed (`_check_step_drift`'s member diff): allowed only while
   the group's record is `pending`, in which case `members` is rewritten to the
   manifest's. A group that has left `pending` has units keyed on the old members. (R2)
5. Steps are written in manifest order. Every kept record is carried byte-for-byte.

A run with no drift prints `nothing to reshape` and exits 0. `_check_step_drift`'s two
messages gain a final line, `fr run reshape <run-id>` (R3).

### B. Read-only commands answer a drifted cursor (R4)

`_resolve_manifest_for_state` gains a lenient sibling,
`_resolve_manifest_for_read(repo_root, state) -> WorkflowManifest`, which runs the same
checks, and on a drift `RunStateError` prints that message as a single yellow warning
(plus `fr run reshape <run-id>`) and returns the manifest anyway. A schema-version
mismatch still refuses: a different grammar is not safe to read with. `gates_cmd` uses
it; the plan audits `status`, `check` and `cost` and switches every read-only call site
that resolves the manifest. Mutating commands keep the strict resolver.

### C. `adopt --supersede` (R5, R6)

`adopt_run` gains `supersede: bool`. Without it, the existing-run refusal (`adopt.py:604`)
names `fr run reshape <existing>` and `fr run adopt --supersede`.

With it, adoption proceeds as today and then a pure `carry_forward(old, new) ->
RunState` merges the old cursor in, step by step, for every step id present in both:

- `gate` and `answered_by` — copied (this is the provenance the hand-delete lost);
- `emitted` — old keys the inference did not set are copied;
- `units` — for every unit key present in both: `attempts` and `evidence` are copied;
  a unit `done` in the old cursor stays `done` (the inference only knows implement
  completion, so a reviewed member is otherwise lost);
- step `state` — the inference's, except that a step `done` in the old cursor stays
  `done` when it sits before the new cursor.

The old cursor is read with the current model; one the current `fr` cannot parse
refuses with `fr migrate artifacts --yes` as the fix — carry-forward from a file fr
cannot read would be a guess. The old run file is deleted and the new one written in
one commit: `chore(fr): run <new> — adopt, supersedes <old>`. When the derived run id
equals the old one (same day), the file is overwritten in place. The new cursor's
`started` is now: it is a new cursor, and what it did not observe is exactly what §D
calls historical.

### D. Historical review evidence (R7–R9)

`HISTORICAL_REVIEWER = "historical"`, a reserved `reviewer` value for phase units only.

**By hand (R7).** In the resolve path that calls `_verify_reviewer` (`run_cmd.py:1812`),
an offered `reviewer=historical` on a phase unit skips the dispatch check and is
accepted iff the `review` entry it is offered with was `created` before
`state.started`; otherwise exit 2: "a historical review predates the run; this one was
recorded after the run started — dispatch a reviewer". `_verify_review_entry` and the
derived `findings` gate run unchanged. On a flat (spec-review) unit it is refused: an
adopted run never leaves spec-review open, and spec-review's rule is that its review
postdates the step.

**By adoption (R8).** `build_run_state` receives the plan journal's entries (read in
`adopt_run`, which already does the I/O) and, per complete non-manual phase, looks for
the latest entry satisfying `fr.journal.model.reviews_phase`. Found, and no finding
against the phase effectively open (the same fold the evidence gate uses), the review
member is `done` with `{review, reviewer: historical, findings}`. Otherwise it stays
`pending`, and a note says which: "no `kind=review` entry for phase N" or "phase N has
open findings: <ids>". If every unit of the group is then `done`, the group step is
`done` and the cursor is the step after it.

**Reporting (R9).** `fr run status`/`check` render a unit whose evidence has
`reviewer: historical` with the sentence in R9, and `_unevidenced_units` does not count
it as debt. `fr.record.pr_body` adds a `## Historical reviews` section, listing
`phase N — journal <id>`, when any unit carries it; when rendered it is required on the
live PR like the other rendered sections, so it cannot be dropped silently.

### E. Prose (R10)

`plugins/super-fr/skills/fr-goal/SKILL.md` — the "Work already in flight" paragraph and
§7's stranded-run recovery; `plugins/super-fr/workflows/fr-goal.yaml`'s `journal-check`
comment; `docs/explainers/01-fr-goal.md` near its `fr run adopt` paragraph (and its
`.html`, regenerated per `.claude/rules/explainers-currency.md`). Mirrors regenerated
with `scripts/sync-opencode.py` and `scripts/sync-hermes.py`. README's `fr run` row
gains `reshape`.

## Non-goals

- **Shape pinning** (snapshotting the manifest into the cursor) — rejected by the
  operator: a cursor schema change that does not rescue runs already stranded.
- **Automatic reshape** inside `advance`/`resolve` — rejected: it mutates the cursor as
  a side effect of an unrelated command.
- Keeping a superseded run file beside its successor — rejected: every locator and
  archiver would need to learn to skip it.
- Carrying gate provenance for steps the new shape does not have.

## Test Plan

Unit/CLI tests (CI) cover each requirement: reshape's preview/apply/no-op and every
refusal (R1–R3); a drifted cursor answering `gates`/`status` with a warning while
`advance` still refuses (R4); adopt's refusal text and `--supersede`'s carry-forward,
including `answered_by` surviving into `fr run gates` (R5–R6); `reviewer=historical`
accepted before and refused after the run's start (R7); adoption inferring review
members from a journal, with and without open findings, and the cursor landing past the
group (R8); status/check/PR-body rendering (R9). Post-merge — operator-driven: none
required beyond CI; the next real upgrade-spanning run exercises it live.
