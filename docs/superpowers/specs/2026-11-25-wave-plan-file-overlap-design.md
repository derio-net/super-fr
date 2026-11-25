# Wave planning: flag batches whose plans touch the same files

Issue: derio-net/super-fr#1577.

## Background

Today, batches of one wave conflict only at merge time. The conflict shows up when the second PR to touch a file
lands. Each conflict costs a hand-back, a session cycle, a full suite, a push and a fresh approval
(2026-11-19: #1550 twice, #1551 twice).

fr already has two partial signals, and neither one fires early enough:

- `fr.triage.batch.planned_merge_order` / `with_forecast` (`packages/fr/src/fr/triage/batch.py`)
  forecast conflicts from the open PRs' actual diffs (`PullRequest.files`). The Backlog's Batches
  fold renders that forecast (`fr.triage.render._merge_step`). A PR's diff is complete only near
  `deliver`, so the warning comes late.
- Every plan phase declares the paths it will touch: `PhaseHeader.files`
  (`packages/fr/src/fr/types.py`, the `files:` key of each `NN.yaml` in the plan folder). A
  batch's plan is written in the `plan` step of its fr-goal run on the batch branch, long before
  its PR is ready. Nothing in the triage engine reads it.

Facts the design rests on:

- A batch's dispatch event records its branch (`fr.triage.batch.last_dispatch(batch).branch`).
  Its run cursor is a `docs/superpowers/runs/<run-id>.yaml` on that branch. The cursor names the
  branch (`branch:`), and the step that wrote the plan records the plan folder in its `emitted`
  mapping (`steps.plan.emitted.plan` in both shipped shapes; `fr.run.model.StepRecord.emitted`).
  Under quiet or stealth placement the plan is not on the batch branch at all. `fr.triage.cursor.read_cursor`
  already reads cursors at a PR head through the git seam (`fr.triage.gitseam.Checkout`, with
  `list_dir` and `show`), keeping the reads version-tolerant over raw mappings.
- A batch whose `after:` names another cannot dispatch until that one is merged or obsolete
  (`fr.triage.batch.dependency_state`). Such a pair is serialised already.
- The repo's `.fr/triage.yaml` declares `generated:` (`TriageConfig.generated`), the globs of the
  files its `mirrors:` regenerate. It may also declare `version.files` (`VersionBlock.files`), the
  files every batch bumps. In both cases the merge resolves the conflict itself.
- Plans name globs as well as literal paths. This repo's plans routinely list `tests/**/*.py` and
  `docs/**/*.md`, so comparing glob against glob would flag nearly every pair.
- The live merge-readiness batch (#1578, #1581) is editing `fr/triage/kanban.py`,
  `fr/triage/kanban_render.py` and `fr/triage/model.py`. This change keeps its edits to the first
  two minimal and leaves `model.py` alone.

## Requirements

R1. For every batch whose derived stage is `dispatched` or `pr-open` and whose last dispatch records a branch, fr reads the plan that the batch's run records on that branch: the run cursor at `origin/<branch>` whose `branch:` names it, the plan folder named by the `plan` value of any of its steps' `emitted` mappings, and the union of every phase file's `files:` there.
R2. The read goes through the local clone's existing remote-tracking ref. It never fetches, never writes and never calls the forge. A batch is listed as not compared, with the reason, when its repo is unknown (`repo of batch unknown`), when the clone has no `origin/<branch>` ref (`no ref origin/<branch>`), when no cursor there names the branch (`no run cursor`), when the cursor records no plan (`no recorded plan`, which also covers quiet and stealth placement), or when a cursor or phase file cannot be read (`unreadable <path>: <why>`). It is never reported as overlapping.
R3. Two compared batches of the same repo overlap on a path P when both name P literally, or when one names P literally and a glob of the other matches P (`fnmatch.fnmatchcase`, where `*` spans `/`). Two globs never make an overlap.
R4. A path that matches the repo's `generated:` globs or its `version.files` globs is never an overlapping path.
R5. A pair linked by an `after:` chain, in either direction and through any number of batches, is not compared. Every other pair is compared, whatever their waves.
R6. `fr triage check` reports a `plan overlap` set. Each entry names both batch ids, their waves, the shared paths and the fix: merge the two into one batch, or order one after the other with `fr triage batch edit <id> --after <other>` or a later `--wave`. The not-compared batches are listed after the entries, with their reasons. `--json` carries the same data under a `plan_overlap` key. The command still always exits 0.
R7. The Batches page (`fr triage batches`, and the board the driver renders) shows each overlap on the cards of both batches: the other batch, the shared paths and the same fix.
R8. The check is advisory only. No dispatch, merge, drive pass or approval changes because of it, and neither `facts.json` nor `judgements.yaml` changes shape.
R9. `fr triage check` and `fr triage batches` read through the git toplevel of the current directory, and only for the repo that is its `origin`. The driver's board reads through the driver's own clones (its `--checkout` map). A batch of a repo with no such clone is not compared, with the reason `no clone of <repo> here`. When the current directory is outside a clone, or the clone has no `origin`, every batch gets the reason `no clone here`.

## Design

### A. One new module, `fr/triage/plan_overlap.py`

Everything lives in this module, so the edits to the files the merge-readiness batch touches stay
small.

- `PlanSource` is a `Protocol` with `exists_at(ref, path) -> bool`,
  `list_dir(ref, directory) -> list[str]` and `show(ref, file) -> str | None`. `gitseam.Checkout` satisfies it, and tests use an in-memory
  fake.
- `read_plan_paths(source, branch) -> PlanPaths | Unread` (R1, R2). It reads at
  `refs/remotes/origin/<branch>`, first checking the ref with `exists_at(ref, "")` (the root tree) so a missing
  ref has its own reason. It lists the runs directory there (`fr.artifacts.paths.KIND_DIRS["run"]`,
  the constant `cursor.py` uses) and parses each `*.yaml` with `yaml.safe_load` as a raw
  mapping. It takes the first one whose `branch` equals *branch* and reads the first `plan` value
  among its steps' `emitted` mappings (every step is scanned, so a renamed step still works). It
  then lists that folder's `NN.yaml` files and collects each one's `phase.files`. Any
  `TriageError`, a YAML error or a missing key returns `Unread(reason)`. It never imports the
  plan parser, because a plan at a branch head may come from an older or newer fr.
- `overlaps(entries, *, ignore) -> list[Overlap]` (R3–R5) is pure. Each entry is a batch with its
  repo (`fr.triage.batch.batch_repo`; None is the `repo of batch unknown` reason), wave, `after`
  closure and `PlanPaths`. A path is a glob when it contains `*`, `?` or `[`.
  The shared paths of A and B are the literal∩literal paths, plus B's literal paths matched by A's
  globs, plus A's literal paths matched by B's globs, minus the paths that match *ignore*. The
  result is sorted, and pairs with no shared path are dropped. The `after` closure is computed
  over every batch in the state file, so a chain through a merged batch still counts.
- `plan_overlap_report(judgements, facts, source_for) -> OverlapReport` is the one entry point
  both callers use. `source_for(repo)` returns a `PlanSource` or the not-compared reason (R9).
  It selects the batches (R1), reads each one, takes *ignore* from
  `facts.config_for(repo).generated` plus `version.files`, and returns
  `OverlapReport(overlaps, unread)`.
- `fix_text(a, b) -> str` is the one wording of the fix (R6, R7), so the two surfaces cannot drift.
- `source_for_clones(cwd, checkouts) -> Callable[[str], PlanSource | str]` implements R9. With
  *checkouts* (repo → clone path, lowercased keys) it opens the named clone. Without it, it uses
  `gitseam.toplevel(cwd)` and `Checkout.origin_repo`, compares repos case-insensitively, and
  returns `no clone of <repo> here` for any other repo. A `GitError` from either path (no clone,
  no `origin`) becomes `no clone here`, never an exception.
- `card_lines(report) -> dict[str, tuple[str, ...]]` maps each batch id to its sentences, one per
  overlap: the other batch, the shared paths and `fix_text`.

### B. `fr triage check` (R6)

`check_command` (`fr/commands/triage_cmd.py`) calls `plan_overlap_report` with
`source_for_clones(Path.cwd(), None)` after `classify`. It prints a `plan overlap (<n>) — unmerged batches whose plans name the same files`
section, one entry per pair, followed by the not-compared lines. In `--json` mode it adds
`plan_overlap: {overlaps: [...], unread: [...]}` to the emitted object. `check.py`'s
`CheckResult` is not changed: the report is gathered in the command, because `classify` stays
pure over facts and judgements.

### C. The Batches page (R7)

`write_board` (`fr/commands/triage_kanban_cmd.py`) gains `checkouts: Mapping[str, Path] | None
= None`. It computes the report with `source_for_clones(Path.cwd(), checkouts)` and passes
`overlaps=card_lines(report)` (`Mapping[str, tuple[str, ...]]`, batch id → sentences) to
`build_board`. `kanban.Card` gets one defaulted field, `overlaps: tuple[str, ...] = ()`, filled
from that mapping. `kanban_render` prints a card's sentences as one `<p class="overlap">` block in
its detail. Each not-compared batch adds one line to the page's notes (the `notes` list
`write_board` already passes to `render_board`): `plan overlap not checked for <batch>: <reason>`.
The driver's `_write_board` (`triage_batch_cmd.py`) passes `checkouts=self.checkout_paths`, one
added line; `triage_drive_loop.py` goes through it. `batch_drive.py` is not edited. The board is a
view, so a failed read becomes a not-compared reason, never a refusal.

### D. What does not change (R8)

There is no new state file, no facts or judgements schema bump, no new event, no driver action
and no change to `merge_order`. The existing PR-diff forecast stays as it is.

## Design shape

```diff
  packages/fr/src/fr/triage/
+   plan_overlap.py              # read plan `files:` at a batch branch, the overlap rule, the fix wording
    kanban.py                    # board model: Card gains `overlaps`, build_board takes them
    kanban_render.py             # one overlap paragraph in a card's detail
  packages/fr/src/fr/commands/
    triage_cmd.py                # `fr triage check`: the `plan overlap` set, text and JSON
    triage_kanban_cmd.py         # write_board computes the report from the cwd clone or the driver's clones
    triage_batch_cmd.py          # the driver's _write_board passes its --checkout map
  tests/unit/
+   test_triage_plan_overlap.py  # reader over a fake source, the rule, after-chains, ignore globs
```

```text
plan_overlap_report(judgements, facts, source_for):
  for batch in batches with stage dispatched|pr-open and a dispatch branch:
    source = source_for(repo)            → str: unread "no clone (of <repo>) here"
    paths  = read_plan_paths(source, branch)  → Unread: listed with its reason
  overlaps(compared, ignore = generated + version.files)
    skip pairs in one after-chain; literal∩literal ∪ glob(A)∋literal(B) ∪ glob(B)∋literal(A)
```

## Verification

strategy: none
- plan-overlap-check: none — unit tests drive `plan_overlap_report` and `fr triage check` over fixture batches and a fake plan source in this PR's CI
- plan-overlap-board: none — unit tests build and render the board with overlaps in this PR's CI
gate: developer

## Test Plan

- pre-merge — CI: `tests/unit/test_triage_plan_overlap.py` covers the reader over the real cursor shape (`steps.plan.emitted.plan`) and real phase files (cursor found, plan read, and every R2 and R9 reason: unknown repo, no ref, no cursor, no recorded plan, unreadable file, no clone, no clone of the repo), the overlap rule (literal, glob against literal, glob against glob not counted, `generated:` and `version.files` ignored), `after` chains in both directions and through a third batch, cross-wave pairs, and R9's clone rule (row `plan-overlap-check`).
- pre-merge — CI: `fr triage check` text and `--json` output with overlaps and unread batches, exit 0 (row `plan-overlap-check`).
- pre-merge — CI: the board model and render show the overlap on both cards and a note per not-compared batch, and `write_board` with a `checkouts` map reads through those clones (row `plan-overlap-board`).

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-25-wave-plan-file-overlap | `derio-net/super-fr` | `2026-11-25-wave-plan-file-overlap` | — |
