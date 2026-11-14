"""`fr acceptance init` — scaffold the fragments directory, CI workflow and rule.

Write-if-missing semantics throughout: re-running init never touches a file
the operator (or a previous run) already owns. The one file init edits rather
than creates, `.gitignore`, gets one appended line and no other byte changed.

The CI workflow is scaffolded only for a repo that already has CI for its
backend, or when the caller asks (`--with-ci`) — see `fr.acceptance.ci`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from fr._hosts import HostBackend
from fr.acceptance.fragment import FRAGMENTS_DIR
from fr.artifacts.paths import KIND_DIRS

# Reports are derived, never committed (spec 2026-11-04 R20): `fr acceptance report`
# writes these two, and init keeps git from ever tracking them.
GITIGNORE_LINES = (f"{KIND_DIRS['acceptance']}/report.html", f"{KIND_DIRS['acceptance']}/report.md")

# The retired matrix's header (spec 2026-11-04 R19): no longer written by init, kept
# because the matrix 4 -> 5 hop rewrites an old header's status comment to it.
MATRIX_TEMPLATE = """\
# Acceptance matrix — the registry of business-level acceptance tests and
# where each is verified. Rendered by `fr acceptance report`; {ci_gate}
#
# Row schema:
#   id:         kebab-case, stable
#   capability: grouping (tables render in first-seen order)
#   acceptance: the business-level statement
#   origin:     list of "repo:path[#anchor]" refs (spec §, design doc)
#   levels:     unit/api/int/ui → list of "repo:path[#test_name]" test refs
#               (a .py fragment names a test, pytest-style: #TestX::test_y —
#               never a #L<n> line, which rots as code moves; gh#531)
#               ([] = level does not verify this row)
#   status:     ci | scheduled | unwired | walk-owed | walked | manual
#               | not-implemented | failing
#     ci               automated on every PR — cannot drift silently
#     scheduled        automated on cron/path triggers
#     unwired          a test exists but does not run in CI → debt, CI warning
#     walk-owed        a live or post-merge walk is owed → debt, CI warning
#     walked           proven live, dated by its latest passing walk
#     manual           a process that is never automatable
#     not-implemented  no test or surface exists yet → debt, CI warning
#     failing          known red → `fr acceptance check` exits 2, CI FAILS
#   notes:      evidence detail, drift context
#
# Rule: .claude/rules/acceptance-matrix.md — update rows in the SAME PR that
# changes a Test Plan, adds tests, ships a surface, or touches CI.
# Add rows with `fr acceptance add` (schema-validated). It inserts a row after
# the last row of the same capability, and appends to the end of this file only
# for a new capability — so keep `rows:` as the LAST top-level key.

schema_version: {schema_version}
org: {org}
repo: {repo}
rows:
"""

RULE_TEMPLATE = """\
# Acceptance Matrix — Backfill Rule (repo-wide)

## Rule

The acceptance matrix is the registry of business-level acceptance tests ×
verification levels × automation status. Its rows live in **per-feature
fragments**, `@@ACC_FRAGMENTS@@/<spec-slug>.yaml`: each row is owned by
the feature (spec) that created it, and `legacy.yaml` holds rows with no single
origin spec. The effective matrix is never stored — `fr` folds the fragments.
**Any PR that does one of the following updates the rows in the SAME PR:**

- adds or changes a spec `## Test Plan` (new spec ⇒ new rows; the CI
  staleness guard fails a spec with a Test Plan that no row cites)
- adds tests that verify an existing row (add the ref to `levels`, move
  `status` up: `not-implemented` → `unwired` → `ci`/`scheduled`)
- ships a surface or capability a `not-implemented` row waits on
- changes CI workflows that run matrix-referenced checks
- discovers a red acceptance: set `status: failing` — the
  `acceptance-report` workflow then FAILS by design until it is fixed or
  re-classified with reasoning in `notes`

Statuses move **explicitly, never silently**: `ci` | `scheduled` (automated
— the safe end) · `walked` (proven live, dated by its walk) · `manual` (a
process that is never automatable) · `local` (an automated test anyone can
run, in a repo with no CI) · `unwired` (a test exists, not in CI — debt) ·
`walk-owed` (a live or post-merge walk is owed — debt) · `not-implemented`
(nothing exists — debt) · `failing` (fails CI).

`local` needs a level ref naming an existing test in this repo, and is refused
while the repo has CI. `deliver` earns it: it stamps the row with the suite log
and the HEAD blob of every test file the row names. A `local` row is debt when
it has no stamp (`local, unstamped`), when a stamped file changed
(`local, stale: <path>`), and once the repo has CI (`local, promote to ci`).

## How

- Add rows: `fr acceptance add --id ... --capability ... --acceptance ...
  --origin spec:<slug>#R<n> --level unit=<repo>:<path>#<test> --status ...
  --notes ...` — the row lands in its origin spec's fragment (`--feature` names
  one for a row with no single origin spec). fr artifacts are cited logically
  (`spec:<slug>[#R<n>]`, `plan:<slug>`), so archiving never rewrites a row; code
  keeps `<repo>:<path>[#test]`.
- Move a row: `fr acceptance set-status --id ... --status ... --notes "<why>"`.
  Never hand-edit a fragment.
- Check: `fr acceptance check` (refs, staleness, statuses; exit 2 on
  `failing`). Nag: `fr acceptance status` — **any agent session in this repo
  runs `fr acceptance status --brief` at session start** (Claude Code does it
  automatically via the super-fr SessionStart hook; other harnesses honor
  this line).
- Reports are derived, never committed: `fr acceptance report` renders one
  locally.
{ci_bullet}
"""

WORKFLOW_TEMPLATE = """\
name: acceptance-report

# The acceptance matrix (@@ACC_FRAGMENTS@@/*.yaml, folded) rendered + gated.
# - `failing` rows FAIL this workflow (by design — fix or re-classify).
# - debt rows (`unwired` / `walk-owed` / `not-implemented`) surface as warning
#   annotations; the backfill rule (.claude/rules/acceptance-matrix.md) owns their lifecycle.
# - A Markdown summary is written to each Actions run (branch, PR, main).
# - The built report (GitHub-linked at this ref) is uploaded as an artifact.
@@DEBT_COMMENT@@# Sister-repo refs are not verifiable here (no checkout) — `fr acceptance
# check` warns and verifies them on local runs, where siblings exist.
# If PR-time path filters are added later, they must include every own-repo
# path the matrix references — `fr acceptance check` warns when one falls outside them.

on:
  pull_request: {}
  push:
    branches: ["**"]
  schedule:
    - cron: "47 5 * * 1" # weekly, Monday 05:47 UTC
  workflow_dispatch:

permissions:
  contents: read
@@DEBT_PERMS@@
jobs:
  matrix:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0 # check judges merged rows against the default branch's history
          persist-credentials: false
      - uses: astral-sh/setup-uv@v5
      - name: Install fr
        run: uv tool install "git+https://github.com/derio-net/super-fr@main#subdirectory=packages/fr"
      - name: Check matrix (gate — failing rows fail here)
        run: fr acceptance check
      - name: Write Actions summary (branch / PR / main)
        if: always()
        run: fr acceptance summary >> "$GITHUB_STEP_SUMMARY"
      - name: Build report (GitHub links at this ref)
        env:
          REF: ${{ github.event.pull_request.head.sha || github.sha }}
        run: fr acceptance report --link-mode github --ref "$REF"
      - name: Upload report artifact
        uses: actions/upload-artifact@v7
        with:
          name: acceptance-report
          path: @@ACC_REPORT@@
          retention-days: 90
@@COMMENT_STEP@@@@PAGES_STEP@@@@DEBT_STEP@@"""

# Gitea Actions is deliberately GitHub-Actions-YAML-compatible (per Gitea's
# own docs — "designed to be compatible with GitHub Actions wherever
# possible"), so this reuses WORKFLOW_TEMPLATE's on:/jobs:/steps: shape
# verbatim, swapping only the `gh issue` calls for `tea` equivalents. Two
# real differences: workflows live at `.gitea/workflows/`, NOT
# `.github/workflows/` (confirmed against Gitea's own docs — a common
# mistake since the YAML itself is copy-pasteable); and Actions must be
# enabled per-repo (disabled by default even when instance-enabled) with a
# self-hosted `act_runner` registered — there's no SaaS-hosted default the
# way GitHub/GitLab provide, so this workflow won't just start working the
# way a fresh GitHub/GitLab repo's does.
#
# Known residual gap (out of scope for this template — see the design
# doc's §10): `fr acceptance report --link-mode github` still constructs
# github.com blob URLs for the report's inline source links, since
# `--link-mode` has no gitea/gitlab mode yet. The workflow itself (check +
# report generation + artifact upload) works regardless; only the
# report's cross-links would point at the wrong host.
#
# Trigger shape and the summary step mirror WORKFLOW_TEMPLATE's own
# simplification (path filters dropped — keeping them in sync with the
# matrix was a maintenance burden; runs on every PR/branch push instead).
WORKFLOW_TEMPLATE_GITEA = """\
name: acceptance-report

# The acceptance matrix (@@ACC_FRAGMENTS@@/*.yaml, folded) rendered + gated.
# - `failing` rows FAIL this workflow (by design — fix or re-classify).
# - debt rows (`unwired` / `walk-owed` / `not-implemented`) surface as warning
#   annotations; the backfill rule (.claude/rules/acceptance-matrix.md) owns their lifecycle.
# - A Markdown summary is written to each Actions run (branch, PR, main) —
#   Gitea Actions supports GITHUB_STEP_SUMMARY (aliased GITEA_STEP_SUMMARY,
#   confirmed against Gitea's own Actions-variables docs).
# - The built report is uploaded as an artifact.
@@DEBT_COMMENT@@#
# IMPORTANT: Gitea Actions must be enabled for this repo (Settings ->
# Enable Repository Actions) even if the instance has Actions on globally,
# and needs a self-hosted act_runner registered — there is no SaaS-hosted
# runner the way GitHub/GitLab provide. This file lives at
# .gitea/workflows/, not .github/workflows/. `timeout-minutes` below is
# kept for forward-compat but is currently a no-op — Gitea Actions ignores
# jobs.<job_id>.timeout-minutes (confirmed against Gitea's own
# Compared-to-GitHub-Actions docs).
# Sister-repo refs are not verifiable here (no checkout) — `fr acceptance
# check` warns and verifies them on local runs, where siblings exist.
# If PR-time path filters are added later, they must include every
# own-repo path the matrix references — `fr acceptance check` warns when
# one falls outside them.

on:
  pull_request: {}
  push:
    branches: ["**"]
  schedule:
    - cron: "47 5 * * 1" # weekly, Monday 05:47 UTC
  workflow_dispatch:

jobs:
  matrix:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0 # check judges merged rows against the default branch's history
      - uses: astral-sh/setup-uv@v5
      - name: Install fr
        run: uv tool install "git+https://github.com/derio-net/super-fr@main#subdirectory=packages/fr"
      - name: Check matrix (gate — failing rows fail here)
        run: fr acceptance check
      - name: Write Actions summary (branch / PR / main)
        if: always()
        run: fr acceptance summary >> "$GITHUB_STEP_SUMMARY"
      - name: Build report
        env:
          REF: ${{ gitea.sha }}
        run: fr acceptance report --link-mode github --ref "$REF"
      - name: Upload report artifact
        uses: actions/upload-artifact@v4
        with:
          name: acceptance-report
          path: @@ACC_REPORT@@
          retention-days: 90
@@COMMENT_STEP@@@@PAGES_STEP@@@@DEBT_STEP@@"""

# GitLab CI is a genuinely different schema (stages:/script:, not
# on:/jobs:/steps:) — not a reuse of WORKFLOW_TEMPLATE's shape. Written to
# `.gitlab-ci.yml` at the repo root (GitLab's fixed convention, not a
# configurable directory). Same residual link-mode gap as the Gitea
# template above. GitLab CI also has no generic job-summary feature
# analogous to GITHUB_STEP_SUMMARY (confirmed against GitLab's own
# artifacts:reports docs — every report type is a specific structured
# format: junit, sast, codequality, etc., not an arbitrary Markdown blob),
# so `fr acceptance summary` is only wired into the GitHub/Gitea templates and the
# report is published here as an `artifacts:expose_as` link on the merge request.
WORKFLOW_TEMPLATE_GITLAB = """\
# The acceptance matrix (@@ACC_FRAGMENTS@@/*.yaml, folded) rendered + gated.
# - `failing` rows FAIL this pipeline (by design — fix or re-classify).
# - debt rows (`unwired` / `walk-owed` / `not-implemented`) surface as
#   warnings; the backfill rule (.claude/rules/acceptance-matrix.md) owns their lifecycle.
# - The built report is kept as a pipeline artifact, exposed on the merge request
#   (`expose_as`) — GitLab CI has no job-summary equivalent (see module comment).
@@DEBT_COMMENT@@# Sister-repo refs are not verifiable here (no checkout) — `fr acceptance
# check` warns and verifies them on local runs, where siblings exist.
# If path filters (`rules:changes:`) are added later, they must include
# every own-repo path the matrix references — `fr acceptance check` warns
# when one falls outside them.

stages:
  - acceptance

acceptance-report:
  stage: acceptance
  image: python:3.12
  variables:
    GIT_DEPTH: "0" # check judges merged rows against the default branch's history
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_PIPELINE_SOURCE == "push"
    - if: $CI_PIPELINE_SOURCE == "schedule"
    - if: $CI_PIPELINE_SOURCE == "web"
  before_script:
    - curl -LsSf https://astral.sh/uv/install.sh | sh
    - export PATH="$HOME/.local/bin:$PATH"
    - uv tool install "git+https://github.com/derio-net/super-fr@main#subdirectory=packages/fr"
  script:
    - git fetch origin "+refs/heads/$CI_DEFAULT_BRANCH:refs/remotes/origin/$CI_DEFAULT_BRANCH"
    - fr acceptance check
    - fr acceptance report --link-mode github --ref "$CI_COMMIT_SHA"
  artifacts:
    expose_as: "Acceptance report" # linked from the merge request
    paths:
      - @@ACC_REPORT@@
    expire_in: 90 days
@@PAGES_STEP@@@@DEBT_STEP@@"""


# The R20-R22 publish steps, each a block included only when its condition holds
# (`render_workflow`). Pages: the HTML report on the default branch, behind a visibility
# re-check on EVERY deploy (spec 2026-11-04 R21). A refusal cannot unpublish a site that is
# already live, and the job exists only where Pages were allowed at init, so a later
# refusal means visibility changed: the job fails loudly and names how to unpublish.
# Gitea has no Pages, and neither it nor GitLab can post a PR comment through fr yet
# (`comment_pr` is unsupported on both), so those blocks exist for GitHub alone.
PAGES_STEP_GITHUB = """\

  # Publishes the HTML report on Pages from the default branch. The site must be no wider
  # than the repo (fr, spec R21): visibility is re-read before EVERY deploy. A refusal
  # fails this job loudly (it was scaffolded only where Pages were allowed, so visibility
  # changed) and cannot unpublish a live site: delete it by hand.
  pages:
    if: >-
      github.event_name == 'push' &&
      github.ref == format('refs/heads/{0}', github.event.repository.default_branch)
    needs: matrix
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: read
      pages: write
      id-token: write
    environment:
      name: github-pages
      url: ${{ steps.deploy.outputs.page_url }}
    concurrency:
      group: pages
      cancel-in-progress: false
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0
          persist-credentials: false
      - uses: astral-sh/setup-uv@v5
      - name: Install fr
        run: uv tool install "git+https://github.com/derio-net/super-fr@main#subdirectory=packages/fr"
      - name: Re-check that Pages is no wider than the repo
        id: visibility
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          if fr acceptance pages-check; then
            echo "allowed=true" >> "$GITHUB_OUTPUT"
          else
            echo "allowed=false" >> "$GITHUB_OUTPUT"
            echo "::error::Pages deploy refused: visibility not shown to match the repo."
            echo "A refusal here means visibility changed since this job was scaffolded."
            echo "A skipped deploy does not unpublish a live site: delete the Pages site"
            echo "in the repo settings, or DELETE /repos/$GITHUB_REPOSITORY/pages (admin)."
            exit 1
          fi
      - name: Render the report
        if: steps.visibility.outputs.allowed == 'true'
        run: |
          mkdir -p _site
          fr acceptance report --link-mode github --ref "$GITHUB_SHA" --out _site/index.html
      - uses: actions/configure-pages@v6
        if: steps.visibility.outputs.allowed == 'true'
      - uses: actions/upload-pages-artifact@v5
        if: steps.visibility.outputs.allowed == 'true'
        with:
          path: _site
      - id: deploy
        if: steps.visibility.outputs.allowed == 'true'
        uses: actions/deploy-pages@v5
"""
PAGES_STEP_GITLAB = """\

# The HTML report on Pages from the default branch. The site must be no wider than the
# repo (fr, spec R21): visibility is re-read before EVERY deploy. A refusal fails the job
# loudly (it was scaffolded only where Pages were allowed, so visibility changed) and
# cannot unpublish a live site. The check reads the forge, so it needs a token: create a
# masked CI/CD variable FR_PAGES_TOKEN with the read_api scope.
pages:
  stage: acceptance
  image: python:3.12
  needs: [acceptance-report]
  variables:
    GIT_DEPTH: "0"
    GITLAB_TOKEN: $FR_PAGES_TOKEN
  rules:
    - if: $CI_PIPELINE_SOURCE == "push" && $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
  before_script:
    - curl -LsSf https://astral.sh/uv/install.sh | sh
    - export PATH="$HOME/.local/bin:$PATH"
    - uv tool install "git+https://github.com/derio-net/super-fr@main#subdirectory=packages/fr"
  script:
    - |
      fr acceptance pages-check || {
        echo "Pages deploy refused: visibility not shown to match the repo."
        echo "A skipped deploy does not unpublish a live site: remove Pages in the"
        echo "project settings (Deploy > Pages) by hand."
        exit 1
      }
    - mkdir -p public
    - fr acceptance report --link-mode github --ref "$CI_COMMIT_SHA" --out public/index.html
  artifacts:
    paths:
      - public
"""
PAGES_STEP = {"github-actions": PAGES_STEP_GITHUB, "gitlab-ci": PAGES_STEP_GITLAB}
COMMENT_STEP_GITHUB = """\

  # Keeps ONE comment on the PR carrying the Markdown report (forge.report_comment: on).
  # Its own job: posting needs pull-requests: write, which the matrix job (it runs on
  # every PR) does not hold. Same-repo PRs only; a fork's token is read-only.
  report-comment:
    if: >-
      github.event_name == 'pull_request' &&
      github.event.pull_request.head.repo.full_name == github.repository
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0
          persist-credentials: false
      - uses: astral-sh/setup-uv@v5
      - name: Install fr
        run: uv tool install "git+https://github.com/derio-net/super-fr@main#subdirectory=packages/fr"
      - name: Upsert the report comment
        env:
          GH_TOKEN: ${{ github.token }}
        run: fr acceptance comment --pr "${{ github.event.pull_request.number }}" --yes
"""
COMMENT_STEP = {"github-actions": COMMENT_STEP_GITHUB}


# The weekly technical-debt steps, split out of each template so they are
# included only when the tracker is the ci type's own platform (#774 §3.E): the
# steps file through that platform's CLI with the pipeline's own credentials.
# `fr debt issue --yes` keeps the one `<repo>: Technical debt` issue and
# `fr debt archive-pr --yes` the one draft archive PR (spec 2026-10-11-debt-engine
# R9-R13); both run on the schedule and on a manual dispatch with `debt: true`.
_DEBT_COMMENT_ACTIONS = (
    '# - The weekly run (and a dispatch with `debt`) upserts one "<repo>: Technical debt"\n'
    "#   issue (closed at zero debt) and refreshes a draft PR archiving long-merged plans.\n"
)
DEBT_COMMENT = {
    "github-actions": _DEBT_COMMENT_ACTIONS,
    "gitea-actions": _DEBT_COMMENT_ACTIONS,
    "gitlab-ci": '# - The weekly (scheduled) run upserts one "<repo>: Technical debt" issue and\n'
    "#   refreshes a draft PR archiving long-merged plans.\n",
}
DEBT_STEP_GITHUB = """\

  # The debt job holds the write permissions and the dedicated token; the matrix
  # job above (which runs this repo's code on every PR) holds neither. It does not
  # `needs:` the matrix, so a week with failing rows still updates the issue.
  debt:
    if: github.event_name == 'schedule' || inputs.debt
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: write
      issues: write
      pull-requests: write
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0
          token: ${{ secrets.FR_DEBT_TOKEN || github.token }}
      - uses: astral-sh/setup-uv@v5
      - name: Install fr
        run: uv tool install "git+https://github.com/derio-net/super-fr@main#subdirectory=packages/fr"
      - name: Technical debt issue (weekly)
        env:
          GH_TOKEN: ${{ github.token }}
        run: fr debt issue --yes
      - name: Archive sweep PR (weekly)
        env:
          GH_TOKEN: ${{ github.token }}
          FR_DEBT_TOKEN: ${{ secrets.FR_DEBT_TOKEN }}
        run: fr debt archive-pr --yes
"""
DEBT_STEP_GITEA = """\

  debt:
    if: gitea.event_name == 'schedule' || inputs.debt
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: astral-sh/setup-uv@v5
      - name: Install fr
        run: uv tool install "git+https://github.com/derio-net/super-fr@main#subdirectory=packages/fr"
      - name: Technical debt issue (weekly)
        run: fr debt issue --yes
      - name: Archive sweep PR (weekly)
        env:
          FR_DEBT_TOKEN: ${{ secrets.FR_DEBT_TOKEN }}
        run: fr debt archive-pr --yes
"""
DEBT_STEP_GITLAB = """\

# Its own job, so a failing `fr acceptance check` above never skips the debt run.
technical-debt:
  stage: acceptance
  image: python:3.12
  variables:
    GIT_DEPTH: "0"
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
    - if: $CI_PIPELINE_SOURCE == "web" && $DEBT == "true"
  before_script:
    - curl -LsSf https://astral.sh/uv/install.sh | sh
    - export PATH="$HOME/.local/bin:$PATH"
    - uv tool install "git+https://github.com/derio-net/super-fr@main#subdirectory=packages/fr"
  script:
    - fr debt issue --yes
    - fr debt archive-pr --yes
"""
DEBT_STEP = {
    "github-actions": DEBT_STEP_GITHUB,
    "gitea-actions": DEBT_STEP_GITEA,
    "gitlab-ci": DEBT_STEP_GITLAB,
}


def _render_paths(template: str) -> str:
    """Fill the artifact directories a template names from the path resolver, so the
    rendered file is the `repo` layout's text and moves with the table (spec R1)."""
    return template.replace("@@ACC_FRAGMENTS@@", KIND_DIRS["acceptance-fragment"]).replace(
        "@@ACC_REPORT@@", f"{KIND_DIRS['acceptance']}/report.html"
    )


RULE_TEMPLATE = _render_paths(RULE_TEMPLATE)
WORKFLOW_TEMPLATE = _render_paths(WORKFLOW_TEMPLATE)
WORKFLOW_TEMPLATE_GITEA = _render_paths(WORKFLOW_TEMPLATE_GITEA)
WORKFLOW_TEMPLATE_GITLAB = _render_paths(WORKFLOW_TEMPLATE_GITLAB)

WORKFLOW_TEMPLATES = {
    "github-actions": WORKFLOW_TEMPLATE,
    "gitea-actions": WORKFLOW_TEMPLATE_GITEA,
    "gitlab-ci": WORKFLOW_TEMPLATE_GITLAB,
}


_DISPATCH = "  workflow_dispatch:\n"
_DISPATCH_DEBT = (
    "  workflow_dispatch:\n    inputs:\n      debt:\n"
    "        description: Run the technical-debt steps now\n"
    "        type: boolean\n        default: false\n"
)


def render_workflow(ci_type: str, *, debt: bool, pages: bool = False, comment: bool = False) -> str:
    """The scaffolded pipeline for `ci_type`, with or without the debt job (and
    the `debt` dispatch input only it reads), the Pages job and the PR report-comment
    job. The write permissions and the dedicated token live on the debt job alone; the
    comment job holds `pull-requests: write` alone."""
    text = WORKFLOW_TEMPLATES[ci_type]
    if debt and ci_type != "gitlab-ci":
        text = text.replace(_DISPATCH, _DISPATCH_DEBT)
    return (
        text.replace("@@DEBT_PERMS@@", "")
        .replace("@@DEBT_COMMENT@@", DEBT_COMMENT[ci_type] if debt else "")
        .replace("@@COMMENT_STEP@@", COMMENT_STEP.get(ci_type, "") if comment else "")
        .replace("@@PAGES_STEP@@", PAGES_STEP.get(ci_type, "") if pages else "")
        .replace("@@DEBT_STEP@@", DEBT_STEP[ci_type] if debt else "")
    )


@dataclass(frozen=True)
class PublishPlan:
    """What the scaffolded CI publishes (R20-R22): the Pages job, the PR comment job,
    and the notices for whatever was asked for and left out."""

    pages: bool = False
    comment: bool = False
    notices: tuple[str, ...] = ()


def publish_plan(
    root: Path, ci_type: str, pages_decision: tuple[bool, str] | None = None
) -> PublishPlan:
    """Decide the publish steps for `ci_type`. `pages_decision` is `pages_allowed`'s
    answer (None: not asked, which is not allowed: Pages fail closed). The comment job
    needs `forge.report_comment: on` and `forge.comments: on`, and a forge client fr
    can post through (GitHub today)."""
    from fr.settings import load_settings

    notices: list[str] = []
    pages = False
    if ci_type in PAGES_STEP:
        allowed, why = pages_decision if pages_decision is not None else (False, "")
        pages = allowed
        if pages_decision is not None and not allowed:
            notices.append(f"no Pages  {why}; the README badge points at the CI run instead")
        if allowed and ci_type == "gitlab-ci":
            notices.append(
                "Pages  create a masked CI/CD variable FR_PAGES_TOKEN (read_api scope) for the "
                "pages job; a self-managed host also needs glab authenticated in the job's image"
            )
    forge = load_settings(root).settings.forge
    comment = False
    if forge.report_comment == "on":
        if forge.comments != "on":
            notices.append("no report comment  forge.comments: off; see `fr settings show`")
        elif ci_type not in COMMENT_STEP:
            notices.append(f"no report comment  fr cannot post a PR comment on {ci_type} yet")
        else:
            comment = True
    return PublishPlan(pages=pages, comment=comment, notices=tuple(notices))


BADGE_OPEN = "<!-- fr:acceptance-badge -->"
BADGE_CLOSE = "<!-- /fr:acceptance-badge -->"


def _web_base(root: Path) -> tuple[str, str] | None:
    from fr._hosts import origin_hostname, origin_slug

    host, slug = origin_hostname(root), origin_slug(root)
    return (host, slug) if host and slug else None


def badge_line(root: Path, ci_type: str, *, pages: bool) -> str | None:
    """The README line: the report's Pages site when one is published, else the latest
    default-branch CI run (R21). None without an origin to name."""
    from fr.acceptance.amend import default_ref_name

    where = _web_base(root)
    if where is None:
        return None
    host, slug = where
    branch = (default_ref_name(root) or "origin/main").removeprefix("origin/")
    owner, _, name = slug.partition("/")
    if pages and ci_type == "github-actions" and host == "github.com" and "/" not in name:
        return f"[Acceptance report](https://{owner}.github.io/{name}/)"
    if pages and ci_type == "gitlab-ci" and host == "gitlab.com" and "/" not in name:
        return f"[Acceptance report](https://{owner}.gitlab.io/{name}/)"
    base = f"https://{host}/{slug}"
    if ci_type == "gitlab-ci":
        return f"[![acceptance]({base}/badges/{branch}/pipeline.svg)]({base}/-/pipelines/latest)"
    workflow = f"{base}/actions/workflows/acceptance-report.yml"
    return (
        f"[![acceptance]({workflow}/badge.svg?branch={branch})]({workflow}?query=branch%3A{branch})"
    )


def write_badge(root: Path, line: str) -> str:
    """Put `line` between the badge markers of `README.md`: `created` (markers added after
    the first heading), `modified` (the span between existing markers replaced),
    `current` (already that) or `no-readme` (no README.md: none is created). Idempotent."""
    readme = root / "README.md"
    if not readme.is_file():
        return "no-readme"
    text = readme.read_text()
    block = f"{BADGE_OPEN}\n{line}\n{BADGE_CLOSE}"
    if BADGE_OPEN in text and BADGE_CLOSE in text.split(BADGE_OPEN, 1)[1]:
        head, rest = text.split(BADGE_OPEN, 1)
        _, tail = rest.split(BADGE_CLOSE, 1)
        new, status = head + block + tail, "modified"
    else:
        lines = text.split("\n")
        at = next((i + 1 for i, ln in enumerate(lines) if ln.startswith("# ")), 0)
        lines[at:at] = ["", block]
        new, status = "\n".join(lines), "created"
    if new == text:
        return "current"
    readme.write_text(new)
    return status


def debt_steps(root: Path, ci_type: str, tracking_type: str | None) -> tuple[bool, str | None]:
    """`(debt, off)`: whether the scaffolded `ci_type` pipeline carries the weekly
    technical-debt job, and, when the repo's settings dropped it, why. The job files
    through the ci platform's own tracker CLI, so it needs that tracker (#774 §3.E), and
    it writes an issue and a PR, so it needs forge issues on (spec
    2026-11-04-repo-feature-settings R9: no forge write of an off kind, including from
    the CI fr scaffolds). An unreadable policy refuses (`SettingsError`)."""
    from fr.acceptance.ci import DEBT_PLATFORM
    from fr.settings import load_settings

    if tracking_type != DEBT_PLATFORM[ci_type]:
        return False, None
    if load_settings(root).settings.forge.issues != "on":
        return False, "forge.issues: off — the weekly technical-debt steps are omitted"
    return True, None


@dataclass(frozen=True)
class RefreshOutcome:
    """What `fr acceptance init --refresh-ci` did, or why it did not."""

    status: str  # rewritten | current | foreign | missing | paste
    path: str
    text: str = ""
    """For `paste` (GitLab): the exact job to paste over the existing one."""


_FR_STEP = re.compile(r"fr acceptance digest|fr debt issue")


def refresh_ci(
    root: Path,
    ci_type: str,
    *,
    debt: bool,
    pages: bool = False,
    comment: bool = False,
) -> RefreshOutcome:
    """Bring an fr-scaffolded pipeline up to the current scaffold (R13).

    GitHub and Gitea files are recognised by their `name: acceptance-report`
    header plus an `fr acceptance digest` or `fr debt issue` step, and rewritten
    whole; a file without both is someone else's and is never touched. GitLab's
    `.gitlab-ci.yml` is shared by every job in the repo, so it is never
    rewritten: the current job is returned to paste."""
    from fr.acceptance.ci import SCAFFOLD_PATHS

    rel = SCAFFOLD_PATHS[ci_type]
    path = root / rel
    if not path.is_file():
        return RefreshOutcome("missing", rel)
    current = path.read_text()
    fresh = render_workflow(ci_type, debt=debt, pages=pages, comment=comment)
    if ci_type == "gitlab-ci":
        if not re.search(r"^acceptance-report:\s*$", current, re.MULTILINE):
            return RefreshOutcome("foreign", rel)
        job = fresh[fresh.index("acceptance-report:") :]
        return RefreshOutcome("paste", rel, job)
    if not re.search(
        r"^name:\s*acceptance-report\s*$", current, re.MULTILINE
    ) or not _FR_STEP.search(current):
        return RefreshOutcome("foreign", rel)
    if current == fresh:
        return RefreshOutcome("current", rel)
    path.write_text(fresh)
    return RefreshOutcome("rewritten", rel)


# The rule's CI bullet. GitHub's wording is the one every GitHub repo was
# scaffolded with, kept byte-for-byte.
_CI_BULLET_GITHUB = """\
- CI: `.github/workflows/acceptance-report.yml` gates every PR and branch push,
  writes a Markdown summary to each Actions run (branch, PR, main), uploads the
  GitHub-linked report artifact{debt}."""
_CI_BULLET = """\
- CI: the acceptance job in `{path}` runs `fr acceptance check` on every
  pipeline{debt}."""
_DEBT_TAIL_GITHUB = ', and upserts the weekly "Technical debt" issue'
_DEBT_TAIL = ' and upserts the weekly "Technical debt" issue'
_NO_CI_BULLET = """\
- CI: none is configured. `fr acceptance check` runs locally, and no row may
  move to `ci` until the repo has a CI config (`fr acceptance init --with-ci`
  scaffolds one)."""


@dataclass(frozen=True)
class InitOutcome:
    created: list[str]
    skipped: list[str]
    notices: list[str] = field(default_factory=list)
    # Existing files init edited rather than created — today only `.gitignore`'s
    # appended line (gh#775: it used to be reported as "created").
    modified: list[str] = field(default_factory=list)

    @property
    def written(self) -> list[str]:
        """Every path this run changed — what `fr acceptance init` commits."""
        return [*self.created, *self.modified]


def _append_gitignore_line(path: Path, line: str) -> bool:
    """Append `line` to `path` unless it already lists it. True when written.

    Append-only and byte-exact (gh#775): the file's existing bytes, line
    endings and blank lines are left alone, so reverting the one line restores
    the original file. A final line with no newline gets one, in the file's
    own style, because the new line cannot share it."""
    data = path.read_bytes() if path.exists() else b""
    if line.encode() in (raw.rstrip(b"\r") for raw in data.split(b"\n")):
        return False
    eol = b"\r\n" if b"\r\n" in data else b"\n"
    lead = eol if data and not data.endswith(b"\n") else b""
    path.write_bytes(data + lead + line.encode() + eol)
    return True


def init(
    root: Path,
    org: str,
    repo: str,
    backend: HostBackend = "github",
    *,
    with_ci: bool = False,
    ci_type: str | None = None,
    tracking_type: str | None = None,
    no_ci_reason: str | None = None,
    pages_decision: tuple[bool, str] | None = None,
) -> InitOutcome:
    """`ci_type`/`tracking_type` are the resolved services (`fr.services`);
    left None (a caller with no declaration) the pipeline follows `backend`
    as #787 had it: the forge's own CI, when the repo has one or `with_ci`.
    `ci_type="none"` scaffolds no pipeline; `no_ci_reason` says why. `pages_decision` is
    `pages_allowed`'s answer: None (not asked) is not allowed, so a bare `init` never
    scaffolds a Pages job."""
    from fr.acceptance.ci import DEBT_PLATFORM, SCAFFOLD_PATHS, ci_config, no_ci_message
    from fr.services.model import CI_FOR_FORGE

    created: list[str] = []
    skipped: list[str] = []
    notices: list[str] = []

    def write_if_missing(rel: str, content: str) -> None:
        path = root / rel
        if path.exists():
            skipped.append(rel)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        created.append(rel)

    # Decided before anything is written: a pipeline only for a repo whose ci
    # service is active (a declared type, or the forge's own CI already
    # present / asked for with --with-ci).
    if ci_type is None:
        own = CI_FOR_FORGE[backend]
        ci_type = own if with_ci or ci_config(root, backend) is not None else "none"
        tracking_type = backend if tracking_type is None else tracking_type
    has_ci = ci_type != "none"
    # The weekly debt issue is filed through the ci platform's own tracker CLI,
    # so it is kept only when the tracker is that platform (#774 §3.E), and only
    # while forge issues are on (R9).
    debt, debt_off = debt_steps(root, ci_type, tracking_type) if has_ci else (False, None)
    if has_ci:
        scaffold_path = SCAFFOLD_PATHS[ci_type]
        if ci_type == "github-actions":
            ci_bullet = _CI_BULLET_GITHUB.format(debt=_DEBT_TAIL_GITHUB if debt else "")
        else:
            ci_bullet = _CI_BULLET.format(path=scaffold_path, debt=_DEBT_TAIL if debt else "")
    else:
        ci_bullet = _NO_CI_BULLET
    # Rows live in per-feature fragments (R16): init creates their directory and
    # no fragment — `fr acceptance add` writes the first. The `.gitkeep` keeps the
    # directory in a clone, where it tells fr this repo keeps acceptance rows.
    del org, repo  # the identity lives in each fragment's `repo:` (`fr acceptance add`)
    write_if_missing(f"{FRAGMENTS_DIR.as_posix()}/.gitkeep", "")
    write_if_missing(
        ".claude/rules/acceptance-matrix.md", RULE_TEMPLATE.replace("{ci_bullet}", ci_bullet)
    )
    plan = publish_plan(root, ci_type, pages_decision) if has_ci else PublishPlan()
    if has_ci:
        write_if_missing(
            scaffold_path,
            render_workflow(ci_type, debt=debt, pages=plan.pages, comment=plan.comment),
        )
        notices.extend(plan.notices)
        if debt_off is not None:
            notices.append(f"no debt  {debt_off} from {scaffold_path}; see `fr settings show`")
        elif not debt:
            notices.append(
                f'no debt  the weekly "Technical debt" steps are omitted from '
                f"{scaffold_path} — tracking is {tracking_type!r}, not the {ci_type} platform's "
                f"own ({DEBT_PLATFORM[ci_type]}); see `fr services`"
            )
    elif no_ci_reason:
        notices.append(f"no CI  no pipeline scaffolded — {no_ci_reason}; see `fr services`")
    else:
        notices.append(
            f"no CI  no pipeline scaffolded — {no_ci_message(backend)}; "
            "pass --with-ci to scaffold one"
        )

    # No report is written: reports are derived, never committed (spec
    # 2026-11-04-repo-feature-settings R20). Git is told to ignore the two files
    # `fr acceptance report` writes.
    gitignore = root / ".gitignore"
    existed = gitignore.exists()
    modified: list[str] = []
    wrote = [_append_gitignore_line(gitignore, line) for line in GITIGNORE_LINES]
    if any(wrote):
        (modified if existed else created).append(".gitignore")
    else:
        skipped.append(".gitignore")
    if has_ci and (line := badge_line(root, ci_type, pages=plan.pages)) is not None:
        status = write_badge(root, line)
        if status in ("created", "modified"):
            modified.append("README.md")
    return InitOutcome(created=created, skipped=skipped, notices=notices, modified=modified)
