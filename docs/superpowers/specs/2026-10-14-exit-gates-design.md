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
  `plugins/super-fr/verifications/*.yaml` and `fr/verification/model.py`, which
  is closed-world: `extra="forbid"`, with `schema: Literal[1]`. A row's
  effective strategy is decided in one place,
  `fr/verification/effective.py:effective_strategy`, in a fixed order: the row's
  `verify:`, the spec's per-row line, the spec's `strategy:`, then the shape
  default.
- **The spec section grammar** (`fr/verification/spec_section.py`). It checks
  only lines that start `strategy:` and bullets. Any other line is ignored, and a
  bullet that breaks the row grammar raises `SectionError`.
- **`deliver` refuses a premature close.** It refuses `Closes #n` for an issue
  cited by a post-merge row that is not yet walked
  (`fr/record/pr_body.py:premature_closes`, `holds_open_for_run`). Close-out
  then prints `fr:awaiting-live` label commands for the issues the PR `Refs`
  (`fr/run/closeout.py:awaiting_live_lines`). It prints the commands; it does not
  run them.
- **Filing at archive** (`fr/archive_followups.py`). Two filers exist:
  - `file_open_ends` files open findings as issues labelled `follow-up` when
    `fr archive --issues` selects them.
  - `file_owed_ends` files every `owed` journal entry as `fr:owed`, whatever
    `--issues` / `--no-issues` say, and records `filed_as`.

  `_write_manual_owed` creates `owed` entries for manual-phase blockers at
  archive. Archive also refuses to move a plan whose spec's Test Plan steps have
  no recorded outcome (`fr/archive.py:outcome_hold`). An outcome is recorded with
  `fr closeout outcome --ran|--owed|--na`.
- **The approval gate.** A batch PR merges only after the operator adds
  `approved-fr`; a push voids it (`fr/triage/approval.py`). The driver merges a
  close-out's archive PR once it is ready and green, with no approval
  (`fr/triage/batch_drive.py`, `drive_pass` step 3). That step has no hand-back
  path.
- **Conflicts, hand-backs and version files.** The merge train plans a `merge`.
  `batch_merge._update` then merges the base in, resolves a version file or a
  lockfile by itself (`_unresolvable`), and raises `MergeConflictError` for
  anything else. That exception is the only thing that starts the conflict
  hand-back (`conflict_decision`). Red CI goes through `red_decision`. Both count
  one batch's events since its dispatch.
- **Collected facts.** The open-PR join collects `mergeable` and
  `mergeStateStatus` (`fr/triage/collect.py:267`), and labels on open PRs only
  (`collect.py:270`). The triage page reads the first two with its own conflict
  test (`render.py:609`, which also counts `BLOCKED`). The merge train and the
  kanban card's `merge ready` hint ignore them.
- **Close-outs.** The driver starts one per landed batch, all in the same pass
  (`drive_pass` step 2). The collisions #667 reported are partly gone: the
  tripwire no longer suggests `fr archive --all`, usage files are per run, and
  #665 is closed. But N housekeeping PRs still touch the same generated files
  (the matrix and the three acceptance reports).
  - `attributed` (`batch_drive.py:684`) recognises a close-out PR by the head
    `chore/closeout-<batch branch>`, or else by the run file or plan journal it
    touches.
  - The unarchived-plans tripwire only *warns* (since 2026-09-26).
- **"Held" and "gate" are taken.** `drive_pass` already *holds* batches: a
  member claimed by another scope, the in-flight cap, a `held` conflict. And a
  workflow step can carry `gate: operator`. This spec therefore says **gated**
  for a batch waiting on a post-merge gate, and **step gate** for
  `gate: operator`.
- **Installing and releasing.**
  - `scripts/bootstrap.sh` always installs `origin/main`.
  - `scripts/install.sh` refuses any checkout that is not `main` in sync with
    `origin/main`, and every released tag carries that preflight.
  - `scripts/release.py` cuts a final release on every push to `main`.
  - The release tooling reads versions as `X.Y.Z` integers only:
    `bump-version.py:SEMVER_RE`, `changes.bumped`, `floors.parse_version`, and
    `release.previous_tag` matching `v[0-9]*`. `fr_version` floors are checked
    with PEP 440 ordering (`version_floor.admits`).
- **#1155.** When a spec has no `## Verification` section, `fr plan self-review`
  (`plan_ops.py`, `_verification_issues`) and the brainstorm warning
  (`run_cmd.py:_unrunnable_spec_warnings`, which runs only the install check
  even with a section) return early. But `walk_owed` (`verification/walk.py`)
  still makes a walk owed because of a row's own `verify:`. So that row is owed
  and never checked.

## Requirements

R1. A run's **exit** is two things:

- its **kinds**: the set of effective strategies of the run and of every row
  citing its spec (`none` when no strategy applies);
- its **gates**: the run-level gate plus the effective gate of every such row.

The **run-level gate** is, first match wins: the section's run `gate:` line; the
repo's remap of the run strategy's kind; that kind's manifest `gate:`; `none`.
One function computes the exit, and every consumer (labels, `deliver`, the
driver, the board, release) reads it.

R2. Gates are a closed vocabulary: `developer`, `reviewer`, `tester`, `devops`,
`owner`, `security`. Only `tester` and `devops` are **post-merge gates**. The
other four act before merge or at a decision; they are recorded but never hold a
merge or a close-out. A workflow step's `gate: operator` is a **step gate**, a
different thing that this vocabulary does not include.

R3. A strategy manifest may name a default `gate: tester|devops` only at
`schema: 2`. Schema 1 stays valid, and an absent `gate:` means `none`. The
shipped `live` manifest moves to `schema: 2` with `gate: tester`. The other
shipped manifests stay schema 1, with no `gate:`.

R4. A repo can remap the gate of any kind in an `exit:` block of
`.fr/triage.yaml` (`exit: {gates: {<kind>: <gate>}}`). This holds whatever the
kind's `when` is: a repo whose candidate is tested by hand maps
`candidate: tester`.

R5. The spec's `## Verification` section takes `gate:` lines. A released `fr`
ignores them, because it checks only `strategy:` lines and bullets:

- `gate: <gate>` sets the run-level gate;
- `gate: <row-id>=<gate>` sets one row's gate (repeatable, one row each).

A row's effective gate is, first match wins:

1. its `gate: <row-id>=` line;
2. the run-level gate (R1), when the row's effective strategy is the run's
   strategy;
3. the repo's remap of its kind;
4. the kind's manifest `gate:`;
5. `none`.

R6. A run (and its batch) is **gated** iff its gates contain `tester` or
`devops`.

R7. The run's PR carries one `verification:<kind>` label per kind and one
`gate:<gate>` label per post-merge gate, and no stale ones. fr syncs them when a
spec-bearing step resolves and the PR exists, when `fr verification set` runs,
and when `deliver` resolves. It writes through PR-level label methods of the
forge adapter.

- On GitHub, `deliver` refuses a PR whose labels it could not sync, printing the
  command to retry.
- A forge whose adapter cannot label a PR (it raises `UnsupportedForgeOperation`)
  gets a warning instead of a refusal.
- Under `tracking: none` nothing is synced.

R8. `fr verification set --run <id> [--row <id>] --strategy <kind> [--gate <gate>]
--reason <text>` changes the spec's `## Verification` section:

- it inserts or rewrites the matching `strategy:`, row bullet, or `gate:` line,
  and keeps every other line byte-identical;
- it records a spec-journal decision with the reason, commits, and re-syncs the
  labels;
- it refuses a spec with no `## Verification` section and names how to add one.

**Downgrade guard:** once `spec-review` is done, a change that makes the exit
wait less is refused unless `--answered-by operator` holds. Waiting less means a
post-merge gate leaves the gate set, or a kind is replaced by one of lower rank
(post-merge > pre-merge operator-driven > pre-merge agent-driven > `none`).
`--answered-by operator` is verified against the session transcript, as an
out-of-scope finding moved to `fixed` is.

R9. `deliver` refuses an **unaccounted leftover**, naming it with the command
that accounts for it. Each item kind has its own accounting rule:

| Leftover | Accounted when |
|---|---|
| An out-of-scope finding in either journal | it is `deferred --tracked-by <issue>` |
| An `owed` journal entry | it carries `filed_as` |
| An owed row citing the spec (`not-implemented`, `unwired`, `walk-owed`) | a post-merge gate of this run gates it, or the row carries `issues:` |
| A narrowing decision (R12) | it carries `tracked_by=` |

Under `tracking: none` there is no tracker, so only the gate route applies. The
rest stay recorded in the journal and PR body, as today.

R10. `fr journal file --scope <s> [--slug <slug>|--plan-dir <dir>] --id <id>...`
files each item through the archive's existing filers in `fr/archive_followups.py`
and records the result, so filing moves from close-out to `deliver`:

- an out-of-scope finding or a narrowing decision: `file_open_ends`, label
  `follow-up`, then appends a `deferred --tracked-by` resolution (or `tracked_by=`
  on the decision);
- an `owed` entry: `file_owed_ends`, label `fr:owed`, then records `filed_as`.

R11. `deliver` refuses `Closes #n`, printing `Refs #n` as the fix, in two cases:

- a row cites #n and that row is either post-merge and not walk-verified (the
  existing guard, kept) or gated by a post-merge gate;
- a narrowing decision names #n and is not operator-answered (R12).

R12. A journal `decision` may carry these header tokens, so the Owner gate is
recorded:

- `gate=<role>`;
- `narrows=<ref>[,<ref>...]`, comma-separated;
- `answered_by=operator`.

fr writes `answered_by=operator` on a decision in only two cases: when the
brainstorm record applies it (that resolve verified the question rounds), or
when `fr journal add … --answered-by operator` is verified against the
transcript. A narrowing decision without the token is the agent's.

R13. The driver never closes out a **gated** landed batch: one whose merged PR
carries an unpassed `gate:<tester|devops>` label. Its card sits in that gate's
lane (R17), naming the gate and what is owed. The first pass that sees it gated
adds `fr:awaiting-live` to the issues its gated rows cite. Its `Refs` issues stay
open.

R14. **A post-merge gate passes in either of two ways.** Both swap the PR's
`gate:<g>` label for `gate:<g>-passed` and add a PR comment saying what passed
it. The merged PR's labels are the gate ledger; a pass needs no commit to `main`.

- *Rows walked:* every row citing the run's spec that gate `g` gates reads
  `walked` in the matrix on the default branch. The driver detects this and does
  the swap.
- *Explicit:* `fr gate pass --pr <n> --gate <g> --notes <text>`. This is the
  route for a gate with no row, such as a run-level `gate: devops`.

R15. **Collected close-out (#667).** `fr triage batch closeout [<id>...] [--yes]`
closes out, in one session and with ONE housekeeping PR, every landed batch that
is not gated and not yet closed out. For each batch, in order, it:

1. runs verify-merge;
2. if the batch was gated and its gates have passed, records each Test Plan
   step's outcome as `--ran` with the gate-pass comment as evidence;
3. archives the plan with `--no-issues` (R10 moved finding filing to `deliver`;
   the archive's owed step still files any owed entry it creates, which needs no
   decision);
4. closes the issues cited by rows that a passed gate gated, removing
   `fr:awaiting-live`, but never an issue a narrowing decision names.

A batch whose archive holds (for example, a Test Plan step with no outcome)
moves nothing and gets no close-out event, and the verb names it. The driver
then raises a Needs-you row for it. Every other batch gets one close-out event,
whose `archive` names the shared branch. Without `--yes` the verb prints the
plan.

The driver starts at most one collected close-out per repo at a time. It marks
that close-out's PR ready and merges it, with no approval, once the PR is
`MERGEABLE` and green. On a conflict or red checks it hands back **once** to the
close-out's session (R27); a second failure becomes a Needs-you row.

R16. A batch whose gate passes after merge joins the next collected close-out.

R17. The board's columns, in order: Proposed, Waiting, Running,
**Needs you · Developer**, PR open, **Needs you · Reviewer**,
**Needs you · Tester**, **Needs you · DevOps**, Closing out, Partial, Done.

- *Developer:* the run cursor is blocked on a step gate, or a manual phase is
  the next unit.
- *Reviewer:* `deliver` is done and the PR is not approved, or a merge is
  stopped.
- *Tester / DevOps:* the batch landed and is gated (R13).

A card leaves a lane through the person's own act: answering, approving, or
recording a pass.

R18. The board and the driver read the run cursor at the batch PR's head
(`docs/superpowers/runs/<run-id>.yaml`, through `gitseam`) to decide the
Developer and Reviewer lanes, never session status. Session status stays a
secondary hint only: a blocked prompt still flags the card.

R19. One predicate, `conflicting(mergeable, merge_state)`, is true for
`CONFLICTING` or `DIRTY`. The kanban card and `needs_you` use it, and a card it
holds never shows `merge ready`; it shows `conflicting — the driver updates it
or hands it back`. The merge train still plans the merge, so the version-file
auto-resolution and the conflict hand-back (both started inside
`batch_merge._update`) work unchanged.

R20. **Release gating.** On each run (push to `main`, the daily schedule, or a
dispatch), `release.py` takes the first case that applies:

1. *Some change waits:* a PR merged since the last **final** tag carries an
   unpassed post-merge gate label. Cut an RC, unless nothing has merged since
   the newest RC tag; then do nothing.
2. *Nothing waits, and the head is an RC or fragments are pending:* cut the
   final.
3. *Otherwise:* do nothing.

The "last final tag" matches `^v\d+\.\d+\.\d+$` only. Version arithmetic:

- The final is `X.Y.Z`: the last final plus the highest pending fragment bump.
- An RC is `X.Y.Z-rc.N`, where `N` is one past the newest `vX.Y.Z-rc.*`.

An RC is a `release: vX.Y.Z-rc.N` commit, tagged `vX.Y.Z-rc.N` and published as
a GitHub pre-release. It consumes no fragment. Only the final's commit consumes
them. `fr gate pass` prints the dispatch command, so a final follows the last
pass.

R21. `fr release status [--json]` lists every PR merged since the last final tag
that still waits on a post-merge gate, with its gate and owed rows, read through
the forge adapter. `release.py` decides between RC and final from its JSON.
`release` joins `READ_ONLY_COMMANDS`: it touches no registered artifact, and CI
runs it on the default branch.

R22. `scripts/bootstrap.sh` takes a channel with `--version`. It checks out the
chosen tag in its managed checkout and forwards every other flag to the tag's
`install.sh`. A tag is installable only when that `install.sh` carries the
channel marker, the comment `# fr-install-channels: 1`. An unknown, missing or
uninstallable version lists the installable ones and installs nothing.

| `--version` | Installs |
|---|---|
| *(none)* | the newest installable `vX.Y.Z`; if none exists yet, `origin/main` as today, saying so |
| `RC` | the newest installable `vX.Y.Z-rc.N`, by version order |
| `X.Y.Z` | that release |
| `X.Y.Z-RC` | the newest `vX.Y.Z-rc.*` |
| `X.Y.Z-rc.N` | exactly that RC |
| `main` | `origin/main` (`checkout -B main origin/main`), the development channel |

R23. `scripts/install.sh` carries the channel marker and installs the checkout
it runs from. Its preflight accepts `main` in sync with `origin/main` as today,
or a clean, detached HEAD exactly at a `v*` tag. It prints the channel it
installed. The driver's `post_merge: ["./scripts/install.sh"]` keeps installing
`main` unchanged.

R24. **#1155.** One function, `row_verification_issues`, runs every per-row
check:

- the strategy does not resolve;
- the repo cannot run its install;
- an agent-driven pre-merge row has no `scenario:`;
- a post-merge or `none` row has no reason.

It runs whether or not the spec has a `## Verification` section, over the rows
citing the spec. Without a section it covers only rows whose own `verify:` is
set. Both `fr plan self-review` (errors) and the brainstorm warning (advisory)
call it.

The missing-reason message asks for a `## Verification` section with the row's
reason line. It warns that every other row citing the spec then takes the
section's `strategy:`, or the shape default when there is no `strategy:` line.

R25. The release tooling reads both spellings of an RC version:

- `bump-version.py` accepts `X.Y.Z-rc.N`. It writes PEP 440 `X.Y.ZrcN` to the
  Python surfaces and semver `X.Y.Z-rc.N` to the others, and its `--check`
  compares normalized versions.
- `changes.bumped`, `floors.parse_version` and `release.compute` treat an RC of
  `X.Y.Z` as based on the last final, never by int-splitting the RC string.

R26. `fr_version` floors admit an RC of `X.Y.Z` wherever they admit `X.Y.Z`, so
an RC never refuses artifacts written for the final it precedes.

R27. A close-out's hand-back (R15) is recorded as a `closeout_handback` event on
each member batch, keyed by the close-out item id and the PR head. Its budget of
one is counted per close-out item, and step 3 of `drive_pass` detects it from
the close-out PR's live checks and R19's predicate. This moves the judgements
schema.

## Design

### A. The exit (`fr/verification/exit.py`, new)

`run_exit(repo_root, state) -> Exit` returns:

- `kinds: frozenset[str]`;
- `run_gate: Gate`;
- `gates: frozenset[Gate]`;
- `gated_rows: tuple[Row, ...]`;
- `rank`, which R8's guard compares.

It builds on `run_verification` (`verification/rows.py`) and adds
`SpecVerification.gate(row)` and `SpecVerification.run_gate()`, which apply R1's
and R5's orders. `fr.gates` holds `GATES` and `POST_MERGE_GATES`; it is a small
module beside `fr.capabilities`.

`StrategyManifest` (`verification/model.py`) accepts `schema: 1 | 2`, and
`gate:` only at 2. Each fr resolves its own wheel copy before the marketplace
clone, so a released fr reads its own `live.yaml`. The wheel copy is regenerated
(`test_tripwire_shipped_verifications.py`).

`spec_section.py`'s `Section` gains `gate` and `row_gates`, parsed from
`gate:` lines. A malformed `gate:` line raises `SectionError` only in this fr.
`TriageConfig` (`triage/model.py`, strict) gains `exit: ExitBlock | None`.

The exit is computed from the PR's own tree (`deliver`, labels); the driver never
recomputes it and reads the PR's `verification:`/`gate:` labels instead, so the two
cannot diverge.

Compatibility: an older fr ignores `exit:` (naming the dropped key), so it computes
no remap. This repo does not set `exit:` in this PR; the
defaults are enough.

A read-only `fr verification exit --run <id> | --spec <path>` prints kinds,
gates and gated rows. It needs no forge, which makes it the scenario surface.

### B. Labels, PR adapter methods, `fr verification set`

The forge client protocol gains `edit_pr_labels(repo, pr, add, remove)` and
`comment_pr(repo, pr, body)`. The GitHub client implements them through the
issue endpoints, since a PR is an issue there. The GitLab and Gitea clients
raise `UnsupportedForgeOperation` for now.

`fr/labels.py` gains `verification_label(kind)` and
`gate_label(gate, passed=False)`.

`sync_exit_labels(repo_root, state, pr)` runs `ensure_labels`, then adds and
removes. It is called from:

- the resolves of `brainstorm` / `spec-review` when the run has a PR, as a
  warning on failure;
- `fr verification set`;
- `deliver`, where a failure refuses on GitHub and only warns on an unsupported
  forge (R7).

`fr verification set` lives in `commands/verification_cmd.py`. It writes a
decision `exit-change-<n>` and commits. The downgrade guard compares `run_exit`
before and after, applies once `spec-review` is done, and verifies
`--answered-by operator` with the transcript reader that
`journal resolve --answered-by` uses.

### C. `deliver` accounts for leftovers

`record/pr_body.py` gains `unaccounted(repo_root, state, exit) -> list[Leftover]`,
over R9's four item kinds. `run_cmd`'s `deliver` gate refuses while that list is
non-empty, and prints per item either `fr journal file …`, the row's
`set-status --issues …` fix, or the `fr verification set --gate` command to gate
it.

`premature_closes` takes the exit and the narrowing decisions. It keeps
`holds_open_for_run`'s test and ORs in "gated by a post-merge gate" (R11).

`fr journal file` (`commands/journal_cmd.py`) calls `file_open_ends` and
`file_owed_ends`, then writes through `fr journal resolve`'s engine. The archive
keeps calling the same two filers.

`JournalEntry` gains `gate`, `narrows: tuple[str, ...]`, and `answered_by` on a
decision. These are header tokens, written only when set and read by name, so an
older fr ignores them, as it ignored `tracked_by=` and `input=`. The journal
kind's stamp does not move.

The step record's `JournalItem` (`record/model.py`) is closed-world and read by
released fr versions. Adding `gate` and `narrows` therefore moves the `record`
kind from 9 to 10: a stamp migration, a structure validator, and
`fr migrate artifacts --yes` run in this PR, per
`.claude/rules/artifact-versioning.md`. `fr journal add` gains `--gate`,
`--narrows` and `--answered-by`.

### D. Driver routing, the gate ledger, close-out hand-backs

**Facts.** `collect` reads the labels of each batch's merged PR. It also reads,
at the batch PR's head, the run cursor's position: the step it is blocked on, a
done `deliver`, or a manual unit next. Together with `TriageConfig.exit`, this
moves `FACTS_SCHEMA`, and the stamp comment cites both. Per the known collision,
the number is main's plus one when the PR merges.

**`drive_pass`.**

- Step 2 skips a gated batch. When a gated batch first appears, it plans
  `awaiting-live` label actions for that batch. It also plans `gate-pass`
  actions for gated batches whose gated rows all read `walked` in the default
  branch's matrix, which it reads through `gitseam`.
- Step 2 then plans at most one `closeout` per repo, covering every landed batch
  that is not gated and not closed out. The next one waits until the previous
  housekeeping PR merged or was recorded.
- Step 3 marks the collected close-out's PR ready once it is `MERGEABLE` and
  green, then merges it. Otherwise it plans one `closeout-handback`: a runner
  prompt to the close-out item's session naming the conflicting files or the
  failing checks. That action records R27's event. A second failure at a later
  head becomes a `closeout-stuck` need.

Every forge write runs only with `--yes`.

`attributed` (`batch_drive.py:684`) also accepts `pr.head_ref == event.archive`
for a PR by a trusted author, so the shared head names every member, including a
batch with no run.

**`fr gate pass`.** It lives in `commands/gate_cmd.py`, a new group, and is
dry-run without `--yes`. `gate` joins `READ_ONLY_COMMANDS`, since it touches no
registered artifact.

### E. `fr triage batch closeout`

The verb lives in `triage_batch_cmd.py`; the engine is
`triage/batch_closeout.py`. For each batch it reads the run (`find_run`), then
runs R15's four steps in one `gitseam.Checkout` of the default branch, on branch
`chore/closeout-<YYYY-MM-DD>-<n>`, through these commands:

- `fr isolation verify-merge`;
- `fr closeout outcome --ran --evidence <gate-pass comment URL>`;
- `fr archive --branch <b> --no-issues`;
- the issue closes, behind `--yes`.

Then it makes one commit and one PR. The close-out work item is `unit="run"`:
one per collected close-out, with id `closeout-<date>-<n>`, briefed to run the
verb. A single-run `fr pickup` close-out outside batches is unchanged.

### F. Board lanes

`kanban.py`'s `Column` and `COLUMN_TITLES` gain `needs-developer`,
`needs-reviewer`, `needs-tester` and `needs-devops`, in R17's order. `column_of`
places a card from its stage, the facts' cursor position and the gate labels.
`needs_you` (`views.py`) adds one `Need` per card in a Needs-you lane, so
"Needs you now" and the lanes agree.

The `conflicting` predicate lives in `triage/mergeability.py`; the card hint and
`needs_you` use it. The triage page's own test (`render.py:609`, which counts
`BLOCKED`) is left alone. #1107 (draft, conflicting) is read for cursor-reading
code worth salvaging, and closed once this ships.

### G. Release and install channels

`release.py`:

- `compute` asks `fr release status --json` through an injectable `Commands`
  entry, since `release.py` already runs `fr migrate`. It then applies R20's
  cases.
- `previous_tag` and "the last final" match `^v\d+\.\d+\.\d+$`.
- `tag_and_release` passes `--prerelease` for an RC.
- `release.yml` adds a daily `schedule:`.

The version helpers change per R25:

- `version_surfaces.write_version` takes the semver form and writes the PEP 440
  form to `pyproject.toml` and `uv.lock`.
- `bump-version.py --check` normalizes before comparing, and `bump()` checks
  `fr --version` against the normalized form.

`version_floor.admits` compares an RC's release tuple when the floor names
`X.Y.Z` (R26).

`bootstrap.sh` parses `--version` and resolves it against
`git ls-remote --tags`. It checks each candidate tag for the marker with
`git show <tag>:scripts/install.sh`, then checks out the tag detached (or runs
`checkout -B main origin/main` for `main`) and execs `install.sh` with the
remaining flags. `install.sh` adds the marker and the tagged-checkout branch of
its preflight: `git describe --exact-match --tags HEAD` matching `^v[0-9]`, plus
a clean tree.

### H. #1155

`row_verification_issues(repo_root, section | None, rows, shape_default)` lives
in `verification/rows.py`. It absorbs the per-row loop of
`plan_ops._verification_issues` and `unrunnable_strategies`, which now takes
`section: Section | None`.

- `_verification_issues` calls it and keeps its section-only checks.
- `_unrunnable_spec_warnings` calls it in place of `unrunnable_strategies`,
  which widens the warning to all four checks.

A spec with no section and no row `verify:` passes unchanged.

### I. Skill and doc prose

These edits follow the AGENTS.md mirror rules (`sync-opencode.py` and
`sync-hermes.py`):

- **fr-goal §1/§8:** the `gate:` answer, `fr journal file` before `deliver`, and
  labels.
- **fr-brainstorming §1:** the verification question also settles the gate.
- **fr-triage:** the lanes, `batch closeout`, and `gate pass`.
- **fr-acceptance:** a walk passes the gate.

`docs/verification-strategies.md` documents `gate:` and schema 2. The explainer
`01-fr-goal` is updated where it describes delivery and close-out, per
`explainers-currency.md`. The README documents `bootstrap.sh --version`.

## Non-goals

- An `fr upgrade` command. None exists; the install channel is bootstrap's.
- Enforcing the Security gate. Its role is vocabulary only (R2).
- Changing approval (`approved-fr`) for feature PRs.
- PR labels on GitLab and Gitea. Their adapters raise
  `UnsupportedForgeOperation`, and fr only warns there.
- The triage page's conflict test counting `BLOCKED` (spec-review sr-25, out of
  scope).

## Verification

strategy: candidate
- exit-gates-declared-exit: candidate — scenario drives `fr verification exit` over fixture specs
- exit-gates-set-downgrade: candidate — scenario drives `fr verification set` and its refusal
- exit-gates-verify-without-section: candidate — scenario drives `fr plan self-review` on a section-less spec
- exit-gates-deliver-accounting: none — CI integration tests drive `deliver` against a stubbed forge; a scenario cannot reach a forge
- exit-gates-board-lanes: none — CI unit tests render the board and run `drive_pass` over fixture facts
- exit-gates-install-channels: none — CI integration tests run bootstrap.sh/install.sh against a fixture remote with release and RC tags
- exit-gates-pr-labels: live — only a real forge shows the labels a real run's PR carries
- exit-gates-driver-routing: live — a gated batch and its gate pass need a real merged PR, driver and matrix on main
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
   closed out, and its `Refs` issue stays open with `fr:awaiting-live`. Walk its
   row with `set-status --walk` and merge that. The next drive pass swaps the
   label to `gate:tester-passed`.
3. **Collected close-out.** With two or more batches landed and not gated, one
   collected close-out opens ONE housekeeping PR. The driver marks it ready and
   merges it once clean. It records the passed batch's Test Plan outcomes and
   closes that batch's `Refs` issue.
4. **Release.** While step 2's PR is unpassed, a push to `main` cuts
   `vX.Y.Z-rc.N` as a pre-release. After the pass, the next run cuts the final
   `vX.Y.Z`. `bootstrap.sh --version RC` installs the RC, and with no argument it
   installs the final.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-10-14-exit-gates | `derio-net/super-fr` | `2026-10-14-exit-gates` | — |
