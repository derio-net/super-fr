# Change fragments

A PR that changes user-observable behaviour does **not** edit a version. It adds
one fragment here, and the release workflow on `main` assigns the number
(spec `docs/superpowers/specs/2026-09-26-version-bump-churn-design.md`).

## Format

```yaml
# .changes/<branch-slug>.yaml
bump: minor            # patch | minor | major
summary: one line saying what changed, as it should read in the release notes
```

- `bump` and a non-empty, single-line `summary` are required; any other key is
  refused. `scripts/changes.py` owns the schema.
- **Name it after your branch slug**: `feat/foo` becomes `feat-foo.yaml`, so two
  PRs never share a path.
- **Add** a new fragment. Modifying or deleting an existing one does not satisfy
  the gate — it belongs to the PR that added it, until the release consumes it.

## Never edit a version in a PR

Every version surface (`scripts/version_surfaces.py`) must be byte-for-byte the
base branch's value. `scripts/check-change-fragment.py` (the `change-fragment`
CI job) fails a PR that changes one; the fix is to revert the edit and add a
fragment instead. Do not run `scripts/bump-version.py` on a branch.

A hand-written `fr_version` floor (`>=X.Y.Z,<X.Y.Z` under `packages/*/src`) that
names an unreleased version must name the one this PR predicts: the base version
plus the highest `bump` among the fragments it adds.
