# Acceptance fragments and derived reports (plan 2 of 3)

Plan 2 of `2026-11-04-repo-feature-settings-design.md` (R29): R16–R22, with
R18's interim repo-only resolution. Acceptance rows move out of the one shared
`docs/acceptance/matrix.yaml` into per-feature fragments under
`docs/acceptance/features/`, the effective matrix becomes a fold over git
history, and the three committed reports stop being committed. Plan 3
(resolver, quiet, stealth, moves) swaps the logical-ref resolver for R1's.

## Phases

1. **Fragments and the fold** (R17, R18 read side; skeleton). The
   `acceptance-fragment` kind and validator, the fragment model (rows plus
   amendments, identity in `repo:`), logical `spec:`/`plan:` refs resolving to
   repo paths, and `fold()`: merged features in default-ref first-parent
   order, then the branch's own pending entries; revisions; contested rows.
   Library only: nothing reads it yet, so the phase cannot break a reader.
2. **Migration and cutover** (R19). A frozen `MatrixV5` reader, a retiring
   schema step (the runner today re-stamps the path it migrated, so a
   migration cannot delete its artifact), the split by origin spec (rows
   without exactly one spec go to `legacy.yaml`), every reader on the fold,
   writers writing fragments, the test-fixture sweep, the nag hooks, and this
   repo migrated with `fr migrate artifacts --yes`.
3. **Amendments** (R16, R17 write side). `fr acceptance amend` with the five
   ops, `set-status` on a merged row becoming an amendment, the record kind's
   amendment shape (10 → 11), the stale-base refusal at `check` and `deliver`
   after fetching the default ref, and contested rows as debt.
4. **Derived reports** (R20–R22). `fr acceptance report --open`, no tracked
   report, CI job summaries and the GitLab exposed artifact, Pages only where
   the forge proves the site no wider than the repo (fail closed, re-checked
   before every deploy), `report_comment`, and this repo's workflows and
   README.

## Why these splits

Each phase is one independently reviewable ask with a row of its own:
`acceptance-effective-matrix-fold` (added at planning: the fold had no row of
its own, R16's row is about amendments), `acceptance-matrix-migration`,
`acceptance-fragments-amendments` and `acceptance-reports-derived-published`.
Phase 1 lands the fold before anything depends on it (risk first); phase 2's
cutover cannot be split from the migration, because moving the matrix kind's
version makes this repo stale until it is migrated; phases 3 and 4 depend only
on phase 2.

## Decisions the spec left to the plan

- **Identity in the fragments.** The matrix's `org`/`repo` moves to a
  required `repo: <org>/<repo>` in every fragment, agreed across fragments,
  so code refs (`<repo>:<path>#<test>`) keep their own-repo check without a
  remote and the identity travels with the artifacts.
- **Logical forms are `spec:` and `plan:` only**, as R18 names them. Origins
  citing debug journals or code keep their path form; such rows go to
  `legacy.yaml`.
- **A merged row is immutable in place**, even in its own feature's fragment
  (a later plan of the same spec shares the fragment): it changes only by
  amendment, which is what gives R17's revision count meaning.
- **Fold order ties** inside one first-parent commit break by feature slug,
  then list index.
- **Shallow history** with amendments present is refused naming
  `fetch-depth: 0`; the scaffolded CI checks out full history.

## Risks

- **The cutover touches ~40 reader sites and ~100 test files.** Phase 2 is
  `hard`, and the fixture sweep goes through one helper so the shape is
  stated once.
- **The retiring step changes the migration runner** every kind relies on;
  it is a new flag, and every existing hop is asserted unchanged.
- **Other open branches** that still edit `matrix.yaml` will need to migrate
  after this merges; their own `fr` does it, and the fragment names are
  stable across archive.
