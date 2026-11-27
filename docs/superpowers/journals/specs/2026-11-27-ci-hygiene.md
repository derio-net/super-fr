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
