<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-ci-hygiene

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-27T20:15:56+00:00 input=true -->
### operator-brief · discovery · Batch ci-hygiene brief (wave driver dispatch)

Batch `ci-hygiene` of derio-net/super-fr: 6 issues, one PR on `feat/batch-ci-hygiene`.
- #1594 fr-spec-status.yml pins setup-python 3.12 and pip-installs fr v3.0.0; bump or retire.
- #1595 leftover 3.11 prose and a dead FSTRING_MIDDLE fallback in scripts/floors.py.
- #1596 test_ci_shards.py docstring still says 6-way matrix; CI runs 7 shards.
- #1598 acceptance-report.yml, pages.yml, ci-budget.yml, pinned-clis.yml set no UV_PYTHON.
- #1605 / #1675 ci.yml declares no workflow-level permissions; add contents: read.
Delivery: draft PR with one `Closes derio-net/super-fr#<n>` line per member; no member as a
phase tracking_issue; the wave driver owns mergeability and CI (no settle loop); never add approved-fr.

<!-- fr:journal kind=decision scope=spec id=q-spec-status-retire created=2026-11-27T20:15:56+00:00 decided_by=operator -->
### q-spec-status-retire · decision · #1594: retire fr-spec-status.yml and _pr_spec_status.yml

Round 1 the operator asked whether the file needs fr 3. It does not: the pin dates from the
v3.0.0 release (#262). The last 38 runs skipped `Post comment`, since its plan-path match no
longer fits the specs. Round 2 answer: retire it (recommended). `fr spec status` stays.

<!-- fr:journal kind=decision scope=spec id=q-uv-python-tripwire created=2026-11-27T20:15:56+00:00 decided_by=operator -->
### q-uv-python-tripwire · decision · #1598: tripwire every setup-uv workflow pins UV_PYTHON to the floor

Operator chose the recommended tripwire over fixing the four files alone.

<!-- fr:journal kind=decision scope=spec id=q-permissions-every-workflow created=2026-11-27T20:15:56+00:00 decided_by=operator -->
### q-permissions-every-workflow · decision · #1605/#1675: every workflow declares workflow-level permissions; ci.yml's is contents: read

Operator chose the widest guard (recommended).

<!-- fr:journal kind=decision scope=spec id=q-verification created=2026-11-27T20:15:56+00:00 decided_by=operator -->
### q-verification · decision · Verification strategy none, gate developer

Operator accepted strategy `none` + `developer` gate. Retiring spec-status removed the one proposed post-merge row, so there is no Test Plan.

<!-- fr:journal kind=decision scope=spec id=gate-question-rounds-brainstorm created=2026-11-27T20:15:56+00:00 -->
### gate-question-rounds-brainstorm · decision · Operator gate `brainstorm` took two question rounds

Trigger: operator-request. The operator answered round 1's spec-status question with a question (does it need fr 3?); the answer (a stale pin, and a job that has posted nothing in 38 runs) changed the choice to retire-or-rebuild.

<!-- fr:journal kind=finding scope=spec id=sr-r1 created=2026-11-27T20:19:54+00:00 state=open review_scope=in -->
### sr-r1 · finding [open] (reviewer: in scope) · Deleting _pr_spec_status.yml breaks test_ci_budget.py::test_counted_pr_spec_status_counts_every_event, which the spec says stays

tests/unit/test_ci_budget.py:179-201: `_on` reads REPO/.github/workflows/<name>, and the test reads
`_pr_spec_status.yml`. The spec claimed both test files use the name only as data; that holds for
:372-373 and test_tripwire_actions_pinned.py:178-185, not for :199-201.

<!-- fr:journal kind=finding scope=spec id=sr-r2 created=2026-11-27T20:19:54+00:00 state=open review_scope=in -->
### sr-r2 · finding [open] (reviewer: in scope) · Editing pages.yml trips fr docs check: docs/docs-currency.md covers it, and the spec did not touch that page

docs/docs-currency.md:17 covers .github/workflows/pages.yml; R4 edits pages.yml, so the page's reviewed stamp must move.

<!-- fr:journal kind=finding scope=spec id=sr-r3 created=2026-11-27T20:19:54+00:00 state=open review_scope=in -->
### sr-r3 · finding [open] (reviewer: in scope) · The feature's two acceptance rows were not in the Design, and nothing moved them off not-implemented

docs/acceptance/features/2026-11-27-ci-hygiene.yaml holds both rows with empty levels; the Design never said they get unit levels and move to ci.

<!-- fr:journal kind=finding scope=spec id=sr-r4 created=2026-11-27T20:19:54+00:00 state=open review_scope=in -->
### sr-r4 · finding [open] (reviewer: in scope) · test_ci_shards.py has a third literal 6 (the section comment at line 102) that R3's design did not name

tests/unit/test_ci_shards.py:102 says "across 6 groups".

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-27T20:19:54+00:00 -->
### spec-review-1 · review · independent spec review: 4 findings (sr-r1..sr-r4)

findings: sr-r1, sr-r2, sr-r3, sr-r4 (all in scope, all fixed in the spec).
Decisions honoured: q-spec-status-retire (R1), q-uv-python-tripwire (R4),
q-permissions-every-workflow (R5), q-verification (strategy none, gate developer, no Test Plan).
Verified with file:line: both retired workflows and every live mention; floors.py :31-38;
test_ci_shards.py :4, :11, :56, :102, :118, :121; UV_PYTHON only in ci.yml:19 and release.yml:91;
setup-uv without UV_PYTHON in acceptance-report, pages, ci-budget and pinned-clis; workflow-level
permissions missing only in ci.yml and fr-spec-status.yml; no ci.yml job beyond classify,
scoped-tests and ci-ok uses a token, so contents: read is enough.

<!-- fr:journal kind=lens scope=spec id=lens-security-1 created=2026-11-27T20:19:54+00:00 lens=security step=spec-review -->
### lens-security-1 · lens · R5 changes the default token scope of every ci.yml job; confirm no job loses a permission it uses

<!-- fr:journal kind=finding scope=spec id=sr-r1-resolved created=2026-11-27T20:19:54+00:00 state=fixed resolves=sr-r1 -->
### sr-r1-resolved · finding [fixed] · resolves sr-r1: Deleting _pr_spec_status.yml breaks test_ci_budget.py::test_counted_pr_spec_status_counts_every_event, which the spec says stays

Design 1 now deletes test_counted_pr_spec_status_counts_every_event with the workflow (pinned-clis keeps the every-event case) and corrects the 'they stay' claim; Design shape lists it.

<!-- fr:journal kind=finding scope=spec id=sr-r2-resolved created=2026-11-27T20:19:54+00:00 state=fixed resolves=sr-r2 -->
### sr-r2-resolved · finding [fixed] · resolves sr-r2: Editing pages.yml trips fr docs check: docs/docs-currency.md covers it, and the spec did not touch that page

Design 4 moves docs/docs-currency.md's reviewed stamp with a still-true note; Design shape lists it.

<!-- fr:journal kind=finding scope=spec id=sr-r3-resolved created=2026-11-27T20:19:54+00:00 state=fixed resolves=sr-r3 -->
### sr-r3-resolved · finding [fixed] · resolves sr-r3: The feature's two acceptance rows were not in the Design, and nothing moved them off not-implemented

Design 4 and 5 give each row its new test as a unit level and move it to ci with fr acceptance set-status; Design shape lists the fragment.

<!-- fr:journal kind=finding scope=spec id=sr-r4-resolved created=2026-11-27T20:19:54+00:00 state=fixed resolves=sr-r4 -->
### sr-r4-resolved · finding [fixed] · resolves sr-r4: test_ci_shards.py has a third literal 6 (the section comment at line 102) that R3's design did not name

Background and Design 3 name line 102 too.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-27T20:19:56+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  ci-workflows-least-privilege-token: none
  ci-workflows-pin-the-python-floor: none
row_kinds:
  ci-workflows-least-privilege-token: none
  ci-workflows-pin-the-python-floor: none
run_gate: developer
run_kind: none
```
