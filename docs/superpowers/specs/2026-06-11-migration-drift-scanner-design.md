# Migration drift scanner — `fr migrate scan`

**Date:** 2026-06-11
**Status:** Seed spec (not yet approved) — authored from the 2026-05-25
transactional-create/migrator audit follow-ups. Intended to be one-shot with
`/fr-goal`.
**Source audit:** `docs/superpowers/implemented/audits/2026-05-25-transactional-create-migrator-archived-reopen.md`
**Target repo:** derio-net/super-fr (package: `fr`)

## Problem

The three migrator/create bugs (#133, #245, #246) were fixed in code and are
verified present today. But the fixes are forward-only: plans that were already
migrated under the buggy v1→v2 migrator still carry the **damage those bugs
left behind**, scattered across repos (notably `derio-net/frank`, ~71 migrated
plans). The audit's first open follow-up is a read-only cross-repo scan to find
that damage so it can be hand-repaired per finding. There is no tooling for this
today — a manual `grep` sweep is error-prone and not repeatable.

`--force` re-migration is explicitly **not** the remedy: it re-applies the old
bugs and clobbers hand-fixes (e.g. frank#384). The right primitive is a
detector that surfaces exactly which plans/phases carry each fingerprint.

## Requirement

Add a read-only `fr migrate scan` command that walks a repo's plan corpus
(`docs/superpowers/plans/` + `docs/superpowers/implemented/plans/` /
`archived-plans/`) and reports the four damage fingerprints. Read-only: it
mutates nothing, exits 0 with a report, and is safe to run anywhere.

### Fingerprints to detect

1. **Wrong `target_repo` (#245 Bug 1).** A phase/plan `_meta.yaml` whose
   `target_repo` is the plugin's own repo (`derio-net/superpowers-for-vk` or
   `derio-net/super-fr`) when the scanned repo is something else — i.e. the
   silent fallback the migrator used to apply. Report plan + the suspect value.
   *(Note: the repo's own `2026-06-04-plan-pipeline-bugfixes/_meta.yaml` is a
   real in-tree example of this drift.)*

2. **Lost `depends_on` (#245 Bug 2).** A phase whose structured `depends_on` is
   empty **but** whose prose contains a "Blocked by Phase N" construction
   (reuse the migrator's `_BLOCKED_BY_RE` grammar so detection matches recovery).
   Report plan, phase, and the recovered phase numbers.

3. **Dropped task intro / `# manual-operation` block (#245 Bug 3).** A task that
   references a manual-operation block (e.g. prose mentioning a block "above")
   but whose phase YAML has no synthetic leading `S0` step carrying it. Heuristic
   is acceptable; precision over recall — false negatives are fine, loud false
   positives are not.

4. **Possibly-reopened archived Issue (#246).** An archived/implemented plan
   whose tracked Issue is currently OPEN (a closed Issue a prior `vk apply`/buggy
   reconcile may have reopened). Resolve the Issue from the plan's tracking
   metadata; report plan + Issue URL + current state. This check requires `gh`;
   degrade gracefully (skip with an `[info]` note) when `gh` is unavailable or
   the repo has no remote.

### Output

- Human-readable grouped report by fingerprint (default).
- `--json` for machine consumption (each finding: `{fingerprint, plan, phase?,
  detail, path}`).
- Exit 0 always when the scan completes (it is a report, not a gate); reserve
  non-zero for scan errors (unreadable corpus, etc.).
- Scope flags: `--repo-path <dir>` (default cwd), and `--fingerprint <name>` to
  run a single check.

## Non-goals

- **No repair.** The scanner only reports. Repair is per-finding and
  hand-verified, excluding already-hand-fixed plans.
- **No `--force` re-migration.** Out of scope by design.

## The second follow-up: frank re-migration decision

The audit's other open item — "decide whether a curated `--force` re-migration
of frank's plans is worth it" — is an **operational decision, not a feature**.
It cannot be one-shot. The right sequence is: ship this scanner → run it against
`derio-net/frank` → let the finding count inform the decision. This spec
therefore treats the scanner as the deliverable and records the re-migration
decision as a downstream operational step (best delegated to the Frank agent,
per repo ownership), explicitly out of scope for the `/fr-goal` run.

## Testing & verification

- Failing-first tests per fingerprint, using fixture plan corpora under the test
  tree (one clean plan + one carrying each fingerprint).
- The #246 check: stub the `gh`/Issue-state lookup; test both the open-Issue
  finding and the graceful `gh`-absent skip.
- `--json` shape pinned by a test.
- After implementation: full suite green, `ruff`/`mypy` clean; bump version and
  update `CHANGELOG.md`.

## References

- Audit: `docs/superpowers/implemented/audits/2026-05-25-transactional-create-migrator-archived-reopen.md`
  (§"Next steps").
- Migrator code (recovery grammar to reuse): `packages/fr/src/fr/migrate.py`
  (`_BLOCKED_BY_RE`, `_extract_prose_depends_on`, `_find_task_intro`).
- Plan/meta model: `packages/fr/src/fr/plan_ops.py`.
