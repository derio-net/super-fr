# Exit gates — declare each PR's exit, route it, gate the release

**Slug:** exit-gates
**Date:** 2026-10-14
**Issues:** derio-net/super-fr#1189 (absorbs #1086), #1155, #667
**Branch:** `feat/batch-exit-gates` (one PR for the batch)

## Background

An audit of the 35 batch PRs merged in derio-net between 2026-10-10 and
2026-10-13 found 15 complete and 20 partial. No PR had stubs or dead code: every
gap was at the exit. Three patterns:

- A PR narrowed an issue's ask ("out of scope", "operator step", a spec
  non-goal) but still said `Closes #N`, and almost never filed a follow-up.
- Post-merge Test Plan steps stayed `walk-owed` matrix rows with no tracker.
- The exit was decided late and in prose. Nothing told the driver, the board or
  the operator at PR time whether a PR could drive straight through or had to
  wait for a person. So every PR waited: 0.1–5 h to build, then 10–40 h for review.

What already exists, read from the code (and not rebuilt here):

- **Verification strategies.** Each has a manifest with `when` (pre-merge or
  post-merge) and `driver` (agent or operator). See
  `plugins/super-fr/verifications/*.yaml` and `fr/verification/model.py`. The
  effective strategy of a row is decided in one place,
  `fr/verification/effective.py:effective_strategy`, in a fixed order: the
  row's `verify:`, the spec's per-row line, the spec's `strategy:`, then the
  shape default.
- **`deliver` refuses a premature close.** It refuses `Closes #n` for an issue
  cited by a post-merge row that is not yet walked
  (`fr/record/pr_body.py:premature_closes`, `holds_open_for_run`). Close-out
  then prints `fr:awaiting-live` label commands for the issues the PR `Refs`
  (`fr/run/closeout.py:awaiting_live_lines`).
- **The approval gate.** A batch PR merges only after the operator adds
  `approved-fr`; a push voids it (`fr/triage/approval.py`). The driver merges
  a close-out's archive PR once it is ready and green, with no approval
  (`fr/triage/batch_drive.py`, `drive_pass` step 3).
- **Hand-backs.** Conflicts and red CI go back to the session as agent work,
  not to the operator (`conflict_decision`, `red_decision`, since #1138).
- **Collected facts.** The open-PR join already collects `mergeable` and
  `mergeStateStatus` (`fr/triage/collect.py:267`), but neither the merge train
  nor the board reads them. Labels are read only on open PRs
  (`collect.py:270`).
- **Close-outs.** The driver starts one per landed batch, all in the same pass
  (`drive_pass` step 2). The collisions #667 reported are partly gone: the
  tripwire no longer suggests `fr archive --all`, usage files are per run, and
  #665 is closed. But N housekeeping PRs still touch the same generated files
  (the matrix and the three acceptance reports). The unarchived-plans tripwire
  only *warns* (since 2026-09-26), so a merged, unarchived plan turns nothing red.
- **Installing.** `scripts/bootstrap.sh` always installs `origin/main` (fetch,
  then `reset --hard`). `scripts/install.sh` refuses any checkout that is not
  `main` in sync with `origin/main`. `scripts/release.py` cuts a final release
  on every push to `main`. The only RC tags are the per-branch pre-merge ones
  from `fr verification prerelease`.
- **#1155.** When a spec has no `## Verification` section, `fr plan self-review`
  (`plan_ops.py`, `_verification_issues`) and the brainstorm warning
  (`run_cmd.py:_unrunnable_spec_warnings`) return early. But `walk_owed`
  (`verification/walk.py`) still makes a walk owed because of a row's own
  `verify:`. So that row is owed and never checked.

## Requirements

R1. A run's **exit** is two things. Its **kinds** are the set of effective
strategies of the run and of every row citing its spec (`none` when no strategy
applies). Its **gates** are the set of effective gates of those rows. One
function computes it, and every consumer (labels, `deliver`, the driver, the
board, release) reads it.

R2. Gates are a closed vocabulary: `developer`, `reviewer`, `tester`, `devops`,
`owner`, `security`. Only `tester` and `devops` are **post-merge gates**. The
other four act before merge or at a decision; they are recorded but never hold a
merge or a close-out.

R3. A strategy manifest may name a default `gate:`, one of `none`, `tester` or
`devops` (default `none`). The shipped `live` manifest sets `gate: tester`; every
other shipped manifest sets `none`.

R4. A repo can remap the gate of any kind in an `exit:` block of
`.fr/triage.yaml` (`exit: {gates: {<kind>: <gate>}}`). This holds whatever the
kind's `when` is: a repo whose candidate is tested by hand maps
`candidate: tester`.

R5. The spec's `## Verification` grammar gains an optional run-level
`gate: <gate>` line and an optional per-row `gate=<gate>` token, written after
the strategy and before the em dash. A row's effective gate is, first match wins:

1. its line's `gate=`;
2. the section's `gate:`, when the row's effective strategy is the run-level one;
3. the repo's remap of its kind;
4. the kind's manifest `gate:`;
5. `none`.

R6. A run is **held** after merge iff its gates contain `tester` or `devops`.

R7. The run's PR carries one `verification:<kind>` label per kind and one
`gate:<gate>` label per post-merge gate, and no stale ones. fr syncs them
through the forge adapter when a spec-bearing step resolves and the PR exists,
when `fr verification set` runs, and when `deliver` resolves. `deliver` refuses
a PR whose labels it could not sync, printing the command to retry.

R8. `fr verification set --run <id> [--row <id>] --strategy <kind> [--gate <gate>]
--reason <text>` rewrites the spec's `## Verification` line, records a
spec-journal decision with the reason, commits, and re-syncs the labels.
**Downgrade guard:** once `spec-review` is done, a change that makes the exit
wait less is refused unless `--answered-by operator` holds. Waiting less means
a post-merge gate leaves the gate set, or a kind is replaced by one of lower
rank (post-merge > pre-merge operator-driven > pre-merge agent-driven > `none`).
`--answered-by operator` is verified against the session transcript, as an
out-of-scope finding moved to `fixed` is.

R9. `deliver` refuses an **unaccounted leftover** and names it with the command
that accounts for it. An item is accounted when it is held by one of this run's
post-merge gates, or when it is `deferred --tracked-by <issue>`. The items are:

- an out-of-scope finding in either journal;
- a deferred item;
- an owed row citing the spec (`not-implemented`, `unwired`, `walk-owed`).

Under `tracking: none` there is no tracker, so a finding stays recorded in the
journal and PR body as today.

R10. `fr journal file --scope <s> [--slug <slug>|--plan-dir <dir>] --id <id>...`
files one `fr:owed` issue per finding, reusing `fr archive`'s filing code, and
appends each finding's `deferred --tracked-by` resolution. This is how a
leftover is accounted before `deliver`, so filing moves from close-out to
`deliver`.

R11. `deliver`'s `Closes` refusal widens. It refuses `Closes #n` when a row whose
effective gate is post-merge cites #n. It also refuses `Closes #n` when a
spec-journal decision with `narrows=#n` was not answered by the operator. In both
cases the fix it prints is `Refs #n`.

R12. A journal decision may carry `gate=<role>` and `narrows=<issue refs>`
header tokens, so the Owner gate is recorded. A narrowing decided in a verified
brainstorm round is operator-answered. One added after it is the agent's, and R11
refuses `Closes` over it.

R13. The driver never closes out a **held** landed batch. A batch is held when
its merged PR carries an unpassed `gate:<tester|devops>` label. Its card sits in
the lane for that gate (R17), naming the gate and the rows or actions owed. Its
`Refs` issues stay open.

R14. **A post-merge gate passes in either of two ways.** Both swap the PR's
`gate:<g>` label for `gate:<g>-passed` and add a PR comment with what passed it.
The merged PR's labels are the gate ledger; a pass needs no commit to `main`.

- *Rows walked:* every held row citing the run's spec reads `walked` in the
  matrix on the default branch. The driver detects this and does the swap.
- *Explicit:* `fr gate pass --pr <n> --gate <g> --notes <text>`. This is the
  only route for a DevOps action that has no row.

R15. **Collected close-out (#667).** `fr triage batch closeout [<id>...] [--yes]`
closes out every landed batch that is not held and not yet closed out, in one
session, with ONE housekeeping PR. For each batch it:

- runs verify-merge;
- archives the plan with no issue filing (R10 moved filing to `deliver`);
- closes the `Refs` issues whose gates passed, and removes `fr:awaiting-live`
  from them.

It records one close-out event per batch, all naming the shared branch. Without
`--yes` it prints the plan.

The driver starts at most one collected close-out per repo at a time. Once that
close-out's PR is clean (no conflict, checks green), the driver marks it ready
and merges it, with no approval. On a conflict or red checks it hands back
**once**; a second failure becomes a Needs-you row.

R16. A batch whose gate passes after merge joins the next collected close-out.
That close-out closes its `Refs` issues.

R17. The board's columns, in order: Proposed, Waiting, Running,
**Needs you · Developer**, PR open, **Needs you · Reviewer**,
**Needs you · Tester**, **Needs you · DevOps**, Closing out, Partial, Done.

- *Developer:* the run cursor is blocked on a `gate: operator` step, or a manual
  phase is the next unit.
- *Reviewer:* `deliver` is done and the PR is not approved, or a merge is
  stopped.
- *Tester / DevOps:* the batch landed and is held (R13).

A card leaves a lane through the person's own act: answering, approving, or
recording a pass.

R18. The board and the driver read the run cursor at the batch PR's head
(`docs/superpowers/runs/<run-id>.yaml`, through `gitseam`), never session status,
to decide the Developer and Reviewer lanes. Session status stays a secondary hint
only: a blocked prompt still flags the card.

R19. The merge train never plans `merge` or `enqueue` for a PR whose `mergeable`
is `CONFLICTING` or whose `mergeStateStatus` is `DIRTY`. The board never shows
`merge ready` for one. The conflict hand-back is unchanged.

R20. **Release gating.** A push to `main` cuts an RC when any PR merged since
the last final tag carries an unpassed post-merge gate label; otherwise it cuts
the final, as today.

- An RC is a `release: vX.Y.Z-rc.N` commit. It sets every version surface to the
  RC version: PEP 440 `X.Y.ZrcN` where Python reads it, and semver `X.Y.Z-rc.N`
  elsewhere.
- It is tagged `vX.Y.Z-rc.N`, published as a GitHub pre-release, and consumes no
  fragment.
- No RC is cut when nothing merged since the last RC.

`release.yml` also runs on a daily schedule. `fr gate pass` prints the dispatch
command, so a final follows the last pass without waiting for a push.

R21. `fr release status [--json]` lists every PR merged since the last final tag
that still waits on a post-merge gate, with its gate and owed rows, read through
the forge adapter. `scripts/release.py` decides RC or final from its JSON.

R22. `scripts/bootstrap.sh` takes a channel with `--version`. With none, it
installs the newest `vX.Y.Z` tag. It checks out the chosen tag in its managed
checkout and forwards every other flag to `install.sh`. An unknown or missing
version lists the available ones and installs nothing.

| `--version` | Installs |
|---|---|
| *(none)* | the newest `vX.Y.Z` tag |
| `RC` | the newest `vX.Y.Z-rc.N` tag, by version order |
| `X.Y.Z` | that release |
| `X.Y.Z-RC` | the newest `vX.Y.Z-rc.*` |
| `X.Y.Z-rc.N` | exactly that RC |
| `main` | `origin/main`, the development channel |

R23. `scripts/install.sh` installs the checkout it runs from. Its preflight
accepts `main` in sync with `origin/main` as today, or a clean, detached HEAD
exactly at a `v*` tag. It prints the channel it installed. The driver's
`post_merge: ["./scripts/install.sh"]` keeps installing `main` unchanged.

R24. **#1155.** When a spec has no `## Verification` section, `fr plan
self-review` and the brainstorm warning still check every row citing it whose
own `verify:` is set. A failure is reported when:

- the strategy does not resolve;
- the repo cannot run its install;
- an agent-driven pre-merge row has no `scenario:`;
- a post-merge or `none` row has no reason. This one asks for a
  `## Verification` section that carries the row's reason line.

## Design

### A. The exit (`fr/verification/exit.py`, new)

`run_exit(repo_root, state) -> Exit` with the following fields:

- `kinds: frozenset[str]`;
- `gates: frozenset[Gate]`;
- `held_rows: tuple[Row, ...]`, the rows whose effective gate is `tester` or
  `devops`;
- `rank`, used by R8's downgrade guard.

It builds on `run_verification` (`verification/rows.py`) and adds
`SpecVerification.gate(row)`, which applies R5's order. `fr.gates` holds the
closed `GATES` set and `POST_MERGE_GATES = {"tester", "devops"}`. That is a small
new module beside `fr.capabilities`, the other closed vocabulary.

Adding `gate:` to `StrategyManifest` (`verification/model.py`) is an optional,
defaulted manifest field. Manifests are shipped config, not an artifact kind, so
no stamp moves. The `fr` wheel copy is regenerated
(`test_tripwire_shipped_verifications.py`).

`spec_section.py`'s grammar takes the `gate:` line and the row token. Both are
optional, so every existing section parses unchanged. `TriageConfig`
(`triage/model.py`) gains `exit: ExitBlock | None`. `deliver` and the labels
read it from the workspace checkout; the driver reads it at the default branch,
as it reads the rest of `.fr/triage.yaml`.

A read-only `fr verification exit --run <id> | --spec <path>` prints kinds,
gates and held rows. It needs no forge, which makes it the scenario surface.

### B. Labels and `fr verification set`

`fr/labels.py` gains two label families, built the way `spec_label` is:
`verification_label(kind)` and `gate_label(gate, passed=False)`.

`sync_exit_labels(repo_root, state, pr)` adds what is missing and removes stale
`verification:*` / `gate:*` labels through the forge adapter. It creates a label
first if the repo lacks it, as `awaiting_live_lines` does. It is called from:

- the `fr run resolve` paths whose record emits or edits a spec (brainstorm,
  spec-review), only when the run already has a PR, as a warning when it fails;
- `fr verification set`;
- `deliver`, where a failure refuses the resolve.

`fr verification set` lives in `commands/verification_cmd.py`. It rewrites one
grammar line in place and keeps every other line byte-identical. It writes a
`decision` (id `exit-change-<n>`) to the spec journal and commits both.

The downgrade guard compares `run_exit` before and after. It reads
`spec-review`'s cursor state to tell whether the guard applies, and verifies
`--answered-by operator` through the same transcript reader that `journal
resolve --answered-by` uses.

### C. `deliver` accounts for leftovers

`record/pr_body.py` gains `unaccounted(repo_root, state, exit) -> list[Leftover]`.
`run_cmd`'s `deliver` gate refuses while that list is non-empty, printing one
line per item: the `fr journal file …` command, or the row's `--issues` /
`set-status` fix.

`premature_closes` takes the run's exit. Its "post-merge" test becomes "held by
a post-merge gate", which is a superset because `live` maps to `tester`. It also
takes the narrowing decisions (R11).

`fr journal file` (`commands/journal_cmd.py`) reuses `fr archive`'s filer
(`archive_cmd.py`'s `--issues` path), extracted into `fr/journal/file.py`. It
files one `fr:owed` issue per finding, then appends each resolution through
`fr journal resolve`'s engine. `fr archive --issues` keeps working and calls the
same filer.

`JournalEntry` gains `gate: str | None` and `narrows: tuple[str, ...]`.

- Header tokens `gate=` and `narrows=` are serialized only when set and read by
  name (`journal/model.py`'s named projection). An older `fr` ignores them, as it
  ignored `tracked_by=` and `input=`, so the journal kind's stamp does not move.
- The step record's journal entry model (`record/model.py`) gains the same two
  optional fields.
- That record model is closed-world. Whether that moves the `record` kind's
  stamp is decided by the artifact-versioning rule
  (`.claude/rules/artifact-versioning.md`) at plan time. If it moves, the stamp,
  migration and validator ship in this PR.

### D. Driver routing and the gate ledger

**Facts.** `collect` reads the labels of each batch's merged PR, not only open
ones. It also reads, at the batch PR's head, the run cursor's position:
the blocked gate step, `deliver` done, or a manual unit next. This adds a field
to facts, so `FACTS_SCHEMA` moves. Per the known collision, the number is main's
plus one when the PR merges.

**`drive_pass`.** Step 2 (close out) skips a held batch and plans
`gate-pass` actions for held batches whose rows are all walked on the default
branch. It reads the matrix there through `gitseam`. A `gate-pass` swaps the
label and comments through the forge adapter, only with `--yes`, like every
forge write.

Step 2 then plans at most one `closeout` per repo. That close-out covers every
landed, not-held, not-closed batch. The next one waits until the previous
housekeeping PR merged or was recorded.

**Close-out's PR.** Step 3 (archive) marks the collected close-out's PR ready
once it is `MERGEABLE` and green, then merges it. On a conflict or red checks it
uses the existing hand-back machinery with a budget of one for close-outs; the
second failure is a `Need`.

**`fr gate pass`.** It lives in `commands/gate_cmd.py`, a new group. Like every
forge-writing verb it is dry-run without `--yes`. `gate` joins
`READ_ONLY_COMMANDS`, since it never touches a registered artifact.

### E. `fr triage batch closeout`

The verb lives in `triage_batch_cmd.py`, with its engine in
`triage/batch_closeout.py`. It reads each batch's run through `find_run`, then
executes R15's steps in one `gitseam.Checkout` of the default branch on branch
`chore/closeout-<YYYY-MM-DD>-<n>`:

- `fr isolation verify-merge` per batch;
- `fr archive --branch <b> --no-issues` per batch;
- one commit, one PR.

Closing issues is a forge write behind `--yes`. Each close-out event's `archive`
field names the shared branch, so `attributed` (`batch_drive.py`) recognises the
PR for every member. The close-out work item stays `unit="run"`: one item per
collected close-out, id `closeout-<date>-<n>`, briefed to run the verb. A
single-run `fr pickup` close-out outside batches is unchanged.

### F. Board lanes

`kanban.py`'s `Column` and `COLUMN_TITLES` gain `needs-developer`,
`needs-reviewer`, `needs-tester` and `needs-devops`, in R17's order.
`column_of` places a card from the stage plus the facts cursor position plus the
held gate. `needs_you` (`views.py`) adds one `Need` per card in a Needs-you lane,
so "Needs you now" and the lanes agree.

The merge-ready hint and the merge train read `mergeable` / `merge_state` (R19)
in `_walk_merge_train` and `_walk_queue`. A PR they skip for that reason gets
the hint `conflicting — handed back` or `conflicting`. #1107 (draft,
conflicting) is read for cursor-reading code worth salvaging and closed once
this ships.

### G. Release and install channels

`release.py`'s `compute` asks `fr release status --json` (an injectable
`Commands` entry, since `release.py` already runs `fr migrate`). Then:

- If anything waits, it computes `vX.Y.Z-rc.N`. `X.Y.Z` is the next final from
  the pending fragments, and `N` is one past the newest existing `vX.Y.Z-rc.*`.
  It runs `bump-version.py` with the RC version and commits without `git rm` of
  fragments.
- `bump-version.py`'s `SEMVER_RE` accepts `-rc.N`. It writes `X.Y.ZrcN` to
  `pyproject.toml` / `uv.lock` and `X.Y.Z-rc.N` to `plugin.json`,
  `marketplace.json` and `package.json`.
- `tag_and_release` passes `--prerelease` for an RC.
- When nothing new merged since the newest tag, the run is a no-op. That keeps
  the app push of an RC commit from cutting another RC.

`release.yml` adds `schedule:` (daily) beside `push` and `workflow_dispatch`.

`bootstrap.sh` parses `--version`, resolves it against `git ls-remote --tags`,
fetches and checks out the tag detached (or resets to `origin/main` for `main`),
and execs `install.sh` with the remaining flags. `install.sh`'s preflight adds
the tagged-checkout branch: `git describe --exact-match --tags HEAD` matching
`^v[0-9]`, plus a clean tree.

### H. #1155

`plan_ops._verification_issues` and `run_cmd._unrunnable_spec_warnings` stop
returning early on a missing section. With `section is None` they still run the
row checks over `rows_citing(matrix, spec_ref)` whose `verify` is set:

- `unrunnable_strategies` takes `section: Section | None`;
- the scenario and unresolvable checks need no section;
- the reason check reports `row <id> is <strategy> with no reason — add a
  ## Verification section with "- <id>: <strategy> — <reason>"`.

A spec with no section and no row `verify:` still passes unchanged.

### I. Skill and doc prose

These edits follow the AGENTS.md mirror rules (`sync-opencode.py` and
`sync-hermes.py`):

- **fr-goal §1/§8:** the spec's `gate:` answer, `fr journal file` before
  `deliver`, and labels.
- **fr-brainstorming §1:** the verification question also settles the gate.
- **fr-triage:** the lanes, `batch closeout`, and `gate pass`.
- **fr-acceptance:** a walk passes the gate.

`docs/verification-strategies.md` documents `gate:`. The explainer
`01-fr-goal` is updated where it describes delivery and close-out, per
`explainers-currency.md`.

## Non-goals

- An `fr upgrade` command. None exists; the install channel is bootstrap's.
- Enforcing the Security gate. Its role is vocabulary only (R2). How to detect
  a security-relevant change is a separate design.
- Changing approval (`approved-fr`) for feature PRs.

## Verification

strategy: candidate
- exit-gates-declared-exit: candidate — scenario drives `fr verification exit` over fixture specs
- exit-gates-set-downgrade: candidate — scenario drives `fr verification set` and its refusal
- exit-gates-verify-without-section: candidate — scenario drives `fr plan self-review` on a section-less spec
- exit-gates-deliver-accounting: none — CI integration tests drive `deliver` against a stubbed forge; a scenario cannot reach a forge
- exit-gates-board-lanes: none — CI unit tests render the board and run `drive_pass` over fixture facts
- exit-gates-install-channels: none — CI integration tests run bootstrap.sh/install.sh against a fixture remote with release and RC tags
- exit-gates-pr-labels: live — only a real forge shows the labels a real run's PR carries
- exit-gates-driver-routing: live — a held batch and its gate pass need a real merged PR, driver and matrix on main
- exit-gates-collected-closeout: live — one close-out over a real merged queue needs real merges and a real housekeeping PR
- exit-gates-release-gating: live — an RC and the final after it need release.yml on the real main

## Test Plan

Post-merge, operator-driven. These are only the rows no pre-merge strategy can
exercise.

1. **Labels.** Open a batch whose spec says `strategy: candidate` and
   `gate: tester`. Its PR carries `verification:candidate` and `gate:tester`.
   `fr verification set --gate none` without `--answered-by operator` after
   spec-review is refused.
2. **Routing.** Merge that batch. It shows under Needs you · Tester. It is not
   closed out, and its `Refs` issue stays open. Walk its row with
   `set-status --walk` and merge that. The next drive pass swaps the label to
   `gate:tester-passed`.
3. **Collected close-out.** With two or more batches landed and not held, one
   collected close-out opens ONE housekeeping PR. The driver marks it ready and
   merges it once clean, and closes the passed batch's `Refs` issue.
4. **Release.** While step 2's PR is unpassed, a push to `main` cuts
   `vX.Y.Z-rc.N` as a pre-release. After the pass, the next run cuts the final
   `vX.Y.Z`. `bootstrap.sh --version RC` installs the RC, and with no argument
   it installs the final.
