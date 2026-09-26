# Version on merge — implementation plan

Spec: `docs/superpowers/specs/2026-09-26-version-bump-churn-design.md`.

PRs stop choosing version numbers. A PR declares its bump in `.changes/<slug>.yaml`;
`release.yml` on `main` turns pending fragments into one `release: vX.Y.Z` commit, a tag,
and a GitHub Release. Committed acceptance reports stop carrying cross-row content, and
`fr acceptance add` inserts by capability, so row-adding PRs stop colliding.

## Shape

1. **Skeleton** — `scripts/version_surfaces.py`, the one list of every place a version lives
   (now including `uv.lock` member entries); `bump-version.py` reads it. Nothing observable
   changes except `--check` reporting the lock lines.
2. **PR gate** — `changes.py` (fragment schema), `floors.py` (unreleased-floor guard),
   `check-change-fragment.py` replacing `check-version-bump-needed.py`; the CI job is renamed
   `change-fragment`; this PR's own fragment lands here.
3. **Release workflow** — `release.py` + `release.yml`; `auto-tag.yml` goes. The hard phase:
   race recompute, protection-refusal detection, CI-less commit verification, idempotent tag.
4. **Acceptance** — insert-by-capability and an `aggregates` flag on the renderers
   (independent of 2–3, depends only on the skeleton).
5. **Docs/config** — `AGENTS.md`, `HERMES.md`, `.fr/triage.yaml` loses its `version:` block,
   matrix rows move.
6. **[manual]** — the first live bot release after merge (Test Plan item 1).

## Invariant for every phase

**No phase changes a version value.** This PR is the first under the new rules (spec §4): its
own `change-fragment` job must pass rule 2. `bump-version.py --check` stays green throughout.
