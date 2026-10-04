"""`fr acceptance init` — scaffold the matrix, CI workflow, rule, HTML report.

Write-if-missing semantics throughout: re-running init never touches a file
the operator (or a previous run) already owns. The one file init edits rather
than creates, `.gitignore`, gets one appended line and no other byte changed.

The CI workflow is scaffolded only for a repo that already has CI for its
backend, or when the caller asks (`--with-ci`) — see `fr.acceptance.ci`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from fr._hosts import HostBackend

# `report.html` is the ad-hoc / uncommitted render (git-stamped, CI/local);
# the committed set is report_local.html / report_linked.html / report_linked.md.
GITIGNORE_LINE = "docs/acceptance/report.html"

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
- Reports: THREE **committed, tracked** renderings of `matrix.yaml`, kept in
  sync — `docs/acceptance/report_local.html` (local links, viewable from a
  checkout), `docs/acceptance/report_linked.html` (github.com blob links), and
  `docs/acceptance/report_linked.md` (the linked report as **Markdown**, which
  github.com renders inline — committed `.html` is shown as source, not
  rendered). `fr acceptance add` regenerates **all three**; drift (incl.
  hand-edited status flips) is gated by `fr acceptance check` itself — it fails
  when any committed report is missing or stale. Regenerate by hand with `fr
  acceptance report --deterministic` (writes all three) and commit them.
  `docs/acceptance/report.html` is a separate **ad-hoc, gitignored** render: `fr
  acceptance report` (no flag) writes it git-stamped honoring `--link-mode`
  (github in CI, local otherwise); links resolve relative to sibling checkouts
  (`--sibling-root`, default `..`).
{ci_bullet}
"""

WORKFLOW_TEMPLATE = """\
name: acceptance-report

# The acceptance matrix (docs/acceptance/matrix.yaml) rendered + gated.
# - `failing` rows FAIL this workflow (by design — fix or re-classify).
# - `skipped` / `not-implemented` rows surface as warning annotations; the
#   backfill rule (.claude/rules/acceptance-matrix.md) owns their lifecycle.
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
@@DEBT_STEP@@"""

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
@@DEBT_STEP@@"""

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
@@DEBT_COMMENT@@# - No step-summary equivalent — GitLab CI has none (see module comment).
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
@@DEBT_STEP@@  artifacts:
    paths:
      - docs/acceptance/report.html
    expire_in: 90 days
"""


# The weekly "Acceptance debt" issue step, split out of each template so it is
# included only when the tracker is the ci type's own platform (#774 §3.E): the
# step files through that platform's CLI with the pipeline's own credentials.
_DEBT_COMMENT_ACTIONS = (
    '# - The weekly run upserts one "Acceptance debt" issue (closed at zero debt).\n'
)
DEBT_COMMENT = {
    "github-actions": _DEBT_COMMENT_ACTIONS,
    "gitea-actions": _DEBT_COMMENT_ACTIONS,
    "gitlab-ci": '# - The weekly (scheduled) run upserts one "Acceptance debt" issue.\n',
}
DEBT_STEP_GITHUB = """\
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
DEBT_STEP_GITEA = """\
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
DEBT_STEP_GITLAB = """\
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
"""
DEBT_STEP = {
    "github-actions": DEBT_STEP_GITHUB,
    "gitea-actions": DEBT_STEP_GITEA,
    "gitlab-ci": DEBT_STEP_GITLAB,
}
WORKFLOW_TEMPLATES = {
    "github-actions": WORKFLOW_TEMPLATE,
    "gitea-actions": WORKFLOW_TEMPLATE_GITEA,
    "gitlab-ci": WORKFLOW_TEMPLATE_GITLAB,
}


DEBT_PERMS = "  issues: write\n"


def render_workflow(ci_type: str, *, debt: bool) -> str:
    """The scaffolded pipeline for `ci_type`, with or without the debt step
    (and the `issues: write` permission only that step needs)."""
    text = WORKFLOW_TEMPLATES[ci_type]
    return (
        text.replace("@@DEBT_PERMS@@", DEBT_PERMS if debt else "")
        .replace("@@DEBT_COMMENT@@", DEBT_COMMENT[ci_type] if debt else "")
        .replace("@@DEBT_STEP@@", DEBT_STEP[ci_type] if debt else "")
    )


# The matrix header's gate line, and the rule's CI bullet. GitHub's wording is
# the one every GitHub repo was scaffolded with, kept byte-for-byte.
_CI_GATE = "gated in CI by\n# {path} (`fr acceptance check`)."
_NO_CI_GATE = "no CI is configured,\n# so `fr acceptance check` runs locally and no row is `ci`."
_CI_BULLET_GITHUB = """\
- CI: `.github/workflows/acceptance-report.yml` gates every PR and branch push,
  writes a Markdown summary to each Actions run (branch, PR, main), uploads the
  GitHub-linked report artifact{debt}."""
_CI_BULLET = """\
- CI: the acceptance job in `{path}` runs `fr acceptance check` on every
  pipeline{debt}."""
_DEBT_TAIL_GITHUB = ', and upserts the weekly "Acceptance debt" issue'
_DEBT_TAIL = ' and upserts the weekly "Acceptance debt" issue'
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
    # Legacy reports deleted by `prune_stale_reports` — a deletion dirties the
    # tree as surely as a write does.
    removed: list[str] = field(default_factory=list)

    @property
    def written(self) -> list[str]:
        """Every path this run changed — what `fr acceptance init` commits."""
        return [*self.created, *self.modified, *self.removed]


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
) -> InitOutcome:
    """`ci_type`/`tracking_type` are the resolved services (`fr.services`);
    left None (a caller with no declaration) the pipeline follows `backend`
    as #787 had it: the forge's own CI, when the repo has one or `with_ci`.
    `ci_type="none"` scaffolds no pipeline; `no_ci_reason` says why."""
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

    from fr.artifacts.registry import artifact_kind

    # Born at the kind's current version, so a fresh matrix is never stale.
    stamp = artifact_kind("matrix").current_version
    # Decided before anything is written: a pipeline only for a repo whose ci
    # service is active (a declared type, or the forge's own CI already
    # present / asked for with --with-ci).
    if ci_type is None:
        own = CI_FOR_FORGE[backend]
        ci_type = own if with_ci or ci_config(root, backend) is not None else "none"
        tracking_type = backend if tracking_type is None else tracking_type
    has_ci = ci_type != "none"
    # The weekly debt issue is filed through the ci platform's own tracker CLI,
    # so it is kept only when the tracker is that platform (#774 §3.E).
    debt = has_ci and tracking_type == DEBT_PLATFORM[ci_type]
    if has_ci:
        scaffold_path = SCAFFOLD_PATHS[ci_type]
        ci_gate = _CI_GATE.format(path=scaffold_path)
        if ci_type == "github-actions":
            ci_bullet = _CI_BULLET_GITHUB.format(debt=_DEBT_TAIL_GITHUB if debt else "")
        else:
            ci_bullet = _CI_BULLET.format(path=scaffold_path, debt=_DEBT_TAIL if debt else "")
    else:
        ci_gate, ci_bullet = _NO_CI_GATE, _NO_CI_BULLET
    write_if_missing(
        "docs/acceptance/matrix.yaml",
        MATRIX_TEMPLATE.format(org=org, repo=repo, schema_version=stamp, ci_gate=ci_gate),
    )
    write_if_missing(
        ".claude/rules/acceptance-matrix.md", RULE_TEMPLATE.replace("{ci_bullet}", ci_bullet)
    )
    if has_ci:
        write_if_missing(scaffold_path, render_workflow(ci_type, debt=debt))
        if not debt:
            notices.append(
                f'no debt  the weekly "Acceptance debt" issue step is omitted from '
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

    # The committed report SET (report_local.html + report_linked.html +
    # report_linked.md) are TRACKED artifacts kept in lockstep with the matrix
    # (enforced by `fr acceptance check`). Generate them so a freshly scaffolded
    # repo carries the committed matrix→report correspondence from row zero. The
    # ad-hoc `report.html` stays gitignored (github doesn't render committed
    # HTML; report.html is a throwaway local/CI render).
    from fr.acceptance.model import load_matrix
    from fr.acceptance.report import REPORT_SET, prune_stale_reports, render_committed_set

    # Degrade, don't crash: an unresolvable identity (hand-rolled matrix with no
    # org/repo keys AND no git remote) must not abort the whole scaffold after
    # the other files are written — mirrors add_cmd's warn-don't-roll-back
    # policy. The scaffolded matrix always carries the keys, so this only guards
    # a pre-existing partial state; re-running init (write-if-missing) recovers.
    try:
        rendered = render_committed_set(
            load_matrix(root / "docs" / "acceptance" / "matrix.yaml"), root
        )
    except Exception:  # noqa: BLE001 — a render hiccup never fails init
        rendered = None
    for report_rel in REPORT_SET:
        report_path = root / report_rel
        if report_path.exists():
            skipped.append(report_rel)
        elif rendered is not None:
            report_path.write_text(rendered[report_rel])
            created.append(report_rel)
        else:
            skipped.append(report_rel)
    removed = prune_stale_reports(root) if rendered is not None else []

    # `report.html` is the ad-hoc / uncommitted render — gitignore it.
    gitignore = root / ".gitignore"
    existed = gitignore.exists()
    modified: list[str] = []
    if _append_gitignore_line(gitignore, GITIGNORE_LINE):
        (modified if existed else created).append(".gitignore")
    else:
        skipped.append(".gitignore")
    return InitOutcome(
        created=created, skipped=skipped, notices=notices, modified=modified, removed=removed
    )
