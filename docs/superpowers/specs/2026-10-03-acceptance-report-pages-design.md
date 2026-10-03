# Publish the acceptance report on GitHub Pages

**Date:** 2026-10-03
**Branch:** `feat/acceptance-report-deployment`

## Background

`.github/workflows/acceptance-report.yml` already renders the acceptance report
on every push, `main` included: its "Build report" step runs
`fr acceptance report --link-mode github --ref "$REF"` and writes the
git-stamped, gitignored `docs/acceptance/report.html`. The only thing that
happens to that file is an `actions/upload-artifact` with a 90-day retention.
Nobody can open it without downloading a zip from an Actions run.

The committed `docs/acceptance/report_linked.html` is a different render. It
comes from `--deterministic`, has no git stamp, and links to `blob/main`. PR
authors regenerate it and `fr acceptance check` keeps it in sync. CI never
writes it.

GitHub Pages allows **one site per repository**, and super-fr's site is already
taken. `.github/workflows/pages.yml` (`Deploy explainers to Pages`) uploads
`docs/explainers/` as the whole Pages artifact on a push to `main` that touches
`docs/explainers/**`. Every Pages deploy **replaces the entire site**. If a
second workflow deployed the report on its own, each deploy would remove the
other's pages.

## Requirements

R1. A push to `main` that touches `docs/explainers/**`, `docs/acceptance/**` or `packages/fr/src/fr/acceptance/**`, and a manual `workflow_dispatch`, redeploy the Pages site to the `github-pages` environment, where the deploy shows up under the repository's Deployments.
R2. The deployed site serves the acceptance report at `/acceptance/` (`https://derio-net.github.io/super-fr/acceptance/`). The deploy job renders it fresh with `fr acceptance report --link-mode github --ref <deployed commit SHA>`, so it is git-stamped and its links point at the deployed commit.
R3. Every explainer page keeps its current URL. One workflow (`pages.yml`) builds a single Pages artifact that holds both the explainers and the report, so neither deploy can remove the other.
R4. The deploy does not depend on the matrix being green. A matrix with `failing` rows is rendered and published as it is.
R5. The explainers landing page (`docs/explainers/index.html`) links to the acceptance report.
R6. `README.md` has a badge that links to the published acceptance report.

## Design

### A. `pages.yml` builds one combined site

`pages.yml` is still the only workflow that deploys to `github-pages`. Its name
stays `Deploy explainers to Pages`, so the `ci-budget.yml` watch-list entry and
the `test_ci_budget.py` coverage of `pages.yml` still apply as they are.

Triggers (R1):

```yaml
on:
  push:
    branches: [main]
    paths:
      - 'docs/explainers/**'
      - 'docs/acceptance/**'
      - 'packages/fr/src/fr/acceptance/**'
  workflow_dispatch:
```

The job steps, in order:

1. `actions/checkout` (pinned, as today).
2. `astral-sh/setup-uv` (pinned to the same SHA as `acceptance-report.yml`).
3. `uv tool install ./packages/fr`. This is the same self-hosting install
   `acceptance-report.yml` uses, so the renderer is always the one in the
   commit being deployed.
4. Assemble: `mkdir -p _site && cp -R docs/explainers/. _site/` (R3).
5. Render (R2): `fr acceptance report --link-mode github --ref "$GITHUB_SHA"
   --out _site/acceptance/index.html`. The `--out` path skips
   `--deterministic`, so the page carries the git stamp. `report` never gates
   on row statuses: a `failing` row renders and the command exits 0 (R4). No
   `fr acceptance check` step goes before the deploy.

   `report` is not exempt from fr's CLI-entry migration gate. In CI, stale
   registered artifacts make it refuse before rendering, and the deploy then
   fails. That is accepted on purpose and is the same behaviour
   `acceptance-report.yml`'s steps have today. Stale artifacts on `main` are
   already a red `validate-artifacts` job, and a report rendered over
   unmigrated artifacts would describe a matrix the shipped `fr` cannot read.
   The step does **not** set `FR_SKIP_MIGRATION`. R4 covers row statuses, not
   artifact staleness.
6. `actions/configure-pages`, then `actions/upload-pages-artifact` with
   `path: _site`, then `actions/deploy-pages`.

The `pages` concurrency group and `cancel-in-progress: true` stay. The
permissions also stay as they are (`contents: read`, `pages: write`,
`id-token: write`).

`_site/` is a directory only the job creates. It is never committed, and
`docs/explainers/` is unchanged, so `test_tripwire_explainers_fresh.py` (its
closed set of source-less pages) does not see it.

### B. Discoverability (R5, R6)

- `docs/explainers/index.html` is hand-authored (explainers-currency rule,
  Known gap 1). It gets one link, added in place in the closing `.foot` row
  (`index.html:577-581`). That row already holds three spans, so the new one
  is the fourth: one new line straight after the `isolation, covered in full →`
  span (line 580), using the same markup,
  `<span><a href="./acceptance/">acceptance coverage &rarr;</a></span>`.
  No other lines change.
- `README.md` gets a fourth badge in its badge row:
  `[![Acceptance](https://img.shields.io/badge/acceptance-report-blue)](https://derio-net.github.io/super-fr/acceptance/)`.
  This is a static badge, because a dynamic count would need a JSON endpoint
  that is out of scope here.

### C. Not changed

`acceptance-report.yml` keeps its artifact upload, because PR runs need it and
PRs never deploy. The committed `report_*` set and its drift gate are
unchanged. No new workflow file is added, so the ci-budget watch-list tripwire
is not affected.

### D. Tests

There is a new unit test file, `tests/unit/test_pages_workflow.py`, which
parses `pages.yml` and pins:

- the three trigger paths and `workflow_dispatch` (R1);
- a render step that runs `fr acceptance report` with `--link-mode github`,
  `--ref` set to the commit SHA, and `--out` under the uploaded directory at
  `acceptance/index.html` (R2);
- the explainers copied into that same uploaded directory, and only one
  `upload-pages-artifact` step (R3);
- no `fr acceptance check` step, and no step condition that depends on one
  (R4).

It also pins the README badge URL (R6) and the `./acceptance/` link in
`index.html` (R5).

A render test goes in `tests/unit/test_acceptance_report.py`, using its
existing `make_repo` + `VK_REPO_ROOT` harness. It runs `fr acceptance report
--link-mode github --ref <sha> --out _site/acceptance/index.html`, with the
repo-relative `--out` CI uses, against a fixture matrix that has a `failing`
row. It checks for exit 0, the file written at `_site/acceptance/index.html`,
`blob/<sha>/` links, and the `(ref <sha>)` git stamp. The stamp proves that
`--out` took the non-deterministic branch (R2, R4).

### E. Acceptance rows

The brainstorm added three rows, which cite this spec's requirements. That
keeps `fr acceptance check`'s staleness guard happy about the Test Plan below.
This means the PR touches `docs/acceptance/matrix.yaml` and the three
committed reports, which is also why its merge triggers the first deploy:

- `pages-acceptance-report-published` (R1, R2, R4), `verify: post-merge`;
- `pages-explainers-preserved` (R3), `verify: post-merge`;
- `pages-acceptance-report-discoverable` (R5, R6).

Implementation adds the §D tests as each row's `unit` level, and moves rows
with `fr acceptance set-status`. The live deploy, Test Plan steps 1-5, stays
owed after merge.

No change fragment is needed: the PR touches only `.github/**`, `docs/**`,
`README.md` and `tests/**`.

## Test Plan

Post-merge, operator-driven:

1. After the merge commit lands, confirm that a `Deploy explainers to Pages`
   run starts (the PR touches `docs/acceptance/**` through its matrix rows, or run it with
   `workflow_dispatch`) and succeeds.
2. Repository → Deployments → `github-pages`: the new deployment is there.
3. Open `https://derio-net.github.io/super-fr/acceptance/`. The report loads,
   its stamp names the merge commit, and a test link resolves to
   `github.com/derio-net/super-fr/blob/<that sha>/…`.
4. Open `https://derio-net.github.io/super-fr/` and
   `…/fr-isolation.html`. Both still load, and the index's new link opens the
   report.
5. The README's Acceptance badge opens the report.
