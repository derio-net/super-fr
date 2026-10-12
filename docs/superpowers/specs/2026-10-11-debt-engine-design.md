# One debt engine: `fr debt`, a weekly Technical debt issue, and `skipped` split

**Status:** draft · **Run:** `2026-10-11-feat-batch-debt-engine` · **Issue:** derio-net/super-fr#1121

## Background

Debt is computed in four places and surfaced in none of the places the operator looks.

- **Acceptance.** `.github/workflows/acceptance-report.yml` upserts an "Acceptance debt" issue
  weekly, keyed on the body marker `fr-acceptance-digest` (`fr acceptance digest`,
  `packages/fr/src/fr/commands/acceptance_cmd.py:912`). The upsert is shell in the workflow,
  and so are the scaffolds `fr acceptance init` writes for GitHub, Gitea and GitLab
  (`acceptance/scaffold.py`, goldens in `tests/fixtures/acceptance_scaffold/`). GitLab's and
  Gitea's call `glab api` and `tea` directly. `write_if_missing` (`scaffold.py:472`) never
  updates an existing scaffold. Consumer repos install `fr` from `main` on every run, so
  logic that lives in `fr` reaches them.
- **Plans.** `fr status` already sorts plans into archivable, merged-with-manual-open,
  complete-unmerged and in-progress (`closeout.py:138` `PlanSweep`, `plan_sweep` :173). It
  has no notion of a stale in-progress plan. `fr.archive.merge_evidence(...).complete_on_ref`
  (`archive.py:216`) is the one definition of "merged". It carries no merge date.
- **Triage.** `fr triage collect` reads the forge only (`triage/collect.py:68`) and already
  stores every issue's `body` (`triage/model.py:327`; facts schema 8). The org triages of
  2026-10-10 ranked every "Acceptance debt" issue as a tier-6 tracker. `fr:awaiting-live`
  issues already get their own never-ranked set (`triage/check.py:382`).
- **Owed actions.** A close-out brief says "run the spec's Test Plan" (`run/closeout.py:242`)
  and leaves an unrunnable step to the session. derio-net/frank#835 left step 4 to the
  operator, and only an issue the session happened to file kept it alive. A held plan with an
  unticked `[manual]` phase is visible only through `fr status`. In derio-net/agent-images two
  such plans sat unseen for two months after their PRs merged.

The matrix status `skipped` ("verification exists, not in CI") hides four situations. Of this
repo's 38 `skipped` rows (2026-10-11), 27 carry neither `verify` nor `walks`, so their meaning
lives only in free-text `notes` and cannot be derived. Eight carry `verify: live` with no walk,
and three carry a passing walk.

The relevant kind versions are in `artifacts/registry.py`:

- journal 1, a header stamp, with `JournalKind` a closed Literal (`journal/model.py:28`);
- matrix 4, whose 3→4 hop (`artifacts/matrix_strategies.py:58,90`) validates with the live
  `parse_matrix`;
- record 8, where `record/model.py:29` uses the live `JournalKind` and `record/apply.py:675`
  checks acceptance status against the live `Status`.

Journal resolution records are always `kind=finding` (`journal/model.py:652`), and
`open_finding_ids` (:552) folds every one of them by its `resolves` id.
`fr journal resolve` (`commands/journal_cmd.py:349`) takes `--scope --slug --id --state
--note` and already finds archived journals (:397).

## Requirements

R1. `fr debt` computes a repo's debt as one structured report, available as text and as JSON (`--json`). Every surface that shows acceptance or plan debt renders that report, or the one shared status set it uses, and derives nothing of its own: the digest, `fr acceptance status`, the check's nag, the weekly issue and the triage panel.
R2. The acceptance debt statuses are `not-implemented`, `unwired`, `walk-owed` and `failing`, defined once (`DEBT_STATUSES`). `walked` and `manual` rows are listed with their counts and are not debt, and each `walked` row shows the date of its latest passing walk.
R3. The plans section reports three categories: merged complete but not archived, with the `fr archive` command for each; in progress and stale; and merged with manual phases still open. An in-progress plan that is not stale is not listed.
R4. An in-progress plan is stale when, for N days, neither its plan directory nor its run branch has had a commit and its PR (if any) has had no activity. N defaults to 14 and is set by `stale_days` in `.fr/debt.yaml` or by `--stale-days`. Without the forge (offline, or `tracking: none`), staleness falls back to git alone and the report says so. An unreadable source (such as a matrix still awaiting migration) is reported as unavailable, never as zero.
R5. The matrix status `skipped` is replaced by four statuses: `unwired` (a test exists but does not run in CI), `walk-owed` (a live or post-merge walk is owed), `walked` (proven live, dated by its walk) and `manual` (a process that is never automatable).
R6. A registered matrix migration (kind 4 → 5) moves every existing `skipped` row into exactly one new status using a fixed rule. A row with a passing walk becomes `walked`. Otherwise, a row whose own `verify` names a post-merge strategy becomes `walk-owed`. Otherwise it becomes `unwired`. Rows in other statuses are untouched. A `verify` name that does not resolve leaves the matrix byte-identical, and the migration reports it as that matrix's failure. The migration also regenerates the committed reports, and every older matrix (v1–v4) still migrates to v5.
R7. This PR reclassifies super-fr's own former `skipped` rows by hand wherever the mechanical rule is wrong, each through `fr acceptance set-status` with a note saying why.
R8. Every surface that names or counts `skipped` uses the new statuses:
- the check's nag set, `fr acceptance status` and `fr acceptance summary`;
- the three committed reports and the digest;
- the scaffolded CI comments and the matrix scaffold's comment block;
- the step-record engine's own messages;
- the `fr-acceptance`, `fr-execute` and `fr-progress` skills, the acceptance nag hook, and the acceptance-matrix rule.

A matrix or step record that still says `skipped` is refused by name, with the migrate command as the way forward.
R9. The weekly CI job keeps one open issue per repo titled `<repo>: Technical debt`, with Acceptance, Plans and Owed sections rendered from `fr debt`. The upsert lives in `fr` (`fr debt issue`), not in workflow shell, and works on GitHub, GitLab and Gitea through the forge adapter.
R10. `fr debt issue` finds an existing issue by either the new marker or the legacy `fr-acceptance-digest` marker. It renames a legacy issue to `<repo>: Technical debt` in place, never opens a duplicate, writes the new marker, and closes the issue when the report holds zero debt.
R11. The issue body embeds the report's figures (counts per status and category, the owed count, the generation time) in an encoded block that free text cannot break, so a forge-only reader recovers them without a checkout. The body stays within the forge's size limit, truncating long tables with a pointer to `fr debt`.
R12. When plans have been merged complete and unarchived for longer than the stale threshold, the weekly job opens or refreshes one draft archive PR on the fixed branch `chore/debt-archive-sweep`. It never marks that PR ready and never merges it. It uses the secret `FR_DEBT_TOKEN` when set, and otherwise falls back to the workflow's own token. On that fallback the PR body says CI will not run on the PR until someone pushes. A forge refusal to create the PR is reported by name with both remedies, and it never fails the weekly issue step.
R13. The CI scaffolds for all three forges fetch full history and run `fr debt issue` and `fr debt archive-pr` on the schedule and on a manual dispatch with a `debt` input. `fr acceptance init --refresh-ci` rewrites an existing fr-scaffolded GitHub or Gitea workflow to the current scaffold, and refuses a file it does not recognise as fr's. For GitLab, whose `.gitlab-ci.yml` is shared, it refuses and prints the exact job to paste. This repo's own workflow is updated to match.
R14. `fr triage check` lists debt issues (either marker) in a set of their own, never ranked and never reported as unranked or unplaced, and parses each one's embedded figures from the issue body the facts already hold.
R15. The triage board shows a Debt panel with one line per repo in scope: acceptance debt by status, plan debt by category, the owed count, and a trend against the previous snapshot (for example `not-implemented 28 → 30`). A repo with no debt issue reads "no report", and a legacy digest with no embedded figures reads "legacy digest — no figures". Snapshots store the per-repo figures the trend needs.
R16. `fr:owed` is a new fr label for an operator action that is owed. Triage gives its issues their own never-ranked set, as it does for `fr:awaiting-live`.
R17. Every top-level list item under a spec's `## Test Plan` is a step, numbered by position. A Test Plan section with no list items is one step.
R18. `fr closeout outcome --run <id> --step N[-M]` records one outcome per step, with exactly one of: `--ran --evidence <text>`, `--owed --why <text>` or `--na --reason <text>`. It writes the spec-journal entry `test-plan-step-<n>`: a `discovery` for ran and n/a, and an `owed` entry for owed. A step that already has an outcome is refused.
R19. Every `fr archive` mode holds a plan whose spec has a Test Plan step with no recorded outcome: `--branch`, a plan dir, and the weekly sweep. The hold names each missing step and prints the command that records it, and the close-out brief (`fr pickup --run`) lists the steps with the same commands.
R20. A new journal kind `owed` records an action the operator owes: what is owed, why, how it is completed, and its owed key. It ships with a journal stamp bump (1 → 2), a registered migration and the structure validator. Owed entries fold separately from findings, so an open `owed` entry never fails `fr journal check`.
R21. At archive, every open `owed` entry is filed as one `fr:owed` issue, whatever `--issues` or `--no-issues` say. The issue names the step and the command or check that completes it. Filing is idempotent by the owed key, and the entry records the issue it was filed as. Under `tracking: none` nothing is filed and the journal holds the entry.
R22. When `fr archive` holds a plan because a `[manual]` phase is unticked, it writes one `owed` entry per unticked manual phase into the plan journal and files its `fr:owed` issue, idempotently.
R23. `fr debt` has an Owed section folded from four sources: open `fr:owed` and `fr:awaiting-live` issues, held plans with an unticked manual phase, `walk-owed` acceptance rows, and unresolved `owed` journal entries, archived journals included. Each owed item has one key. The fold deduplicates by key, and an item is counted toward the debt total exactly once.
R24. `fr journal resolve --scope <s> --slug <slug> --id <id> --state fixed --note <evidence>` discharges an `owed` entry, live or archived, which drops it from the Owed section. It closes the entry's filed issue through the forge adapter, and prints the close command instead when the forge cannot be reached. The note is required and is the evidence.
R25. `fr debt` joins `READ_ONLY_COMMANDS`. Its report writes nothing. `issue` writes only to the forge, and only with `--yes`. `archive-pr` previews without `--yes`, and with it acts only through a nested `fr archive`, which the migration gate checks on its own.
R26. The forge adapters gain what R9–R12 and R24 need on every forge that has the operation: editing an issue's title and body, listing open issues with their bodies, creating a draft PR, finding the open PR for a head branch, closing an issue, and a PR's last-activity time. A forge that cannot do one raises the adapter's unsupported error by name.
R27. The step-record kind moves 8 → 9 because records carry `JournalKind` and acceptance `Status`. Its migration rewrites an in-flight record's `status: skipped` by R6's rule.

## Design

### A. The engine — `fr/debt/` (R1–R4, R23, R25)

A new package `packages/fr/src/fr/debt/` has a pure core and thin adapters.

- **`model.py`** defines `DebtReport` (frozen pydantic, `schema: 1`):
  - `acceptance: {by_status, rows, available}`;
  - `plans: {archivable, stale, manual_open}`;
  - `owed: [OwedItem(key, source, title, how, ref)]`;
  - `stale_days`, `sources` (each input: read | unavailable + why), `generated_at`.

  `DEBT_STATUSES` lives in `acceptance/model.py`, beside `Status`, so that
  `acceptance.check.open_rows` and the engine share it.

  `debt_total()` is the one definition of zero debt. It counts acceptance debt rows, plus
  archivable and stale plans, plus owed items whose key does not start `row:` (a `walk-owed`
  row is already counted under acceptance). `manual_open` plans are listed and counted only
  through their owed items.

- **Owed keys.** Every owed item carries one of:
  - `spec:<slug>#step<n>` for a Test Plan step;
  - `plan:<name>#p<n>` for a manual phase;
  - `row:<id>` for a walk-owed row;
  - `issue:<owner/repo#n>` for a labelled issue that carries no fr key.

  An `fr:owed` issue carries its key in a body marker, so the issue, the owed entry and the
  row it stands for fold to one item. When several sources share a key, the journal entry or
  the row wins as the item's source.

- **`engine.py`** provides `compute(repo_root, *, forge, now, stale_days) -> DebtReport`. The
  clock and the forge are passed in, so the engine is tested without either.
  - **Acceptance** comes from `load_matrix`. A refusal (an unmigrated matrix) makes the source
    unavailable, never zero.
  - **Plans** reuse `plan_sweep`. For each in-progress plan, staleness takes the latest of
    `git log -1` on the plan dir across the default ref, `git log -1` on the run branch (from
    its run cursor), and the PR's `updatedAt` from `pr_for_branch`, which gains that field.
  - **Merge age** for archivable plans is the commit date of the last default-ref commit
    touching the plan dir. That commit is when it became complete there, so no forge is
    needed.
  - **Owed** folds R23's four sources.

- **`render.py`** provides three renderers:
  - `text(report)`;
  - `markdown(report)`: sections whose tables truncate at 50 rows each with "… N more — run
    `fr debt`", keeping the body under 60,000 characters. It carries the markers
    `<!-- fr-technical-debt -->` and `<!-- fr-debt-figures:<base64 JSON> -->`. The figures are
    counts, the owed count and `generated_at`, never free text.
  - `parse_figures(body)`, used by triage.

- **`commands/debt_cmd.py`** adds `fr debt` (with `--json`, `--stale-days` and `--offline`),
  `fr debt issue [--yes]` and `fr debt archive-pr [--yes]`.

**Exemption.** `debt` joins `READ_ONLY_COMMANDS` (a diff to the pinned line in
`tests/unit/test_migration_trigger.py`). The gate matches only the top-level subcommand
(`trigger.py:231`), so the exemption covers all three subcommands. That is safe:

- the report and `issue` touch no artifact;
- `archive-pr` mutates artifacts only by running `fr archive` as a subprocess, which the gate
  checks on its own and refuses non-interactively over stale artifacts.

`.fr/debt.yaml` is optional, with one key, `stale_days: <int>`. An unknown key is refused.

The digest, status and summary become thin renderers. `fr acceptance digest` renders
`markdown(report)`'s Acceptance section with the legacy marker, and `fr acceptance status`
and the nag use `DEBT_STATUSES`.

### B. Weekly issue, archive PR and CI (R9–R13, R26)

**Adapters (R26).** `GhClient`, `RealGhRestClient`, glab and tea each gain:

- `edit_issue(repo, number, *, title, body)`;
- `list_open_issues_with_body(repo, *, search)`;
- `create_pr(…, draft=True)`;
- `open_pr_for_head(repo, branch)`;
- `close_issue(repo, number, comment)`.

Each forge implements them through its CLI or REST, as `scaffold.py:318-370` already does for
the upsert in shell. A missing operation raises `UnsupportedForgeOperation`.

**`fr debt issue --yes`** does three things:

1. Compute the report.
2. Find open issues whose body carries `fr-technical-debt` or `fr-acceptance-digest`. With
   several, use the oldest and warn.
3. At zero debt, close the issue with a comment. Otherwise edit its title to
   `<repo>: Technical debt` and its body, or create the issue.

**`fr debt archive-pr --yes`** selects archivable plans whose merge age exceeds `stale_days`.
The floor is deliberate: the batch driver starts a close-out at merge, and a sweep of a
just-merged plan would archive it out from under its own close-out (#660/#664). It then:

1. checks out `chore/debt-archive-sweep` from the default branch;
2. runs `fr archive <plan-dir>` per plan. Plans R19 holds are skipped and listed in the PR
   body as "held: Test Plan outcomes missing" with the command. Owed entries are filed as R21
   says, with the job's token;
3. commits, and force-pushes the bot-owned branch with `--force-with-lease`;
4. opens or refreshes one draft PR whose body lists the plans and the token note.

The token is `FR_DEBT_TOKEN` when set, else the scaffold's forge token. A forge refusal to
create the PR (GitHub's "Allow GitHub Actions to create and approve pull requests" setting is
off by default) prints a `::warning::` naming both remedies and exits 0.

**Scaffolds and this repo's workflow (R13).**

- Checkout uses `fetch-depth: 0`.
- A `workflow_dispatch` input `debt` (boolean) runs the debt steps outside the schedule.
- The weekly steps are `fr debt issue --yes`, then `fr debt archive-pr --yes`.
- GitHub gets `contents: write` and `pull-requests: write`.
- The goldens are regenerated.

**`fr acceptance init --refresh-ci`** recognises GitHub and Gitea files by their
`name: acceptance-report` header plus an `fr acceptance digest` or `fr debt issue` step, and
rewrites them. For GitLab it finds the `acceptance-report:` job in `.gitlab-ci.yml`, refuses
to rewrite the shared file, and prints the current job to paste over it.

**Rollout.** The matrix, journal and record stamps all move, so after release every consumer
repo's CI refuses at `fr acceptance check` until someone runs `fr migrate artifacts --yes`
there. That is standard for a stamp bump, not continuity. The PR body's rollout note lists
it, along with `--refresh-ci`, as owed per consumer repo. The five parked digests (super-fr#363,
blog-craft#41, willikins#288, herdr-vertical-tabs#10, presentation-craft#5) rename themselves
on the first weekly run after both are done.

### C. Triage (R14–R16)

The figures come from `Issue.body`, which is already collected. A digest counts only when a
trusted login opened it: the workflow's bot, the viewer `collect` ran as, or the repo's
`pr_authors`. `pr_authors` is the claim-marker trust set, read from the default branch's
`.fr/triage.yaml`. That is wider than `fr debt issue`'s bot-and-viewer rule, on purpose. A
marker-bearing issue from anyone else is listed as `untrusted_digests`, with its figures
never shown. Judging trust needs the author, so the facts schema moves 8 → 9 with
`Issue.author` and still reads 3–9. A pre-9 facts file has no author, so every digest in it
reads as untrusted until the next collect. Facts are a cache, not an artifact kind, so the
move needs no migration.

- **`check`** parses `parse_figures` at check and render time, and gains two sets:
  `debt_digests`, keyed on either marker, and `owed` (open `fr:owed`). Each has one predicate,
  `is_debt_digest` and `is_owed`, and both are excluded from ranking, unranked and unplaced
  exactly as `is_awaiting_live` is.
- **`render`** adds the Debt panel: one collapsed section per repo (`components.collapsed`).
- **Snapshots** gain `debt: {repo: figures}`. `Snapshot.schema_version` moves 1 → 2, and
  version 1 still reads, as "no trend". The first snapshot after the split shows the one-time
  move from `skipped` to the new statuses as a trend, and the panel says so when the previous
  snapshot predates schema 2.
- **`fr.labels`** gains `FR_OWED`, created on demand like `fr:awaiting-live`.

### D. The `skipped` split (R5–R8, R27)

`Status` becomes `ci | scheduled | unwired | walk-owed | walked | manual | not-implemented |
failing`. A `mode="before"` status validator, modelled on `check_verify`, refuses `skipped`
by name and names `fr migrate artifacts --yes`. Matrix kind 4 → 5 removes a value, so per
`.claude/rules/artifact-versioning.md`:

1. **Freeze `fr.acceptance.legacy.MatrixV4`.** It is a closed superset of v1–v4, with its
   vocabulary (`StatusV4` including `skipped`) inlined and its source pinned.
2. **Point every hop at it.** The 3→4 hop's `_is_v4` and its output check
   (`matrix_strategies.py:58,90`) move from the live `parse_matrix` to `MatrixV4`.
3. **Rewrite once.** The 4→5 rewrite builds the body and the committed reports
   (`render_committed_set`, as `matrix_anchors.py:113` does) in memory, writes everything
   through `write_text_atomic`, and recognises a body already wholly v5.
4. **Map by the row's own `verify`.** `is_post_merge(row.verify, repo_root)` decides; no spec
   or shape default is consulted. A `StrategyError` refuses that matrix byte-identical.
5. **Test the whole chain.** It runs from a v1 matrix carrying `skipped` rows through every
   hop, `[2, 3, 4, 5]`.

The reports replace the "Skipped" panel with one panel per new status. `fr acceptance
set-status --walk … --status walked` is the explicit move after a walk, and the close-out's
awaiting-live lines print that form.

**Record 8 → 9 (R27).** `RecordV8` is frozen with the old kinds and statuses inlined, and the
migration maps an acceptance item's `status: skipped` by R6's rule.

### E. Owed actions (R17–R22, R24)

- **Test Plan steps.** `fr/spec.py` gains `test_plan_steps(text) -> list[Step(n, text)]`:
  top-level `1.`, `-` and `*` items, with continuation lines joined.
- **`fr closeout outcome`** is a new `closeout` group (`commands/closeout_cmd.py`). It
  resolves the run's spec, validates the range, and writes through the journal engine:
  - `discovery` entries for ran and n/a, so they never read as operator decisions;
  - `owed` entries for owed, with body fields `what`, `why`, `how` and `owed_key:
    spec:<slug>#step<n>`.
- **The hold.** `fr.archive.missing_outcomes(repo_root, spec)` is called by every archive
  path before it moves anything. It exits 2 with the commands, and `run/closeout.py`'s brief
  prints the steps.
- **The `owed` kind.**
  - `JournalKind` gains `owed`, and the journal stamp moves 1 → 2 with a stamp-only migration.
  - The fold tells resolution records apart by their target's kind. `open_finding_ids` skips
    ids whose entry is `owed`, and a sibling `open_owed_ids` folds those.
  - `resolve` accepts an `owed` target.
  - `fr journal check` and `render` show open owed entries in their own block. They never
    fail the check.
- **Filing at archive.** `archive_followups.owed_ends()` files open `owed` entries outside the
  `--issues`/`--no-issues` selection.
  - Each issue carries `fr:owed` and `<!-- fr-owed:<owed_key> -->`. An existing open issue
    with that marker is reused.
  - `write_back` appends an `open` resolution record carrying the token `filed_as=<ref>`,
    validated by `TRACKED_BY_RE`, which `open_owed_ids` reads as still owed.
- **Manual phases.** A held `[manual]` phase writes `owed` entry `manual-phase-<n>` (key
  `plan:<name>#p<n>`) into the plan journal before filing.
- **Discharge (R24).** `fr journal resolve --state fixed --note <evidence>` on an `owed`
  entry closes its `filed_as` issue with the note as a comment. It prints the close command
  when the forge is unreachable or `tracking: none` holds. Archived journals already resolve
  (`journal_cmd.py:397`).

### Docs and rules

The following change with this PR:

- `.claude/rules/acceptance-matrix.md`;
- `AGENTS.md`, which gains an `fr/debt` paragraph and corrects facts schema "3" to 8;
- the `fr-acceptance`, `fr-execute` and `fr-progress` skills, with both mirror syncs;
- `plugins/super-fr/hooks/fr-acceptance-nag.sh`;
- `docs/explainers/` pages that name the digest or `skipped`, if any (their `.md` and `.html`
  regenerated, or the regeneration stated as owed).

## Testing

Pre-merge, per requirement group: unit and CLI tests in CI, and candidate scenarios under
`tests/scenarios/`, run by `fr verification walk`.

- **R1–R4, R23, R25:** engine tests over fixture repos (a fake forge and a fixed clock), one
  per plan category, stale and not stale, the offline fallback, an unavailable matrix, and owed
  keys deduplicated across journal, issue and row. Scenario `debt-report.sh` runs `fr debt`
  and `--json` on a fixture repo.
- **R5–R8, R27:** the migration chain from v1 with `skipped` rows, `unwired`/`walk-owed`/
  `walked` mapping, the unresolvable-verify refusal, the companion reports, the crash window,
  the refused-by-name validator, and the record 8→9 hop. Scenario
  `matrix-status-split.sh` migrates a fixture matrix. This repo's own matrix migrates in the PR.
- **R9–R13, R26:** `fr debt issue` against a recording forge double: create, rename a legacy
  issue, refresh, and close at zero. Also the figure round-trip with `-->` in free text, the
  size truncation, `archive-pr` selection with the merge-age floor and held plans, the
  PR-permission refusal, the regenerated goldens, and `--refresh-ci` on all three forges.
- **R14–R16:** check sets, the parse of embedded figures, panel states and trend, snapshot
  v1 reading. The board's Debt panel is captured in a browser for the row's `visual` states.
- **R17–R22, R24:** the Test Plan parser, the outcome verb (ranges, refusals), the hold on
  every archive mode, owed filing ignoring `--no-issues`, idempotence, the manual-phase owed
  entry, and resolve closing the issue. Scenario `closeout-owed.sh` covers a close-out whose
  skipped step is never silently dropped: archive holds, the outcome is recorded owed, and
  archive files the issue.

## Verification

strategy: candidate
- debt-weekly-issue-rename: live — renaming a real legacy issue needs the workflow on `main` against GitHub; no pre-merge strategy reaches it.
- debt-archive-pr-weekly: live — the bot PR and its token behaviour exist only in a real run on `main`.
- forge-adapter-debt-ops: none — CI unit tests against recorded-command doubles for every client verify it (## Testing, R26); a candidate walk has no forge to exercise.
- step-record-status-migration: none — the record 8→9 hop is unit-tested in CI on fixture records (## Testing, R27); no installed-build behaviour differs.
- debt-ci-scaffold-refresh: none — the regenerated goldens and `--refresh-ci` refusals are CI unit tests (## Testing, R13); the scheduled run itself is the two live rows above.
- triage-debt-panel: none — CI render tests cover the sets and panel states, and the phase's browser capture of the `visual` states verifies the board (## Testing, R14–R16).

## Test Plan

Post-merge rows only. The pre-merge walk is set out in `## Verification`.

1. `debt-weekly-issue-rename` (`live`). After `fr migrate artifacts --yes` has landed on `main`, dispatch `acceptance-report.yml` with `debt: true`. The open "Acceptance debt" issue (#363) is renamed `super-fr: Technical debt` in place, and its body carries Acceptance, Plans and Owed sections plus the encoded figures. No second issue is opened.
2. `debt-archive-pr-weekly` (`live`). In the same run, with at least one plan merged complete and unarchived for more than 14 days, one draft PR from `chore/debt-archive-sweep` is opened (or refreshed), or the permission refusal is reported by name. A second dispatch refreshes the PR rather than opening another.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-10-11-debt-engine | `derio-net/super-fr` | `2026-10-11-debt-engine` | — |
