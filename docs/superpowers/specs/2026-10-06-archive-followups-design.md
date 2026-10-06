# Archive does its own follow-ups — design

Batch `archive-followups` (super-fr#930, #528, #458), one PR.

## 1. Goal

A post-merge close-out ends with `fr archive`. Today that command leaves three
jobs behind, and each one is done by hand later or not at all:

1. **Unpriced usage (#930).** The closeout's own session is still open when it
   is captured. Claude Code writes a session's dollars only when the session
   exits, so every archived usage file carries one unpriced session. The fix is
   `fr usage backfill`, followed by a commit, followed by a third PR. It is
   usually forgotten until the transcript is gone.
2. **Stale matrix refs (#528).** Archive moves specs, plan dirs, journals, runs
   and usage, but it never rewrites the `docs/acceptance/matrix.yaml` refs that
   name them. A stale spec or journal ref warns forever. 60 of these had
   accumulated before PR #524 cleared them. A stale **plan** ref has no archive
   twin, so `fr acceptance check` fails on `main` after closeout (#817).
3. **Untracked open ends (#458).** Findings still `open` or `out-of-scope` in
   the journals archive moves become invisible once they are in `implemented/`.
   The closeout brief asks the agent to open each issue by hand and then fill in
   an `fr journal resolve … --tracked-by '<#N>'` line.

After this change, `fr archive` does all three in the same operation, and the
results land in the housekeeping commit that is being made anyway.

## 2. Background (verified against the code)

- `packages/fr/src/fr/commands/archive_cmd.py` has three entry modes:
  `plan_dir`/`--all`, `--sweep-only` and `--branch <b>` (`_archive_branch`).
  Most paths call `_repair_in_passing` after a move. Two do not: `--all`'s
  owed-artifact moves alone (`:580`), and a single-plan archive that exits 2
  after its plan dir already moved (`:519-524`).
- `fr.archive._archive_usage` captures the closeout (`capture(..., "closeout")`)
  and `_note_unpriced` prints the gh#756 "run `fr usage backfill` here and
  commit" message.
- `fr.usage.backfill.refreshed_file(usage, raw, env)` re-reads this host's
  unpriced sessions. It returns `None` when nothing changed and only ever
  touches this host's capture. `backfill()` loops it over
  `implemented/runs/*.yaml` paired with `implemented/usage/<run>.yaml`.
- `fr.acceptance.model.archive_twin` pairs `specs/` ↔ `implemented/specs/` and
  each journal scope dir. Plan dirs, runs and usage have no twin.
  `fr.acceptance.check._resolve_ref` warns on a twin hit ("update the matrix ref
  when convenient") and errors on a miss.
- The matrix carries `repo:`, and `resolve_identity(matrix, root)[1]` is the
  own-repo name `check` uses. `fr acceptance report --deterministic`
  (`report.render_committed_set`) writes the three committed reports.
- Journals: `fr.journal.model.effective_finding_states` is the fold.
  `append_journal_entry` is the write path. A `deferred` record is an
  `open`-state resolution record carrying `tracked_by`.
  `resolve_journal_read_path` finds a journal live or archived.
- `fr.run.closeout._out_of_scope_lines` prints the per-finding manual lines
  that the brief carries today. `_tracker_note` handles `tracking: none`.
- `GhClient.create_issue(repo, title=, body=, labels=)` returns a URL.
  `list_issues` raises `UnsupportedForgeOperation` on glab/tea.
- `fr.artifacts.trigger.is_interactive` is the repo's TTY predicate.
- Rework `origin_items` exist in exactly one archived plan, so they are not
  worth scanning.

## Requirements

R1. Whenever an `fr archive` invocation has staged at least one move — on every exit path, including one that then refuses or exits 2 — it refreshes every existing `implemented/usage/*.yaml` whose run cursor is archived, using `refreshed_file`, and stages each rewritten file; an invocation that staged no move refreshes nothing.
R2. The refresh never fails the archive: a usage file or cursor that cannot be read, or a usage file with uncommitted changes, is skipped with a one-line note; it never creates a usage file for a run that has none.
R3. The closeout's "no dollars yet" message says the next `fr archive` (or `fr usage backfill`) will price the session, and no longer asks for a manual commit.
R4. Whenever an invocation has staged at least one move (same trigger as R1), `fr archive` rewrites every same-repo matrix ref listed under a row's `origin` or a `levels.<level>` list that names a path this invocation moved — a spec, a journal, a run cursor, a usage file, a plan dir or any file inside one — to that path's new location, keeping any `#fragment`.
R5. The retarget changes nothing else in `matrix.yaml`: row ids, statuses, notes, scenarios, walks, ordering, comments and every other ref stay byte-identical; refs naming another repo are never touched.
R6. When the retarget changed the matrix, archive regenerates the three committed reports and stages them with the matrix. A repo with no matrix is a no-op. A matrix or report with uncommitted changes, a matrix that cannot be read, or a rewrite whose re-parse differs from the original in anything but the retargeted refs, is a warning that leaves every file untouched — never a failure.
R7. A stale plan-dir ref stays an error in `fr acceptance check` (no plan archive twin); the spec/journal twin warning is reworded to say that the ref names an archived path, survived an archive fr did not perform, and should be retargeted.
R8. Whenever an invocation has staged at least one move, `fr archive` lists every finding whose folded state is `open` or `out-of-scope` in the spec, plan and debug journals this invocation moved, each under its qualified id `<scope>/<slug>/<id>` with its title.
R9. `fr archive --issues all` files one tracker issue per listed open end; `fr archive --issues <qid>[,<qid>…]` files exactly the named findings, each read from its journal wherever it lives (live or archived), whether or not this invocation moved anything; a bare `<id>` is accepted only when it names exactly one finding among the listed ones; an id that resolves to no open/out-of-scope finding, or to several, is refused before anything is filed. `--no-issues` only lists; `--issues` and `--no-issues` together are a usage error.
R10. With neither flag, an interactive archive prompts once (`y`/`N`/`select`); a non-interactive one only lists. Under `tracking: none`, or a services declaration that cannot be read (with the same warning the closeout brief prints), archive only lists, whatever the flags. Filing never changes archive's exit code and never blocks the moves: a forge error is reported per finding and the rest proceed.
R11. Each filed issue's body carries the finding's body, the journal path, the spec/plan paths when known, and a `fr:journal <scope>/<slug>/<id>` marker; when the forge can list issues, an open issue already carrying the marker is reused instead of a duplicate being created.
R12. For each filed (or reused) issue, archive appends a `deferred` resolution record (`tracked_by` = the issue URL) to that finding's journal at its current location, built by the same builder `fr journal resolve --state deferred` uses, and stages it, so the journal folds the finding to `deferred`.
R13. The closeout brief (`fr pickup --run`) lists the run's out-of-scope findings by qualified id and gives one `fr archive --branch <b> --issues <qid,…>` command (with `--no-issues` named as the way to file none), replacing the per-finding manual `fr journal resolve` lines; under `tracking: none` it keeps saying no tracker is configured. The shipped fr-goal skill's close-out prose (and its OpenCode/Hermes mirrors and the fr-goal explainer) describes this route.

## Design

### 0. One trigger, one move log (R1, R4, R8)

Every archive move goes through `fr.archive._git_mv` (reached from
`archive_plan_dir`, `archive_run_cursor`, `_archive_usage`, `archive_journal`
and `spec_archive_sweep`). `fr.archive` gains a `MoveLog` (an ordered list of
`(src_rel, dst_rel)` pairs) and a `contextvars.ContextVar[MoveLog | None]`,
`_MOVE_LOG`, which `_git_mv` appends to after a successful move when it is
set. The public functions' signatures do not change; other callers (e.g.
`fr migrate dirs`) never set the var and record nothing.

`archive_command` opens one `MoveLog` per invocation (`with recording_moves()
as log:`) and wraps every entry mode's body in `try: … finally:
_after_moves(repo_root, log, opts)`. `_after_moves` is a no-op when the log is
empty. So the trigger is "at least one move was staged", on every exit path —
including a single-plan archive that moved the plan dir and then exited 2
because a follower move raised (`archive.py:403-405`,
`archive_cmd.py:519-524`), and the `--all` path whose `owed_moved` alone does
not call `_repair_in_passing` (`archive_cmd.py:580`). The follow-ups never
alter the exit code the body chose. The one exception is R9's explicit
`--issues <qids>`, which files even when the log is empty (§C).

`_after_moves` runs, each step in its own `try` so one failure never stops
the next: the usage refresh (§A), the matrix retarget (§B), the open ends
(§C).

### A. Usage refresh (R1–R3)

`fr.usage.backfill.refresh_archived(repo_root, env, *, skip: Callable[[Path],
bool]) -> BackfillReport` holds the existing-file branch of `backfill()`.
`backfill()` calls it for that branch, so there is still one implementation.
It only refreshes: it never writes a new file. Each per-run exception lands in
`report.failed`. `skip` is `paths_dirty`, so an archived usage file with
uncommitted edits is reported, not rewritten (R2). Archive `git add`s each
refreshed file and prints `  priced: <path>`. It prints one `note:` per
failure or skip.

`_note_unpriced`'s text becomes: "no dollars yet for session(s) … — a harness
may write a session's cost only when it exits. The next `fr archive` here will
price it (or run `fr usage backfill`)."

### B. Matrix retarget (R4–R7)

**Matching.** A ref `own:<path>[#frag]` matches a log pair when `path ==
src`, or when `path` starts with `src + "/"` for a directory move (a plan
dir). The new path is `dst` plus the carried-over suffix. `own` is
`resolve_identity(matrix, root)[1]`, the identity `fr acceptance check` uses.

**Rewriting.** `fr.acceptance.retarget.retarget_text(text, own, moves) ->
(new_text, changes)` is pure and line-based. It tracks which row-level key
block it is in, and rewrites only block-list item lines (`- <ref>`) directly
under a row's `origin:` key or under a `levels:` → `<level>:` key. It never
touches `notes`, `scenario`, `walks` or anything else (R5), and it never
round-trips through `yaml.dump`. The result is parsed with
`fr.artifacts.structure._StrictLoader` into a `Matrix`. That `Matrix` must
equal the original with the `changes` applied, or the retarget is abandoned
(R6).

**Writing.** When `changes` is non-empty and none of `matrix.yaml` and the
three reports is dirty (`paths_dirty`), archive writes the matrix through
`write_text_atomic`, renders `render_committed_set`, writes those files, and
`git add`s all four. It prints `  retargeted: <row> · <old> → <new>`. A dirty
file or any exception produces a `warning:` line naming the reason, and no
file is touched. All renders happen in memory before the first write, so a
render failure writes nothing.

**Check wording (R7).** `_resolve_ref`'s twin warning becomes: "row X: REF
names an archived path (now TWIN) — it survived an archive fr did not
perform; retarget it". `ARCHIVE_TWIN_DIRS` gains no plan pair.

### C. Open ends → issues (R8–R13)

**Ids.** An open end's qualified id is `<scope>/<slug>/<id>`, the same token
as the R11 marker. Finding ids are unique only within one journal, and one
`--branch` archive moves a spec journal and a plan journal.

**Listing (R8).** `fr.archive_followups.open_ends(repo_root, journals) ->
list[OpenEnd]` takes the `(scope, slug)` set whose journal dst appears in the
move log under `implemented/journals/<scope-dir>/`. Each `OpenEnd` carries
`scope, slug, id, title, body, state, path`, where the path comes from
`resolve_journal_read_path`. The fold is `effective_finding_states`, keeping
`open` and `out-of-scope`.

**CLI (R9).** `--issues TEXT` takes a required value: `all`, or a comma list
of qualified (or unambiguous bare) ids. `--no-issues` is a bool flag. Both
together is exit 2 before anything moves. Explicit qids are resolved against
the journal they name, live or archived (`resolve_journal_read_path`). That
makes the brief's command work even when a spec was held, an earlier archive
already moved the journal, or the operator answered `N` last time (spec review sr-3). A
qid naming no `open`/`out-of-scope` finding, or a bare id naming several, is
refused with a warning before anything is filed. The archive's moves have
already happened by then (the follow-ups run after them) and the exit code is
unchanged.

**Deciding (R10).** The rules are evaluated in order:

1. Print the listing, if non-empty.
2. Run `require_tracker`. `TrackerRequiredError` → print "no tracker
   configured — left in the journal" and stop. `ServicesError` → print the
   same invalid-declaration warning `closeout._tracker_note` prints and stop.
3. `--no-issues` → stop.
4. `--issues …` → file the resolved selection.
5. No flag and `is_interactive()` → prompt `open issues for these?
   [y/N/select]` (`select` reads a comma list of ids).
6. Otherwise → stop.

**Filing (R11).** The repo slug is `"/".join(resolve_identity(matrix_or_empty,
repo_root))`. That is the same identity the retarget uses. It falls back to
the origin remote when there is no matrix, and it has a known two-segment
limit for nested GitLab groups (`check.py:33-38`). Per end, the body holds the
finding body, the journal path, the spec and plan paths (from the run
cursor's `emitted`, when the log moved one), and `<!-- fr:journal
<qid> -->`. `list_issues(repo, "open", 200, fields="number,url,body")` is read
once per invocation. Any error (including `UnsupportedForgeOperation` on
glab/tea) means no dedup. A marker hit is reused. Otherwise filing calls
`create_issue(…, labels={"follow-up"})` after `ensure_labels`, and an
`ensure_labels` failure files the issue without the label. Each error is
recorded per finding.

**Write-back (R12).** The pure deferral-entry builder in
`fr.record.apply` (`record/apply.py:367-380`: `resolution_record_id`, title
`resolves <id>: <title>`, body = note, `state="open"`, `tracked_by`,
`created` stamp, `scope`) is extracted to `fr.journal.model.resolution_entry(...)`
and used by both writers, so they cannot drift. Archive appends the result
through `append_journal_entry` to the finding's journal at its current path,
with the note "Filed at archive as <url>.", and `git add`s it. It is never
committed by fr: archive's contract stays "staged, the operator commits".

**Closeout brief (R13).** `fr.run.closeout._out_of_scope_lines` becomes
`  - <qid>: <title>` lines plus one line, `fr archive --branch <b> --issues
<qid,…>   # keep the ids the operator chose; --no-issues files none`. This
replaces the brief's plain `fr archive --branch <b>` line when out-of-scope
findings exist. The `tracking: none` wording is unchanged.
`plugins/super-fr/skills/fr-goal/SKILL.md`'s post-merge close-out paragraph
is updated to match. The OpenCode and Hermes mirrors are regenerated
(`sync-opencode.py`, `sync-hermes.py`), and `docs/explainers/01-fr-goal.md`
plus its `.html` are re-rendered per `.claude/rules/explainers-currency.md`.

### D. Order and atomicity

1. The moves.
2. Then, in the `finally`, the refresh, the retarget and the open ends, each
   best-effort. Nothing in the follow-ups changes archive's documented exit
   codes.
3. Everything is staged. The operator reviews, commits and PRs it as one
   housekeeping change.

This is #528's "only after successful archive" in the sense that matters: a
move that happened always gets its refs fixed, and a move that never happened
is never retargeted.

## Risks

- **Line-based retarget versus YAML.** A ref written in flow style or as a
  folded scalar is not matched. Today's matrix has none (spec review
  verified). The re-parse equality check turns any surprise into a warning
  rather than a corruption.
- **Forge write in a closeout.** It needs an explicit `--issues` or an
  interactive `y`. The journal record is the durable idempotency, because a
  `deferred` finding is no longer an open end. The marker covers a crash
  between creating the issue and writing the record.

## Test Plan

Unit/CLI (in CI), per requirement group:

- **R1–R3:** `refresh_archived` refreshes only unpriced files, skips dirty and
  unreadable ones with notes, and never creates a file. An archive that moved
  something stages refreshed files. An archive that moved nothing leaves the
  tree clean. Covers the reworded `_note_unpriced` text.
- **R4–R6:** `retarget_text` rewrites `origin` and `levels` refs for file and
  plan-dir moves, keeping fragments. It leaves notes, scenarios,
  other-repo refs and comments byte-identical. Archive regenerates and stages
  the reports. A dirty matrix or report warns and touches nothing. No matrix is
  a no-op. A single-plan archive that exits 2 after moving the plan dir still
  retargets.
- **R7:** the reworded twin warning, and a stale plan-dir ref is still an
  error.
- **R8–R12:** listing by qid; `--issues all`, `--issues <qids>` and bare-id
  ambiguity refusal; `--issues`+`--no-issues` usage error; explicit qids
  against an already-archived journal; non-interactive list-only;
  `tracking: none` and an invalid services declaration list only; marker
  dedup; per-finding forge failure; the appended `deferred` record folds the
  finding to `deferred` and equals what `fr journal resolve --state deferred`
  writes.
- **R13:** brief text (qids, the `--issues` command, `--no-issues`), and the
  `tracking: none` wording kept.

Post-merge, operator-driven: run the next real close-out (`fr pickup --run`)
with this `fr`. Its housekeeping commit should carry refreshed
`implemented/usage` files, and every matrix ref naming a path that close-out
moved should be retargeted, with the reports regenerated. The issues the
operator chose should be filed, with `deferred` records in the archived
journals. Refs left stale by earlier, pre-feature archives are out of this
feature's reach. One exists today (`matrix.yaml`, the
`2026-09-27-spec-ref-writers` spec ref), and this PR retargets it by hand so
the baseline is zero.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-10-06-archive-followups | `derio-net/super-fr` | `2026-10-06-archive-followups` | — |
