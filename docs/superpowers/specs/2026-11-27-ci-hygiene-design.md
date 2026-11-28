---
fr_schema: 2
---
# CI hygiene sweep: retire spec-status, one Python everywhere, least-privilege ci.yml

Issues: derio-net/super-fr#1594, derio-net/super-fr#1595, derio-net/super-fr#1596,
derio-net/super-fr#1598, derio-net/super-fr#1605, derio-net/super-fr#1675.

## Background

CI moved to one Python, 3.14 (#1589), and its leftovers are spread over six issues. Every
location below was checked on `main` at `e110425d6`.

- **spec-status workflow (#1594).** `.github/workflows/fr-spec-status.yml:20-24` sets up
  Python 3.12 and pip-installs `fr` from the `v3.0.0` tag. The pin was written when v3.0.0
  was the current release (#262) and never moved; nothing needs fr 3. Its only caller is
  `.github/workflows/_pr_spec_status.yml` (merged PRs). In the last 38 runs its `Post comment`
  step was skipped every time: the job looks for a plan directory's path inside spec files
  (`grep -q -F "$d" "$spec"`), and specs no longer carry that path, so it posts nothing.
  Operator decision: retire both workflows. `fr spec status` itself stays. Mentions:
  `.github/ci-budget.yaml:9`, `.github/workflows/ci-budget.yml:20`,
  `plugins/super-fr/skills/fr-progress/SKILL.md:78` (and its OpenCode and Hermes mirrors),
  `docs/explainers/fr-progress.md:78`, `packages/fr/src/fr/states.py:70` (a docstring).
- **floors.py (#1595).** `scripts/floors.py:31-38` explains how Python 3.11's tokenizer hands
  over an f-string, and builds `_STRING_TOKENS` with `getattr(tokenize, "FSTRING_MIDDLE", …)`.
  Every `requires-python` is `>=3.14`, where `tokenize.FSTRING_MIDDLE` always exists.
- **test_ci_shards.py (#1596).** The module docstring (lines 4 and 11) and the section
  comment at line 102 say the `test` job is
  a 6-way matrix; it has 7 shards (line 56 asserts `[1..7]`). The partition test also splits
  into a literal 6 groups (lines 115-121), not the matrix's 7.
- **UV_PYTHON (#1598).** `ci.yml:19` and `release.yml:91` set `UV_PYTHON: "3.14"`.
  `acceptance-report.yml`, `pages.yml`, `ci-budget.yml` and `pinned-clis.yml` use
  `astral-sh/setup-uv` with no `UV_PYTHON`, so uv downloads 3.14 on each run.
  `tests/unit/test_ci_python_floor.py` pins `ci.yml` and `release.yml` only.
- **ci.yml permissions (#1605, #1675, one defect).** `ci.yml` has no workflow-level
  `permissions:`; only `classify` (`:40`), `scoped-tests` (`:276`) and `ci-ok` (`:459`) set
  their own, so every other job runs with the repo's default token. No other job uses a
  token (no `gh`, no `GH_TOKEN`; artifacts move through the runtime token). Every other
  workflow file already has a workflow-level block, except `fr-spec-status.yml`, which this
  change deletes.

## Requirements

| ID | Requirement |
|----|-------------|
| R1 | `fr-spec-status.yml` and `_pr_spec_status.yml` are deleted, and every live mention of them (budget config, budget watch list, the fr-progress skill and its mirrors, the fr-progress explainer, the `states.py` docstring) is removed or reworded; `fr spec status` is unchanged. |
| R2 | `scripts/floors.py` keeps no Python 3.11 prose and no `getattr` fallback for `tokenize.FSTRING_MIDDLE`; its behaviour is unchanged. |
| R3 | `tests/unit/test_ci_shards.py` describes the 7-shard matrix, and its partition test splits into the matrix's own shard count instead of a literal. |
| R4 | Every workflow that uses `astral-sh/setup-uv` sets a workflow-level `UV_PYTHON` equal to the `requires-python` floor, and a test fails when one does not. |
| R5 | `ci.yml` declares a workflow-level `permissions: {contents: read}`, every workflow file declares a workflow-level `permissions:` block, and a test fails when either stops holding. |

## Design

1. **Retire (R1).** `git rm` both workflow files. Drop the `fr-spec-status.yml` line from
   `.github/ci-budget.yaml` and `PR spec status (self)` from `ci-budget.yml`'s
   `on.workflow_run.workflows`. In the fr-progress skill, drop the sentence that says the
   workflow posts the output; run `scripts/sync-opencode.py` and `scripts/sync-hermes.py`.
   In the explainer, drop the same sentence and move its `reviewed` stamp. In `states.py`,
   say "in `fr spec status` output". `test_ci_budget.py:372-373` (an in-memory config) and
   `test_tripwire_actions_pinned.py:178-185` (a tmp file) use the file name only as data;
   they stay. `test_ci_budget.py:199-201`, `test_counted_pr_spec_status_counts_every_event`,
   reads the real `_pr_spec_status.yml` and is deleted with it: the every-event case keeps its
   cover in `test_counted_pinned_clis_counts_every_event` (`:204`). A patch change fragment is
   added (the skill and `packages/*/src` changed).
2. **floors.py (R2).** `_STRING_TOKENS = {tokenize.STRING, tokenize.FSTRING_MIDDLE}`; the
   comment says only what the regex accepts on 3.12+ (the middle piece ends after `<`).
   The regex is unchanged. `tests/unit/test_version_floors.py` proves no behaviour moved.
3. **Shards (R3).** Docstring (lines 4, 11) and the section comment (line 102) say 7, or
   the matrix's count; the partition test reads the shard list from
   `ci.yml`'s `test` matrix and splits into `len(shards)`.
4. **UV_PYTHON (R4).** Add `env: UV_PYTHON: "3.14"` at workflow level to the four files
   (merged into an existing `env:` when there is one). In `test_ci_python_floor.py`, a new
   test walks every workflow; one whose steps use `astral-sh/setup-uv` must have
   workflow-level `env.UV_PYTHON == _floor()`. `pages.yml` is covered by
   `docs/docs-currency.md` (`covers:`, line 17); the page stays true, so its `reviewed` stamp
   moves with a "still true" note. The row `ci-workflows-pin-the-python-floor` gets the new
   test as its `unit` level and moves to `ci` (`fr acceptance set-status`).
5. **Permissions (R5).** Add `permissions:\n  contents: read` at the top of `ci.yml`; the
   job-level blocks stay (they replace it for their job). A new test (in
   `tests/unit/test_ci_lanes_workflow.py`, which already pins `ci.yml`'s permissions) asserts
   `ci.yml`'s workflow-level block is exactly `{contents: read}`, and that every
   `.github/workflows/*.yml` has a workflow-level `permissions` key. The row
   `ci-workflows-least-privilege-token` gets those tests as its `unit` levels and moves to
   `ci`.

## Design shape

```
.github/
  ci-budget.yaml                 ~ drop fr-spec-status.yml line
  workflows/
    fr-spec-status.yml           - deleted (R1)
    _pr_spec_status.yml          - deleted (R1)
    ci-budget.yml                ~ drop "PR spec status (self)"; + env UV_PYTHON (R4)
    acceptance-report.yml        ~ + env UV_PYTHON (R4)
    pages.yml                    ~ + env UV_PYTHON (R4)
    pinned-clis.yml              ~ + env UV_PYTHON (R4)
    ci.yml                       ~ + permissions: {contents: read} (R5)
scripts/floors.py                ~ drop 3.11 prose + getattr fallback (R2)
packages/fr/src/fr/states.py     ~ docstring wording (R1)
plugins/super-fr/skills/fr-progress/SKILL.md  ~ drop workflow sentence (R1) -> mirrors
docs/explainers/fr-progress.md   ~ drop workflow sentence, reviewed stamp (R1)
tests/unit/
  test_ci_shards.py              ~ 7-shard docstring, partition from matrix (R3)
  test_ci_python_floor.py        + every setup-uv workflow pins UV_PYTHON (R4)
  test_ci_lanes_workflow.py      + workflow-level permissions guards (R5)
  test_ci_budget.py              - test_counted_pr_spec_status_counts_every_event (R1)
docs/docs-currency.md            ~ reviewed stamp (pages.yml touched, R4)
docs/acceptance/features/2026-11-27-ci-hygiene.yaml  ~ both rows: unit levels, status ci
.changes/feat-batch-ci-hygiene.yaml  + patch fragment
```

## Verification

strategy: none
gate: developer
settle.conflicts: report — batch ci-hygiene: the wave driver owns this PR's mergeability
settle.ci: report — batch ci-hygiene: the wave driver owns this PR's CI

- ci-workflows-pin-the-python-floor: none — the unit test of R4 reads every workflow file in CI
- ci-workflows-least-privilege-token: none — the unit test of R5 reads every workflow file in CI

No installable behaviour changes. This PR's own CI runs the edited `ci.yml`, and the new
unit tests pin R3-R5; `test_version_floors.py` pins R2. Nothing is owed after merge, so
there is no Test Plan.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-27-ci-hygiene | `derio-net/super-fr` | `2026-11-27-ci-hygiene` | — |
