# One debt engine: `fr debt`, a weekly Technical debt issue, and `skipped` split

**Status:** draft · **Run:** `2026-10-11-feat-batch-debt-engine` · **Issue:** derio-net/super-fr#1121

## Background

Debt is computed in four places and surfaced in none of the places the operator looks.

- **Acceptance.** `.github/workflows/acceptance-report.yml` upserts an "Acceptance debt" issue
  weekly, keyed on the body marker `fr-acceptance-digest` (`fr acceptance digest`,
  `packages/fr/src/fr/commands/acceptance_cmd.py:912`). The upsert itself is shell in the
  workflow, and the scaffolds `fr acceptance init` writes for GitHub, Gitea and GitLab carry
  the same shell (`packages/fr/src/fr/acceptance/scaffold.py`, goldens in
  `tests/fixtures/acceptance_scaffold/`). `write_if_missing` never updates an existing
  scaffold, so consumer repos keep whatever shell they were born with. They do install `fr`
  from `main` on every run, so logic that lives in `fr` reaches them.
- **Plans.** `fr status` already sorts plans into "merged but not archived", "merged, manual
  phases still open", "complete, unmerged" and "in progress", plus `owed` artifacts and `held`
  specs (`commands/status_cmd.py:_sweep_json`). It has no notion of a stale in-progress plan.
  `fr.archive.merge_evidence(...).complete_on_ref` is the one definition of "merged".
- **Triage.** `fr triage collect` reads the forge only and never checks a repo out
  (`triage/collect.py`, `Forge` protocol). The org triages of 2026-10-10 ranked every
  "Acceptance debt" issue as a tier-6 tracker, where it can be neither batched nor closed.
  `fr:awaiting-live` issues already get their own never-ranked set (`triage/check.py:382`).
- **Owed actions.** A close-out brief says "run the spec's Test Plan"
  (`run/closeout.py:242`). What happens to a step the session cannot run is left to the
  session. derio-net/frank#835 left step 4 to the operator, and only an issue the session
  happened to file kept it alive. A held plan with an unticked `[manual]` phase is visible
  only through `fr status`. In derio-net/agent-images two such plans sat unseen for two
  months after their PRs merged.

The matrix status `skipped` ("verification exists, not in CI") hides four different
situations. Profiling this repo's 38 `skipped` rows (2026-10-11), 27 have neither `verify` nor
`walks`, so their meaning lives only in free-text `notes`. It cannot be derived from fields
that already exist. Eight carry `verify: live` with no walk, and three carry a passing walk.

Journal kinds are a closed vocabulary (`journal/model.py:28`). The `journal` artifact kind is
at version 1, and the matrix at 4 (`artifacts/registry.py`).

## Requirements

R1. `fr debt` computes a repo's debt as one structured report, available as text and as JSON (`--json`), and every other surface in this spec renders that report instead of deriving debt itself.
R2. The acceptance section counts and lists rows by status. `not-implemented`, `unwired`, `walk-owed` and `failing` count as debt. `walked` and `manual` are listed with their counts, and `walked` rows show the date of their latest passing walk. Neither counts as debt.
R3. The plans section reports three categories: merged complete but not archived, with the `fr archive` command for each; in progress and stale; and merged with manual phases still open. An in-progress plan that is not stale is not listed.
R4. An in-progress plan is stale when neither its plan directory nor its run branch has had a commit, and its PR (if any) no activity, for N days. N defaults to 14 and is set by `stale_days` in `.fr/debt.yaml` or by `--stale-days`. Without the forge (offline, or `tracking: none`), staleness falls back to git alone, and the report says so.
R5. The matrix status `skipped` is replaced by four statuses: `unwired` (a test exists but does not run in CI), `walk-owed` (a live or post-merge walk is owed), `walked` (proven live, dated by its walk) and `manual` (a process that is never automatable).
R6. A registered matrix migration (kind 4 → 5) moves every existing `skipped` row into exactly one new status, using a fixed rule: a row with a passing walk becomes `walked`; else a row whose effective strategy is post-merge becomes `walk-owed`; else it becomes `unwired`. Rows in other statuses are untouched.
R7. This PR reclassifies super-fr's own former `skipped` rows by hand, each through `fr acceptance set-status` with a note saying why, wherever the mechanical rule's answer is wrong.
R8. Every fr surface that names or counts `skipped` uses the new statuses: the check's nag set, `fr acceptance status`, the three committed reports, the digest, the scaffolded CI comments, the matrix scaffold's comment block, and the acceptance-matrix rule text. A matrix that still says `skipped` after migration is refused by name, with the way forward.
R9. The weekly CI job keeps one open issue per repo titled `<repo>: Technical debt`, with Acceptance, Plans and Owed sections rendered from `fr debt`. The upsert logic lives in `fr` (`fr debt issue`), not in workflow shell, and works on GitHub, GitLab and Gitea through the forge adapter.
R10. `fr debt issue` finds an existing issue by either the new marker or the legacy `fr-acceptance-digest` marker. It renames a legacy issue to `<repo>: Technical debt` in place and never opens a duplicate. It writes the new marker, and closes the issue when the report holds zero debt.
R11. The issue body embeds the JSON report in a marked HTML comment, so a forge-only reader can recover the figures without a checkout.
R12. When plans have been merged complete but not archived for longer than the stale threshold, the weekly job opens or refreshes one draft archive PR on the fixed branch `chore/debt-archive-sweep`. It never marks that PR ready and never merges it. It uses the secret `FR_DEBT_TOKEN` when set. Otherwise it falls back to the workflow's own token, and the PR body says that CI will not run on the PR until someone pushes to it.
R13. The CI scaffolds for all three forges call `fr debt issue` and `fr debt archive-pr` instead of inline shell. `fr acceptance init --refresh-ci` rewrites an existing fr-scaffolded acceptance workflow to the current scaffold and refuses to touch a file it does not recognise as fr's. This repo's own workflow is updated to match.
R14. `fr triage collect` recognises the debt issue by either marker and parses its embedded report. `fr triage check` lists debt issues in a set of their own, never ranked and never reported as unranked or unplaced.
R15. The triage board shows a Debt panel with one line per repo in scope: acceptance debt by status, plan debt by category, owed count, and a trend against the previous snapshot (for example `not-implemented 28 → 30`). A repo with no debt issue reads "no report". Snapshots store the per-repo figures the trend needs.
R16. `fr:owed` is a new fr label for an operator action that is owed. Triage gives its issues their own never-ranked set, as it does for `fr:awaiting-live`.
R17. Every top-level list item under a spec's `## Test Plan` is a step, numbered by position. A Test Plan section with no list items is one step.
R18. `fr closeout outcome --run <id> --step N[-M]` records one outcome per step, with exactly one of: `--ran --evidence <text>`, `--owed --why <text>` or `--na --reason <text>`. It writes the spec-journal entry `test-plan-step-<n>`: a `decision` for ran and n/a, an `owed` entry for owed. A step that already has an outcome is refused.
R19. `fr archive --branch` holds every close-out whose spec has a Test Plan step with no recorded outcome. It names each missing step and prints the command that records it. The close-out brief (`fr pickup --run`) lists the steps with the same commands.
R20. A new journal kind `owed` records an action the operator owes: what is owed, why, and how it is completed. It ships with a journal stamp bump (1 → 2), a registered migration and the structure validator. An open `owed` entry does not fail `fr journal check`.
R21. At archive, every open `owed` entry is filed as one `fr:owed` issue, whatever `--issues` or `--no-issues` say. The issue names the step and the command or check that completes it. Filing is idempotent by marker, and the entry records the issue it was filed as. Under `tracking: none` nothing is filed and the journal holds the entry.
R22. When `fr archive` holds a plan because a `[manual]` phase is unticked, it also writes one `owed` entry per unticked manual phase into the plan journal and files its `fr:owed` issue, idempotently.
R23. `fr debt` has an Owed section folded from four sources: open `fr:owed` and `fr:awaiting-live` issues, held plans with an unticked manual phase, `walk-owed` acceptance rows, and unresolved `owed` journal entries, archived journals included.
R24. `fr journal resolve <id> --state fixed --evidence <text>` discharges an `owed` entry, in a live or an archived journal, which drops it from the Owed section. It closes the entry's filed issue through the forge adapter, and prints the close command instead when the forge cannot be reached. An `owed` entry cannot be discharged without evidence.
R25. `fr debt` is read-only and joins `READ_ONLY_COMMANDS`, except for `issue` and `archive-pr`. Those write to the forge only with `--yes` and preview otherwise.

## Design

### A. The engine — `fr/debt/` (R1–R4, R23, R25)

A new package `packages/fr/src/fr/debt/`, beside `fr/triage`, split like it into a pure core and
thin adapters:

- `model.py`: `DebtReport` (frozen pydantic, `schema: 1`): `acceptance: {by_status, rows}`,
  `plans: {archivable, stale, manual_open}`, `owed: [OwedItem]`, `stale_days`, `sources`
  (which inputs were read and which were unavailable, never a silent zero), `generated_at`.
  `debt_total()` is the one definition of "zero debt" that R10's close uses.
- `engine.py`: `compute(repo_root, *, forge, now, stale_days) -> DebtReport`. The clock and the
  forge are passed in, so the engine is tested without either.
  - **Acceptance** reads `load_matrix`.
  - **Plans** reuse the `fr status` sweep (`PlanSweep`, `merge_evidence`) for archivable and
    manual-open plans. For each in-progress plan, staleness takes the latest of three
    timestamps: `git log -1` on the plan dir across the default ref, `git log -1` on the run
    branch (from the run cursor, if there is one), and the PR's `updatedAt` through the forge.
  - **Owed** folds R23's four sources.
- `render.py`: `text(report)` for terminal output, `markdown(report)` for the issue body (which
  embeds `<!-- fr-debt:{json} -->` and `<!-- fr-technical-debt -->`), and `parse_embedded(body)`
  for triage. The JSON round-trips through `DebtReport`.
- `commands/debt_cmd.py` registers the `debt` group:
  - `fr debt` (report, `--json`, `--stale-days`, `--offline`);
  - `fr debt issue [--yes]`;
  - `fr debt archive-pr [--yes]`.

`debt` joins `READ_ONLY_COMMANDS` because the report mutates no artifact. That is a diff to
the pinned exemption line in `tests/unit/test_migration_trigger.py`, argued in the PR. `issue`
and `archive-pr` write only to the forge, never to an artifact.

`.fr/debt.yaml` is optional, with one key, `stale_days: <int>`. An unknown key is refused.

### B. The weekly issue and archive PR (R9–R13)

`fr debt issue --yes` runs in this order:

1. Compute the report.
2. Find the open issue whose body carries `fr-technical-debt` or `fr-acceptance-digest`.
   Several matches: use the oldest, and warn.
3. Zero debt: close it with a comment. Otherwise edit its title to `<repo>: Technical debt`
   and its body to the rendered report, or create the issue.

All forge calls go through `fr.hostclient.client_for`. A forge without an edit-title verb
raises the adapter's unsupported error, which the command reports by name.

`fr debt archive-pr --yes` selects the archivable plans whose merge is older than `stale_days`.
The age is deliberate: the batch driver starts a close-out at merge, and a sweep of a just-merged
plan would archive it out from under its own close-out (#660/#664). With none selected it
exits 0. Otherwise it runs four steps:

1. Check out `chore/debt-archive-sweep` from the default branch.
2. Run `fr archive <plan-dir>` per selected plan.
3. Commit and force-push the bot-owned branch with `--force-with-lease`.
4. Open or refresh one draft PR, whose body lists the plans and carries the token note from R12.

The token is `FR_DEBT_TOKEN` when the environment has it, else `GH_TOKEN`/`GITLAB_TOKEN`/
`GITEA_TOKEN` as each scaffold already passes.

The scaffolds' weekly step becomes `fr debt issue --yes` followed by `fr debt archive-pr --yes`,
with `contents: write` and `pull-requests: write` permissions on GitHub. The goldens are
regenerated. `fr acceptance init --refresh-ci` recognises an fr-scaffolded file by its
`name: acceptance-report` header plus the `fr acceptance digest` (legacy) or `fr debt issue`
step, and refuses anything else. `fr acceptance digest` stays, unchanged in behaviour apart
from R8's status names, so un-refreshed consumer workflows keep working until refreshed.

### C. Triage (R14–R16)

`collect` already lists open issues. Any issue whose body carries either marker gets
`Issue.debt_report: DebtReport | None` from `parse_embedded`. A legacy body without JSON gives
`None`, and the panel reads "legacy digest — no figures". `check` gains:

- `debt_digests`: issues with either marker;
- `owed`: open `fr:owed` issues, excluded from ranking, unranked and unplaced exactly as
  `is_awaiting_live` is (one predicate per set, `is_debt_digest` and `is_owed`).

The facts schema moves 3 → 4 (judgements are untouched). `render` adds the Debt panel, a
collapsed section per repo in the existing component style (`components.py`). Snapshots gain
`debt: {repo: figures}`, and `diff` yields the per-figure trend. A snapshot without the key
reads as "no trend".

`fr.labels` gains `FR_OWED = LabelDef("fr:owed", …)`, created on demand like
`fr:awaiting-live`.

### D. The `skipped` split (R5–R8)

`Status = Literal["ci", "scheduled", "unwired", "walk-owed", "walked", "manual",
"not-implemented", "failing"]`. Matrix kind 4 → 5 removes a value, so per
`.claude/rules/artifact-versioning.md` it freezes `fr.acceptance.legacy.MatrixV4`, with its
vocabulary inlined and its source pinned. Every matrix hop reads through it. The rewrite is
built in memory, written once through `write_text_atomic`, and recognises a body already
wholly v5. The mapping is R6's rule, with "post-merge" decided by
`fr.verification.effective.is_post_merge`, never by string compare. A test asserts every hop
`[2, 3, 4, 5]`. `check.open_rows` (the nag set) becomes
`{unwired, walk-owed, not-implemented}`. The reports gain one panel per new status, replacing
the "Skipped" panel. `fr acceptance set-status --walk … --status walked` is the explicit move
for a walked row, and the close-out's awaiting-live lines print that form.

### E. Owed actions (R17–R22, R24)

- **Test Plan parsing** lives in `fr/spec.py`: `test_plan_steps(text) -> list[Step(n, text)]`,
  taking top-level `1.`, `-` and `*` items, with continuation lines joined.
- **`fr closeout outcome`** is a new `closeout` typer group in `commands/closeout_cmd.py`. It
  resolves the run's spec, validates the range against the parsed steps, and writes through
  the journal engine (the same path as `fr journal add`).
  - The outcomes are id-addressed, `test-plan-step-<n>`.
  - `owed` bodies carry `why`, `owner: operator` and the step text.
- **The archive hold.** `fr archive --branch` calls `missing_outcomes(spec, journal)` before it
  moves anything, and exits 2 with the commands. `closeout.py`'s brief prints the steps.
- **The `owed` journal kind.** `JournalKind` gains `owed`, and the journal stamp moves 1 → 2,
  with a stamp-only `SchemaMigration` because no body changes. `fr journal check` folds an
  `owed` entry separately from findings. It never fails the check, and `render` shows it in
  its own block.
- **Filing at archive.** `archive_followups` gains `owed_ends()`: open `owed` entries are
  always filed, outside the `--issues`/`--no-issues` selection. Each issue gets `fr:owed`, and
  `write_back` records `filed_as=<ref>` as a token on a resolution record. A held manual
  phase writes `owed` entry `manual-phase-<n>` into the plan journal before it is filed.
- **Resolving archived journals.** `fr journal resolve` locates the entry under
  `implemented/journals/` when it is not live, but only for `owed` entries. Appending a
  resolution record there is an operational record, not a migration, so the frozen-archive
  rule (no migration rewrites history) is not touched. On `--state fixed` it closes the
  `filed_as` issue through the forge.

### Docs and rules

Several files describe the `skipped` status or the digest, and change with this PR:

- `.claude/rules/acceptance-matrix.md`;
- the matrix scaffold's comment block;
- `AGENTS.md`, which gains an `fr/debt` paragraph;
- `docs/explainers/` pages that name the digest, if any. Their `.md` and `.html` are
  regenerated, or the PR says the regeneration is owed.

`fr-acceptance`'s SKILL.md replaces `skipped` with the four statuses, and both mirror syncs run.

## Verification

strategy: candidate
- debt-weekly-issue-rename: live — renaming a real legacy issue needs the scheduled workflow on `main` against GitHub; no pre-merge strategy reaches the scheduled trigger.
- debt-archive-pr-weekly: live — the bot PR and its token behaviour exist only in a real scheduled run on `main`.

## Test Plan

Post-merge rows only. The pre-merge walk is set out in `## Verification`.

1. `debt-weekly-issue-rename` (`live`). Dispatch `acceptance-report.yml` by hand on `main` with the schedule path enabled (or wait for Monday). The open "Acceptance debt" issue (#363) is renamed `super-fr: Technical debt` in place, its body carries Acceptance, Plans and Owed sections plus the embedded JSON, and no second issue is opened.
2. `debt-archive-pr-weekly` (`live`). In the same run, with at least one plan merged complete and unarchived for more than 14 days, one draft PR from `chore/debt-archive-sweep` is opened (or refreshed) and is not marked ready. A second dispatch refreshes it rather than opening another.
