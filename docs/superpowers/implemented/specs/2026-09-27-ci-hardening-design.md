# CI hardening: actions pinned by commit SHA, and one `ci-ok` check to require

- **Date:** 2026-09-27
- **Status:** designed
- **Origin:** triage batch `ci-hardening`: super-fr#707 (#703's security scan:
  every workflow pins third-party actions by tag, and `release.yml` pushes to
  `main` with a write token) and super-fr#706 (#703's spec review: `main`
  requires no status checks, and the sharded test contexts are `test (1)` to
  `test (4)`). Both ship in one PR.
- **Goal:** every remote `uses:` in `.github/workflows/` names a full commit
  SHA plus its version in a trailing comment. Dependabot keeps those pins
  current. A tripwire fails CI when a new tag-pinned reference appears. `ci.yml`
  gets one aggregating job, `ci-ok`, whose name a future required-check rule can
  depend on.

## 1. Problem

**Mutable pins (#707).** 34 remote `uses:` references (35 in all, one of them
local) across 8 workflow files name a tag (`actions/checkout@v4`, `astral-sh/setup-uv@v4`, …). A tag is a movable
pointer: whoever controls the action's repo can move `v4` to new code, and the
next run executes it. That code runs with each workflow's token.
`release.yml` has `contents: write` + `issues: write` and pushes the release
commit and tag to `main`. `acceptance-report.yml` and `ci-budget.yml` have
`issues: write`. Pinning by SHA makes the executed code immutable. Without an
update mechanism, though, the pins rot and quietly miss security fixes.

**No stable required-check name (#706).** Since #703, the `test` job is a
4-way matrix, and its check contexts are `test (1)` to `test (4)`. A ruleset
requiring them would have to list four names and change whenever the shard
count changes. There is also a trap here: GitHub treats a required check whose
job was **skipped** as passing. So a naive `needs: test` aggregator gets skipped
when a shard fails, and the rule passes.

## 2. Decisions (operator, 2026-09-27, one question round)

1. **Pin scope: every remote action.** GitHub-owned `actions/*` references are
   pinned too, because their tags are just as mutable. The only exemption is a
   local reusable-workflow reference (`./.github/workflows/…`).
2. **The aggregator gates every CI job and is named `ci-ok`.** It
   aggregates all of `ci.yml`, not just the test shards, so a ruleset needs
   exactly one name for the whole gate. (#706 suggested `test-all`. The
   broader scope makes `ci-ok` the honest name.)
3. **Dependabot: weekly, one grouped PR** for the `github-actions` ecosystem.
4. **Tripwire strictness: a SHA plus a version comment, with the same
   versions.** Each reference must carry a 40-hex SHA **and** a trailing
   `# vX.Y.Z` comment. The pinned commit is the one each current tag points
   to today. There are no upgrades here, only pinning, so behavior is
   byte-for-byte unchanged.
5. (From the brief, not asked) **The `main` ruleset is not touched.** Adding
   `ci-ok` as a required check is the operator's call, and the release bot
   would need a bypass actor on it (AGENTS.md, "Release / version bumping").

## 3. Design

### 3.A SHA pins (`.github/workflows/*.yml`)

Every remote reference becomes `owner/repo@<40-hex sha> # vX.Y.Z`. Each SHA
was resolved on 2026-09-27 through the GitHub API from the tag it replaces:
`git/ref/tags/<tag>`, with annotated tag objects dereferenced to their commit.
The exact version is the highest `vX.Y.Z` tag that dereferences to the **same**
commit, so the comment names the version that actually runs:

| today | commit | comment |
|---|---|---|
| `actions/checkout@v4` | `11d5960a326750d5838078e36cf38b85af677262` | `v4.4.0` |
| `actions/checkout@v7` | `3d3c42e5aac5ba805825da76410c181273ba90b1` | `v7.0.1` |
| `actions/configure-pages@v5` | `983d7736d9b0ae728b81ab479565c72886d7745b` | `v5.0.0` |
| `actions/deploy-pages@v4` | `d6db90164ac5ed86f2b6aed7e0febac5b3c0c03e` | `v4.0.5` |
| `actions/download-artifact@v4` | `d3f86a106a0bac45b974a628896c90dbdf5c8093` | `v4.3.0` |
| `actions/setup-python@v5` | `a26af69be951a213d495a4c3e4e4022e16d87065` | `v5.6.0` |
| `actions/upload-artifact@v4` | `ea165f8d65b6e75b540449e92b4886f43607fa02` | `v4.6.2` |
| `actions/upload-artifact@v7` | `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` | `v7.0.1` |
| `actions/upload-pages-artifact@v3` | `56afc609e74202658d3ffba0e8f6dda462b719fa` | `v3.0.1` |
| `astral-sh/setup-uv@v4` | `38f3f104447c67c051c4a08e39b64a148898af3a` | `v4.2.0` |
| `astral-sh/setup-uv@v5` | `d4b2f3b6ecc6e67c4457f6d3e41ec42d3d0fcb86` | `v5.4.2` |
| `oven-sh/setup-bun@v2` | `0c5077e51419868618aeaa5fe8019c62421857d6` | `v2.2.0` |

The implementing phase **re-resolves every row** before it writes it. If a
tag has moved since this table was written, it stops and records a finding
rather than silently pinning a different commit. The existing version
inconsistencies (`checkout` v4 vs v7, `setup-uv` v4 vs v5,
`upload-artifact` v4 vs v7) stay as they are (decision 4). Unifying them is
an upgrade, and upgrades are what Dependabot now proposes.

### 3.B Dependabot (`.github/dependabot.yml`, new)

```yaml
version: 2
updates:
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
    groups:
      github-actions:
        patterns: ["*"]
```

Dependabot recognizes `@<sha> # vX.Y.Z` and bumps the SHA and the comment
together. `dependabot.yml` is not a workflow file, so the ci-budget watch-list
tripwire does not apply to it. Its PRs touch only `.github/**`, so they need
no change fragment (AGENTS.md).

### 3.C The tripwire (`tests/unit/test_tripwire_actions_pinned.py`, new)

It scans every `.github/workflows/*.yml` **as text**, because comments do not
survive a YAML parse. For each `uses:` value it requires one of:

- a local reference starting with `./` (exempt), or
- `owner/repo[/path]@<exactly 40 lowercase hex>` followed by a
  `# vX.Y.Z` comment (`v\d+\.\d+\.\d+`, exactly three components, per
  decision 4) on the same line.

Anything else fails, naming `file:line` and the offending reference: a tag, a
branch, a short SHA, a missing comment, or `docker://`.
The regex scan must not be something a differently-formatted reference can
slip past, such as a flow-style `{uses: …}` or a quoted value. So the test also
parses each file with `yaml.safe_load` and collects BOTH shapes of `uses`:
job-level `jobs.<id>.uses` (a reusable-workflow call, which has no `steps:`;
the real-repo case is `_pr_spec_status.yml:21`, `uses:
./.github/workflows/fr-spec-status.yml`) and step-level
`jobs.<id>.steps[].uses`. It then asserts that the parsed multiset equals the
scanned multiset.
A second test pins `dependabot.yml`: the `github-actions` ecosystem at `/`, a
weekly interval, and one group covering `*`.

Negative cases run on a temp directory: a tag, a short SHA, a SHA with no
comment, and a flow-style reference all fail, and a local `./` reference
passes. The check is a function taking a directory, as
`test_ci_budget.check_watch_list` does, so the real repo and the fixtures use
the same code path.

### 3.D `ci-ok` (`.github/workflows/ci.yml`)

```yaml
  # One stable check name for a future required-check rule (#706).
  ci-ok:
    if: always()
    needs: [lint, typecheck, test, coverage, validate-artifacts,
            opencode-plugin-test, version-sync, change-fragment]
    runs-on: ubuntu-latest
    steps:
      - name: Every CI job succeeded or was skipped by its own condition
        env:
          RESULTS: ${{ join(needs.*.result, ' ') }}
        run: |
          echo "job results: $RESULTS"
          case " $RESULTS " in
            *" failure "*|*" cancelled "*) exit 1 ;;
          esac
```

- **`if: always()`** is the load-bearing line. Without it, `ci-ok` is
  skipped whenever a dependency fails, and a skipped required check passes
  (§1).
- **`skipped` is accepted** because two jobs skip legitimately:
  `change-fragment` on a push (its `if: github.event_name ==
  'pull_request'`), and `coverage` when `test` failed. In the second case
  `test`'s own `failure` already fails `ci-ok`.
- **`needs` must list every other job in `ci.yml`.** A test pins this as an
  equality: the set of `needs` equals the set of the file's other job ids. A
  job added later without being added to `ci-ok` fails CI at authoring time,
  instead of quietly falling outside the gate.
- The result string reaches the shell through `env`, never through
  `${{ }}` inside `run:`, matching the existing script-injection convention
  (`ci-budget.yml`, `release.yml`).
- `ci-ok` uses no action, so §3.C has nothing to check in it. It adds one
  job start (~5s) after the slowest job. `CI` is already on ci-budget's
  watch-list, and the watcher measures files, not jobs, so no watch-list
  change is needed.

### 3.E What does not change

- `main`'s ruleset (decision 5).
- `packages/fr/src/fr/acceptance/scaffold.py`, which emits an
  `acceptance-report.yml` into **consumer** repos with tag pins (`checkout@v7`,
  `setup-uv@v5`, `upload-artifact@v7`/`@v4`). Other running batches own
  `packages/` source, and the tripwire covers this repo's own workflows only.
  This is filed as a follow-up issue (out of scope, §6).
- Action versions (decision 4).

## 4. Rollout

One PR on `feat/batch-ci-hardening`: `Closes derio-net/super-fr#707` and
`Closes derio-net/super-fr#706`. It changes only `.github/**`, `tests/**` and
`docs/**`, so no change fragment is needed. No explainer describes CI, so
`explainers-currency` is not triggered. The PR's own CI run is the first live
evidence: every pinned action resolves, and `ci-ok` reports as one check.

## 5. Error handling

- **A tag moved between spec and implementation:** re-resolution (§3.A)
  stops and records a finding. Nothing is pinned to an unreviewed commit.
- **A pinned SHA that does not exist:** the run fails at "Set up job"
  (`Unable to resolve action`). The PR's own CI run catches this before
  merge.
- **Dependabot PR with a broken bump:** it is an ordinary PR, CI gates it,
  and it is never auto-merged.

## 6. Non-goals

- Adding `ci-ok` (or anything) as a required check on `main`.
- SHA-pinning the consumer-facing scaffold template (§3.E; follow-up issue).
- Upgrading or unifying action versions.
- Pinning `npm install -g opencode-ai@1.18.32` or `uv tool install` by hash.
  Those are package installs, not `uses:`, and are already exact-version
  pinned.

## 7. Test Plan

1. **Unit (CI):** `test_tripwire_actions_pinned.py`. The real repo's
   workflows pass, every negative fixture fails with `file:line`, the
   parsed set equals the scanned set, and the `dependabot.yml` shape is pinned.
2. **Unit (CI):** `ci-ok`'s shape in `ci.yml`. `if: always()`, `needs`
   equals every other job id, the result check goes through `env`, and it
   exits non-zero on `failure`/`cancelled`.
3. **Branch CI run (pre-merge, observed at `deliver`):** every job starts,
   so every pinned SHA resolved, and the PR's checks list one `ci-ok`
   context, green.
4. **Post-merge (operator-driven):** the repo's Insights → Dependency graph
   → Dependabot tab lists `.github/dependabot.yml` with the `github-actions`
   ecosystem, and the first weekly run either opens one grouped PR or
   reports that everything is up to date.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-27-ci-hardening | `derio-net/super-fr` | `2026-09-27-ci-hardening` | — |
