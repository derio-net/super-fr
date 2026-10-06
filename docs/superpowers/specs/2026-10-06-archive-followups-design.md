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
  Each mode ends in `_repair_in_passing` when something moved, then prints
  `moves staged via git mv`.
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

R1. When an `fr archive` invocation moves anything, it refreshes every existing `implemented/usage/*.yaml` whose run cursor is archived, using `refreshed_file`, and stages each rewritten file; an invocation that moves nothing refreshes nothing.
R2. The refresh never fails the archive: a usage file or cursor that cannot be read is skipped with a one-line note, and the archive proceeds; it never creates a usage file for a run that has none.
R3. The closeout's "no dollars yet" message says the next `fr archive` (or `fr usage backfill`) will price the session, and no longer asks for a manual commit.
R4. After the moves of an invocation succeed, `fr archive` rewrites every same-repo matrix ref (in `origin` and every `levels` list) that names a path this invocation moved — a spec, a journal, a run cursor, a usage file, a plan dir or any file inside one — to that path's new location, keeping any `#fragment`.
R5. The retarget changes nothing else in `matrix.yaml`: row ids, statuses, notes, ordering, comments and every other ref stay byte-identical; refs naming another repo are never touched.
R6. When the retarget changed the matrix, archive regenerates the three committed reports and stages them with the matrix; a repo with no matrix is a no-op; a matrix that cannot be read or rewritten is a warning, never a failure, and leaves the matrix untouched.
R7. A stale plan-dir ref stays an error in `fr acceptance check` (no plan archive twin); the spec/journal twin warning is reworded to say that a ref survived an archive fr did not perform and should be retargeted.
R8. After the moves of an invocation succeed, `fr archive` lists every finding whose folded state is `open` or `out-of-scope` in the spec, plan and debug journals this invocation moved — id, title, scope/slug.
R9. `fr archive --issues` opens one tracker issue per listed open end; `--issues <id>[,<id>…]` opens only the named ones (an id that is not listed is refused before anything is created); `--no-issues` only lists.
R10. With neither flag, an interactive archive prompts once (`y`/`N`/`select`); a non-interactive one only lists. Under `tracking: none` archive only lists, whatever the flags. Filing never fails or blocks the archive: a forge error is reported per finding and the rest proceed.
R11. Each filed issue's body carries the finding's body, the journal path, the spec/plan paths when known, and a `fr:journal <scope>/<slug>/<id>` marker; when the forge can list issues, an open issue already carrying the marker is reused instead of a duplicate being created.
R12. For each filed (or reused) issue, archive appends a `deferred` resolution record (`tracked_by` = the issue URL) to that finding's journal at its archived location and stages it, so the archived journal folds the finding to `deferred`.
R13. The closeout brief (`fr pickup --run`) lists the run's out-of-scope findings and gives one `fr archive --branch <b> --issues <ids>` command for the ones the operator chose, replacing the per-finding manual `fr journal resolve` lines; under `tracking: none` it keeps saying no tracker is configured.

## Design

### A. Usage refresh (R1–R3)

A new `fr.usage.backfill.refresh_archived(repo_root, env) -> BackfillReport`
contains the existing-file branch of `backfill()`. `backfill()` calls it for that
branch, so there is still one implementation. Two differences matter:

- It only refreshes. It never writes a new file (R2's last clause).
- Any exception per run becomes `report.failed`, and the call as a whole is
  wrapped in the caller as well. The archive never raises from it.

`archive_cmd` gains `_after_moves(repo_root, moved: MovedPaths, ...)`. Every
entry mode calls it once at the point where it prints `moves staged via git mv`,
which is exactly the "moved anything" condition. It runs, in order:

1. the usage refresh,
2. the matrix retarget (§B),
3. the open-ends listing and filing (§C).

Each step is isolated in its own try. The refresh `git add`s each rewritten
file, prints `  priced: <path>` per file, and prints one `note:` line per
failure.

`_note_unpriced`'s text becomes: "no dollars yet for session(s) … — a harness
may write a session's cost only when it exits. The next `fr archive` here will
price it (or run `fr usage backfill`)."

### B. Matrix retarget (R4–R7)

**Collecting the moves.** Every move goes through `fr.archive._git_mv`. A
module-level recorder (`fr.archive.MoveLog`, opened by the command around one
invocation and passed down, not a global) collects `(src_rel, dst_rel)` pairs.
For a plan dir, the pair is the directory. A ref is retargeted when its path
equals a moved `src`, or sits under a moved directory `src` (with the suffix
carried over).

**Rewriting.** `fr.acceptance.retarget.retarget_text(text, own_repo,
moves) -> (new_text, changes)` is a pure **textual** rewrite of the YAML. It
replaces only the scalar `own_repo:<path>[#frag]` tokens whose path matches. It
never round-trips through `yaml.dump`, so comments, ordering, quoting and
every other byte survive (R5). The result is re-parsed with the strict loader
and must yield the same rows apart from the rewritten refs. If it does not, the
retarget is abandoned with a warning (R6).

`own_repo` comes from `resolve_identity(matrix, root)[1]`, the same identity
`check` uses.

**Reports.** When `changes` is non-empty, the command writes `matrix.yaml`
atomically, runs `render_committed_set`, writes the three reports and
`git add`s all four. It prints `  retargeted: <row> · <old> → <new>` per
change. Any exception produces a `warning:` line, and the matrix bytes are
restored if they had been written.

**Check wording (R7).** `_resolve_ref`'s twin warning becomes: "row X: REF
names an archived path (now TWIN) — a ref survived an archive fr did not
perform; retarget it". `ARCHIVE_TWIN_DIRS` gains no plan pair.

### C. Open ends → issues (R8–R13)

**Collecting.** `fr.archive_followups.open_ends(repo_root, journals) ->
list[OpenEnd]`. `journals` is the `(scope, slug)` set whose journal this
invocation moved, read from the move log (a dst under
`implemented/journals/<scope-dir>/`). Each `OpenEnd` carries `scope, slug, id,
title, body, state, journal_path`. The fold is
`effective_finding_states`, keeping `open` and `out-of-scope`.

**Deciding.** The CLI adds `--issues [IDS]` and `--no-issues`, which are
mutually exclusive. The rules are evaluated in this order:

1. No open ends → print nothing.
2. Print `archive: N open end(s)` plus one line per finding.
3. `tracking: none` (`require_tracker` raises `TrackerRequiredError`) → print
   "no tracker configured — left in the journal" and stop.
4. `--no-issues` → stop.
5. `--issues` with ids → validate them against the list. On an unknown id,
   print the refusal and file nothing (the archive itself has already
   succeeded, and the exit stays 0 with a warning). Otherwise use the
   selection.
6. `--issues` bare → all of them.
7. No flag and `is_interactive()` → prompt `open issues for these? [y/N/select]`
   (`select` reads a comma list of ids).
8. Otherwise → list only.

**Filing.** `file_open_ends(gh, repo, ends, repo_root) -> list[Filed |
Failed]`. Per end, it builds the body from the finding body, the journal path,
the spec and plan paths (the run cursor's `emitted`, when one moved), and the
marker line `<!-- fr:journal <scope>/<slug>/<id> -->`. Then:

- `list_issues(repo, "open", 200, fields="number,url,body")` is tried once per
  invocation. On `UnsupportedForgeOperation` or any error, it falls back to no
  dedup.
- An open issue whose body contains the marker is reused.
- Otherwise `create_issue(repo, title="<finding title>", body=…,
  labels=frozenset({"follow-up"}))` is called. The `follow-up` label is
  ensured through `ensure_labels` first, and a failure there drops the label
  rather than the issue.

A `GhClient` error is a `Failed` entry. Filing continues with the next end.

**Write-back (R12).** For each `Filed`, append a resolution record through
`append_journal_entry` to the archived journal path:

```
kind=finding, resolves=<id>, state=open, tracked_by=<url>, note="Filed at archive as <url>."
```

This is the same shape `fr journal resolve --state deferred` writes. Then
`git add` it.

The repo slug comes from the forge client the command already builds
(`_make_gh_client`), plus the `owner/repo` of the `origin` remote, the same way
`fr.closeout` callers resolve it today.

**Closeout brief (R13).** `_out_of_scope_lines` is replaced by a list of
`  - <scope>/<slug> <id>: <title>` lines plus one command, `fr archive --branch
<b> --issues <id,…>   # keep the ids the operator chose; drop the flag to file
none`. The brief's archive step already names `fr archive --branch <b>`, and
the `--issues` form replaces it when out-of-scope findings exist. Under
`tracking: none`, the existing no-tracker wording stays.

### D. Order and atomicity

All three follow-ups run **after** a successful move set, in the same process,
before the final `moves staged` line. That satisfies #528's "only after
successful archive". Each is independently best-effort. None of them changes
the exit code: archive's exit codes stay exactly as documented, and a
follow-up's failure is a `warning:` or `note:` line. The operator still
reviews, commits and PRs everything as one housekeeping change.

## Risks

- **Textual retarget versus YAML semantics.** A ref split across a folded
  scalar would be missed. The re-parse equality check turns that into a warning
  rather than a corruption.
- **Forge write in a closeout.** It only happens with an explicit `--issues` or
  an interactive `y`. The marker dedup protects against a crash between
  creating the issue and writing the journal record. The journal record itself
  is the durable idempotency, because a `deferred` finding is no longer an open
  end.

## Test Plan

Post-merge, operator-driven: run the next real close-out (`fr pickup --run`)
with this `fr`. The housekeeping commit should contain refreshed
`implemented/usage` files, retargeted matrix refs with regenerated reports, and,
when the run had out-of-scope findings, the issues the operator chose, with
`deferred` records in the archived journals. `fr acceptance check` on `main`
after merge should be clean of archive warnings.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-10-06-archive-followups | `derio-net/super-fr` | `2026-10-06-archive-followups` | — |
