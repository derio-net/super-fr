# Acceptance Matrix — Backfill Rule (repo-wide)

## Rule

The acceptance matrix is the registry of business-level acceptance tests ×
verification levels × automation status. Its rows live in **per-feature
fragments**, `docs/acceptance/features/<spec-slug>.yaml` (spec
`2026-11-04-repo-feature-settings` R16): each row is owned by the feature (spec)
that created it, `legacy.yaml` holds the rows with no single origin spec, and
every fragment carries the repo's identity as `repo: <org>/<repo>`. The
effective matrix is never stored — `fr` folds the fragments over git history
(`fr.acceptance.fold`, R17), and every reader (`check`, `status`, `debt`,
self-review, the PR body, close-out) reads that fold. The single
`docs/acceptance/matrix.yaml` is retired: `fr migrate artifacts --yes` splits an
old one (R19). An in-flight branch that kept editing it after its base split merges
the base and lets the split run again: rows the fragments lack are carried over,
identical ones dropped, and a row they hold differently refuses by id. Restore or
delete that row in `matrix.yaml`, migrate, then re-apply the edit with
`fr acceptance set-status`. **Any PR that does one of the following updates the rows in the
SAME PR:**

- adds or changes a spec `## Test Plan` (new spec ⇒ new rows; the CI
  staleness guard fails a spec with a Test Plan that no row cites)
- adds tests that verify an existing row (add the ref to `levels`, move
  `status` up: `not-implemented` → `unwired` → `ci`/`scheduled`)
- ships a surface or capability a `not-implemented` row waits on
- changes CI workflows that run matrix-referenced checks
- discovers a red acceptance: set `status: failing` — the
  `acceptance-report` workflow then FAILS by design until it is fixed or
  re-classified with reasoning in `notes`

Statuses move **explicitly, never silently** — and they move with
`fr acceptance set-status`, never a hand-edit: `ci` | `scheduled` (automated
— the safe end) · `walked` (proven live, dated by its latest passing walk —
`set-status --walk … --status walked` is the move after a walk) · `manual` (a
process that is never automatable) · `local` (an automated test anyone can run,
in a repo with no CI — see below) · `unwired` (a test exists, not in CI —
debt) · `walk-owed` (a live or post-merge walk is owed — debt) ·
`not-implemented` (nothing exists — debt) · `failing` (fails CI). The debt set
is `DEBT_STATUSES` (`fr.acceptance.model`); `walked`, `manual` and a fresh
`local` are listed, never debt. The old `skipped` (matrix v4) is refused by name
— `fr migrate artifacts --yes` splits it.

**`local`** (spec `2026-11-14-acceptance-local-status`) is for a repo with no CI
(`fr services` reports `ci none`). Setting it needs at least one level ref naming an
existing test in this repo, and every writer refuses it while the repo has CI (use
`ci`, or `unwired`). `deliver` earns it: it stamps each `local` row the run's
feature added or set, `local: {at, tree, log, files}`, from its fresh local suite log
(no uncommitted code path) or a `tests: reuse`, with the HEAD blob of every file the
row's level refs name, in the resolve's own commit. A `local` row is debt when it has
no stamp (`local, unstamped`), when a stamped file changed or vanished at HEAD or its
level refs moved (`local, stale: <path>`), and once the repo has CI (`local, promote
to ci`). A later run re-earns a stale row by setting it `local` again and delivering.
Under `ci none`, `deliver`'s leftover refusal offers `set-status --status local` first.

## How

- Add rows: `fr acceptance add --id ... --capability ... --acceptance ...
  --origin spec:<slug>#R<n> --level unit=<repo>:<path>#<test> --status ...
  --notes ...` (`add` CREATES; re-adding an existing id is refused, exit 2.)
  The row lands in its origin spec's fragment; a row whose origins name no
  single spec needs `--feature <slug>` (`legacy` for none). fr's own artifacts
  are cited **logically** — `spec:<slug>[#R<n>]`, `plan:<slug>` (R18) — so an
  archive or a placement move never rewrites a row; a spec or plan path given to
  `add` is written in that form. Code and debug journals keep
  `<repo>:<path>[#anchor]`.
- Move a status: `fr acceptance set-status --id ... --status ...
  --notes "<why it moved>" [--level unit=<repo>:<path>]` — the whole
  documented transition in one command: a row still pending on this branch is
  rewritten in place in the fragment that holds it, a row merged on the default
  ref is amended (below); either way it adds the evidence refs and the commit
  holds only that fragment. `--notes`
  is required (a status that moved for no recorded reason is the silent
  change this rule forbids), and an unknown id or status is refused rather
  than created. `--drop-level <level>=<ref>` (repeatable) removes a stale
  evidence ref in the same rewrite — pair it with `--level` to re-point a
  row in one call — and is refused (exit 2, nothing changed) when the ref is
  not on the row or is also named in `--level`. The matrix is a registry of
  CURRENT state, so this mutates;
  its journal counterpart `fr journal resolve` appends instead, because a
  journal is a log.
  The **link-only form** records an issue on a row without touching its status
  or note: `fr acceptance set-status --id ... --issue <owner/repo#n>` (`--notes`
  optional, and then appended to the note with `; `). Without `--status`, any
  flag other than `--id`, `--issue` and `--notes` is refused (exit 2, nothing
  changed); with `--status`, `--notes` stays required and replaces the note.
- **Amend a row an earlier feature merged** (R16). A merged row changes only by
  an amendment appended to YOUR feature's fragment, never in place (`fr acceptance
  check` refuses an in-place edit of a row as it stands on the default ref):
  `fr acceptance amend --id <row> --op <op> --why "<reason>"`, one of `reword`
  (`--acceptance`/`--capability`; `--origin`, repeatable, corrects the origins of a row
  still PENDING on this branch, in place, moving it to the spec its origin names, and is
  refused for a merged row), `set-status` (`--status --notes`, optional
  `--issue`/`--verify`/`--scenario`), `add-level` / `drop-level` (`--level
  <level>=<ref>`) or `retire` (`--notes`). `set-status` on a merged row writes the
  same amendments; a step record's `acceptance:` entry `{row, op, why, …}` (record
  kind 11) is one too. The feature is `--feature <spec-slug>`, else the spec of
  this branch's run; with neither, `set-status` and `amend` both refuse (a
  post-merge walk or issue link names the `--feature` it closes; fr's printed
  commands carry it). Each amendment names its row's revision (`base`, the count of
  amendments applied; default the current one).
- **The stale-base rule** (R17). `fr acceptance check` and `deliver` first fetch
  the default ref (`check --no-fetch` offline; in CI a failed fetch, or a remote with no
  resolvable default ref, is a refusal: check out with `fetch-depth: 0`),
  then refuse, exit 2, a branch amendment whose base another feature's merged
  amendment has passed: review the row, then `fr acceptance amend --rebase`. A
  stale amendment that merged anyway marks its row **contested**, which is debt
  (`fr acceptance status`, `fr debt`, the digest) whatever its status, until the
  next amendment based on its current revision; a retired row a merged amendment
  still names is listed too, as `retired, contested`.
- Anchor a Python ref on the test's NAME, never its line:
  `<repo>:tests/x.py#test_y` or `#TestX::test_y` (pytest's node spelling). A
  `#L<n>` slides onto whatever test lands there next, silently — 27 of this
  matrix's 78 had, by the time gh#531 measured it. `add` / `set-status` refuse
  a new one; `check` fails one, and a name that no longer resolves;
  `fr migrate artifacts --yes` converts existing ones where the line still
  sits in a test.
- Check: `fr acceptance check` (refs, staleness, statuses; exit 2 on
  `failing`). Nag: `fr acceptance status` — **any agent session in this repo
  runs `fr acceptance status --brief` at session start** (Claude Code does it
  automatically via the super-fr SessionStart hook; other harnesses honor
  this line).
- Reports are derived from the fold, never committed: `fr acceptance report
  [--open] [--format md]` renders one locally (`docs/acceptance/report.html` or
  `report.md`, both gitignored), and `fr acceptance check` fails on a tracked
  report file. CI publishes it: a job summary, the report artifact, and the HTML
  on Pages only where `fr acceptance pages-check` shows the site is no wider than
  the repo (a public repo, or access-controlled Pages; it fails closed, and the
  deploy re-checks every time). With `forge.report_comment: on`, `fr acceptance
  comment --pr N --yes` keeps one marker comment on the PR.
- Never hand-edit a fragment: `add` and `set-status` are the writers.
- CI: `.github/workflows/acceptance-report.yml` gates every PR and every push to main,
  writes a Markdown summary to each Actions run (PR, main), uploads the
  GitHub-linked report artifact, and upserts the weekly "Acceptance debt" issue.
