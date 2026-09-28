# Close-out is an always condition — keyed on the branch

**Date:** 2026-09-28
**Issue:** derio-net/super-fr#733 (batch `closeout-always-2`)
**Branch:** `feat/batch-closeout-always-2`
**Journal:** `docs/superpowers/journals/specs/2026-09-28-closeout-always.md`

## Requirements

| id | requirement | source |
|---|---|---|
| R1 | Any fr flow's branch can be closed out with one command: `fr pickup --branch <b>` prints a close-out brief (verify-merge, housekeeping workspace, archive, commit/push/PR, isolation down) built from git alone. No run cursor is needed. | input "One close-out keyed on the branch"<br>input "Key it on the **branch**, not the skill or the run cursor, because every flow ends with a branch and a PR."<br>decision d1-surface |
| R2 | `fr pickup --run <id>` is a caller of the branch brief. It adds only the run-specific lines (PR, spec/plan, Test Plan, out-of-scope filing lines) and has no second close-out path. | input "fr-goal's `fr pickup --run` becomes a caller of it, not a second path."<br>decision d1-surface |
| R3 | `fr archive --branch <b>` archives every live artifact the branch added or modified: plans, specs, and journals of every scope, debug included, plus the runs and usage files that follow a plan. Each passes its own kind's gate. An artifact whose gate holds it back is reported, never silently skipped. | input "archive every live artifact the branch *added* (plans, specs, and journals of every scope, `debug` included);"<br>decision d2-added-and-modified |
| R4 | "What did the branch touch" reuses the hardened branch-diff logic behind `branch_changes_present`. `fr archive --branch` refuses (exit 2) a branch whose changes are not present on the default ref. | input "already has hardened diff logic in `branch_changes_present`"<br>input "`fr isolation verify-merge`;" |
| R5 | `fr status` reports every live artifact whose introducing PR has merged: a debug journal live on the default ref, a plan the archive gate would pass, a spec the sweep would move, and a plan/spec journal whose owner is already archived. Each is listed with the command that clears it. This is advisory and never fails CI. | input "a live artifact is legal only while the PR that introduced it is open."<br>input "report every live artifact whose introducing PR has merged,"<br>decision d3-status-advisory |
| R6 | fr-debugging's deliver relays the same close-out line, `fr pickup --branch <b>`, that fr-goal's run relays. It does this without gaining a run cursor. | input "fr-debugging's deliver relays the close-out line."<br>input "**fr-debugging's `deliver`** relays the same close-out line fr-goal does."<br>decision d4-no-debug-cursor |
| R7 | This PR sweeps every debug journal live on `main`, using the new code (`fr archive --all` learns debug journals), and no evidence ref to a moved journal breaks. | input "The first run sweeps the 26."<br>decision d5-sweep-in-pr |

## Deferred from input

| input | reason |
|---|---|
| "and/or `fr triage check`" | Operator chose `fr status` only (d3-status-advisory). |
| "#458 (`fr archive` offering to file open ends) belongs in the same close-out step." | #458 is its own issue. This change only lists open debug findings in the brief, the same way fr-goal's run brief lists out-of-scope ones (§D). |
| "closeout-queue (#667) builds on this." | A follow-up that loops over R1, one branch per merged batch. It is out of this change. |

## Background

Only fr-goal has a close-out today. `fr pickup --run` (`packages/fr/src/fr/commands/pickup_cmd.py:46`)
calls `closeout_brief` (`packages/fr/src/fr/run/closeout.py:125`), which needs a done `deliver`
step and names `fr archive <plan-dir>`. fr-debugging's §4 Deliver
(`plugins/super-fr/skills/fr-debugging/SKILL.md:101`) ends at "Stop — the operator merges".
`fr archive` (`packages/fr/src/fr/commands/archive_cmd.py:78`) moves plan dirs, their runs, usage
and plan journals (`archive.py:374` `archive_plan_dir`, `:467` `_archive_run`, `:513`
`_archive_journal`), then specs and their journals via `spec_archive_sweep` (`archive.py:531`).
Nothing moves a debug journal. At `1f31d2e6`, 36 debug journals are live under
`docs/superpowers/journals/debug/`. Four were archived by hand in #782.

`docs/acceptance/matrix.yaml` cites debug journals as evidence 22 times, and `fr acceptance
check` fails on a ref that does not resolve. `archive_twin` (`packages/fr/src/fr/acceptance/model.py:46`)
already makes refs to a spec resolve on either side of `specs/` ↔ `implemented/specs/`, and nothing
does the same for journals.

## Design

### §A. Branch artifacts — one helper, the existing diff

`fr.isolation.local` gains `branch_changed_paths(run, repo_root, branch, base_ref) -> list[str]`.
It is the first half of `branch_changes_present` (`local.py:624`) lifted out: `merge-base`, then
`_fork_point`, then `_diff_names([fork, branch])`. `branch_changes_present` calls it, so the two
cannot drift (#696/#727/#716 all hardened that one path).

A new module `fr.closeout` holds the pure classification:

```python
@dataclass(frozen=True)
class BranchArtifact:
    kind: Literal["plan", "spec", "journal", "run", "usage"]
    path: Path          # repo-relative, live location
    owner: str | None   # plan dir name / spec slug for followers; journal scope for journals

def branch_artifacts(repo_root: Path, changed: Iterable[str]) -> list[BranchArtifact]
```

The function keeps only paths under the live artifact roots (`docs/superpowers/{plans,specs,
journals/{specs,plans,debug},runs,usage}`) that still exist in the working tree, so deletions
drop out. Files under one plan dir collapse into one `plan` artifact. Added and modified are
treated alike (d2).

### §B. `fr archive --branch <b>`

`--branch` is a fourth mode of `archive_command`. It is mutually exclusive with `plan_dir`,
`--all`, `--sweep-only` and `--force`, and each conflict is refused with exit 2 in the existing
`--sweep-only` style.

1. `merge_evidence(repo_root, fetch=True)` supplies the default ref. If there is none, refuse
   (exit 2) naming `ref_error`.
2. Run `branch_changes_present(branch, <default ref>)`. If it is not present, refuse with exit 2,
   listing the missing paths and pointing at `fr isolation verify-merge --branch <b>`. This is
   the mutating step's own guard; the brief still runs verify-merge (with its PR-state check)
   first.
3. Compute `branch_artifacts(branch_changed_paths(...))`, then per kind:
   - **plan**: the same path a single `fr archive <dir>` takes (`archive_blockers`, `paths_dirty`,
     `archive_plan_dir`, which already moves its run, usage and plan journal). A blocked plan is
     a `held:` line with its blockers, never a failure of the command.
   - **spec**: after the plan moves, run `spec_archive_sweep` once, exactly as today, and report
     only its moves. A branch spec that stays live prints `held: <spec> — <note>`.
   - **journal, scope debug**: live on the default ref means done (d2/d3). Move it with
     `_archive_journal(repo_root, "debug", slug)`.
   - **journal, scope plan/spec**: it follows its owner. It moves only when the owner moved in
     this run or is already archived (§C's orphan rule). Otherwise it is held, naming the owner.
   - **run / usage** that no plan move carried: held, naming the plan it follows.
4. Repair in passing through the existing `_repair_in_passing`, once. Print one line per artifact
   (`archived:` / `held:`), then the "moves staged via git mv" footer. If the branch touched no
   artifact, print `nothing to archive for <b>` and exit 0.

### §C. `fr archive --all` learns debug journals; one "owed" predicate

`fr.closeout.owed_artifacts(repo_root, evidence) -> list[Owed]` is the ONE definition of "live
but its PR merged". It reads the working tree and the default ref only; it makes no forge call:

- **debug journal**: live, and the same path exists on the default ref.
- **plan**: already computed by `status_cmd._sweep_lists`' `archivable` bucket. It is moved into
  `fr.closeout` so status and archive share it.
- **spec**: `_spec_fully_implemented(spec, repo_root, gh=None)` is true. A cross-repo row that
  cannot be resolved without the forge is simply not listed, because it is unknown rather than
  owed.
- **orphan plan/spec journal**: live, while its owner (`implemented/plans/<slug>/` or
  `implemented/specs/<slug>-design.md`) is already archived.

`fr archive --all` (after its plan loop and spec sweep, as today) also moves every owed debug
journal and every orphan journal. `--no-spec-sweep` does not affect them, because they are not
specs.

### §D. `fr pickup --branch <b>` — the brief; `--run` becomes a caller

`closeout_brief` is split. `branch_closeout_brief(repo_root, branch, *, run_extras=None)` builds
the brief. `closeout_brief(repo_root, state)` keeps its done-`deliver` refusal and calls it with
the run's extras (PR, spec, plan, Test Plan line, out-of-scope lines). The brief:

```
branch: <b>
[PR / spec / plan lines — run mode only]
Run this from <primary checkout> — the base clone, after the branch's PR has merged.

Closeout, in order:
  fr isolation verify-merge --branch <b>
  STOP here if that refuses — the branch is not actually merged yet.
  [run the spec's Test Plan: <spec> — run mode, when present]
  fr status
  fr isolation up --branch <housekeeping>   # from the base clone above — …
  [file an issue for each finding below … + one `fr journal resolve` line each]
  fr archive --branch <b>   # inside the new <housekeeping> workspace
  git add -A && git commit -m 'chore: close out <b>' && git push -u origin <housekeeping>
  open the housekeeping PR (e.g. `<forge pr command>`)
  fr isolation down --branch <b>
```

- The housekeeping branch is `chore/archive-<plan-slug>` when the run names a plan (unchanged),
  and `chore/closeout-<branch-slug>` otherwise (`/` → `-`).
- The findings lines come from the run's spec/plan journals (unchanged) **plus** every debug
  journal in `branch_artifacts` whose effective finding state is `out-of-scope` or `open`, using
  the same `_out_of_scope_lines` shape with `--scope debug`. Unlike the old brief, which printed
  them only when a plan existed, the housekeeping step is now always printed, because
  `fr archive --branch` always has something to consider.
- `fr pickup --branch` refuses (exit 2) a branch that resolves neither locally nor as
  `origin/<b>`, and refuses in combination with a plan dir, `--phase` or `--run`.

### §E. fr-debugging relays the line

fr-debugging §4 Deliver gains one sentence after the PR opens: relay
`closeout: fr pickup --branch <branch>` to the operator verbatim; after merge, a NEW session runs
it from the base clone. The "Cleanup" sentence points at that brief instead of `fr isolation
down` alone. fr-goal's Post-merge close-out section names `fr archive --branch <b>` where it
says `fr archive <plan-dir>`. Mirrors: `scripts/sync-opencode.py` and `scripts/sync-hermes.py`,
both of them.

### §F. Refs survive the move — `archive_twin` covers journals

`ARCHIVE_TWIN_DIRS` becomes a tuple of `(live, done)` pairs: specs (today's), plus
`journals/specs`, `journals/plans` and `journals/debug` against their `implemented/journals/…`
twins. `archive_twin` returns the counterpart for whichever pair matches. Every existing caller
(`acceptance/check.py:118,222`, `report.py:79`, `acceptance_cmd.py:623`, `requirements.py:326`)
is unchanged. Matrix refs to a debug journal therefore resolve before and after the sweep, and
no row is rewritten. The prose mentions of one debug journal path (`AGENTS.md:418`,
`scripts/install.sh:48`, two test docstrings) are updated to the archived path in the sweep
phase.

### §G. The one-time sweep

The last agentic phase runs `uv run fr archive --all` in the workspace. It commits the debug
journal moves (and any orphan journal) as `chore: sweep live debug journals (#733)`, then
regenerates the acceptance reports if any link text changed (`fr acceptance report
--deterministic`). The PR body states the count moved.

### Change fragment and explainers

`.changes/feat-batch-closeout-always-2.yaml`, `bump: minor` (new `--branch` modes, new
mandatory skill behaviour). `docs/explainers/01-fr-goal.md` is checked for close-out prose. If it
names `fr archive <plan-dir>`, it is updated and re-rendered per `explainers-currency.md`;
otherwise the PR body says no explainer describes it.

## Error handling

- No default ref, a branch not merged, or a branch that does not resolve: exit 2 with the
  next command named, and nothing moved.
- A held artifact is output, not an error. Exit 0.
- A dirty plan path is held, following today's `--all` behaviour.

## Test Plan

Post-merge, operator-driven: in a NEW session from the base clone, run the `fr pickup --run`
line this run's `deliver` relays. Confirm the brief names `fr archive --branch
feat/batch-closeout-always-2`, and that running it in the housekeeping workspace archives this
branch's spec, plan, run, usage and both journals with no `held:` line. Then `fr status` reports
no owed artifact from this branch.
