<!-- fr:journal-schema=4 -->
# Journal: 2026-11-20-ci-single-python

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-20T07:34:38+00:00 input=true -->
### operator-brief · discovery · Operator brief, verbatim

/fr-goal Implement derio-net/super-fr#1589: run the PR test suite in .github/workflows/ci.yml on a single Python version instead of 3.11 and 3.14. Context: ci.yml's collect and test jobs have a python axis [3.11, 3.14] x 7 shards; release.yml already runs only 3.11 (UV_PYTHON). The second leg was added on purpose in #940/#945 so a version-specific break shows from either end, so decide in the spec which version stays (default: the declared floor 3.11, which requires-python and tests/unit/test_ci_python_floor.py pin) and whether any cheaper check of the newest Python survives (release only, or main only). Touch points the issue lists: coverage is measured on the 3.14 leg only (cov_args, the coverage upload step), split-check merges the 3.14 leg's durations-py3.14-shard-* files on main, tests/unit/test_ci_split_workflow.py asserts [3.11, 3.14] and py3.14, test_ci_shards.py, test_ci_python_floor.py, .github/ci-budget.yaml and the CI notes in AGENTS.md. Out of scope: changing requires-python, and the hook flake in #1586 (draft PR #1588, already open). The host is loaded: run single test files only, never the full suite; CI is the suite evidence. Reference #1589 in the PR so it closes. Deliver a draft PR; never mark it ready or merge.

<!-- fr:journal kind=decision scope=spec id=d-python-version created=2026-11-20T07:34:38+00:00 decided_by=operator -->
### d-python-version · decision · The whole base moves to Python 3.14; no 3.11 anywhere

Round 1 Q1, operator free text: "we move the whole base to 3.14, no python 3.11 anywhere". This overrides the brief's out-of-scope note on requires-python. Round 2 Q1 confirmed: requires-python >=3.14 in all six pyproject.toml files, ruff py314, mypy 3.14.

<!-- fr:journal kind=decision scope=spec id=d-major-bump created=2026-11-20T07:34:38+00:00 decided_by=operator -->
### d-major-bump · decision · Released as a major bump

Round 2 Q1: "Yes, >=3.14, major bump". The operator asked whether uv handles it; answered from the code: install.sh and the scaffolded CI use `uv tool install` with no --python, so uv downloads a managed 3.14; only download-disabled hosts and plain-pip installs break. The operator's choice (major) stands.

<!-- fr:journal kind=decision scope=spec id=d-no-second-leg created=2026-11-20T07:34:38+00:00 decided_by=operator -->
### d-no-second-leg · decision · No second interpreter is tested anywhere

Round 1 Q2 answer "Nowhere but for 3.11", clarified in round 2 Q3: 3.14 only, no second leg, no main-only leg, no scheduled run.

<!-- fr:journal kind=decision scope=spec id=d-shards created=2026-11-20T07:34:38+00:00 decided_by=operator -->
### d-shards · decision · The test job keeps 7 shards

Round 1 Q3 chose 9 shards under the 3.11-coverage premise; round 2 Q4, with coverage on 3.14, chose to keep 7.

<!-- fr:journal kind=decision scope=spec id=d-scaffold-image created=2026-11-20T07:34:38+00:00 decided_by=operator -->
### d-scaffold-image · decision · Scaffolded consumer CI moves to python:3.14

Round 2 Q2. scaffold.py:290,391,548 and the golden fixtures.

<!-- fr:journal kind=decision scope=spec id=d-verification created=2026-11-20T07:34:38+00:00 decided_by=operator -->
### d-verification · decision · Verified by this PR's CI plus one post-merge row; no gate holds the close-out

Round 1 Q4: strategy none before merge (pinned unit tests and the PR's own CI); one Test Plan row for the first main push (durations merge, release suite on 3.14); gate developer.

<!-- fr:journal kind=decision scope=spec id=gate-question-rounds-brainstorm created=2026-11-20T07:34:40+00:00 -->
### gate-question-rounds-brainstorm · decision · Operator gate `brainstorm` took two question rounds

Trigger: operator-request. Round 1's free-text answer moved the whole base to Python 3.14, which the brief listed as out of scope (requires-python). Round 2 was not forecast in round 1; it was needed to settle the floor, the scaffolded consumer CI image, the meaning of "Nowhere but for 3.11", and the shard count chosen under the 3.11-coverage premise. After fr refused design-risk, the operator confirmed in prose: "yes, go for the second round, it's necessary".

<!-- fr:journal kind=finding scope=spec id=s-r1 created=2026-11-20T07:41:57+00:00 state=open review_scope=in -->
### s-r1 · finding [open] (reviewer: in scope) · `gate: developer` does not reach the live row ci-single-leg-main-push (live.yaml gives it tester)

packages/fr/src/fr/verification/rows.py:99-128; plugins/super-fr/verifications/live.yaml:12. Against decision d-verification.

<!-- fr:journal kind=finding scope=spec id=s-r2 created=2026-11-20T07:41:57+00:00 state=open review_scope=in -->
### s-r2 · finding [open] (reviewer: in scope) · Four docs pages cover paths this change edits; the spec said none

docs/reference/acceptance-matrix.md:190, docs/explainers/fr-acceptance.md:261 (python:3.12), docs/reference/components.md (covers packages/*/pyproject.toml), docs/merge-protection.md (covers release.yml).

<!-- fr:journal kind=finding scope=spec id=s-r3 created=2026-11-20T07:41:57+00:00 state=open review_scope=in -->
### s-r3 · finding [open] (reviewer: in scope) · Merged row ci-shards-complete cites the renamed test and says every leg / 6 shards

docs/acceptance/features/2026-11-01-ci-speed.yaml:26-42.

<!-- fr:journal kind=finding scope=spec id=s-r4 created=2026-11-20T07:41:57+00:00 state=open review_scope=in -->
### s-r4 · finding [open] (reviewer: in scope) · Test Plan names only the post-merge row; the three none rows have no Test Plan entry

spec ## Verification vs ## Test Plan.

<!-- fr:journal kind=finding scope=spec id=s-r5 created=2026-11-20T07:41:57+00:00 state=open review_scope=in -->
### s-r5 · finding [open] (reviewer: in scope) · uv.lock moves more than the header under >=3.14

uv.lock:155 tomli marker, :773 tomli package, cp311-cp313 wheels.

<!-- fr:journal kind=finding scope=spec id=s-r6 created=2026-11-20T07:41:57+00:00 state=open review_scope=in -->
### s-r6 · finding [open] (reviewer: in scope) · AGENTS.md names the durations-py<v>-shard-<n> artifact that R5 renames

AGENTS.md:448-450.

<!-- fr:journal kind=finding scope=spec id=s-r7 created=2026-11-20T07:41:57+00:00 state=open review_scope=out -->
### s-r7 · finding [open] (reviewer: out of scope) · fr-spec-status.yml pins setup-python 3.12 and pip-installs fr v3.0.0

.github/workflows/fr-spec-status.yml:20-24; installs an old tag with floor 3.11, unaffected by this change.

<!-- fr:journal kind=finding scope=spec id=s-r8 created=2026-11-20T07:41:57+00:00 state=open review_scope=out -->
### s-r8 · finding [open] (reviewer: out of scope) · Leftover 3.11 prose and a dead fallback in scripts/floors.py

scripts/floors.py:31-38; safe_spawn.py:5 stays true; check-run names in fixtures are captured data.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-20T07:41:57+00:00 -->
### spec-review-1 · review · independent spec review: 8 findings (6 in scope, 2 out of scope)

Reviewer fr-spec-reviewer. In scope s-r1..s-r6 fixed in the spec; s-r7, s-r8 out of scope. All six operator decisions honoured once s-r1 is fixed.

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-20T07:41:57+00:00 lens=tests step=spec-review -->
### lens-tests-1 · lens · The change rewrites the tests that pin CI layout and the rows that cite them; check renamed tests still assert and anchors resolve

<!-- fr:journal kind=finding scope=spec id=s-r1-resolved created=2026-11-20T07:41:57+00:00 state=fixed resolves=s-r1 -->
### s-r1-resolved · finding [fixed] · resolves s-r1: `gate: developer` does not reach the live row ci-single-leg-main-push (live.yaml gives it tester)

Added `gate: ci-single-leg-main-push=developer`; fr verification exit reports gates developer, gated no.

<!-- fr:journal kind=finding scope=spec id=s-r2-resolved created=2026-11-20T07:41:57+00:00 state=fixed resolves=s-r2 -->
### s-r2-resolved · finding [fixed] · resolves s-r2: Four docs pages cover paths this change edits; the spec said none

New R11 and §G name the four pages and what each owes; dropped the claim that docs owe nothing.

<!-- fr:journal kind=finding scope=spec id=s-r3-resolved created=2026-11-20T07:41:57+00:00 state=fixed resolves=s-r3 -->
### s-r3-resolved · finding [fixed] · resolves s-r3: Merged row ci-shards-complete cites the renamed test and says every leg / 6 shards

§F amends ci-shards-complete: reword (one leg, 7 shards) and re-point its level to test_split_check_checks_the_one_leg.

<!-- fr:journal kind=finding scope=spec id=s-r4-resolved created=2026-11-20T07:41:57+00:00 state=fixed resolves=s-r4 -->
### s-r4-resolved · finding [fixed] · resolves s-r4: Test Plan names only the post-merge row; the three none rows have no Test Plan entry

Test Plan gains three pre-merge CI entries naming each none row and its tests, plus the amended rows.

<!-- fr:journal kind=finding scope=spec id=s-r5-resolved created=2026-11-20T07:41:57+00:00 state=fixed resolves=s-r5 -->
### s-r5-resolved · finding [fixed] · resolves s-r5: uv.lock moves more than the header under >=3.14

§A states the true uv lock expectation: header moves, below-3.14-only entries and wheels drop, no version changes.

<!-- fr:journal kind=finding scope=spec id=s-r6-resolved created=2026-11-20T07:41:57+00:00 state=fixed resolves=s-r6 -->
### s-r6-resolved · finding [fixed] · resolves s-r6: AGENTS.md names the durations-py<v>-shard-<n> artifact that R5 renames

§F names the artifact rename in the AGENTS.md recipe.

<!-- fr:journal kind=finding scope=spec id=s-r7-resolved created=2026-11-20T07:41:57+00:00 state=open resolves=s-r7 out_of_scope=true -->
### s-r7-resolved · finding [out-of-scope] · resolves s-r7: fr-spec-status.yml pins setup-python 3.12 and pip-installs fr v3.0.0

Pre-existing; the workflow installs fr v3.0.0 (floor 3.11) and tests nothing, so this change does not affect it.

<!-- fr:journal kind=finding scope=spec id=s-r8-resolved created=2026-11-20T07:41:57+00:00 state=open resolves=s-r8 out_of_scope=true -->
### s-r8-resolved · finding [out-of-scope] · resolves s-r8: Leftover 3.11 prose and a dead fallback in scripts/floors.py

Pre-existing prose that stays true, captured fixture data, and an optional dead-branch cleanup not caused by this change.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-20T07:42:00+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  ci-floor-python-3-14: none
  ci-scaffold-python-3-14: none
  ci-single-leg: none
  ci-single-leg-main-push: developer
row_kinds:
  ci-floor-python-3-14: none
  ci-scaffold-python-3-14: none
  ci-single-leg: none
  ci-single-leg-main-push: live
run_gate: developer
run_kind: none
```

<!-- fr:journal kind=finding scope=spec id=s-r7-resolved-2 created=2026-11-20T08:43:56+00:00 state=open resolves=s-r7 tracked_by=https://github.com/derio-net/super-fr/issues/1594 -->
### s-r7-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1594] · resolves s-r7: fr-spec-status.yml pins setup-python 3.12 and pip-installs fr v3.0.0

Filed at deliver as https://github.com/derio-net/super-fr/issues/1594.

<!-- fr:journal kind=finding scope=spec id=s-r8-resolved-2 created=2026-11-20T08:44:04+00:00 state=open resolves=s-r8 tracked_by=https://github.com/derio-net/super-fr/issues/1595 -->
### s-r8-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1595] · resolves s-r8: Leftover 3.11 prose and a dead fallback in scripts/floors.py

Filed at deliver as https://github.com/derio-net/super-fr/issues/1595.

<!-- fr:journal kind=finding scope=spec id=gate-round2-trigger-gap created=2026-11-20T08:45:25+00:00 state=open review_scope=out -->
### gate-round2-trigger-gap · finding [open] (reviewer: out of scope) · fr-goal has no honest round-2 trigger when a round-1 answer reopens the scope

The brainstorm gate accepts round 2 only as design-risk (forecast in round 1) or operator-request (operator asked in prose). In this run the brief put requires-python out of scope, round 1 forecast no second round, and a free-text round-1 answer moved the whole base to 3.14, which needed round 2. resolve refused design-risk; the run recorded operator-request with the operator's after-the-fact confirmation in the reason. Wanted: a trigger such as answer-reopened-scope, verified against the transcript. Out of scope: a gap in fr-goal's gate, not caused by this change.

<!-- fr:journal kind=finding scope=spec id=gate-round2-trigger-gap-resolved created=2026-11-20T08:45:55+00:00 state=open resolves=gate-round2-trigger-gap out_of_scope=true -->
### gate-round2-trigger-gap-resolved · finding [out-of-scope] · resolves gate-round2-trigger-gap: fr-goal has no honest round-2 trigger when a round-1 answer reopens the scope

A gap in fr-goal's brainstorm gate, met by this run, not caused by this change.

<!-- fr:journal kind=finding scope=spec id=gate-round2-trigger-gap-resolved-2 created=2026-11-20T08:46:04+00:00 state=open resolves=gate-round2-trigger-gap tracked_by=https://github.com/derio-net/super-fr/issues/1599 -->
### gate-round2-trigger-gap-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1599] · resolves gate-round2-trigger-gap: fr-goal has no honest round-2 trigger when a round-1 answer reopens the scope

Filed at deliver as https://github.com/derio-net/super-fr/issues/1599.

<!-- fr:journal kind=owed scope=spec id=owed-main-push-walk created=2026-11-20T08:50:54+00:00 -->
### owed-main-push-walk · owed · Walk ci-single-leg-main-push after #1593 merges

owed_key: row:ci-single-leg-main-push
On the first push to main after merge: ci.yml's split-check merges the durations-shard-* files and saves test-durations-<run_id>, and the Release workflow's shards run green on Python 3.14. Record it with fr acceptance set-status --id ci-single-leg-main-push --walk … --status walked --feature 2026-11-20-ci-single-python.
