# Journal: 2026-09-25-closeout-brief-resolve-lines

<!-- fr:journal kind=repro scope=debug id=3dc9a5d03d32 created=2026-09-25T19:22:48 -->
### 3dc9a5d03d32 · repro · closeout brief resolve lines: stranded on main and missing --note (#621)

First live use of `fr pickup --run 2026-09-25-fix-610-closeout-defects` (housekeeping PR #620). (1) The brief lists `fr journal resolve … --state deferred` BEFORE `fr isolation up --branch chore/archive-<slug>`; run from the base clone on the default branch, fr writes each record but makes no commit (§3.C), so they never reach the housekeeping PR and leave main dirty. (2) Each printed line fails: `Missing option '--note'` — journal_cmd.resolve declares --note required.

<!-- fr:journal kind=root-cause scope=debug id=022b8fb20d26 created=2026-09-25T19:22:48 -->
### 022b8fb20d26 · root-cause · closeout_brief emits resolves before the housekeeping workspace and without --note

packages/fr/src/fr/run/closeout.py:165-174 appends the out-of-scope resolve lines before `fr status` and the `fr isolation up --branch chore/archive-…` line (186-190); _out_of_scope_lines (107-108) formats `fr journal resolve … --state deferred --tracked-by <#N>` with no --note, while journal_cmd.resolve's --note is typer.Option(...) (required). The existing ordering test pinned the wrong order (resolves < status < archive) and no test ran the lines against the CLI signature.
