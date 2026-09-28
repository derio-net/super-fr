# Journal: 2026-09-25-closeout-brief-resolve-lines

<!-- fr:journal kind=repro scope=debug id=3dc9a5d03d32 created=2026-09-25T19:22:48 -->
### 3dc9a5d03d32 · repro · closeout brief resolve lines: stranded on main and missing --note (#621)

First live use of `fr pickup --run 2026-09-25-fix-610-closeout-defects` (housekeeping PR #620). (1) The brief lists `fr journal resolve … --state deferred` BEFORE `fr isolation up --branch chore/archive-<slug>`; run from the base clone on the default branch, fr writes each record but makes no commit (§3.C), so they never reach the housekeeping PR and leave main dirty. (2) Each printed line fails: `Missing option '--note'` — journal_cmd.resolve declares --note required.

<!-- fr:journal kind=root-cause scope=debug id=022b8fb20d26 created=2026-09-25T19:22:48 -->
### 022b8fb20d26 · root-cause · closeout_brief emits resolves before the housekeeping workspace and without --note

packages/fr/src/fr/run/closeout.py:165-174 appends the out-of-scope resolve lines before `fr status` and the `fr isolation up --branch chore/archive-…` line (186-190); _out_of_scope_lines (107-108) formats `fr journal resolve … --state deferred --tracked-by <#N>` with no --note, while journal_cmd.resolve's --note is typer.Option(...) (required). The existing ordering test pinned the wrong order (resolves < status < archive) and no test ran the lines against the CLI signature.

<!-- fr:journal kind=finding scope=debug id=29e4d3f7b5f3 created=2026-09-25T19:42:06 state=fixed -->
### 29e4d3f7b5f3 · finding [fixed] · resolves after isolation up, runnable as printed; PR line guarded

closeout.py: out-of-scope resolve lines now sit between `fr isolation up --branch chore/archive-<slug>` (or `chore/closeout-<run>` with no plan) and `fr archive`; each carries `--tracked-by '<#N>' --note 'Filed at closeout as <#N>.'` (quoted: a bare #618 is a shell comment). Failing-first tests in tests/unit/test_run_closeout.py: ordering (red on old order), parse-against-click-signature (red on missing --note, and on the unquoted #), no-plan edge; review follow-up guards the housekeeping-PR line (revert-proven). Full suite 5279 passed.

<!-- fr:journal kind=review scope=debug id=e620db1fd65f created=2026-09-25T19:42:06 -->
### e620db1fd65f · review · independent review: no in-scope findings; one low-confidence observation fixed

Dispatched reviewer (feature-dev:code-reviewer) verified ordering, no-plan branch, quoting, that journal resolve commits off the default branch (commit_paths refuses only on_default_branch), and that the archive commit is still needed. Raised one out-of-scope/low-confidence observation: 'open the housekeeping PR' printed with no housekeeping branch — adjacent to this change, fixed with a test.
