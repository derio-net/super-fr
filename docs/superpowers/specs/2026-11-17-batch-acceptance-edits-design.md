# Acceptance edits and artifact adoption — design

Batch `acceptance-edits`: derio-net/super-fr#1439, #1394, #1390, #1154, #1219, #1461,
delivered as one PR on `feat/batch-acceptance-edits`.

## 1. Goal

Six small defects in how `fr` edits acceptance fragments and adopts or repairs
artifacts. Each fix also repairs what older versions already wrote, where they wrote
anything: a fix that stops new damage but leaves the old damage in place is half a fix.

- **#1439.** An origin-only `fr acceptance amend --op reword --origin …` fills the
  item's `acceptance` from the effective (folded) matrix
  (`packages/fr/src/fr/commands/acceptance_cmd.py:1050-1055`). A row with a pending
  reword amendment then gets the amended statement written into its own definition, so
  the fragment states the amendment twice. The engine already keeps the row's own
  statement when the item carries none (`packages/fr/src/fr/record/apply.py:1180-1185`,
  `_reword_pending`); the CLI is what fills it.
- **#1394.** `fr gate backfill`'s old printed link commands replaced row notes. The
  command is fixed (#1387), but 33 rows in `docs/acceptance/features/*.yaml` still hold
  a bare `notes: tracked by derio-net/super-fr#N`. For 17 of them the note before the
  sweep held real text, recoverable from `docs/acceptance/matrix.yaml`'s history before
  the fragment split (#1408); the other 16 held only `post-merge walk owed (gate
  backfill)` and need nothing.
- **#1390.** `_applies` in `packages/fr/src/fr/artifacts/spec_test_plan_heading.py:79-80`
  calls `path.read_text()` and `_fn` (:83-84) calls `.decode("utf-8")`;
  `packages/fr/src/fr/artifacts/matrix_anchors.py` reads its file with `read_text()` in
  `conversions` (:61) and `_fn` (:102). On non-UTF-8 bytes each raises
  `UnicodeDecodeError`. The runner records a raising `applies` as a `FailedAction`
  (`packages/fr/src/fr/artifacts/runner.py:551-555`), `inspection_failures` reports it,
  and the CLI-entry gate refuses — correctly, but with the raw Python codec message.
- **#1154.** `git check-ignore` is run ad hoc in `acceptance_cmd._committable` (:1440),
  `artifacts/commit.py:505`, `isolation/scaffold.py:672-674`, `run/visual.py:243-247` and
  `triage/gitseam.py:905-911`.
- **#1219.** `adopt_run` derives the run id from the checked-out branch
  (`packages/fr/src/fr/run/adopt.py:864`, :921: `derive_run_id(resolved_branch)`), so
  every plan adopted on one branch gets the same `<date>-<branch>` id and every plan
  after the first is refused at :927-931. `fr migrate artifacts --yes --adopt` on one
  branch therefore adopts one plan. Completed plans are already excluded from the offer
  set (`adoptable_plans`, :1127), so that part of the issue's ask needs nothing.
- **#1461.** Fragments created before #1451 are `<slug>-design.yaml` with
  `feature: <slug>-design`; every writer since creates `<slug>.yaml`, so one feature can
  hold two fragments. No such fragment exists in this repo today; consumer repos have
  them.

### Non-goals

- `triage/gitseam.py` keeps its own `check-ignore` call (d6): triage's git calls stay in
  its seam.
- No change to which plans adoption offers.
- No new artifact kind and no stamp bump: #1461 is a `Repair` (a constraint, the file's
  name and its `feature:` key, not the shape).

## 2. Operator decisions (question round 1)

- **d1 (#1219, id).** Every adoption that is given no `--run-id` takes its run id from
  the plan folder's slug (already `YYYY-MM-DD-<slug>`), single `fr run adopt` and bulk
  `--adopt` alike.
- **d2 (#1219, branch).** The run's `branch` stays the checked-out branch, but when that
  is the repository's default branch, adoption says so once per adopted run and names
  `--branch`.
- **d3 (#1461).** When both `<slug>-design.yaml` and `<slug>.yaml` exist, merge into
  `<slug>.yaml`; an entry identical in both is kept once; an id held differently leaves
  both files byte-identical and fails that artifact, naming the id.
- **d4 (#1394).** A restored note is the old note followed by
  `; tracked by derio-net/super-fr#N` (the tracker the bare note named).
- **d5 (#1390).** A file fr cannot decode keeps refusing (unknown state is not current),
  with one plainly named reason instead of the codec error.
- **d6 (#1154).** One shared helper module offers a set listing and a one-path probe; the
  four non-triage call sites use it, `gitseam` keeps its own.
- **d7 (verification).** CI tests verify every row; no walk, gate `developer`, no Test
  Plan.

## Requirements

R1. `fr acceptance amend --id <row> --op reword --origin <ref>` given neither `--acceptance` nor `--capability` rewrites only the row's `origin`: the row's own `acceptance` and `capability` in its fragment stay byte-identical, even when a pending `reword` amendment of that row exists.
R2. An origin-only reword still refuses a merged row, an unknown row and a non-`reword` op, as today, and writes nothing when it refuses.
R3. Each of the 17 rows whose note the gate-backfill sweep replaced with a bare `tracked by derio-net/super-fr#N`, and whose note before the sweep was more than `post-merge walk owed (gate backfill)`, carries the note it held before the sweep followed by `; tracked by derio-net/super-fr#N`, with its status, levels and `issues:` unchanged.
R4. The restore is written as `set-status` amendments in this feature's fragment (the rows are merged), never as in-place edits of their fragments; the 16 rows whose old note was only the gate-backfill boilerplate are not touched.
R5. When a spec's bytes are not valid UTF-8, the Test Plan heading repair's predicate and its rewrite refuse with the reason `<path> is not UTF-8 text (byte 0x<hh> at offset <n>)`; the file is left byte-identical.
R6. The `matrix_anchors` repair refuses the same way, with the same reason shape, for a `matrix.yaml` that is not valid UTF-8.
R7. `fr migrate artifacts` and the CLI-entry gate's refusal print that reason for the file, never a Python codec message, and the gate still refuses over it.
R8. One module answers "which of these paths does git ignore" and "is this one path ignored"; `acceptance_cmd._committable`, `artifacts/commit.py`, `isolation/scaffold.py` and `run/visual.py` call it instead of running `git check-ignore` themselves, with their current behaviour unchanged. `triage/gitseam.py` is not changed.
R9. `fr run adopt <plan-dir>` and `fr migrate artifacts --yes --adopt`, given no `--run-id`, name an adopted run after its plan folder's slug; adopting a spec with no plan names the run after the spec's slug (its file stem without `-design`).
R10. `fr migrate artifacts --yes --adopt` on one branch with N adoptable plans adopts all N, one run each, and a follow-up dry run offers none of them.
R11. An explicit `--run-id` still wins; an id that already names a run is still refused, except the run `--supersede` replaces.
R12. When the branch an adopted run records is the repository's default branch, adoption prints one warning for that run naming the branch and `--branch <b>`; it still adopts.
R13. A `Repair` on the `acceptance-fragment` kind renames `docs/acceptance/features/<slug>-design.yaml` to `<slug>.yaml` and sets its `feature:` key to `<slug>`, leaving every row and amendment as it was.
R14. When both files exist, the repair moves every row and amendment of the `-design` file into `<slug>.yaml`, keeps an entry identical in both once, and deletes the `-design` file. When the two hold one id differently, it writes nothing, leaves both files byte-identical, and fails that artifact with a reason naming the id.
R15. After the repair the effective matrix (`fr.acceptance.fold`) is the one before it, row for row; the repair refuses, writing nothing, when it would not be.

## Design

### A. Origin-only reword keeps the row's statement (R1, R2)

Delete the CLI's fill at `acceptance_cmd.py:1050-1055`. `AmendmentItem` (record model)
validates a `reword` against `fr.acceptance.fragment`'s amendment, which needs an
`acceptance` or `capability`; an origin-only correction carries neither. Add an explicit
origin-only form to the item, `origin_only: bool = False`, accepted only with `op:
reword` and neither field, and only on the CLI's `--origin` path (the engine receives
`origins`; a record's `acceptance:` entry cannot set it, so the record kind's shape is
unchanged). `_reword_pending` already keeps `existing.acceptance`/`existing.capability`
when the item has none. The amendment-op validation in `fr.acceptance.fragment` is not
touched: no amendment is written by an origin correction.

### B. Restoring the 17 notes (R3, R4)

A one-off data change, made with `fr acceptance set-status --id <row> --status <its
current status> --notes "<old>; tracked by derio-net/super-fr#N" --feature
2026-11-17-batch-acceptance-edits` per row, so each lands as an amendment in this
feature's fragment. The old text is the row's last note in `docs/acceptance/matrix.yaml`
history that is not a bare `tracked by …` note; the recovery script lives outside the
repo, and its output (row → old note) is recorded in the plan journal as a discovery so a
reviewer can check each restore against history.

### C. Undecodable files are named (R5–R7)

A small helper in `fr.artifacts` (beside `atomic.py`), `read_utf8(path) -> str`, reads
bytes and decodes, raising `NotUtf8Error(ValueError)` whose message is
`<path> is not UTF-8 text (byte 0x<hh> at offset <n>)` from the codec error's `start`.
Both repairs read through it (`_fn` of the heading repair keeps its no-newline-translation
decode). The runner already formats a raised exception as `f"{type(e).__name__}: {e}"`;
for `NotUtf8Error` it prints the message alone, so the gate and `fr migrate artifacts`
show the named reason.

### D. One `check-ignore` helper (R8)

`fr.git` (`packages/fr/src/fr/git.py`, beside `git_answer` at :113): `ignored_paths(root, paths) -> set[str]` (one `git check-ignore --`
call, exit 0 and 1 both answers, the paths it prints) and `is_ignored(root, path) ->
bool` (`check-ignore -q`). The four call sites switch to it. The helper takes the repo root and runs git through
`git_answer`.

### E. Adopted run ids come from the plan (R9–R12)

In `adopt_run`, with no `run_id`: `rid = validate_run_id(<plan folder name>)` when a plan
was observed, else the spec stem without `-design`. `derive_run_id` stays for `fr run
start`. The module docstring (:35) and `fr run adopt`'s help say so. `--supersede`
already handles an id change (its usage file moves, `_usage_move`). `migrate_cmd`'s bulk
loop needs no change beyond the id: each plan gets its own. The default-branch warning
compares `resolved_branch` with the default branch `fr.acceptance.amend.default_ref_name`
already resolves, and is appended to `notes` (the outparam the callers already print).

### F. The `-design` fragment repair (R13–R15)

A new module `fr.artifacts.fragment_design_name`, imported by `fr/artifacts/__init__.py`,
registers `Repair(kind="acceptance-fragment", …)`. `applies(path)`: the file name ends
`-design.yaml` and its `feature:` key equals the stem. `fn(path)` builds everything in
memory: the renamed fragment (or the merge with an existing `<slug>.yaml`, refusing on an
id held differently), checks the fold of the new set equals the fold of the old one, then
writes through `write_text_atomic` and removes the `-design` file, returning the written
path as `also_wrote`. The plan confirms the runner stages a removal made by a repair (it
does for a retiring migration, `PlannedAction.removed`), and adds that support if not.

## Verification

gate: developer

- acceptance-amend-origin-only-keeps-statement: none — verified by CI unit tests of the amend command
- spec-repairs-name-undecodable-files: none — verified by CI unit tests of both repairs and the gate's refusal text
- adopt-run-id-from-plan-slug: none — verified by CI unit tests of `fr run adopt` and `fr migrate artifacts --adopt`
- adopt-default-branch-warning: none — verified by CI unit tests of the adoption notes
- fragment-design-spelling-repair: none — verified by CI unit tests of the repair over fixture fragments

There is no `## Test Plan` (d7). R3–R4 (the note restores) are a one-off data correction
proven by the amendments in this PR's diff and the journal's recovery record; R8 is an
internal refactor. Neither is a business-level claim, so neither has a row.

## Acceptance rows

| Row | Requirements | Claim |
|---|---|---|
| `acceptance-amend-origin-only-keeps-statement` | R1, R2 | An origin correction never restates a pending reword in the row. |
| `spec-repairs-name-undecodable-files` | R5–R7 | A non-UTF-8 artifact is refused by name, not with a codec error. |
| `adopt-run-id-from-plan-slug` | R9–R11 | Bulk adoption on one branch adopts every in-flight plan. |
| `adopt-default-branch-warning` | R12 | Adopting onto the default branch is said, not silent. |
| `fragment-design-spelling-repair` | R13–R15 | `fr migrate artifacts` leaves one fragment per feature. |

## Implementation Plans

- `docs/superpowers/plans/2026-11-17-batch-acceptance-edits/` (written at `plan`).
