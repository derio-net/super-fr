<!-- fr:journal-schema=4 -->
# Journal: 2026-11-14-acceptance-local-status

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-14T09:14:53+00:00 input=true -->
### operator-brief · discovery · Operator brief: issue #1453 and goal text

Goal: Implement derio-net/super-fr#1453: a `local` acceptance status for rows verified by automated tests in a repo with no CI. Context: the gap was found on a live quiet-placement walk whose run is held at deliver until this ships, so deliver must be able to accept `local` under ci none. Take it to a draft PR, wait for CI, report; do not mark it ready or merge.

Issue title: acceptance: a `local` status for rows verified by automated tests in a repo with no CI

## Problem

In a repo with no CI (`ci: none` chosen in the question round), a row verified by a passing, automated unit test can only be `unwired`. `unwired` is debt, so `deliver` refuses:

```
row <id> — unwired, neither gated nor tracked
  fix: fr verification set --run <run> --row <id> --gate tester --reason "<why it waits for a live walk>"
```

The only fix fr offers is a post-merge tester gate with a "live walk" reason. That reason is false (the row does not wait for a walk; its test exists and passes), and it adds a gate the operator did not ask for. Under quiet (`forge.issues: off`) tracking the row by an issue is closed too, and `ci` or `manual` would misstate how the row is verified. So a repo with no CI cannot deliver even the smallest unit-tested feature honestly.

Found on the Quiet walk of spec `2026-11-04-repo-feature-settings` (Test Plan step 1), fr `7.0.0-rc.5`.

## Proposal: a `local` status

`local` means: automated, and runs on demand on any checkout, but no CI runs it. It sits beside `walked`:

| | `walked` | `local` (new) | `ci` |
|---|---|---|---|
| What it proves | it ran successfully at least once | an automated test anyone can run at any time | it runs on every PR |
| Evidence | a recorded walk | a test level ref, plus a passing suite log covering the tree | CI gate checks |
| Debt? | no | no | no |

Rules it needs:

- **Earned, not declared.** A row moves to `local` only with a test-level ref and a recorded local suite log covering that tree. `deliver`'s `evidence: {tests: <log>}` already checks that the log is newer than every code path on a clean committed tree; `deliver` accepts `local` only when that check holds.
- **The referenced test must exist.** A level ref naming a missing file or test is refused.
- **It goes stale like any evidence.** When later work changes the code with no fresh log, `fr acceptance check` flags the row.
- **CI promotes it.** When the repo gains CI, a `local` row is something to promote to `ci`.
- **`deliver`'s refusal offers it.** Under `ci: none`, the leftover-row refusal suggests `local`, not only a tester gate.

`local` is not in `DEBT_STATUSES`. It is a new value of a row's status, so the acceptance-fragment kind needs the stamp bump, migration and validator the artifact-versioning rule asks for.

## Acceptance

In a repo with no CI, a feature whose rows are covered by passing local tests delivers with those rows `local`, with no tester gate and no issue; `fr acceptance status`, `fr debt`, the report and the digest list `local` rows and do not count them as debt.

<!-- fr:journal kind=decision scope=spec id=q1-earning created=2026-11-14T09:14:53+00:00 decided_by=operator -->
### q1-earning · decision · Q1: a row earns local at deliver

Operator chose 'Bound at deliver': any writer may set local when level refs resolve; deliver refuses unless its own tests evidence is a verified local log (or reuse of one) and stamps each row with tree and date. decider: operator

<!-- fr:journal kind=decision scope=spec id=q2-staleness created=2026-11-14T09:14:53+00:00 decided_by=operator -->
### q2-staleness · decision · Q2: stale when its test files change

Operator chose 'Its test files changed': stale when a file named by the row's level refs changed since the stamp. decider: operator

<!-- fr:journal kind=decision scope=spec id=q3-severity created=2026-11-14T09:14:53+00:00 decided_by=operator -->
### q3-severity · decision · Q3: a stale local row counts as debt

Operator chose 'Counts as debt' (not the recommended warning): debt whatever its status, like a contested row, until a fresh stamp. decider: operator

<!-- fr:journal kind=decision scope=spec id=q4-with-ci created=2026-11-14T09:14:53+00:00 decided_by=operator -->
### q4-with-ci · decision · Q4: refuse new local with CI, existing local is debt

Operator chose 'Refuse new, debt existing': setting local refused while CI exists; existing local rows count as debt, listed 'promote to ci'. decider: operator

<!-- fr:journal kind=decision scope=spec id=q5-verify created=2026-11-14T09:14:53+00:00 decided_by=operator -->
### q5-verify · decision · Q5: candidate strategy with a scenario

Operator chose 'candidate + scenario': unit tests in CI plus tests/scenarios/acceptance-local-status.sh. decider: operator

<!-- fr:journal kind=decision scope=spec id=q6-post-merge created=2026-11-14T09:14:53+00:00 decided_by=operator -->
### q6-post-merge · decision · Q6: post-merge row gated tester

Operator chose 'Row, gate tester': a verify: live row for the held quiet walk, gated tester. decider: operator
