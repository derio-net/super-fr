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
| R8 | Every shipped skill whose flow ends at a PR it opens ends by relaying a close-out line: fr-goal relays its `fr pickup --run` line, and fr-debugging and standalone fr-execute relay `fr pickup --branch <b>`. fr-isolation's post-merge cleanup points at the same brief. A flow that relays nothing is still caught by R5. | input "Make the close-out an always-on condition at the end of **every** fr-shaped flow."<br>decision d4-no-debug-cursor |

## Deferred from input

| input | reason |
|---|---|
| "and/or `fr triage check`" | Operator chose `fr status` only (d3-status-advisory). |
| "#458 (`fr archive` offering to file open ends) belongs in the same close-out step." | #458 is its own issue. The brief keeps only today's run-mode out-of-scope filing lines (§D). |
| "closeout-queue (#667) builds on this." | A follow-up that loops over R1, one branch per merged batch. It is out of this change. |

## Background

Only fr-goal has a close-out today. `fr pickup --run` (`pickup_command`,
`packages/fr/src/fr/commands/pickup_cmd.py:24`, its `--run` branch at `:48`) calls `closeout_brief`
(`packages/fr/src/fr/run/closeout.py:118`), which needs a done `deliver`
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
`--sweep-only` style. `--no-spec-sweep` is accepted and skips the spec step, and each branch
spec is then reported `held: <spec> — spec sweep skipped`.

1. `merge_evidence(repo_root, fetch=True)` supplies the default ref. If there is none, refuse
   (exit 2) naming `ref_error`.
2. **Branch refs.** Resolve refs the same way verify-merge does
   (`isolation_cmd.py:878`, `local.py` `_branch_refs`): try to fetch `origin/<b>` with the
   explicit refspec, then take every ref that resolves, which is `origin/<b>` and the local
   `<b>`. If neither resolves, refuse with exit 2: `branch <b> resolves neither locally nor as
   origin/<b> — nothing to diff`, and nothing moves.
3. Run `branch_changes_present(ref, <default ref>)` for **each** resolved ref. If any is not
   present, refuse with exit 2, listing the missing paths and pointing at `fr isolation
   verify-merge --branch <b>`. This is the mutating step's own guard; the brief still runs
   verify-merge (with its PR-state check) first.
4. Compute `branch_artifacts` over the **union** of `branch_changed_paths` across the resolved
   refs, then per kind:
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
5. Repair in passing through the existing `_repair_in_passing`, once. Print one line per artifact
   (`archived:` / `held:`), then the "moves staged via git mv" footer. If the branch touched no
   artifact, print `nothing to archive for <b>` and exit 0.

### §C. `fr archive --all` learns debug journals; one "owed" predicate

`fr.closeout.owed_artifacts(repo_root, evidence) -> list[Owed]` is the ONE definition of "live
but its PR merged". It reads the working tree and the default ref only; it makes no forge call:

Every live kind is covered, and each owed entry carries the command that clears it:

| kind | owed when (live, and …) | clearing command printed |
|---|---|---|
| debug journal | the same path exists on the default ref | `fr archive --all` |
| plan (+ its run, usage, plan journal) | `status_cmd._sweep_lists`' `archivable` bucket, moved into `fr.closeout` so status and archive share it | `fr archive <plan-dir>` (today's line) |
| spec (+ its spec journal) | `fr.migrate._spec_fully_implemented(spec, repo_root, gh=None)[0]` is true | `fr archive --sweep-only` |
| orphan plan/spec journal | its owner (`implemented/plans/<slug>/` or `implemented/specs/<slug>-design.md`) is already archived | `fr archive --all` |
| orphan run cursor (+ usage) | its `emitted.plan` names a plan that is already archived, or it names no plan, its `deliver` is done, and it is on the default ref | `fr archive --all` |

Some things are deliberately **not** reported as owed, because the PR that introduced them does
not end their life. A merged plan with open manual phases stays in today's "merged, manual
phases still open" block, as back-loaded operator work. A spec whose `_spec_fully_implemented`
note says it is held (a pending slice, an unresolved cross-repo row without the forge) is
listed in a separate `held live (spec): <spec> — <note>` block, visible but not owed. That keeps
R5 honest: every live artifact whose PR merged is either owed (with a command) or shown as held
(with its reason). None of them is silent.

`fr archive --all` (after its plan loop and spec sweep, as today) also moves every owed debug
journal, orphan journal and orphan run. `--no-spec-sweep` does not affect them, because they are
not specs.

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
  [run mode: file an issue for each out-of-scope finding … + one `fr journal resolve` line each]
  fr archive --branch <b>   # inside the new <housekeeping> workspace
  git add -A && git commit -m '<commit message>' && git push -u origin <housekeeping>
  open the housekeeping PR (e.g. `<forge pr command>`)
  fr isolation down --branch <b>
```

The brief's findings lines are exactly today's run-mode out-of-scope lines
(`_out_of_scope_lines`, `closeout.py:93`, from the run's spec and plan journals). Branch mode
prints none, and no debug-journal finding lines are added (#458 is deferred).

**Run-mode changes, stated explicitly** (everything else in today's run brief is unchanged):

| | today (`closeout.py:118-211`) | after |
|---|---|---|
| archive line | `fr archive <plan-dir>`, only when the run names a plan | `fr archive --branch <b>`, always |
| housekeeping block | printed only `if plan_path or out_of_scope` | always printed, because the branch always has at least its run cursor to consider |
| housekeeping branch | `chore/archive-<plan-slug>`; else `chore/closeout-<run-id>` | unchanged |
| commit line | `chore: archive <plan-slug>`; the no-plan case prints only `git push` | `chore: archive <plan-slug>` when a plan exists; otherwise `chore: close out <b>`, with the commit line always printed |

Branch mode (`fr pickup --branch <b>`, no run) uses `chore/closeout-<branch-slug>` (`/` → `-`)
and `chore: close out <b>`.

`fr pickup --branch` refuses (exit 2) a branch that resolves neither locally nor as `origin/<b>`
(the same resolution as §B.2, without the fetch). It also refuses in combination with a plan
dir, `--phase` or `--run`.

### §E. fr-debugging relays the line

fr-debugging §4 Deliver gains one sentence after the PR opens: relay
`closeout: fr pickup --branch <branch>` to the operator verbatim; after merge, a NEW session runs
it from the base clone. The "Cleanup" sentence points at that brief instead of `fr isolation
down` alone. fr-goal's Post-merge close-out section names `fr archive --branch <b>` where it
says `fr archive <plan-dir>`. fr-execute's step 5 (standalone dispatched flow only, never
under fr-goal) relays `closeout: fr pickup --branch <phase-branch>` after opening its PR. On a
non-final phase, that close-out reports the plan `held:` until the last phase lands, so its
housekeeping PR carries only what the phase itself finished. fr-isolation's "clean up after a
merged PR" guidance names `fr pickup --branch <b>` as the route, with `fr isolation down` as
its last step. fr-dispatch relays nothing, because its runners open the PRs; `fr status`
(§C) is the backstop there (R8). Mirrors: `scripts/sync-opencode.py` and
`scripts/sync-hermes.py`, both of them.

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

The last agentic phase runs `uv run fr status` first and records what §C reports as owed.
It then runs `uv run fr archive --all` in the workspace. `--all` is repo-wide: besides the
debug journals, it moves any gate-passing plan, qualifying spec, orphan journal or orphan run,
and repairs refs in passing. The phase checks that the moves equal the owed set it recorded
beforehand, and treats any extra move as a finding. It commits every move as `chore: sweep owed
artifacts (#733)`, then regenerates the acceptance reports (`fr acceptance report
--deterministic`) and confirms `fr acceptance check` passes. The PR body lists the moves by kind
with a count for each.

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

Pre-merge, automated (unit level, with real git repos in `tmp_path` and no mocked git):

1. `branch_changed_paths` returns the same set `branch_changes_present` diffs, and
   `branch_artifacts` groups plan-dir files, drops deleted paths and ignores non-artifact paths
   (R3, R4).
2. `fr archive --branch <b>` on a merged branch that added a plan, spec, run and debug journal
   moves all of them. It prints `held:` for an incomplete plan and for a spec under
   `--no-spec-sweep`; it prints `nothing to archive for <b>` (exit 0) for a branch that touched
   no artifact; it refuses an unmerged branch and an unresolvable branch with exit 2, moving
   nothing; and it refuses each conflicting flag (R3, R4).
3. A branch that only **modified** an existing debug journal gets that journal archived (d2).
4. `fr pickup --branch <b>` on a branch with no run cursor prints the brief with `fr archive
   --branch <b>`, `chore/closeout-<slug>` and the verify-merge STOP. `fr pickup --run` on a done
   run prints the same core and its run extras, with the run-mode table of §D pinned line by
   line. Both mutual-exclusion refusals exit 2 (R1, R2).
5. `fr status` lists each owed kind of §C with its clearing command, lists the held spec block,
   and exits 0 (R5).
6. `fr archive --all` moves debug journals present on the default ref, leaves one that exists
   only on the branch, and moves orphan journals and runs (R7).
7. `archive_twin` maps each journal scope both ways, and `fr acceptance check` passes on a
   matrix citing a debug journal before and after it is moved (R7).
8. A tripwire over the canonical skills: fr-debugging §4, fr-execute step 5 and fr-isolation's
   cleanup contain `fr pickup --branch`, and the OpenCode and Hermes mirrors are in sync (R6, R8).

Post-merge, operator-driven: in a NEW session from the base clone, run the `fr pickup --run`
line this run's `deliver` relays. Confirm the brief names `fr archive --branch
feat/batch-closeout-always-2`, and that running it in the housekeeping workspace archives this
branch's spec, plan, run, usage and both journals with no `held:` line. Then `fr status` reports
no owed artifact from this branch.
