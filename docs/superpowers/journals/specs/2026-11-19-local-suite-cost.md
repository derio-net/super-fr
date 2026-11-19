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

<!-- fr:journal kind=finding scope=spec id=sr-r1 created=2026-11-19T09:16:34+00:00 state=open review_scope=in -->
### sr-r1 · finding [open] (reviewer: in scope) · §2/§3.D misstate release.py: its shards and collect already clear addopts; only the one-process path does not

check/evidence: scripts/release.py:227,:301,:317 override addopts; :221/_run_staged_tests (via :1046-1050) does not.

<!-- fr:journal kind=finding scope=spec id=sr-r2 created=2026-11-19T09:16:34+00:00 state=open review_scope=in -->
### sr-r2 · finding [open] (reviewer: in scope) · split-check cannot prove scenarios ran

check/evidence: collect and shards shrink together under a shared filter (ci.yml:87,:142,:196-203).

<!-- fr:journal kind=finding scope=spec id=sr-r3 created=2026-11-19T09:16:34+00:00 state=open review_scope=in -->
### sr-r3 · finding [open] (reviewer: in scope) · load_gate_checks ignores unknown keys today; rev unstated

check/evidence: ci_evidence.py:73-98 reads only gate_checks; :101 unions base and HEAD.

<!-- fr:journal kind=finding scope=spec id=sr-r4 created=2026-11-19T09:16:34+00:00 state=open review_scope=in -->
### sr-r4 · finding [open] (reviewer: in scope) · R8 tests_log: none contradicts agent and fr-goal §5/§6

check/evidence: fr-phase-executor.md:139-148,:150-159; SKILL.md §5, §6.

<!-- fr:journal kind=finding scope=spec id=sr-r5 created=2026-11-19T09:16:34+00:00 state=open review_scope=in -->
### sr-r5 · finding [open] (reviewer: in scope) · Fingerprint misses config scopes, nested refs, reftable, worktrees, not-a-repo

check/evidence: git.py:193,:196,:234-241; conftest.py:266.

<!-- fr:journal kind=finding scope=spec id=sr-r6 created=2026-11-19T09:16:34+00:00 state=open review_scope=in -->
### sr-r6 · finding [open] (reviewer: in scope) · git-dir/toplevel lookups span ~20 call sites

check/evidence: commands/common.py:67, isolation/marker.py:52, artifacts/commit.py, settings/load.py, …

<!-- fr:journal kind=finding scope=spec id=sr-r7 created=2026-11-19T09:16:34+00:00 state=open review_scope=in -->
### sr-r7 · finding [open] (reviewer: in scope) · Clear-at-CLI-entry does not scope library callers

check/evidence: cli.py:69-79; fr_dispatch, runner adapters call fr as a library.

<!-- fr:journal kind=finding scope=spec id=sr-r8 created=2026-11-19T09:16:34+00:00 state=open review_scope=in -->
### sr-r8 · finding [open] (reviewer: in scope) · 928 → ≤464 mixes subprocesses and git calls; for-each-ref misattributed

check/evidence: git.py:184-242 issues no for-each-ref.

<!-- fr:journal kind=finding scope=spec id=sr-r9 created=2026-11-19T09:16:34+00:00 state=open review_scope=in -->
### sr-r9 · finding [open] (reviewer: in scope) · Session template built outside sandbox; copies share origin and LAST_BRIEF

check/evidence: conftest.py:238-266; test_fr_goal_shape.py:174-177; record_support.py LAST_BRIEF; test_run_cli.py _repo per branch.

<!-- fr:journal kind=finding scope=spec id=sr-r10 created=2026-11-19T09:16:34+00:00 state=open review_scope=in -->
### sr-r10 · finding [open] (reviewer: in scope) · R6 'reach' vs §3.E direct imports; changed helpers and untracked files missed

check/evidence: record_support.py is a helper, not test_*.py; git diff omits untracked files.

<!-- fr:journal kind=finding scope=spec id=sr-r11 created=2026-11-19T09:16:34+00:00 state=open review_scope=in -->
### sr-r11 · finding [open] (reviewer: in scope) · Default local run is partial after R5 yet unmarked

check/evidence: pyproject.toml:54; run_cmd.py:3273-3308.

<!-- fr:journal kind=finding scope=spec id=sr-r12 created=2026-11-19T09:16:34+00:00 state=open review_scope=in -->
### sr-r12 · finding [open] (reviewer: in scope) · R2, R3, R4, R10 lack rows; rows do not name their R

check/evidence: spec Verification.

<!-- fr:journal kind=finding scope=spec id=sr-r13 created=2026-11-19T09:16:34+00:00 state=open review_scope=in -->
### sr-r13 · finding [open] (reviewer: in scope) · --stage require preconditions and strict policy omitted

check/evidence: configure-main-protection.sh:67-69,:73-85,:93-96.

<!-- fr:journal kind=finding scope=spec id=sr-r14 created=2026-11-19T09:16:34+00:00 state=open review_scope=in -->
### sr-r14 · finding [open] (reviewer: in scope) · Agents procedure misses PINNED_AT_VERSION and the OpenCode mirror

check/evidence: agents/__init__.py:31-34; AGENTS.md.

<!-- fr:journal kind=finding scope=spec id=sr-r15 created=2026-11-19T09:16:34+00:00 state=open review_scope=in -->
### sr-r15 · finding [open] (reviewer: in scope) · q4's change fragment missing

check/evidence: q4-git-memo.

<!-- fr:journal kind=finding scope=spec id=sr-r16 created=2026-11-19T09:16:34+00:00 state=open review_scope=in -->
### sr-r16 · finding [open] (reviewer: in scope) · Durations refresh command would drop scenarios

check/evidence: AGENTS.md:436,:455; test_scenarios.py:200.

<!-- fr:journal kind=finding scope=spec id=sr-r17 created=2026-11-19T09:16:34+00:00 state=open review_scope=in -->
### sr-r17 · finding [open] (reviewer: in scope) · R7's reuse coverage implicit; match rule unstated

check/evidence: run_cmd.py:3191,:3600,:3442-3493.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-19T09:16:34+00:00 -->
### spec-review-1 · review · independent spec review: 17 findings, all in scope, all fixed in the spec

Reviewer fr-spec-reviewer raised sr-r1..sr-r17 (all in scope); each is fixed in the spec (see resolutions). Decisions q1-q10 honoured; q4's fragment added.

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-19T09:16:34+00:00 lens=tests step=spec-review -->
### lens-tests-1 · lens · shared fixtures are rewritten and tiers deselected: every level ref and scenario must still run somewhere

<!-- fr:journal kind=lens scope=spec id=lens-errors-1 created=2026-11-19T09:16:34+00:00 lens=errors step=spec-review -->
### lens-errors-1 · lens · a cache over git state can go stale silently: its invalidation edges need a whole-feature look

<!-- fr:journal kind=finding scope=spec id=sr-r1-resolved created=2026-11-19T09:16:34+00:00 state=fixed resolves=sr-r1 -->
### sr-r1-resolved · finding [fixed] · resolves sr-r1: §2/§3.D misstate release.py: its shards and collect already clear addopts; only the one-process path does not

§2 now names the exact paths; §3.D puts `-m ""` on `_run_staged_tests` and pins every command line.

<!-- fr:journal kind=finding scope=spec id=sr-r2-resolved created=2026-11-19T09:16:34+00:00 state=fixed resolves=sr-r2 -->
### sr-r2-resolved · finding [fixed] · resolves sr-r2: split-check cannot prove scenarios ran

§3.D adds a unit test parsing every CI/release pytest command line and asserting collect lists both scenario files; the row cites it, not split-check.

<!-- fr:journal kind=finding scope=spec id=sr-r3-resolved created=2026-11-19T09:16:34+00:00 state=fixed resolves=sr-r3 -->
### sr-r3-resolved · finding [fixed] · resolves sr-r3: load_gate_checks ignores unknown keys today; rev unstated

R8/§3.F: new `declared_tests_mode` read at HEAD; load_gate_checks unchanged; unknown keys stay ignored; only a bad `tests` value refused.

<!-- fr:journal kind=finding scope=spec id=sr-r4-resolved created=2026-11-19T09:16:34+00:00 state=fixed resolves=sr-r4 -->
### sr-r4-resolved · finding [fixed] · resolves sr-r4: R8 tests_log: none contradicts agent and fr-goal §5/§6

§3.F lists the conditional edits to the agent (:139, :147, :150) and fr-goal §5, §6, §8.

<!-- fr:journal kind=finding scope=spec id=sr-r5-resolved created=2026-11-19T09:16:34+00:00 state=fixed resolves=sr-r5 -->
### sr-r5-resolved · finding [fixed] · resolves sr-r5: Fingerprint misses config scopes, nested refs, reftable, worktrees, not-a-repo

§3.A: repo located by parsing .git/commondir without git; fingerprint covers system/global/XDG/local config and GIT_CONFIG_* env, packed-refs, remote HEAD and every consulted ref file; reftable, include/includeIf, worktreeConfig, GIT_DIR and not-a-repo are never cached; tests for worktree, global defaultRemote, fetch, set-head, remote add, packed-ref delete.

<!-- fr:journal kind=finding scope=spec id=sr-r6-resolved created=2026-11-19T09:16:34+00:00 state=fixed resolves=sr-r6 -->
### sr-r6-resolved · finding [fixed] · resolves sr-r6: git-dir/toplevel lookups span ~20 call sites

R1 narrowed to remote_name and remote_default_ref; other lookups moved to §4 out of scope.

<!-- fr:journal kind=finding scope=spec id=sr-r7-resolved created=2026-11-19T09:16:34+00:00 state=fixed resolves=sr-r7 -->
### sr-r7-resolved · finding [fixed] · resolves sr-r7: Clear-at-CLI-entry does not scope library callers

§3.A: a ContextVar cache that is None unless _FrGroup.invoke opened a scope; a test pins that a library call always runs git.

<!-- fr:journal kind=finding scope=spec id=sr-r8-resolved created=2026-11-19T09:16:34+00:00 state=fixed resolves=sr-r8 -->
### sr-r8-resolved · finding [fixed] · resolves sr-r8: 928 → ≤464 mixes subprocesses and git calls; for-each-ref misattributed

§2 states 926 git of 928 subprocesses and attributes ~490 to the two helpers; the pin is git subprocesses 926 → ≤500.

<!-- fr:journal kind=finding scope=spec id=sr-r9-resolved created=2026-11-19T09:16:34+00:00 state=fixed resolves=sr-r9 -->
### sr-r9-resolved · finding [fixed] · resolves sr-r9: Session template built outside sandbox; copies share origin and LAST_BRIEF

§3.B: template built under the same sandbox env through a shared helper; copies get their own origin.git (set-url), repaired worktree, rewritten marker, restored LAST_BRIEF; test_run_cli templates keyed per branch; tests for push isolation and sandboxed HOME.

<!-- fr:journal kind=finding scope=spec id=sr-r10-resolved created=2026-11-19T09:16:34+00:00 state=fixed resolves=sr-r10 -->
### sr-r10-resolved · finding [fixed] · resolves sr-r10: R6 'reach' vs §3.E direct imports; changed helpers and untracked files missed

R6 and §3.E now say the same: direct or through tests/ helpers, not through source modules; changed helpers and conftest.py select; untracked via ls-files --others; base defaults to remote_default_ref.

<!-- fr:journal kind=finding scope=spec id=sr-r11-resolved created=2026-11-19T09:16:34+00:00 state=fixed resolves=sr-r11 -->
### sr-r11-resolved · finding [fixed] · resolves sr-r11: Default local run is partial after R5 yet unmarked

R7: any session that is not the whole configured suite (incl. the default, which deselects scenarios) prints the advisory line; `-m ""` is the full local run; R8 states deliver still accepts a full local log (q10 is the operative decision over q8's wording).

<!-- fr:journal kind=finding scope=spec id=sr-r12-resolved created=2026-11-19T09:16:34+00:00 state=fixed resolves=sr-r12 -->
### sr-r12-resolved · finding [fixed] · resolves sr-r12: R2, R3, R4, R10 lack rows; rows do not name their R

Added row template-fixture-copies-independent (R2); each Verification line names its R; R3/R4/R10 carry a stated reason for no row and their evidence.

<!-- fr:journal kind=finding scope=spec id=sr-r13-resolved created=2026-11-19T09:16:34+00:00 state=fixed resolves=sr-r13 -->
### sr-r13-resolved · finding [fixed] · resolves sr-r13: --stage require preconditions and strict policy omitted

R9/§3.G: bypass → an app-pushed release → require; the strict up-to-date consequence is stated.

<!-- fr:journal kind=finding scope=spec id=sr-r14-resolved created=2026-11-19T09:16:34+00:00 state=fixed resolves=sr-r14 -->
### sr-r14-resolved · finding [fixed] · resolves sr-r14: Agents procedure misses PINNED_AT_VERSION and the OpenCode mirror

§3.F lists PINNED_AT_VERSION, sync-opencode.py for the agent mirror, and sync-opencode.py + sync-hermes.py for the skill.

<!-- fr:journal kind=finding scope=spec id=sr-r15-resolved created=2026-11-19T09:16:34+00:00 state=fixed resolves=sr-r15 -->
### sr-r15-resolved · finding [fixed] · resolves sr-r15: q4's change fragment missing

§3.H names .changes/perf-test-suite-cost.yaml, bump minor.

<!-- fr:journal kind=finding scope=spec id=sr-r16-resolved created=2026-11-19T09:16:34+00:00 state=fixed resolves=sr-r16 -->
### sr-r16-resolved · finding [fixed] · resolves sr-r16: Durations refresh command would drop scenarios

R10 names `-m ""` in the refresh command and AGENTS.md:436 changes with it; the tripwire test stays unmarked (R5, §3.D).

<!-- fr:journal kind=finding scope=spec id=sr-r17-resolved created=2026-11-19T09:16:34+00:00 state=fixed resolves=sr-r17 -->
### sr-r17-resolved · finding [fixed] · resolves sr-r17: R7's reuse coverage implicit; match rule unstated

R7 states the reuse consequence and a whole-line match; §3.E adds a test that a quoting log is accepted.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-19T09:16:40+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  ci-ok-required-on-main: developer
  fast-tier-advisory-and-refused: none
  git-answers-cached-per-invocation: none
  repo-declares-ci-tests-evidence: none
  scenario-tier-deselected-locally: none
  template-fixture-copies-independent: none
row_kinds:
  ci-ok-required-on-main: live
  fast-tier-advisory-and-refused: none
  git-answers-cached-per-invocation: none
  repo-declares-ci-tests-evidence: none
  scenario-tier-deselected-locally: none
  template-fixture-copies-independent: none
run_gate: developer
run_kind: candidate
```

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-19-local-suite-cost-p2 created=2026-11-19T09:19:42+00:00 -->
### phase-split-2026-11-19-local-suite-cost-p2 · decision · ask: the test diet (R2-R4) is its own ask, reviewable apart from the cache

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-19-local-suite-cost-p3 created=2026-11-19T09:19:45+00:00 -->
### phase-split-2026-11-19-local-suite-cost-p3 · decision · ask: the tiers and the tests gate (R5-R8, R10) are their own ask

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-19-local-suite-cost-p4 created=2026-11-19T09:19:48+00:00 -->
### phase-split-2026-11-19-local-suite-cost-p4 · decision · ask: R9 is an operator-only ruleset change (manual)

<!-- fr:journal kind=decision scope=spec id=tier-2026-11-19-local-suite-cost-p1 created=2026-11-19T09:19:52+00:00 -->
### tier-2026-11-19-local-suite-cost-p1 · decision · hard: a correctness cache over git state on the default-ref path every merge, archive and dispatch check relies on

<!-- fr:journal kind=decision scope=spec id=tier-2026-11-19-local-suite-cost-p3 created=2026-11-19T09:19:55+00:00 -->
### tier-2026-11-19-local-suite-cost-p3 · decision · hard: changes what deliver accepts as tests evidence (a gate) and the agents artifact kind
