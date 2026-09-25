# Journal: 2026-09-25-closeout-brief-resolve-lines

<!-- fr:journal kind=repro scope=debug id=3dc9a5d03d32 created=2026-09-25T19:22:48 -->
### 3dc9a5d03d32 · repro · closeout brief resolve lines: stranded on main and missing --note (#621)

First live use of `fr pickup --run 2026-09-25-fix-610-closeout-defects` (housekeeping PR #620). (1) The brief lists `fr journal resolve … --state deferred` BEFORE `fr isolation up --branch chore/archive-<slug>`; run from the base clone on the default branch, fr writes each record but makes no commit (§3.C), so they never reach the housekeeping PR and leave main dirty. (2) Each printed line fails: `Missing option '--note'` — journal_cmd.resolve declares --note required.
