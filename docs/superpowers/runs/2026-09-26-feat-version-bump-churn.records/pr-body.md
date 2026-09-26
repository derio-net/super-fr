> **Draft — not ready.** Ready checklist (all three before `gh pr ready`):
> - [ ] CI green
> - [ ] explicit review ok from the operator
> - [ ] no commits since that ok (fr's own `chore(fr):` record commits do not count)

## Summary

PRs stop choosing version numbers. A PR that changes shipped behaviour adds a **change fragment**, `.changes/<branch-slug>.yaml` (`bump: patch|minor|major` + a one-line `summary`), and never edits a version. On merge, `release.yml` turns every pending fragment into one `release: vX.Y.Z` commit on `main`, a tag and a GitHub Release. Two ready PRs can no longer collide on the version, and no PR reruns CI just to re-bump.

The acceptance matrix loses its own hotspots: `fr acceptance add` inserts a row after its capability's last row (not at EOF), and the three committed reports drop their cross-row content (row counts, status tiles, sharp-line panels), which lives on in the ad-hoc report, `fr acceptance summary/status` and the digest.

- Spec: `docs/superpowers/specs/2026-09-26-version-bump-churn-design.md`
- Plan: `docs/superpowers/plans/2026-09-26-version-bump-churn/`
- **This PR is the first under the new rules:** it carries `.changes/feat-version-bump-churn.yaml` (`bump: minor`) and edits no version value — its own `change-fragment` job proves gate rule 2 live.

### What changed
- `scripts/version_surfaces.py` — the ONE list of every version location (10 files, 11 values, plus the 6 `uv.lock` member entries, which `version-sync` now checks too).
- `scripts/check-change-fragment.py` (CI job `change-fragment`, replaces `version-bump-required`) — rule 1: bump-required paths need an added valid fragment; rule 2: no changed version value (an added workspace member at the base version is fine); plus an unreleased-`fr_version`-floor guard.
- `scripts/release.py` + `.github/workflows/release.yml` (replace `auto-tag.yml`) — aggregates fragments, bumps, verifies the staged diff is version lines only (and `uv lock --check`) because no CI runs on a `GITHUB_TOKEN` push, recomputes on a lost race, tells a ruleset/protection refusal (GH006/GH013/`[remote rejected]`) from a race, tags idempotently. Dry run on this branch: `would release 4.23.3 -> 4.24.0 (minor)`.
- `fr acceptance`: insert-by-capability; committed reports without aggregates; `status --brief`/digest now order open rows by origin date (file position stopped meaning age).
- `AGENTS.md`, `HERMES.md` rewritten; `.fr/triage.yaml` drops its `version:` block (batch reservations are no longer needed here — the engine is unchanged for other repos).

### Decisions (operator, 2026-09-26)
- d1 intent in the PR, number on merge · d2 no consolidation of version surfaces · d3 acceptance-report conflicts in scope · d4 no general version-only test-skip guard (the release commit triggers no CI by construction).

### Live evidence gathered while building it
Merging `origin/main` mid-run (4.23.0 → 4.23.3, three foreign releases) produced **zero** version conflicts, while `matrix.yaml` and all three reports conflicted on EOF appends — exactly the two halves of this change. The phase 4 concurrent-merge test reproduces that shape red against the old code and merges clean now.

## Operator gates

```
brainstorm: operator gate answered by the operator
```

## Unimplemented — operator pushes to this PR / walks post-merge

Phase 6 `[manual]` — **unimplemented**: after merge, confirm `release.yml` committed `release: v4.24.0`, deleted the fragment, tagged `v4.24.0`, published a Release with the summary, and that no CI run started for the release commit; then move row `release-on-merge` with `fr acceptance set-status`.

## Test Plan (post-merge — operator-driven)

1. **Live: the first bot release.** After this PR merges, `release.yml` commits
   `release: v4.24.0` to `main`, deletes the fragment, pushes the `v4.24.0`
   tag and publishes a Release whose notes contain the fragment summary, and
   no CI run starts for the release commit. Checked by hand on the merge;
   evidence in the close-out.
2. **Unit: fragment schema.** Valid fragments parse; each invalid shape in
   §5 is refused with the field named; the repo's own `.changes/` validates.
3. **Unit: the PR gate.** Table-driven over synthetic diffs: a bump-required
   path with no added fragment fails; with an added fragment passes; a
   modified-only fragment fails; any changed version value fails even with a
   fragment; an added workspace member at the base version passes, at another
   version fails; a `uv.lock` dependency-only change passes; a docs-only PR passes.
4. **Unit: `release.py` in a temp git repo.** Several fragments aggregate to
   the highest bump; fragments are removed in the same commit; no fragments and
   the version already tagged is a no-op; a non-fast-forward recomputes and
   includes a fragment that landed meanwhile; the dispatch override refuses
   a non-increasing version; a pre-existing tag makes it bump past, never
   re-tag; an invalid fragment refuses the release; a protection refusal is
   reported as such, not as a race; three lost races fail; a stale `uv.lock`
   or a staged line outside `version_surfaces()` refuses the commit; a rerun
   reads its notes from the release commit body.
5. **Unit: floor guard.** A PR adding `>=4.24.0,<5.0.0` against base 4.23.0
   with a minor fragment passes, and with a patch fragment fails; a floor at or
   below base passes; reformatting a historical floor and moving an upper bound
   pass; `"demo>=1.0.0"` is not a floor. At release, a lower bound newer than the
   previous tag but not equal to the released version still tags, then fails
   the job and opens an issue.
6. **Unit: acceptance insert-by-capability.** `add` to an existing capability
   lands after its last row; a new capability appends; rendered report order for
   existing rows is unchanged.
7. **Unit: two concurrent row additions merge cleanly.** In a temp repo, two
   branches each `fr acceptance add` a **not-implemented** row (the common case,
   and the one the panels broke) to a different existing capability and
   regenerate the reports; `git merge` of the second into the first conflicts in
   none of the four files.
8. **Unit: committed reports carry no cross-row content.** The deterministic
   Markdown and HTML contain no row count, status-count table or sharp-line
   panel; the ad-hoc report and `fr acceptance summary` still do.
9. **Unit: one surface list.** `bump-version.py`, the gate and `release.py`
   all read `version_surfaces()`, and a tripwire fails if a **manifest**
   (`pyproject.toml`, `package.json`, `plugin.json`, `marketplace.json`)
   anywhere in the tree carries a `version` key outside it — the `git grep` done
   by hand for §1 item 2, scoped to manifests so test fixtures that quote a
   version do not trip it.

## Acceptance

**Rows added since brainstorm (4), each with its defense:**
- `release-on-merge` (not-implemented; unit half in CI) — the whole promise: the number appears on main with nobody touching it. Live walk owed (phase 6).
- `prs-never-conflict-on-version` → ci — the pain reported; the structural refusal keeps hand-bumps from creeping back.
- `version-floor-guard` → ci — the one hazard intent-on-merge introduces: a floor naming a release that shipped without its feature.
- `concurrent-acceptance-rows-merge-clean` → ci — tested by outcome (a real clean `git merge`), not mechanism.

Also moved: `invariants-tripwires` (stays ci) now cites the fragment gate.

**Acceptance debt** (`fr acceptance status`): ci 218 · skipped 23 · not-implemented 10 · scheduled 1 — unchanged by this PR except the rows above.

## Out-of-scope findings to file (asked at merge, never blocking)
All five are listed below by fr. Suggested to file: `rp5-f1` (the bump classifier covers only `plugins/super-fr/{skills,rules}/` while the docs say `plugins/*/skills/**` — inherited; widening it changes which PRs must release) and `rp1-f3` (`write_version`'s table-unaware TOML regex, now the single writer). `p4-unarchived-plans-tripwire` resolved itself once `main` archived those plans (#660); the rest are informational.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

<!-- rendered by fr for run 2026-09-26-feat-version-bump-churn; edit above this line only -->

## Findings

- `sr1-f1` (spec) — HIGH: committed reports still share a status-panel hotspot, so rows added far apart still conflict in the committed reports; Test Plan item 7 would fail — **fixed**
- `sr1-f2` (spec) — HIGH: 'the bot can push to main' was checked against rulesets only; classic branch protection was not checked — **fixed**
- `sr1-f3` (spec) — MEDIUM: tests/unit/test_version_bump_guard.py and matrix row invariants-tripwires both depend on the script this spec deletes — **fixed**
- `sr1-f4` (spec) — MEDIUM: gate rule 2 would refuse adding a new workspace member or plugin manifest — **fixed**
- `sr1-f5` (spec) — MEDIUM: the floor guard's 'any >=X.Y.Z string literal the diff adds or changes' flags historical floors and non-floors — **fixed**
- `sr1-f6` (spec) — MEDIUM: nothing checks that the uv.lock changes in the CI-less release commit are version-only, contrary to d4's rationale — **fixed**
- `sr1-f7` (spec) — MEDIUM: HERMES.md's release and branch-protection rules are not in the rewrite list — **fixed**
- `sr1-f8` (spec) — LOW: §1 says '12 files'; the tree has 10 files carrying 11 values — **fixed**
- `sr1-f9` (spec) — LOW: rule 2 says 'values bump-version.py --check enumerates', but --check does not read uv.lock — **fixed**
- `sr1-f10` (spec) — LOW: release.yml needs issues: write, and the notes source for a tag-only rerun is not defined — **fixed**
- `sr1-f11` (spec) — LOW: the Test Plan misses several promised behaviours, and existing tests pin the aggregates — **fixed**
- `sr1-f12` (spec) — LOW: AGENTS.md's CI job list names version-bump-required — **fixed**
- `rp1-f1` (plan, phase 1) — HIGH: version_surfaces() silently skips a missing marketplace.json / opencode package.json, weakening --check — **fixed**
- `rp1-f2` (plan, phase 1) — MEDIUM: tests re-derive expectations with the module's own globs and member predicate — **fixed**
- `rp2-f1` (plan, phase 2) — MEDIUM: a quoted fragment value followed by a ` #` comment keeps its literal quotes — **fixed**
- `rp3-f1` (plan, phase 3) — MEDIUM: protected-push detection only knew classic GH006 wording, not the GH013 ruleset wording this repo's `protect main` would send — **fixed**
- `rp4-f1` (plan, phase 4) — MEDIUM: matrix.yaml's header comment, and the one `fr acceptance init` scaffolds, still say `add` appends to the end of the file — **fixed**
- `rp4-f2` (plan, phase 4) — MEDIUM: insert-by-capability breaks 'matrix order = age order', which `status --brief` (3 oldest) and the weekly digest rely on — **fixed**

## Out-of-scope findings

- `rp1-f3` (plan, phase 1) — LOW: write_version's TOML rewrite uses a table-unaware first-match regex — **out-of-scope**
- `rp2-f2` (plan, phase 2) — LOW: the change-fragment CI step runs bare `python`, not uv-managed Python — **out-of-scope**
- `p4-unarchived-plans-tripwire` (plan, phase 4) — LOW: test_tripwire_unarchived_plans fails on the merged tree - two plans from origin/main are complete but unarchived (phase 4) — **out-of-scope**
- `rp4-f3` (plan, phase 4) — LOW: committed reports no longer contain row ids (they only appeared in the dropped panels) — **out-of-scope**
- `rp5-f1` (plan, phase 5) — LOW: the gate's requires_bump covers only plugins/super-fr/{skills,rules}/, narrower than the documented plugins/*/skills/** — **out-of-scope**

## Proportionality

```text
proportionality: merge-base fdbe500cb3940be0f8cb40ebdd3be674544b7be1

## Unreferenced new files

none.

## Out-of-plan touches

- packages/fr/src/fr/acceptance/check.py — justified by rp4-f2
- packages/fr/src/fr/acceptance/scaffold.py — justified by rp4-f1

## Size

3508 lines changed (+3183 -325; fr artifacts excluded) against an estimate of 2220 (1.6×).
```

## Cost

| step | turns | cost |
|---|---:|---:|
| brainstorm | 20 | — |
| spec-review | — | — |
| plan | — | — |
| plan-review | — | — |
| implement | — | — |
| journal-check | — | — |
| deliver | — | — |
| (outside run) | 4 | — |
| **total** | | — |

Sessions: 1 read, 0 unavailable.
