# Version on merge: PRs declare a bump, main assigns the number

- **Date:** 2026-09-26
- **Status:** designed
- **Origin:** operator request, 2026-09-26 — version conflicts between ready PRs
  fail `version-bump-required` late and churn the version files and the
  acceptance reports
- **Goal:** two PRs that are both ready to merge never conflict because of the
  version or because each added acceptance rows; a PR that only needed a
  version reconciliation never reruns CI for it.

## 1. Problem

A PR that changes shipped behaviour must bump the version (`AGENTS.md`,
"Release / version bumping"; gate: `scripts/check-version-bump-needed.py`,
the `version-bump-required` job). The number is chosen **when the PR is
written**, not when it merges:

1. **Two PRs cut from the same main claim the same number.** Both go from
   4.23.0 to 4.24.0. The second to merge must re-bump, rebase, and rerun the
   full CI suite for a change of zero behaviour.
2. **The number lives in 12 files plus 6 `uv.lock` lines** — the root and five
   member `pyproject.toml`s, two `plugin.json`, `marketplace.json` (two entries),
   `packages/fr-opencode-plugin/package.json`. Every one conflicts.
3. **The conflict surfaces late.** A PR is green, another merges, and only the
   rebase shows the collision.
4. **The workaround is already machinery.** Triage batches (spec
   `2026-09-25-triage-batches-design.md` §3.D/§3.F) reserve version numbers per
   batch at dispatch, re-slot them at merge, and auto-resolve conflicts confined
   to the version files. That treats the symptom for batch-dispatched work
   only; hand-driven PRs still collide.

The acceptance matrix has the same shape of problem on a second surface:

5. **`fr acceptance add` appends at the end of `matrix.yaml`**
   (`fr/acceptance/edit.py::append_row`), so any two PRs adding rows conflict at
   end-of-file, whatever their capability.
6. **All three committed reports carry aggregates** — `243 rows` in the stamp
   and a status-count table (`fr/acceptance/report.py`). Any two PRs that change
   a row count or a status conflict in all three files, even when their rows
   are far apart.

Consolidating the version into one file would shrink problem 2 but leave 1 and
3: a one-line conflict is still a conflict, and still a rerun.

## 2. Decisions (operator, 2026-09-26)

| # | Decision |
|---|---|
| d1 | **Intent in the PR, number on merge.** A PR declares *how much* to bump in a change fragment; the release workflow on `main` assigns the number. PRs never edit a version surface. |
| d2 | Version surfaces are **not** consolidated (no `VERSION` file, no dynamic hatch version). Once PRs stop touching them, only the release bot writes them, and `bump-version.py` already writes all of them. |
| d3 | Acceptance reports are in scope: committed reports drop their aggregates. |
| d4 | No general "version-only diff skips tests" guard. The release commit is pushed with `GITHUB_TOKEN`, which triggers no workflow, so it reruns nothing by construction. |

## 3. Design

### 3.A Change fragments

A PR that needs a release adds one file under `.changes/`:

```yaml
# .changes/<branch-slug>.yaml
bump: minor            # patch | minor | major
summary: fr triage batches — create, dispatch through any run-unit runner, merge in order
```

- One file per PR, named after the branch slug (`feat/foo` → `feat-foo.yaml`),
  so two PRs never share a path. A name clash is an ordinary add/add conflict
  and is the only way fragments can conflict.
- `bump` and a non-empty single-line `summary` are required; any other key is
  refused. `scripts/changes.py` owns the schema (parse, validate, aggregate)
  and is imported by the CI check, the release script, and a unit test over
  the repo's own `.changes/`.
- `.changes/` is super-fr's own release plumbing, **not an fr artifact kind**:
  `fr` never reads it, and it is not shipped to consumer repos. So
  `artifact-versioning` does not apply and nothing is registered in
  `fr.artifacts.registry`.
- `.changes/README.md` explains the format; the directory always exists.

### 3.B PR gate: `version-bump-required` becomes `change-fragment`

`scripts/check-version-bump-needed.py` is replaced by
`scripts/check-change-fragment.py <base-ref>`, run by the renamed CI job.
Two rules:

1. **Bump-required paths need a fragment.** The path classifier
   (`requires_bump`) is kept as it is. If any changed path requires a bump, the
   diff `<base>...HEAD` must **add** at least one valid fragment. Modifying or
   deleting an existing fragment does not count.
2. **PRs never edit a version surface.** If the diff touches any version value
   that `bump-version.py --check` enumerates, the job fails, naming the file.
   This is the structural half of d1: the old habit cannot creep back in and
   reintroduce the conflict. `uv.lock` is checked at the member-version lines
   only, since a dependency change legitimately edits it.

Both failures print the fix (`add .changes/<slug>.yaml with bump: patch`, or
`revert the version edit — main assigns the number`).

The surface list moves out of `bump-version.py` into one importable function
(`version_surfaces()`), used by `bump-version.py`, the gate, and the release
script, so there is exactly one list.

### 3.C Release workflow: `release.yml` replaces `auto-tag.yml`

Runs on `push` to `main` and on `workflow_dispatch` (optional `version` input).
`concurrency: {group: release, cancel-in-progress: false}`.

1. Check out the **tip of `main`** (fetched now, not the event SHA), so a run
   sees every fragment merged before it started.
2. `scripts/release.py`:
   - reads `.changes/*.yaml` (skipping `README.md`); none → step 4.
   - bump = the highest of the pending fragments (major > minor > patch);
     a `workflow_dispatch` `version` input overrides it with an explicit number.
   - runs `bump-version.py <bump>` (this also runs `uv sync`, so `uv.lock` is
     written), `git rm`s the consumed fragments, and commits
     `release: vX.Y.Z` whose body lists every summary, grouped by bump.
   - pushes to `main`. On a non-fast-forward it fetches, resets to the new tip,
     and **recomputes from scratch** (up to 3 attempts). It never rebases its
     own commit: the newer main may have added fragments that belong in this
     release.
3. Floor check (§3.E).
4. Tag and release, **exactly as `auto-tag.yml` does today**: if the
   `pyproject.toml` version has no `v` tag, create an annotated tag and a GitHub
   Release, whose notes are the fragment summaries plus `--generate-notes`.
   Idempotent, so a rerun or a run with no fragments is a no-op.

Two runs back to back are safe: the first consumes every pending fragment;
the second finds none, and step 4 finds the tag.

**Pushing to `main`.** The `protect main` ruleset enforces only `deletion` and
`non_fast_forward` (read 2026-09-26 through `GET
/repos/derio-net/super-fr/rules/branches/main`), so the `GITHUB_TOKEN` with
`contents: write` can fast-forward `main`. **If a required-PR or
required-checks rule is ever added, the release bot needs a bypass actor** —
`release.yml`'s header says so, and so does `AGENTS.md`. `AGENTS.md`'s current
sentence "branch-protection blocks direct commits to `main`" overstates the
ruleset. It is corrected to "the process forbids direct commits; the ruleset
forbids only force-push and deletion".

**No CI on the release commit.** A push made with `GITHUB_TOKEN` triggers no
workflow (d4). The commit only rewrites values that `version-sync` checks, and
`bump-version.py` produced them, so nothing is lost. `pages.yml` and
`acceptance-report.yml` do not run on it either, and they have nothing to
redo.

### 3.D Mid-flight between merge and release

Between a merge and its release commit (about one workflow's startup), `main`
carries new behaviour under the old number. `install.sh` rsyncs into the
version-named cache dir on every run, so an install in that window refreshes
the old number's content and the next install moves to the new one. No
consumer is stranded.

**Known limitation, accepted:** in a PR worktree, `fr --version` and a local
`install.sh` report the last released number while running unreleased code.
This is no worse than today for hand-installed branches (whose "bumped" number
was a guess that collided often), and the AGENTS.md rule "`uv run fr` from the
worktree" still covers artifact-reading correctness.

### 3.E Hand-written `fr_version` floors

Plans carry floors such as `SCOPE_FR_VERSION = ">=4.20.0,<5.0.0"`
(`fr/commands/plan_cmd.py`, and the matching refusal text in `plan_ops.py`).
A PR introducing a floor names the release that first ships its feature. Under
d1 it no longer knows that number, and a guess goes stale silently: PR A guesses
4.24.0, PR B merges first and becomes 4.24.0 without A's feature, and A's floor
now admits an `fr` that lacks it. Three floors were introduced in two months,
so this gets a guard, not a mechanism:

- **PR time** (`check-change-fragment.py`): a floor literal that the diff
  adds or changes must equal `base version + this PR's fragment bump`, the
  predicted number.
- **Release time** (`release.py`, before tagging): every floor literal that
  changed since the previous tag must equal the version being released. On a
  mismatch the release **still tags**, because the number itself is correct,
  and the job then fails and opens an issue naming the floor and the right
  value. Fixing it is a normal patch PR.

Floor literals are found by one regex over `packages/*/src` for
`>=MAJOR.MINOR.PATCH` in a string literal, which is the same inventory the
review of this spec did by hand.

### 3.F Triage batches: super-fr opts out of reservations

The batch engine is unchanged; other repos may still declare a `version:`
block. super-fr's `.fr/triage.yaml` **drops its `version:` block**, so a batch
brief no longer tells a worker to bump to a reserved number, and `batch merge`
has no version files to auto-resolve. The worker follows `AGENTS.md` and adds
a fragment. A batch run then conflicts with another only on real content.

### 3.G `AGENTS.md` and the Hermes rule

"Release / version bumping" is rewritten: which paths need a fragment (the
list is unchanged), the fragment format, "never run `bump-version.py` in a PR",
and the manual `workflow_dispatch` escape for an explicit number. The Hermes
docs test (`tests/unit/test_hermes_docs.py`) pins that the release rule is
inline and names `bump-version.py`; it moves to naming `.changes/`.

### 3.H Acceptance matrix: insert by capability

`fr acceptance add` inserts a new row **after the last row with the same
`capability`**, and appends at the end only for a capability not yet present.
Reports render capabilities in first-seen order and rows in matrix order, so
this changes no rendered order for existing rows. Two PRs now conflict in
`matrix.yaml` only when both add to the same capability or both open a new
one. Row order within a capability is not part of any shape (the parser keys on
`id`), so this is **not** an artifact shape change and bumps no
`current_version`.

### 3.I Committed reports drop aggregates

The **deterministic** renderings, which are the three committed files that
`--deterministic`, `add` and `set-status` write, omit:

- the `N rows` figures in the stamp/meta line, and
- the status-count table (Markdown) and count strip (HTML).

The ad-hoc gitignored `report.html` (`fr acceptance report`, no flag) keeps
both, and so do `fr acceptance summary` (the Actions job summary), `fr
acceptance status` and the weekly digest issue: every place a human actually
reads counts. A committed report is now a pure per-row rendering, so it
conflicts exactly where `matrix.yaml` conflicts. Resolving is always: fix
`matrix.yaml`, run `fr acceptance report --deterministic`, and let `fr
acceptance check` confirm freshness, as today.

This is `fr` behaviour that ships to consumer repos, so the change fragment is
`minor` (§3.A dogfooded). Consumers' committed reports go stale once and are
regenerated by the next `add`/`set-status` or by `report --deterministic`;
`fr acceptance check` already names the fix.

## 4. Rollout (the PR that ships this)

This PR is the first to use the new process, and the last to use the old one:

1. The gate change and `release.yml` land together; `auto-tag.yml` is deleted.
2. This PR adds `.changes/feat-version-bump-churn.yaml` with `bump: minor` and
   **does not edit a version surface**. Its own CI runs the new gate, which
   exercises rule 2.
3. On merge, `release.yml` makes the first bot release, 4.23.0 → 4.24.0. This
   is the live proof in Test Plan item 1.
4. Open PRs that already hand-bumped fail rule 2 on their next push. The fix
   printed is "revert the version edit, add a fragment". That is intended.

## 5. Error handling

- Invalid fragment (bad `bump`, empty or multi-line `summary`, unknown key):
  the PR gate fails naming the file and the field. `release.py` refuses to
  release over it rather than skip it, because a skipped fragment is a silent
  missing changelog line.
- Release push loses the race three times: the job fails, and the next push to
  `main` retries naturally.
- Tag exists but a fragment is still pending (a manual tag): `release.py`
  bumps past the tag. It never re-tags.
- `workflow_dispatch` `version` not above the current one: refused.

## 6. Non-goals

- Consolidating version surfaces into one file (d2).
- A general test-skip guard for version-only diffs (d4).
- Offering change fragments to consumer repos as an `fr` feature. That would
  make it an artifact kind with a registry entry, a validator and migrations.
  Revisit if a consumer asks.
- Removing the triage batch reservation engine. It stays for repos that bump
  in PRs.
- A git merge driver for `matrix.yaml` or the reports. GitHub's "Update
  branch" ignores drivers, and per-clone setup is a new install surface.

## 7. Test Plan

1. **Live: the first bot release.** After this PR merges, `release.yml` commits
   `release: v4.24.0` to `main`, deletes the fragment, pushes the `v4.24.0`
   tag and publishes a Release whose notes contain the fragment summary, and
   no CI run starts for the release commit. Checked by hand on the merge;
   evidence in the close-out.
2. **Unit: fragment schema.** Valid fragments parse; each invalid shape in
   §5 is refused with the field named; the repo's own `.changes/` validates.
3. **Unit: the PR gate.** Table-driven over synthetic diffs: a bump-required
   path with no added fragment fails; with an added fragment passes; a
   modified-only fragment fails; any version-surface edit fails even with a
   fragment; a `uv.lock` dependency-only change passes; a docs-only PR passes.
4. **Unit: `release.py` in a temp git repo.** Several fragments aggregate to
   the highest bump; fragments are removed in the same commit; no fragments and
   the version already tagged is a no-op; a non-fast-forward recomputes and
   includes a fragment that landed meanwhile; the dispatch override refuses
   a non-increasing version.
5. **Unit: floor guard.** A PR adding `>=4.24.0` against base 4.23.0 with a
   minor fragment passes, and with a patch fragment fails; at release, a floor
   naming an already-tagged version is reported.
6. **Unit: acceptance insert-by-capability.** `add` to an existing capability
   lands after its last row; a new capability appends; rendered report order for
   existing rows is unchanged.
7. **Unit: two concurrent row additions merge cleanly.** In a temp repo, two
   branches each `fr acceptance add` a row to a different existing capability
   and regenerate the reports; `git merge` of the second into the first
   conflicts in none of the four files.
8. **Unit: committed reports carry no aggregates.** The deterministic Markdown
   and HTML contain no row count or status-count table; the ad-hoc report and
   `fr acceptance summary` still do.
9. **Unit: one surface list.** `bump-version.py`, the gate and `release.py`
   all read `version_surfaces()`, and a tripwire fails if a **manifest**
   (`pyproject.toml`, `package.json`, `plugin.json`, `marketplace.json`)
   anywhere in the tree carries a `version` key outside it — the `git grep` done
   by hand for §1 item 2, scoped to manifests so test fixtures that quote a
   version do not trip it.

## Implementation Plans

_None yet._
