"""`fr acceptance init` — scaffold the matrix, CI workflow, rule, HTML report.

Write-if-missing semantics throughout: re-running init never touches a file
the operator (or a previous run) already owns.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fr._hosts import HostBackend

MATRIX_TEMPLATE = """\
# Acceptance matrix — the registry of business-level acceptance tests and
# where each is verified. Rendered by `fr acceptance report`; gated in CI by
# .github/workflows/acceptance-report.yml (`fr acceptance check`).
#
# Row schema:
#   id:         kebab-case, stable
#   capability: grouping (tables render in first-seen order)
#   acceptance: the business-level statement
#   origin:     list of "repo:path[#anchor]" refs (spec §, design doc)
#   levels:     unit/api/int/ui → list of "repo:path[#Lline]" test refs
#               ([] = level does not verify this row)
#   status:     ci | scheduled | skipped | not-implemented | failing
#     ci               automated on every PR — cannot drift silently
#     scheduled        automated on cron/path triggers
#     skipped          verification exists but does not run in CI (proven
#                      live once / manual walk) → CI warning, backfill owed
#     not-implemented  no test or surface exists yet → CI warning
#     failing          known red → `fr acceptance check` exits 2, CI FAILS
#   notes:      evidence detail, drift context
#
# Rule: .claude/rules/acceptance-matrix.md — update rows in the SAME PR that
# changes a Test Plan, adds tests, ships a surface, or touches CI.
# Add rows with `fr acceptance add` (schema-validated append). Keep `rows:`
# as the LAST top-level key — `add` appends to the end of this file.

org: {org}
repo: {repo}
rows:
"""

RULE_TEMPLATE = """\
# Acceptance Matrix — Backfill Rule (repo-wide)

## Rule

`docs/acceptance/matrix.yaml` is the registry of business-level acceptance
tests × verification levels × automation status. **Any PR that does one of
the following updates the matrix in the SAME PR:**

- adds or changes a spec `## Test Plan` (new spec ⇒ new rows; the CI
  staleness guard fails a spec with a Test Plan that no row cites)
- adds tests that verify an existing row (add the ref to `levels`, move
  `status` up: `not-implemented` → `skipped` → `ci`/`scheduled`)
- ships a surface or capability a `not-implemented` row waits on
- changes CI workflows that run matrix-referenced checks
- discovers a red acceptance: set `status: failing` — the
  `acceptance-report` workflow then FAILS by design until it is fixed or
  re-classified with reasoning in `notes`

Statuses move **explicitly, never silently**: `ci` | `scheduled` (automated
— the safe end) · `skipped` (verification exists, not in CI — warning,
backfill owed) · `not-implemented` (nothing exists — warning) · `failing`
(fails CI).

## How

- Add rows: `fr acceptance add --id ... --capability ... --acceptance ...
  --origin <repo>:<path> --level unit=<repo>:<path> --status ... --notes ...`
- Check: `fr acceptance check` (refs, staleness, statuses; exit 2 on
  `failing`). Nag: `fr acceptance status` — **any agent session in this repo
  runs `fr acceptance status --brief` at session start** (Claude Code does it
  automatically via the super-fr SessionStart hook; other harnesses honor
  this line).
- Report: `docs/acceptance/report.html` is a **committed, tracked** rendering
  of `matrix.yaml`, kept in sync — `fr acceptance add` regenerates it, and drift
  (incl. hand-edited status flips) is gated by `fr acceptance report --check`
  plus the report-sync tripwire. Regenerate by hand with `fr acceptance report
  --deterministic` and commit it. Ad-hoc `fr acceptance report` (no flag) gives a
  git-stamped throwaway local render; links resolve relative to sibling checkouts
  (`--sibling-root`, default `..`).
- CI: `.github/workflows/acceptance-report.yml` gates every PR and branch push,
  writes a Markdown summary to each Actions run (branch, PR, main), uploads the
  GitHub-linked report artifact, and upserts the weekly "Acceptance debt" issue.
"""

WORKFLOW_TEMPLATE = """\
name: acceptance-report

# The acceptance matrix (docs/acceptance/matrix.yaml) rendered + gated.
# - `failing` rows FAIL this workflow (by design — fix or re-classify).
# - `skipped` / `not-implemented` rows surface as warning annotations; the
#   backfill rule (.claude/rules/acceptance-matrix.md) owns their lifecycle.
# - A Markdown summary is written to each Actions run (branch, PR, main).
# - The built report (GitHub-linked at this ref) is uploaded as an artifact.
# - The weekly run upserts one "Acceptance debt" issue (closed at zero debt).
# Sister-repo refs are not verifiable here (no checkout) — `fr acceptance
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
  issues: write

jobs:
  matrix:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v7
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
          path: docs/acceptance/report.html
          retention-days: 90
      - name: Upsert acceptance-debt issue (weekly digest)
        if: github.event_name == 'schedule'
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          fr acceptance digest > /tmp/digest.md
          # Idempotence keyed on the body marker `fr acceptance digest` emits,
          # not the title — a pre-existing issue that merely says "Acceptance
          # debt" in its title must not be hijacked.
          num=$(gh issue list --state open --search '"fr-acceptance-digest" in:body' \\
                --json number --jq '.[0].number // empty')
          if grep -q "No open acceptance debt." /tmp/digest.md; then
            if [ -n "$num" ]; then
              gh issue close "$num" --comment "Acceptance debt cleared — closing."
            fi
          elif [ -n "$num" ]; then
            gh issue edit "$num" --body-file /tmp/digest.md
          else
            gh issue create --title "Acceptance debt" --body-file /tmp/digest.md
          fi
"""

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

# The acceptance matrix (docs/acceptance/matrix.yaml) rendered + gated.
# - `failing` rows FAIL this workflow (by design — fix or re-classify).
# - `skipped` / `not-implemented` rows surface as warning annotations; the
#   backfill rule (.claude/rules/acceptance-matrix.md) owns their lifecycle.
# - A Markdown summary is written to each Actions run (branch, PR, main) —
#   Gitea Actions supports GITHUB_STEP_SUMMARY (aliased GITEA_STEP_SUMMARY,
#   confirmed against Gitea's own Actions-variables docs).
# - The built report is uploaded as an artifact.
# - The weekly run upserts one "Acceptance debt" issue (closed at zero debt).
#
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
          path: docs/acceptance/report.html
          retention-days: 90
      - name: Upsert acceptance-debt issue (weekly digest)
        if: gitea.event_name == 'schedule'
        run: |
          fr acceptance digest > /tmp/digest.md
          # Idempotence keyed on the body marker `fr acceptance digest` emits,
          # not the title — a pre-existing issue that merely says "Acceptance
          # debt" in its title must not be hijacked.
          num=$(tea issues list --state open --output json \\
                --fields index,body | python3 -c '
          import json, sys
          rows = json.load(sys.stdin)
          for r in rows:
              if "fr-acceptance-digest" in (r.get("body") or ""):
                  print(r["index"])
                  break
          ')
          if grep -q "No open acceptance debt." /tmp/digest.md; then
            if [ -n "$num" ]; then
              tea comments add "$num" "Acceptance debt cleared — closing."
              tea issues close "$num"
            fi
          elif [ -n "$num" ]; then
            tea issues edit "$num" --description "$(cat /tmp/digest.md)"
          else
            tea issues create --title "Acceptance debt" --description "$(cat /tmp/digest.md)"
          fi
"""

# GitLab CI is a genuinely different schema (stages:/script:, not
# on:/jobs:/steps:) — not a reuse of WORKFLOW_TEMPLATE's shape. Written to
# `.gitlab-ci.yml` at the repo root (GitLab's fixed convention, not a
# configurable directory). Same residual link-mode gap as the Gitea
# template above. GitLab CI also has no generic job-summary feature
# analogous to GITHUB_STEP_SUMMARY (confirmed against GitLab's own
# artifacts:reports docs — every report type is a specific structured
# format: junit, sast, codequality, etc., not an arbitrary Markdown blob),
# so `fr acceptance summary` is only wired into the GitHub/Gitea templates.
WORKFLOW_TEMPLATE_GITLAB = """\
# The acceptance matrix (docs/acceptance/matrix.yaml) rendered + gated.
# - `failing` rows FAIL this pipeline (by design — fix or re-classify).
# - `skipped` / `not-implemented` rows surface as warnings; the backfill
#   rule (.claude/rules/acceptance-matrix.md) owns their lifecycle.
# - The built report is kept as a pipeline artifact.
# - The weekly (scheduled) run upserts one "Acceptance debt" issue.
# - No step-summary equivalent — GitLab CI has none (see module comment).
# Sister-repo refs are not verifiable here (no checkout) — `fr acceptance
# check` warns and verifies them on local runs, where siblings exist.
# If path filters (`rules:changes:`) are added later, they must include
# every own-repo path the matrix references — `fr acceptance check` warns
# when one falls outside them.

stages:
  - acceptance

acceptance-report:
  stage: acceptance
  image: python:3.12
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
    - fr acceptance check
    - fr acceptance report --link-mode github --ref "$CI_COMMIT_SHA"
    - |
      if [ "$CI_PIPELINE_SOURCE" = "schedule" ]; then
        fr acceptance digest > /tmp/digest.md
        # Idempotence keyed on the body marker `fr acceptance digest` emits.
        iid=$(glab api "projects/:id/issues?search=fr-acceptance-digest&in=description" \\
              | python3 -c '
        import json, sys
        rows = json.load(sys.stdin)
        for r in rows:
            if "fr-acceptance-digest" in (r.get("description") or ""):
                print(r["iid"])
                break
        ')
        if grep -q "No open acceptance debt." /tmp/digest.md; then
          if [ -n "$iid" ]; then
            glab api "projects/:id/issues/$iid" -X PUT -F state_event=close
          fi
        elif [ -n "$iid" ]; then
          glab api "projects/:id/issues/$iid" -X PUT -F description=@/tmp/digest.md
        else
          glab api projects/:id/issues -F title="Acceptance debt" -F description=@/tmp/digest.md
        fi
      fi
  artifacts:
    paths:
      - docs/acceptance/report.html
    expire_in: 90 days
"""


@dataclass(frozen=True)
class InitOutcome:
    created: list[str]
    skipped: list[str]


def init(root: Path, org: str, repo: str, backend: HostBackend = "github") -> InitOutcome:
    created: list[str] = []
    skipped: list[str] = []

    def write_if_missing(rel: str, content: str) -> None:
        path = root / rel
        if path.exists():
            skipped.append(rel)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        created.append(rel)

    write_if_missing("docs/acceptance/matrix.yaml", MATRIX_TEMPLATE.format(org=org, repo=repo))
    write_if_missing(".claude/rules/acceptance-matrix.md", RULE_TEMPLATE)
    # Template + destination path both vary by backend — see
    # WORKFLOW_TEMPLATE_GITEA/WORKFLOW_TEMPLATE_GITLAB's module-level
    # docstrings for why each is shaped the way it is.
    if backend == "gitea":
        write_if_missing(".gitea/workflows/acceptance-report.yml", WORKFLOW_TEMPLATE_GITEA)
    elif backend == "gitlab":
        write_if_missing(".gitlab-ci.yml", WORKFLOW_TEMPLATE_GITLAB)
    else:
        write_if_missing(".github/workflows/acceptance-report.yml", WORKFLOW_TEMPLATE)

    # The HTML report is a TRACKED artifact kept in lockstep with the matrix
    # (enforced by the sync tripwire) — no longer gitignored. Generate an
    # initial deterministic render so a freshly scaffolded repo carries the
    # committed matrix→report correspondence from row zero.
    report_rel = "docs/acceptance/report.html"
    report_path = root / report_rel
    if report_path.exists():
        skipped.append(report_rel)
    else:
        from fr.acceptance.model import load_matrix
        from fr.acceptance.report import render_deterministic

        matrix = load_matrix(root / "docs" / "acceptance" / "matrix.yaml")
        report_path.write_text(
            render_deterministic(matrix, root, report_path.parent, "..", "local")
        )
        created.append(report_rel)
    return InitOutcome(created=created, skipped=skipped)
