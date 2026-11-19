<!-- fr:journal-schema=4 -->
# Journal: 2026-11-19-local-suite-cost

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-19T09:03:42+00:00 input=true -->
### operator-brief · discovery · Operator brief and issue #1555, verbatim

Operator goal (as typed): derio-net/super-fr#1555 — investigate and fix the cost of the local full suite (15,182 tests, ~5.2 worker-hours per .test_durations; on 2026-11-18 three wave-22 batch sessions each sat 4.5 h+ on a local full suite). Two tracks, both in the issue: (1) profile the heaviest test files and make them lighter (shared fixtures, in-process CLI calls, a separate scenario tier, dropping redundant cases), with measured savings per file; (2) design a sound scoped local run for deliver's tests evidence, with CI's full suite staying the merge gate. Track 2 changes a gate, so it is an operator decision for your question round. Note: this host is loaded by the wave-22 batch sessions right now, so profile per file (pytest --durations on single files), not by running the whole suite repeatedly.

Issue #1555 — The local full suite costs ~5 worker-hours: make heavy tests lighter and design a scoped local run with CI as the full gate

## Problem

The local full suite has become the slowest step of every fr-goal and fr-debugging run. `deliver` needs a fresh full-suite log as `tests` evidence. CI runs the same suite again in 7 shards on every PR, so the local run only stops a red push, and it costs hours.

Measured from the committed `.test_durations` (refreshed 2026-11-15):

- **15,182 tests, 18,855 worker-seconds (about 5.2 worker-hours).** AGENTS.md still says "~150 s vs ~870 s on a 12-core host". That figure is long out of date.
- With 12 free workers, a full run takes about 26 minutes. On a loaded host, `-n auto` starts only 2 workers (the gh#1225 rule), so one run takes about **2.6 hours with nothing else running**.
- Observed 2026-11-18: three batch sessions (wave 22) each ran a full suite at the same time on one host. Each suite took **more than 4.5 hours**, and every batch stayed in flight for the whole time. One session also left an orphaned duplicate suite running in its worktree. Nothing noticed, and that duplicate doubled the load.
- **The cost sits in a small part of the suite.** The 3,193 tests that take over 1 s account for 89% of the time, and the slowest 1% account for 28%. The slowest files:

  | File | Seconds |
  |---|---|
  | `tests/unit/test_run_cli.py` | 1368 |
  | `tests/integration/test_scenarios.py` | 1263 |
  | `tests/unit/test_run_question_rounds.py` | 463 |
  | `tests/unit/test_record_review_fixes.py` | 450 |
  | `tests/unit/test_release_script.py` | 449 |
  | `tests/integration/test_install_sh.py` | 445 |
  | `tests/unit/test_record_apply.py` | 436 |
  | `tests/unit/test_exit_label_sync_points.py` | 397 |
  | `tests/unit/test_deliver_pr_body.py` | 367 |
  | `tests/unit/test_forge_quiet_pr_body.py` | 354 |
  | `tests/unit/test_gate_cmd.py` | 332 |
  | `tests/unit/test_gatebackfill_closes.py` | 325 |

  Most of these start `fr` as a subprocess, or build git repositories and install trees in each test.

## What this issue asks for

An investigation that ends in a decision with numbers. Two tracks:

1. **Make the heavy tests lighter.** Profile the top files: how much of each test's time is setup (git init, commits, install trees, subprocess start-up) and how much is the assertion itself. For each file, propose a remedy and estimate its saving, for example:
   - build a fixture once per module or session and copy it;
   - call the CLI in-process instead of starting a subprocess;
   - move the end-to-end scenarios to a tier of their own;
   - remove duplicate or redundant parametrized cases.
2. **A scoped local run, with CI as the full gate.** Selecting tests from the import graph is unsound here, because many tests reach the code by starting `fr` as a subprocess, and no import graph sees that link. Design a sound scoped run, for example the touched packages' tests plus a fixed smoke set. Also design how `deliver`'s `tests` evidence accepts it while CI's full suite stays the merge gate. This changes a gate, so it needs a spec and the operator's decision.

Also: update the outdated timing in AGENTS.md, and refresh `.test_durations`.

## Related

- #1340: `ci.yml` under 4 minutes of wall clock. That covers CI, not the local run.
- #1238: the release's staged suite.
- #1225, #1292, #1296, #1223: earlier fixes for symptoms of load.

<!-- fr:journal kind=decision scope=spec id=q1-tests-evidence created=2026-11-19T09:03:42+00:00 decided_by=operator -->
### q1-tests-evidence · decision · Track 2: CI is the suite evidence

Operator chose: the repo declares `tests: ci` as its default; deliver cites CI's full suite; local phase runs are a fast advisory tier, never evidence (over a new `tests: scoped` log and a coverage-map selection). decider: operator.

<!-- fr:journal kind=decision scope=spec id=q2-required-ci created=2026-11-19T09:03:42+00:00 decided_by=operator -->
### q2-required-ci · decision · ci-ok becomes required on main in a back-loaded manual phase

Operator chose: a [manual] last phase runs configure-main-protection.sh --stage bypass then --stage require (over keeping it a checklist line or filing a follow-up). decider: operator.

<!-- fr:journal kind=decision scope=spec id=q3-scenario-tier created=2026-11-19T09:03:42+00:00 decided_by=operator -->
### q3-scenario-tier · decision · Scenarios get their own tier, CI runs it

Operator chose: a `scenario` marker deselected by default locally; CI runs it; test_install_sh.py joins the tier. decider: operator.

<!-- fr:journal kind=decision scope=spec id=q4-git-memo created=2026-11-19T09:03:42+00:00 decided_by=operator -->
### q4-git-memo · decision · Per-invocation git answer cache in fr is allowed

Operator chose: memoize read-only default-remote/ref, git-dir and toplevel answers per invocation, never stale after fr's own writes; ships with a change fragment (over test-side fixes only). decider: operator.

<!-- fr:journal kind=decision scope=spec id=q5-pruning created=2026-11-19T09:03:42+00:00 decided_by=operator -->
### q5-pruning · decision · Merge cases only when the claim survives

Operator chose: template fixtures, and cases merged only when another test asserts the same claim on the same path; each journaled with its covering test; no acceptance level ref loses its test. decider: operator.

<!-- fr:journal kind=decision scope=spec id=q6-verify-gate created=2026-11-19T09:03:42+00:00 decided_by=operator -->
### q6-verify-gate · decision · candidate strategy, developer gate

Operator chose: the shape's candidate walk, gate developer (over gate tester). decider: operator.

<!-- fr:journal kind=decision scope=spec id=q7-ci-shards created=2026-11-19T09:03:42+00:00 decided_by=operator -->
### q7-ci-shards · decision · Scenarios stay in CI's shards

Round 2, from the finding that CI overrides addopts (ci.yml:87/142): operator chose to keep scenarios in the balanced shards rather than a ~1263 s job of their own. decider: operator.

<!-- fr:journal kind=decision scope=spec id=q8-phase-tests created=2026-11-19T09:03:42+00:00 decided_by=operator -->
### q8-phase-tests · decision · Phases run the fast tier; only deliver cites CI

Round 2, from the executor's existing tests: ci mode: operator chose no CI wait per phase; phases return tests_log: none with the fast tier's summary; deliver owes tests: ci. decider: operator.

<!-- fr:journal kind=decision scope=spec id=q9-fast-tier created=2026-11-19T09:03:42+00:00 decided_by=operator -->
### q9-fast-tier · decision · Fast tier = changed + import-touched + smoke

Round 2: operator chose a --fr-scope conftest option selecting changed test files, files importing touched modules and a smoke set, scenarios excluded, honest about being partial. decider: operator.

<!-- fr:journal kind=decision scope=spec id=q10-local-logs created=2026-11-19T09:03:42+00:00 decided_by=operator -->
### q10-local-logs · decision · Accept full local logs, refuse marked advisory ones

Round 2, from the finding that nothing marks a log partial: operator chose that the fast tier prints `fr-scope: advisory — not deliver evidence` and fr refuses any tests log carrying it; a local full log stays valid. decider: operator.

<!-- fr:journal kind=decision scope=spec id=gate-question-rounds-brainstorm created=2026-11-19T09:03:43+00:00 -->
### gate-question-rounds-brainstorm · decision · Operator gate `brainstorm` took two question rounds

Trigger: design-risk. Round 1's evidence-model choice decided which sub-decisions exist (phase behaviour, fast-tier contents, local-log policy) and the scenario answer needed checking against CI's addopts override.
