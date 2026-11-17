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
- **d8 (#1394, scope; asked at implement).** The recovery first read row definitions, not the fold: 9 of the 17 rows had been re-noted on 2026-11-14. The 4 `walk-owed` ones get their old text spliced in before the tracker; the 5 `walked` ones are left alone.
- **d7 (verification).** CI tests verify every row; no walk, gate `developer`, no Test
  Plan.

## Requirements

R1. `fr acceptance amend --id <row> --op reword --origin <ref>` given neither `--acceptance` nor `--capability` rewrites only the row's `origin`: the row's own `acceptance` and `capability` in its fragment stay byte-identical, even when a pending `reword` amendment of that row exists.
R2. An origin-only reword still refuses a merged row, an unknown row and a non-`reword` op, as today, and writes nothing when it refuses.
R3. Of the 17 rows whose note the gate-backfill sweep replaced with a bare `tracked by derio-net/super-fr#N`, and whose note before the sweep was more than `post-merge walk owed (gate backfill)`, each row whose effective note is still that bare note (8 rows) carries the note it held before the sweep followed by `; tracked by derio-net/super-fr#N`; each `walk-owed` row whose later note still opens with that bare tracker (4 rows: ci-under-time-budget, debt-archive-pr-weekly, debt-weekly-issue-rename, exit-gates-release-gating) has that opening replaced by `<old note>; tracked by derio-net/super-fr#N.`, keeping the rest of its note. The 5 rows later `walked` keep their walk notes (decision d8). Status, levels and `issues:` are unchanged.
R4. The restore is written as `set-status` amendments in this feature's fragment (the rows are merged), never as in-place edits of their fragments; the 16 rows whose old note was only the gate-backfill boilerplate are not touched.
R5. When a spec's bytes are not valid UTF-8, every read the migration runner makes of it — the stamp read (`read_verbatim`) and the Test Plan heading repair's predicate and rewrite — fails with the reason `<path> is not UTF-8 text (byte 0x<hh> at offset <n>)`; the file is left byte-identical.
R6. A `docs/acceptance/matrix.yaml` that is not valid UTF-8 fails the same way, with the same reason shape, in its stamp read and in the retiring split hop (`fr.artifacts.matrix_fragments`, including the `#L<n>` conversion it applies), and is left byte-identical. (`MATRIX_NAME_ANCHORS_REPAIR` is not registered since the matrix kind retired; its own `read_text` calls go through the same reader.)
R7. `fr migrate artifacts` and the CLI-entry gate's refusal print that reason for the file, never a Python codec message, and the gate still refuses over it. Every place the runner reports a raised exception uses one formatter, which prints this reason alone.
R8. One module answers "which of these paths does git ignore" and "is this one path ignored"; `acceptance_cmd._committable`, `artifacts/commit.py`, `isolation/scaffold.py` and `run/visual.py` call it instead of running `git check-ignore` themselves, with their current behaviour unchanged: the set listing reads `check-ignore -z` output (so a path with spaces or non-ASCII bytes matches its input), treats exit 0 and 1 as answers, and returns no paths on any other exit or when git is missing (each set-listing site then drops nothing, as today); the one-path probe answers False on any error. `triage/gitseam.py` is not changed.
R9. `fr run adopt <plan-dir>` and `fr migrate artifacts --yes --adopt`, given no `--run-id`, name an adopted run after its plan folder's slug. Adopting a spec with no plan keeps today's `<date>-<branch>` id, so a spec-only run never takes the id its plan's later adoption needs (bulk adoption offers plans only).
R10. `fr migrate artifacts --yes --adopt` on one branch with N adoptable plans adopts all N, one run each, and a follow-up dry run offers none of them.
R11. An explicit `--run-id` still wins; an id that already names a run is still refused, except the run `--supersede` replaces.
R12. When the branch an adopted run records is the repository's default branch (the remote default ref with its remote prefix removed: `origin/main` → `main`), adoption prints one warning for that run naming the branch and `--branch <b>`; it still adopts. With no remote, or a default ref fr cannot name, there is no warning.
R13. A `Repair` on the `acceptance-fragment` kind renames `docs/acceptance/features/<slug>-design.yaml` to `<slug>.yaml` and sets its `feature:` key to `<slug>`, leaving every row and amendment as it was.
R14. When both files exist, the repair moves every row and amendment of the `-design` file into `<slug>.yaml`, keeps an entry identical in both once, and deletes the `-design` file. When the two hold one id differently, it writes nothing, leaves both files byte-identical, and fails that artifact with a reason naming the id.
R15. After the repair the effective matrix (`fr.acceptance.fold`) is the one before it, row for row; the repair refuses, writing nothing, when it would not be.
R16. The repair holds back, like any artifact the operator is mid-edit in, when `<slug>.yaml` has uncommitted changes.
R17. After the repair, `fr acceptance check` and `deliver`'s merged-row rule (R16 of spec `2026-11-04-repo-feature-settings`) report no edit: a fragment merged on the default ref as `<slug>-design.yaml` is compared, row and amendment by id, with the branch's `<slug>.yaml`, on a branch and in CI on the default branch (in-place migration) alike.

## Design

### A. Origin-only reword keeps the row's statement (R1, R2)

The CLI keeps filling the item's `acceptance` for an origin-only reword (the record
model's `AmendmentItem` validates through `fr.acceptance.fragment.Amendment`, which needs
an `acceptance` or `capability`), but reads it from the row's own definition in the
pending fragment that holds it, not from `effective(root)`
(`acceptance_cmd.py:1050-1055`). `_reword_pending` then writes
`item.acceptance or existing.acceptance`, which is the row's own statement, unchanged.
No model, record or fragment shape changes. A row not pending on this branch keeps
today's path to `_reword_pending`'s refusals (R2); the CLI reads no statement for it.

### B. Restoring the 17 notes (R3, R4)

A one-off data change, made with `fr acceptance set-status --id <row> --status <its
current status> --notes "<old>; tracked by derio-net/super-fr#N" --feature
2026-11-17-batch-acceptance-edits` per row, so each lands as an amendment in this
feature's fragment. The old text is the row's last note in `docs/acceptance/matrix.yaml`
history that is not a bare `tracked by …` note; the recovery script lives outside the
repo, and its output (row → old note) is recorded in the plan journal as a discovery so a
reviewer can check each restore against history.

### C. Undecodable files are named (R5–R7)

`fr.artifacts` gets `NotUtf8Error(ValueError)` and the decode that raises it: message
`<path> is not UTF-8 text (byte 0x<hh> at offset <n>)`, from the codec error's `start`.
`read_verbatim` (`registry.py:148`, under every stamp reader) decodes through it, as do
the heading repair's `_applies`/`_fn` (no newline translation kept), `matrix_anchors`'
`conversions`/`_fn` and the split hop's reads (`matrix_fragments.py:258`, :270).
`conversions` keeps returning `{}` only for `OSError`. The runner's seven
`f"{type(e).__name__}: {e}"` sites (`runner.py:453`, :496, :554, :725, :785, :819, :866)
call one `describe(e)`, which returns the message alone for `NotUtf8Error` and today's
text otherwise. Tests run through `run_migrations` and the gate's refusal.

### D. One `check-ignore` helper (R8)

In `fr.git` (`packages/fr/src/fr/git.py`, beside `git_answer` at :113):
`ignored_paths(root, paths) -> set[str]` runs `git check-ignore -z --stdin` once through
`git_answer` (paths on stdin: git refuses `-z` with paths on the command line), splits on NUL, and returns an empty set on any exit but 0/1 and on
`GitUnavailableError`; `is_ignored(root, path) -> bool` runs `check-ignore -q` and is
False on any error, git missing included. `_committable`, `commit.py`'s
`_without_ignored`, `scaffold.py:672-674` and `visual.py`'s `git_ignored` call them.
Each site's current error behaviour is pinned by a test before the switch; the one
narrowing is that a missing git at the two one-path sites reads as "not ignored" instead
of raising `FileNotFoundError`, which every other failure there already does.

### E. Adopted run ids come from the plan (R9–R12)

In `adopt_run`, with no `run_id`: `rid = validate_run_id(<plan folder name>)` when a plan
was observed, else `derive_run_id(resolved_branch)` as today (R9; a spec stem would equal
the plan folder name its plan's adoption later needs). `derive_run_id` stays for `fr run
start`. The module docstring (:35) and `fr run adopt`'s help say so. `--supersede`
already handles an id change (its usage file moves, `_usage_move`). `migrate_cmd`'s bulk
loop needs no change beyond the id: each plan gets its own. The default-branch warning reads
`fr.git.remote_default_ref` (git.py:181) directly, strips the remote prefix (the remote's
name and one `/`), compares with `resolved_branch`, and is appended to `notes` (the
outparam both callers print). `None`, a `GitRefusal` or `GitUnavailableError` mean no
warning.

### F. The `-design` fragment repair (R13–R17)

A new module `fr.artifacts.fragment_design_name`, imported by `fr/artifacts/__init__.py`,
registers `Repair(kind="acceptance-fragment", …)` with
`companions=lambda p: [p.with_name(<slug>.yaml)]`, so the uncommitted-changes veto
(`runner.py:564-595`) holds a `<slug>.yaml` the operator is editing (R16). `applies(path)`:
the file name ends `-design.yaml` and its `feature:` key equals the stem. `fn(path)` builds
everything in memory: the renamed fragment, or the merge into an existing `<slug>.yaml`
(its rows and amendments first, then the `-design` file's, an identical entry once,
refusing on an id held differently), checks the fold of the new set equals the fold of
the old one, then writes `<slug>.yaml` through `write_text_atomic`, deletes the `-design`
file, and returns `<slug>.yaml` as `also_wrote`. The deleted path is the action's own
`path`, which `changed_paths` already includes (`runner.py:226-230`), and `commit_paths`
stages its deletion through `git add` (`commit.py:997-1007`, :1039), so no new runner
support is needed; a test pins the staged deletion.

R17: `merged_row_edits` and `outside_merged_row_edits` (`fr/acceptance/amend.py:127-189`)
key the default ref's fragments by their one spelling, `<slug>.yaml`: a tip (and merge
base) holding `<slug>-design.yaml` is read as that fragment, merged with a `<slug>.yaml`
there by the repair's own merge rule, before the comparison with the branch's
`<slug>.yaml`. The merged-amendments-lead check reads the combined list in the repair's
order. Tests hold a merged `-design` fragment on a fixture default ref.

## Verification

strategy: none
gate: developer

- acceptance-amend-origin-only-keeps-statement: none — verified by CI unit tests of the amend command
- spec-repairs-name-undecodable-files: none — verified by CI unit tests of both repairs and the gate's refusal text
- adopt-run-id-from-plan-slug: none — verified by CI unit tests of `fr run adopt` and `fr migrate artifacts --adopt`
- adopt-default-branch-warning: none — verified by CI unit tests of the adoption notes
- fragment-design-spelling-repair: none — verified by CI unit tests of the repair and `fr acceptance check` over fixture fragments on a fixture default ref

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
| `fragment-design-spelling-repair` | R13–R17 | `fr migrate artifacts` leaves one fragment per feature. |

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| 2026-11-17-batch-acceptance-edits | `derio-net/super-fr` | `2026-11-17-batch-acceptance-edits` | — |
