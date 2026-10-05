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
2. **`adopt` will not supersede.** `adopt_run` (`packages/fr/src/fr/run/adopt.py:552`;
   the refusal at `:601-607`) refuses when `fr.archive.find_run_for_plan` (`packages/fr/src/fr/archive.py:409`)
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
ahead of the cursor is inserted `pending`, and a removed step that holds nothing (no
units, no cleared gate, no emitted artifact) is dropped.

R2. `fr run reshape` refuses, naming the step and changing nothing, when an added step
falls at or behind the cursor, when a removed step holds anything or is the cursor, when
a grouped step's members changed while it holds any unit, or when the shape's schema
version changed; the refusal names `fr run adopt --supersede` as the way on.

R3. The shape-drift refusal printed by every mutating `fr run` command names
`fr run reshape <run-id>` as the way forward.

R4. The read-only `fr run` commands — `gates` above all, plus `status`, `check` and
`cost` wherever they resolve the manifest — answer from a drifted cursor, printing one
warning that names the drift and `fr run reshape`, instead of refusing.

R5. `fr run adopt` over a plan that already has a run refuses, naming both
`fr run reshape <existing>` and `fr run adopt --supersede`.

R6. `fr run adopt --supersede` replaces the plan's existing run with a freshly adopted
cursor, carrying forward from the old one every fact still meaningful in the current
shape: gate clearance and `answered_by`, emitted artifacts, and every unit (of a step,
and member, the current shape still has) with its attempts, evidence and `done` state.
A still-open attempt is carried closed as `abandoned`, and the preview names each one.
The old run's usage file moves to the new run id. It refuses while the old run has a
live step record. The old run file is removed in the same commit, whose message names
the superseded run.

R7. A `review-phase` unit may be resolved `done` with `reviewer=historical`, accepted
only when its `review` evidence entry was created before the run itself started and
after the phase's implement member last returned (when this cursor holds such an
attempt), and only for a phase that owes no `visual` evidence; the review-entry and
findings checks apply unchanged.

R8. `fr run adopt` (with or without `--supersede`) marks a complete phase's review
member `done`, with evidence `review=<id>`, `reviewer=historical` and the derived
`findings`, when the plan journal holds a `kind=review` entry for that phase satisfying
R7's bounds, no finding against it is still open and none was fixed without the
operator; otherwise the member stays `pending` and adopt prints
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
and, with `--yes`, writes through `_save_run_state` (`run_cmd.py:301`) inside the
`_commits_run_writes` wrapper (`run_cmd.py:384`) — the path every other cursor write
takes, so the change lands as one `chore(fr):` commit.

A record **holds something** when it has any unit, a `gate`, an `answered_by` or an
`emitted` artifact. Lifecycle is not the test: a `pending` record can hold all four (an
adopted cursor on `implement` is a pending group with `done` units; a cleared `cli`
gate goes back to `pending` keeping `gate`/`answered_by`, `model.py:232-256`; adoption
can put `emitted` on the cursor step, `adopt.py:358`).

Rules, in order — the first that fails refuses, and nothing is written:

1. The manifest's `schema_version` must equal the recorded `@<schema>`. A schema change
   alters the step grammar itself; reshaping across it is not a list edit. (R2)
2. **Removed** steps (recorded, absent from the manifest) are dropped iff the record
   holds nothing and the step is not `state.cursor`. Otherwise the run recorded
   something there that the new shape cannot represent. (R2)
3. **Added** steps (in the manifest, not recorded) are inserted `pending` iff their
   manifest index is strictly greater than the cursor's. A step added at or behind the
   cursor would never run — the cursor only moves forward — so the run passed a check
   the new shape requires; refusing is the honest answer, and `adopt --supersede`
   rebuilds from disk. (R2) The live #891 case passes: `journal-check`
   (`fr-goal.yaml:183`) sits after `implement` (`:98`), where the cursor is.
4. **Grouped members** changed (`_check_step_drift`'s member diff): `members` is
   rewritten to the manifest's iff the group record has no units. Units are keyed on
   member ids, so a group holding any would be orphaned. (R2)
5. Steps are written in manifest order. Every kept record is carried unchanged, except
   for rule 4's `members` rewrite. `started`, `driver` and every other `RunState` field
   are kept.

A run with no drift prints `nothing to reshape` and exits 0. `_check_step_drift`'s two
messages gain a final line naming `fr run reshape <run-id>` (R3).

**What reshape does not cover**, stated in R10's prose: a review dispatched from an
*earlier session* after the run started, whose resolve the drift then blocked. After a
reshape the dispatch check cannot see that session and `reviewer=historical` (§D)
requires the entry to predate `started`, which reshape keeps. That run takes
`adopt --supersede` (§C), whose new cursor did not observe the review and is therefore
exactly the case §D calls historical.

### B. Read-only commands answer a drifted cursor (R4)

`_resolve_manifest_for_state` gains a lenient sibling,
`_resolve_manifest_for_read(repo_root, state) -> WorkflowManifest`, which runs the same
checks, and on a drift `RunStateError` prints that message as a single yellow warning
(plus `fr run reshape <run-id>`) and returns the manifest anyway. A schema-version
mismatch still refuses: a different grammar is not safe to read with. `gates_cmd` uses
it; the plan audits `status`, `check` and `cost` and switches every read-only call site
that resolves the manifest. Mutating commands keep the strict resolver.

### C. `adopt --supersede` (R5, R6)

`adopt_run` gains `supersede: bool`. Without it, the existing-run refusal
(`adopt.py:601-607`) names `fr run reshape <existing>` and `fr run adopt --supersede`.
With it on a plan that has no run, adoption proceeds exactly as without it (the flag
asks for replacement *if* there is something to replace).

With it over an existing run, three checks come first, each refusing with nothing
written:

- the old cursor must parse with the current model — one fr cannot read refuses with
  `fr migrate artifacts --yes` as the fix, since carry-forward from an unreadable file
  would be a guess;
- `docs/superpowers/runs/<old>.records/` must hold no step record (`pr-body.md`, a
  rendering, does not count): a live record is work in hand whose `run:` names the old
  id, and the refusal names each file — resolve it, or delete it;
- the derived new path may equal the old one (same day) — that is the overwrite case and
  bypasses `adopt.py:634`'s existing-path refusal; any *other* existing path still
  refuses.

Then adoption proceeds as today, and a pure `carry_forward(old, new) -> RunState`
(in `fr/run/adopt.py`) merges the old cursor in, for every step id the current shape
still has:

- `gate` and `answered_by` — copied (this is the provenance the hand-delete lost);
- `emitted` — old keys the inference did not set are copied;
- `units` — **every** old unit is carried, whether or not adoption built it (adoption
  writes only `phase/N/<first member>` keys, `adopt.py:370-384`, and no `step/<id>`
  units, so a "present in both" merge would drop every review member, spec-review's
  evidence and deliver's), provided its member still exists in the group. A carried
  unit keeps its `attempts` and `evidence`; its state is the old one when that was
  `done`, else the inference's (or `pending` when adoption did not build it);
- **open attempts** — an attempt with no `returned` is carried with `returned` = now and
  `outcome: abandoned`, exactly what `fr run claim --abandoned` writes, so the new cursor
  starts with no unit held and `advance` can re-brief it. Superseding is an explicit act
  over a cursor that cannot move; the preview lists every hold it closes, with its agent
  and session, so the operator sees whose work is cut off before passing `--yes`;
- `driver` — copied; `at` on each step — the old one where the step is carried `done`.

The old run file is deleted and the new one written in one commit:
`chore(fr): run <new> — adopt, supersedes <old>`. The usage file
`docs/superpowers/usage/<old>.yaml` (`fr.usage.file.usage_path`) is renamed to
`<new>.yaml` in that commit, so `fr run cost <new>`, the PR body's `## Cost` and
`fr archive`'s `_archive_usage` (`archive.py:521-555`) still find what the old run
spent. The new cursor's `started` is now: it is a new cursor, and what it did not
observe is exactly what §D calls historical.

### D. Historical review evidence (R7–R9)

`HISTORICAL_REVIEWER = "historical"`, a reserved `reviewer` value for phase units only.

**The bound.** A review entry is historical for phase N of run S iff:

1. `entry.created < S.started` — it predates this cursor; and
2. when this cursor holds a returned attempt on phase N's implement member, the entry
   postdates the latest such `returned` — a review must follow the work it reviews
   (closes reusing a review of an earlier, abandoned implementation); and
3. phase N owes no `visual` evidence (no linked acceptance row carries `visual`): the
   visual witness (`run_cmd.py:1866-1881`) requires screenshots a reviewer opened in a
   transcript fr can read, and a historical reviewer has none. Such a phase is
   re-reviewed.

**By hand (R7).** In the resolve path that calls `_verify_reviewer` (`run_cmd.py:1812`),
an offered `reviewer=historical` on a phase unit skips `_verify_reviewer` and the
reviewer-return check (`_check_returned_findings`, there is no dispatch to read, so no
`unobserved=reviewer-return` note is written), and is accepted iff the `review` entry
it is offered with meets the bound; otherwise exit 2 naming the failed clause.
`_verify_review_entry` and the derived `findings` gate run unchanged. On a flat
(spec-review) unit it is refused: spec-review's rule is that its review postdates the
step, and adoption never leaves spec-review open.

**By adoption (R8).** `adopt_run` reads the plan journal and passes its entries to
`build_run_state`. Per complete non-manual phase, it takes the latest entry satisfying
`fr.journal.model.reviews_phase` (`journal/model.py:610`) and the bound. Found, with no
finding against the phase effectively open (`phase_finding_states`, `:552`) and none
fixed without the operator (`unauthorized_fixes`, `:513`) — the two predicates
`_closed_findings_witness` (`run_cmd.py:2812`) refuses on, used here directly because
that function exits rather than returns — the review member is `done` with `{review,
reviewer: historical, findings}`, where `findings` is the same witness string the gate
writes (the closed ids in raise order, or `none`). Otherwise the member stays `pending`
and a note says which: "no `kind=review` entry for phase N", "phase N owes visual
evidence", or "phase N has open findings: <ids>". If every unit of the group is then
`done`, the group step is `done` and the cursor is the step after it. Under
`--supersede` the carried units (§C) are applied after inference, so a review the old
cursor resolved keeps its real evidence.

**Trust model, stated.** The bound is checked against timestamps the journal's author
writes (`JournalEntry.created`, `journal/model.py:95`). An agent that writes a review
entry and then supersedes the run could pass clause 1. fr cannot rule that out, so the
human control is visibility: every historical review is listed by name in the PR body
(below), and the operator's review ok is given against that list.

**Reporting (R9).** `fr run status`/`check` render a unit whose evidence has
`reviewer: historical` with the sentence in R9, and `_unevidenced_units` does not count
it as debt. `fr.record.pr_body` renders a `## Historical reviews` section, listing
`phase N — journal <id>`, when any unit carries it. To make it required on the live PR
when rendered, `missing_sections(body)` (`pr_body.py:58`, today checking only the
static `REQUIRED_SECTIONS`) gains a `required` argument, and its caller at
`run_cmd.py:5201` passes the static set plus `## Historical reviews` when the run state
has any. (`## Tests` stays not required, unchanged.)

### E. Prose (R10)

`plugins/super-fr/skills/fr-goal/SKILL.md` — the "Work already in flight" paragraph
(`:36-39`) and §7's stranded-run recovery (`:103`), including the cross-session review
case of §A; `plugins/super-fr/workflows/fr-goal.yaml`'s stranded-run comment
(`:43-49`); `docs/explainers/01-fr-goal.md` near its `fr run adopt` paragraph (`:310`)
and its `.html`, regenerated per `.claude/rules/explainers-currency.md`. Mirrors
regenerated with `scripts/sync-opencode.py` and `scripts/sync-hermes.py`. README's
`fr run` row (`:259`) gains `reshape`.

## Non-goals

- **Shape pinning** (snapshotting the manifest into the cursor) — rejected by the
  operator: a cursor schema change that does not rescue runs already stranded.
- **Automatic reshape** inside `advance`/`resolve` — rejected: it mutates the cursor as
  a side effect of an unrelated command.
- Keeping a superseded run file beside its successor — rejected: every locator and
  archiver would need to learn to skip it.
- Carrying gate provenance or units for steps/members the new shape does not have.
- `fr pickup` on a drifted cursor (`pickup_cmd.py:247`) — pre-existing, outside the
  `fr run` read-only set; reshape removes the drift it trips on.

## Test Plan

Unit/CLI tests (CI), per requirement:

- **R1–R3 reshape:** preview writes nothing; `--yes` inserts an added-after-cursor step
  `pending` (the #891 `journal-check` case) and keeps every record; no-drift no-op;
  refusals — added step at/behind the cursor, removed step that holds a unit / a cleared
  gate / an emitted artifact, removed step that is the cursor, member change on a group
  holding units (and the rewrite on one holding none), schema mismatch; the drift
  message of `advance` names `fr run reshape`.
- **R4:** a drifted cursor answers `gates` and `status` with one warning while
  `advance` still refuses; a schema mismatch still refuses `gates`.
- **R5–R6 supersede:** the plain refusal names both ways on; `--supersede` with no run
  behaves as plain adopt; carry-forward of `answered_by` surfaces in `fr run gates`;
  review-member and `step/<id>` units adoption did not build are carried with their
  evidence; an open attempt arrives `abandoned` and is listed in the preview; the usage
  file is renamed; refusals for an unparseable old cursor and a live step record;
  same-day in-place overwrite; the commit subject names the superseded run.
- **R7:** `reviewer=historical` accepted for an entry between the implement return and
  `started`; refused after `started`, before the implement return, on a phase owing
  `visual`, and on a flat unit; no `unobserved=reviewer-return` note.
- **R8:** adoption infers a `done` review member from a journal; leaves it `pending`
  (with the note) for open findings, an unauthorized fix, a missing entry, a visual
  phase; the cursor lands past the group when all are reviewed.
- **R9:** status/check sentence and no debt; the PR body section is rendered, and
  `deliver` refuses a live PR body that lacks it.

Post-merge — operator-driven: none required beyond CI; the next real upgrade-spanning
run exercises it live.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-10-05-run-upgrade-midflight | `derio-net/super-fr` | `2026-10-05-run-upgrade-midflight` | — |
