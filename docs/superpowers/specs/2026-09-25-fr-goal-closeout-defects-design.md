# fr-goal closeout defects (gh#610)

**Status:** design · **Issue:** gh#610 (closes gh#469) · **Journal:**
`docs/superpowers/journals/specs/2026-09-25-fr-goal-closeout-defects.md`

## 1. Background

Three recorded `/fr-goal` runs on OpenCode, against a Java/Maven demo repo on a
self-hosted GitLab (default branch `master`, host redacted), each hit the same
post-merge closeout problems. Merge, the Test Plan, archive and teardown cost up to
**$4.14 over 81 turns**. The whole delivery cost $6.15. gh#610 names five defects.
The operator's Q&A (spec journal, 2026-09-25) settles them as follows:

| # | Defect | Disposition |
|---|---|---|
| 1 | `verify-merge` assumes `main`; on `master` it tracebacks | **fix** (§3.A) |
| 2 | the demo port in the container is unreachable from the host | **dropped**: operator, "very narrow scope" |
| 3 | the validator-wrapper guard blocks the housekeeping workspace; its remedy names a Claude-only path | **fix** (§3.B) |
| 4 | fr leaves its own record writes uncommitted, then refuses its own `repair`/`archive`/`down` | **fix**: fr commits its records (§3.C) |
| 5 | the closeout replays the delivery's full context | **fix without a new step**: `deliver` hands off an exact `fr pickup` command for a new session (§3.D) |

## 2. Goals / non-goals

**Goals**
- `fr isolation verify-merge --branch <b>` works on a `master` repo with no flags,
  and never ends in a traceback.
- A repo whose first plan was written by `fr plan create` carries a tracked
  validator wrapper in that same change, so a housekeeping `fr isolation up --base
  origin/<default>` is not refused after merge. The guard's remedy names a
  harness-neutral `fr` command.
- Every fr CLI write to fr's own records (run cursor, plan files, journals) is
  committed by fr on a feature branch. fr's closeout commands then never refuse over
  fr's own state.
- After `deliver`, fr prints one exact command that starts the closeout in a new
  session. That command prints a self-contained closeout brief built from the run
  file.

**Non-goals**
- Defect 2: publishing container ports, a `ports:` profile field, and an
  `fr isolation port` helper. Dropped by the operator.
- A `closeout` workflow step, a closeout agent, or closeout cost recorded in the
  run cursor. The operator judged these "too much handholding for little benefit".
  The new session's own harness cost is the measurement. `fr-goal.yaml` does not
  change, so in-flight runs do not drift.
- Making `fr archive` / `fr repair` commit their own output. They are the closeout's
  last writes, and their output is reviewed in the housekeeping PR, as today.
- Tier→model bindings. The Q&A's model decision (claude-code: mechanical=haiku,
  standard=sonnet, hard=opus) configures the operator's environment for this run's
  dispatches. It was applied at brainstorm with `fr models set`, which writes
  `~/.config/fr/models.yaml` outside the repo. It is recorded here and in the spec
  journal, and it changes no code in this PR.
- The wrapper's delegate path (`WRAPPER_TEXT` execs a Claude marketplace path) on
  non-Claude harnesses. That is a real gap with a different cause. It is filed as a
  follow-up if the reviewer confirms it.

## 3. Design

### 3.A verify-merge resolves the default branch (defect 1, gh#469)

`packages/fr/src/fr/commands/isolation_cmd.py:862` declares `--default-branch`
with default `"main"`. The live path at `:909` calls `verify_merge` without the
`try/except IsolationError` that the reaped path (`:899-906`) has. On a `master`
repo, `branch_changes_present` (`isolation/local.py:313`) raises `IsolationError`
("no merge-base … unrelated histories?"). The error escapes Typer as a traceback
with exit 1.

Change:
1. `--default-branch` becomes `str | None = None`. When it is unset, the command
   resolves the branch with the target's existing
   `_resolve_default_branch()` (`isolation/local.py:2175`). That resolver already
   serves `up`'s cold start and gc's merge check (`:1659`), which covers exactly
   the "`master` repo" case (`:1537-1545`). An explicit flag still wins.
2. `verify_merge` / `verify_merge_reaped` (`local.py:989`, `:1011`) drop their
   `"main"` defaults and take the resolved name. No function-level default is left
   to drift from the resolver.
3. Both paths catch `IsolationError` → `_fail` (clean `error: …`, exit 2). When the
   merge-base is missing, the message names the base ref it tried and
   `--default-branch`.
4. The output strings (`:913-925`) print the resolved `origin/<b>`.

### 3.B the validator wrapper ships with the first plan (defect 3)

Root cause, beyond the issue's text: `fr init scaffold` commits
`scripts/validate-plans.sh` only when `docs/superpowers/plans/` **already exists**
at scaffold time (`isolation/scaffold.py:532-539`). A repo scaffolded before its
first plan never gets a tracked wrapper. When that repo's feature PR merges its
first plan, `origin/<default>` has plans but no wrapper. The guard
`_ensure_validator_wrapper_in_ref` (`local.py:1868-1899`) then refuses every
workspace cut from it, and it tells the operator to run a Claude-specific script
(`plan_validator_wrapper.py:8-10`, `REPAIR_COMMAND`).

Change:
1. **`fr plan create` installs the wrapper when it is missing.** After writing the
   plan folder, `create` (`plan_ops.py:159`) calls `ensure_validator_wrapper`
   (`plan_validator_wrapper.py:55`) and adds the wrapper to the paths it stages
   (`plan_ops.py:274`). So the wrapper lands in the same commit as the plan (§3.C),
   and the feature PR carries it to the default branch. A foreign file at that path
   is left untouched and reported as a warning, never overwritten; this is the
   same refusal `ensure_validator_wrapper` already makes.
2. **A harness-neutral installer: `fr init validator-wrapper`.** It writes the
   wrapper (0755) via `ensure_validator_wrapper`, stages it, and prints the commit
   instruction. `REPAIR_COMMAND` becomes `fr init validator-wrapper`, so both guard
   messages (`local.py:1868` and `:1901`) name it. The retired-marketplace AST
   tripwire (`tests/unit/test_retired_marketplace_name.py`) keeps pinning the
   single constant.
3. **Correct wording.** The ref guard never looks at the working tree. Its message
   becomes "plan repo has docs/superpowers/plans in `<ref>` but no
   scripts/validate-plans.sh there; …".

The guard itself stays fail-closed with no bypass flag. The validator-wrapper
lifecycle spec (2026-07-09) records this as a non-goal on purpose. The fix is to
make the wrapper present, not to skip the check.

### 3.C fr commits its own record writes (defect 4)

Today no `fr run` write commits (`run/model.py:661` `save_run_state`, about 15
call sites in `commands/run_cmd.py` and `run/adopt.py:650`). `plan_ops` writes are
staged but deliberately not committed, and the docstring says "the caller (CLI)
decides commit cadence" (`plan_ops.py:8-9`). No CLI caller ever commits.
`fr journal add/resolve` do not commit either. The closeout's guards then count
fr's own records as operator dirt:
- `fr repair --yes`: `repair_cmd.py:61`
- `fr archive`: `archive_cmd.py:194`
- `fr isolation down`: `local.py:1115-1135`

**One committer, three callers.** The generic body of
`fr.artifacts.commit.commit_migration` (`artifacts/commit.py:460`) moves into
`commit_paths(repo_root, paths, message) -> CommitOutcome`. That body is
`git_context`, the default-branch / detached / no-HEAD / `index.lock` refusals,
and the path-scoped `git add -- <p>` + `git commit -m <msg> -- <p>`.
`commit_migration` becomes a thin wrapper that builds its message, so migration
behaviour is unchanged and its tests are unmodified. The CLI layer calls
`commit_paths` after each successful record write:

| Command | Paths | Message |
|---|---|---|
| `fr run start/adopt/advance/resolve/claim` (any `save_run_state`) | the run file | `chore(fr): run <id> — <verb> <step>[ <item>] <state>` |
| `fr plan create` / `edit` (tick, complete, note, tracking) | the paths `plan_ops` staged (plan folder, spec index row, wrapper, seeded journal) | `chore(fr): plan <slug> — <verb>` |
| `fr plan rework` / `rework-add` | the rework folder + its spec row / the rework's `_meta.yaml` | `chore(fr): plan <slug> — rework` / `— rework-add` |
| `fr journal add` / `resolve` | the journal file | `chore(fr): journal <scope>/<slug> — <kind> <id>` |

**One commit seam.** The invariant is the seam, not this list of commands. Every
record commit goes through `commit_records` → `commit_paths`, and there is no
other commit site. A command that writes fr records joins the table by routing
through that seam. (`rework` / `rework-add` were added in the phase-3 review for
exactly that reason: leaving them out would have reintroduced defect 4 for those
two commands.) Cadence is **per invocation** today, and tests assert outcomes
("fr's record paths are clean when the command returns"), never commit counts,
because per-phase batching is planned in `feat/lean-cost-aware-process`. Commit
reporting is at most one stderr line per fr invocation.

The table covers every `save_run_state` and `append_journal_entry` caller. One
caller writes both files: `fr run resolve --no-questions` appends a spec-journal
`decision` (`commands/run_cmd.py:872`) in the same invocation that saves the
cursor. Its commit carries **both** paths, one commit per command invocation. In
general, each committing command collects every record path it wrote and commits
them once, at the end.

Rules:
- **Library functions stay pure.** `plan_ops`, `save_run_state` and the journal
  writer keep their current contracts. Only the CLI commands commit, which is where
  `plan_ops` already said cadence belongs. Library-level tests (such as
  `test_plan_ops.py`'s staged-not-committed pin) stay valid.
- **Never on the default branch.** `commit_paths` inherits `commit_migration`'s
  refusal. A write there stays uncommitted, as today, with one stderr line naming
  why.
- **Never fail the write.** A refused or failed commit is reported on stderr, and
  the command's exit code is what it would have been without the commit. The record
  is already on disk; losing the commit must not lose the write.
- **Path-scoped.** `git commit -- <paths>` commits only fr's paths, even while the
  executor has its own code staged. The executor's TDD commits stay its own.
- **Not in a git repo, or outside one**: no-op, as today.

**The `deliver` ordering.** Resolving `deliver` is fr's last cursor write, and it
now produces a commit after the PR is open. `fr run resolve --step deliver`
prints "cursor committed as `<sha>` — push it (`git push`) so the PR carries it".
The fr-goal skill's §8 changes in two ways. It adds the push after resolving
`deliver`. Its "commit plan + journals" line (`SKILL.md:103`) becomes "confirm
`git status` is clean for plan and journals (fr commits its own writes; commit any
hand edits)", which keeps the check and drops the now-redundant manual commit. That is what lets the squash-merged default
branch hold the final cursor, so `fr isolation down`'s unlanded-content check
(`local.py:1135`) passes after merge instead of refusing a cursor commit that
never landed.

### 3.D closeout starts in a new session from one command (defect 5)

No manifest change. Two pieces:

1. **`fr pickup --run <run-id>`.** `pickup` (`commands/pickup_cmd.py:18`) gains a
   `--run` mode. In that mode `plan_dir` and `--phase` are not taken; passing them
   with `--run` is refused, exit 2. It reads `docs/superpowers/runs/<run-id>.yaml`
   (`fr.run.model` loader) and prints a self-contained closeout brief built only
   from the run file and the artifacts it names:
   - branch, PR (`deliver`'s `emitted.pr`), spec and plan paths;
   - the ordered closeout steps, each as an exact command:
     `fr isolation verify-merge --branch <b>` (STOP if it fails) → the spec's
     `## Test Plan`, if present, named by path → the out-of-scope findings from
     both journals with their `fr journal resolve … --state deferred --tracked-by`
     line → `fr status` → `fr archive <plan-dir>` on a housekeeping branch →
     housekeeping PR → `fr isolation down --branch <b>`.

   A run whose `deliver` is not `done` is refused, exit 2, with the cursor it is on.
2. **The handoff names it.** When `deliver` resolves `done`, and whenever `fr run
   advance` reports a finished run (`run_cmd.py:3319-3326`), fr prints:

   ```
   closeout: after the PR merges, start a NEW session in <workspace> and run
     fr pickup --run <run-id>
   ```

   The fr-goal skill's §8 relays that line to the operator verbatim. Its
   "Post-merge close-out" section is rewritten to say the closeout runs in a new
   session from that brief, not in the delivering session.

The new session's cost is its own harness transcript. fr records nothing for it,
by the operator's decision.

## 4. Artifacts, versions, mirrors

- No artifact shape changes: no new fields and no stamp bump. §3.C changes when
  records are committed, not what they contain.
- `fr` minor bump. Two things are user-visible: new `fr init validator-wrapper` and
  `fr pickup --run`, and a behaviour change, since fr now commits its record writes.
- Skill edits (`fr-goal` §8 and Post-merge close-out) regenerate both mirrors:
  `scripts/sync-opencode.py` **and** `scripts/sync-hermes.py`.
- The explainer `docs/explainers/01-fr-goal.md` is updated only if it describes
  the closeout. If it does, it is re-rendered per the explainers-currency rule.

## 5. Test Plan

All automated. The deliverable is a CLI and skill change that deploys nothing, so
there is no post-merge operator step beyond the normal closeout.

1. `verify-merge` on a fixture repo whose remote default is `master`, with no
   flags: exit 0 and prints `origin/master`. Missing merge-base: exit 2 with an
   `error:` line naming `--default-branch`, no traceback. An explicit
   `--default-branch` still wins.
2. `fr plan create` in a repo with no wrapper stages and commits
   `scripts/validate-plans.sh` (0755) with the plan. A foreign wrapper is left
   byte-identical and warned about. `fr isolation up --base <ref>` on a ref without
   the wrapper names `fr init validator-wrapper`. `fr init validator-wrapper`
   installs and stages it.
3. On a feature branch:
   - `fr run resolve`, `fr plan edit --tick`, and `fr journal add` each leave
     `git status --porcelain` clean for fr's paths and add exactly one `chore(fr):`
     commit touching only those paths. A pre-staged unrelated file stays staged and
     uncommitted.
   - On the default branch the write happens and no commit is made.
   - A held `index.lock` makes the write succeed with a stderr warning.
4. End to end on a fixture: resolve `deliver`, push, squash-merge into the default
   branch. Then `fr archive` and `fr isolation down --branch <b>` do not refuse
   over fr's records.
5. `fr pickup --run <id>` on a run with `deliver` done prints the closeout brief:
   branch, PR, verify-merge, archive and down commands. It refuses (exit 2) a run
   whose `deliver` is not done, and refuses `--run` combined with `--phase`.
   Resolving `deliver` prints the `fr pickup --run` handoff line.

## 6. Acceptance rows

Added `not-implemented` at brainstorm and moved as the tests land:
`closeout-verify-merge-default-branch`, `closeout-wrapper-ships-with-first-plan`,
`closeout-fr-commits-own-records`, `closeout-pickup-run-handoff`.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-25-fr-goal-closeout-defects | `derio-net/super-fr` | `2026-09-25-fr-goal-closeout-defects` | — |
