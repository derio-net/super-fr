# Architecture review of `packages/*/src` (2026-11-16)

Issue: derio-net/super-fr#1318. Spec: `docs/superpowers/specs/2026-11-16-architecture-review-sweep-design.md`
(R1–R7). This report is stage 1 of #1318 (the review) and records which part of stage 2
(the sweep) landed in the same PR. Everything below is this repository's own code; no
host, org or repo outside `derio-net` appears in it.

## 1. Scope and method

**Commit.** Every file:line below was read at `ab3b3a193168af123a1b2d7946fca0571869d4ee` on
`feat/gh-1318`. That commit holds the phase 1 changes of this PR (G01, R01, R02, R03 and the
line budget, commits `dec084335` to `c57126798`) and no other code change; the commits after
`c57126798` touch only the run cursor and the plan journal.

**Inputs reconciled.** Three reviews were posted on #1318, each pinned to a different commit:

- the full engineering audit, at `f0a45b5b` (v8.0.0): findings F01–F09 and one unverified
  risk, two `fr run` commands racing on one cursor;
- the duplication and seams supplement, at `a4281f85` (v8.0.3): clusters R01–R07, the guard
  correction G01, and a table of apparent duplicates that encode different policies;
- the bug index, at `33e12d67`: F01–F04 tracked as #1499, #1500, #1419 and #1501.

The brainstorm of this run added four read-only reviews of the five largest modules. They
were stored unverified (plan journal `review-run-cmd`, `review-triage-batch`,
`review-isolation-local`, `review-plan-ops`). No line range, count or claim from any of
these inputs is repeated here without being re-read at the commit above; where the code
differs, this report says what the input said and what the code shows.

**What was read and run.**

- The source cited in each row, opened at the line given.
- `wc -l` for module sizes; `grep -n "^def \|^class "` for every line range in section 5.
- Two short AST scripts, kept outside the repository: one counts direct PyYAML load calls
  and stdlib `subprocess` calls whose literal argv starts with `"git"` under the tracked
  `packages/*/src` files; the other counts, per module, the test files that import it, its
  `from <module> import` statements and the names they take, and the
  `monkeypatch.setattr(<module alias>, "<name>")` calls in `tests/`.
- `gh issue list --search` reads, one search per finding (section 7).
- No test was run for the review itself; the phase's own tests are listed in the PR.

**Limits.** No defect was reproduced again: F01–F09 and the race are re-checked by reading
the code, not by executing the audit's reproductions. F09's advisory ranges are the audit's;
the advisory records were not fetched again, only the lock's versions were compared. Counts
are syntax inventories, not runtime measurements. `.test_durations` is used as recorded
weights only, never as current wall-clock time.

**The issue's first open question** (one deep session or reviewers by area): reviewers by
area plus one reconciliation pass. The four module reviews and the supplement's area passes
found the material; their unverified output needed this reconciliation, which corrected
several counts (section 5) and found three copies the reviews missed (R05, R06, and a
naive-as-UTC pair, section 3).

## 2. Status of earlier findings

### 2.1 The audit (F01–F09 and the cursor race)

F01–F04 are behaviour fixes outside #1318's refactor lane: they change what the code does,
so each gets its own fix PR with its own contract and regression test. This PR changes none
of the behaviour they describe.

| Item | Earlier commit | Status now | Tracking |
|---|---|---|---|
| F01 failed dedup lookup permits another dispatch | `f0a45b5b` | present: `fr_dispatch/__init__.py:514-518` catches the lookup failure and sets `existing = set()` | #1499 (behaviour fix) |
| F02 cursor write destroys the last valid state | `f0a45b5b` | present: `fr/run/model.py:600`, `path.write_text(dump_run_state(state))` | #1500 (behaviour fix) |
| F03 branch slugs alias | `f0a45b5b` | present: `fr/isolation/types.py:99`, `branch.replace("/", "__")` | #1419 (behaviour fix) |
| F04 cncd payload follows symlinks | `f0a45b5b` | present: `fr_cncd/runner.py:86`, every child with `p.is_file()` is read | #1501 (behaviour fix) |
| F05 CLI steps unbounded | `f0a45b5b` | present: `commands/run_cmd.py:6489-6491`, `subprocess.run(command, shell=True, cwd=..., capture_output=True, text=True)` with no `timeout`; the full stdout goes into the cursor (`run_cmd.py:6493-6495`, `run_cmd.py:1069`) | ISSUE_F05 |
| F06 installed dependencies differ from the tested lock | `f0a45b5b` | present: `scripts/install.sh:879-881` and `901-903` run `uv tool install --force` on `packages/fr` with no lock or constraint file; `packages/fr/pyproject.toml:6-12` gives lower bounds only; `install.sh:1080` installs `@devcontainers/cli` with no version | ISSUE_F06 |
| F07 edit hook loses its decision without `jq` | `f0a45b5b` | present: `plugins/super-fr/hooks/fr-isolation-required.sh:26` and `:37` call bare `jq`; the comment at `:32-34` states the fail-open | ISSUE_F07 |
| F08 policy concentrated in large command modules | `f0a45b5b` | present: sizes in section 5; this PR adds the line budget and the decomposition plan | this PR (budget), section 5 issues |
| F09 lock holds advisory-affected versions | `f0a45b5b` | present: `packages/fr-opencode-plugin/bun.lock:294` `glob@13.0.5`, `:532` `glob@10.5.0`, `:360` `minimatch@10.2.5`, `:560` `minimatch@9.0.9`; the advisories were not re-fetched | ISSUE_F09 |
| Cursor race (two `fr run` commands on one cursor) | `f0a45b5b` | present, not reproduced: `run_cmd.py:369-374` saves whatever state the command loaded; no `fr run` path takes a lock (`fr/file_lock.py` is used only by `fr/triage/operation_lock.py`) and nothing compares the cursor on disk before the write | ISSUE_RACE |

### 2.2 The supplement (G01, R01–R07, and its "preserve" table)

| Item | Earlier commit | Status now | Tracking |
|---|---|---|---|
| G01 import guard reads a line regex | `a4281f85` | landed in this PR, `dec084335` and `c57126798`; guards `test_import_direction.py::test_import_nodes_read_every_spelling` (`:301`) and `::test_soft_point_violations_fire_on_planted_sources` (`:325`) | this PR |
| R01 gate annotations copy the vocabulary | `a4281f85` | landed in this PR, `95cdcbd0c` and `c57126798`; `fr/gates.py:18` adds `PostMergeGate`; guards `test_gate_vocabulary.py::test_annotations_derive_from_the_vocabulary` (`:136`) and `::test_a_divergent_literal_is_reported` (`:147`) | this PR |
| R02 the cloud adapter copies `SessionStatus` | `a4281f85` | landed in this PR, `2a3133051`; guards `test_import_direction.py::test_cloud_status_is_the_protocol_type` (`:339`), `::test_a_redeclared_status_literal_is_reported` (`:367`) and `test_acceptance_status_labels.py::test_every_status_has_a_label_and_no_label_is_orphaned` (`:11`) | this PR |
| R03 four identical aware-timestamp readers | `a4281f85` | landed in this PR, `0fa461055`; `fr/triage/timestamps.py:15`; guard `test_triage_timestamps.py::test_only_the_owner_holds_that_body` (`:101`) with planted copies at `:87` and `:91` | this PR |
| R04 two `_StrictLoader` classes | `a4281f85` | present: `fr/artifacts/structure.py:46` and `fr/harness/model.py:153`; `fr/lenses/model.py:18` imports the private artifact loader and uses it at `:129` | ISSUE_R04 |
| R05 copied record-placement test helpers | `a4281f85` | present, and wider than reported: eleven `_record_file` copies, not eight (section 3, C6-1) | ISSUE_R05 |
| R06 copied `_hermetic_git` fixtures | `a4281f85` | present, and wider than reported: five same-policy copies, not four (section 3, C6-2) | ISSUE_R06 |
| R07 orchestration in five large modules | `a4281f85` | present: `wc -l` gives 8,862 / 7,334 / 3,164 / 2,545 / 2,130 lines (section 5); `triage_batch_cmd.py` is 9 lines shorter than the supplement's 7,343 because R03 removed `_parse_at` | section 5 issues |
| Inventory: direct PyYAML loads | `a4281f85` | unchanged: 130 calls in 87 files (125 `safe_load`, 5 `load`); 416 tracked source files, 142,519 physical lines (the supplement's 415 files plus `fr/triage/timestamps.py`) | #1286 |
| Inventory: git-first subprocess calls | `a4281f85` | unchanged: 40 stdlib `subprocess` calls whose literal argv starts with `"git"`, in 27 files | no work: scoped by design (section 3, C3) |
| Preserve: default-branch and root readers | `a4281f85` | re-checked, kept (section 4) | none owed |
| Preserve: atomic writers | `a4281f85` | re-checked, kept (section 4) | none owed |
| Preserve: marker and workspace checks | `a4281f85` | re-checked, kept (section 4) | none owed |
| Preserve: schema numbers | `a4281f85` | `FACTS_SCHEMA` kept (section 4); `RECORD_SCHEMA_VERSION` is a real, guarded duplicate (C1-4) | none owed |
| Preserve: VK and old-artifact readers | `a4281f85` | re-checked, kept (section 4) | none owed |

## 3. Findings by category

Severity uses the audit's scale: P0 emergency, P1 release blocker, P2 next maintenance
cycle, P3 planned maintainability work. "Disagree today" says whether the copies already
give different answers.

### Category 1 — duplicated contracts

**C1-1 Gate annotations (R01).** P3. Defined in `fr/gates.py:15-22`; read by
`fr/triage/model.py` (`ExitBlock.gates`), `fr/spec.py` (`StepGate`, the step tag pattern),
`fr/ops/stub.py` (`_LEAD_RE`) and `fr/verification/model.py` (the strategy gate field).
Disagree today: no. Fix: derive each from `Gate`/`PostMergeGate`. Guard:
`test_gate_vocabulary.py:136`, `:147`. Files: the five above. Tracking: landed in this PR.

**C1-2 Session statuses (R02).** P3. `SessionStatus` in `fr_dispatch/protocols.py`;
`FrStatus` was a third copy in `fr_claude_cloud/mailbox.py`. Disagree today: no. Fix:
`FrStatus = SessionStatus`. `BoardStatus` stays (section 4). Guard:
`test_import_direction.py:339`, `:367`; `STATUS_LABEL` coverage at
`test_acceptance_status_labels.py:11`. Tracking: landed in this PR.

**C1-3 Gate list in `fr journal add --gate` help.** P3. `commands/journal_cmd.py:219`
spells the six gates by hand, in `Gate`'s order (`fr/gates.py:15`). Spec Design C listed it
as a duplicate to keep; re-read, it encodes no policy of its own (it is help text for the
same closed set), so it moves here. Disagree today: no. Fix: build the string from
`get_args(Gate)`. Guard: a test that the option's help names every member of `GATES`.
Files: `commands/journal_cmd.py`. Tracking: ISSUE_LEFTOVERS.

**C1-4 Record schema number.** P3. `RECORD_SCHEMA_VERSION = 12` at `fr/record/model.py:69`
and the record kind's `current_version=12` at `fr/artifacts/registry.py:593`. Disagree
today: no. Guard already present: `test_record_schema.py:185` and four migration tests
assert the two are equal. Fix: none required; a lazy getter is optional, with an
import-cycle review, as the supplement says. Tracking: none owed (guarded).

### Category 2 — duplicated mechanisms

**C2-1 Aware-timestamp readers (R03).** P3. Owner `fr/triage/timestamps.py:15`. Tracking:
landed in this PR.

**C2-2 Two other aware readers with a different body.** P3. The R03 scan finds copies, not
other implementations of the contract.
- `_pr_time` (`commands/triage_batch_cmd.py:2043-2049`) reads `record.get("createdAt")`,
  applies `str()`, and returns `None` for missing, unparseable or naive: the same contract
  as `parse_aware` on the value. Disposition: replace its body with
  `parse_aware(str(stamp) if stamp else None)` in the `triage_batch_cmd.py` slice
  (ISSUE_TRIAGE_SLICES); callers at `:2197` and `:2255` are unchanged.
- `_created_since` (`fr/triage/collect.py:1106-1114`) is a predicate, not a reader: unknown
  or naive creation counts as "yes". Its read is `parse_aware`'s contract followed by
  `created is None → True`. Disposition: read through `parse_aware`, keep the predicate.
  Tracking: ISSUE_LEFTOVERS.

**C2-3 Naive-as-UTC readers copy each other.** P3, new. `_instant`
(`fr/usage/compare.py:173-178`) and `_parse` (`fr/debt/engine.py:310-317`) both replace `Z`,
parse, return `None` on `ValueError` and read a naive time as UTC; `fr/usage/backfill.py:165-169`
inlines the same rule. These are not `parse_aware` (a naive value becomes UTC, not
`None`, section 4), but they are one contract written three times. Disagree today: no, on
string input (`_instant` has no `None` guard; its callers pass strings). Fix: one
`parse_as_utc` beside the usage or debt engine; guard: the R03 body scan, pointed at it.
Tracking: ISSUE_LEFTOVERS.

**C2-4 The spec and plan journal read in `plan_ops.py`.** P3. `_spec_journal_entries`
(`plan_ops.py:2129-2146`) and `_refactor_justifications` (`plan_ops.py:2519-2536`) both
resolve the journal path, return empty when the file is absent and swallow
`JournalParseError`. Disagree today: no. Fix: one `_journal_entries(root, scope, slug)`
when the self-review half moves (section 5.4). Tracking: ISSUE_PLANOPS_SLICES.

**C2-5 Strict duplicate-key loader (R04).** P3. `fr/artifacts/structure.py:46`,
`fr/harness/model.py:153`; `fr/lenses/model.py:18` reaches the private one. Their error
translation differs on purpose (supplement); the detector is the same. Fix: one detector in
a dependency-light YAML module, each reader keeping its errors. Guard: single-owner AST
check plus a dependency check. Files: the three above. Shares `structure.py` with #1286,
which keeps the backend switch. Tracking: ISSUE_R04.

### Category 3 — seam violations

No current violation was found. Each seam and its guard:

| Seam | Guard |
|---|---|
| `fr` imports no sibling package outside `_SOFT_POINTS` | `test_import_direction.py::test_fr_imports_no_siblings` (`:56`), `::test_soft_points_are_guarded` (`:86`), syntax-tree reader since G01 |
| `fr_dispatch` imports no adapter | `test_import_direction.py::test_fr_dispatch_never_imports_fr_cncd` (`:94`), `::test_fr_dispatch_never_imports_fr_herdr` (`:132`), `::test_fr_dispatch_never_imports_fr_claude_cloud` (`:183`); adapters among themselves `::test_adapters_never_import_each_other` (`:106`) |
| git only through `gitseam` in batch modules | `test_forge_adapter_batch_ops.py::test_batch_modules_reach_git_only_through_the_declared_worktree_methods` (`:524`), `::test_the_git_seam_runs_git_and_declared_commands_only` (`:457`); scoped to the globs `triage/batch*.py` and `commands/triage_batch*.py` (`:380-383`) |
| forge writes only through the adapter | `test_tripwire_forge_adapter.py::test_no_forge_call_bypasses_the_adapter` (`:93`); batch modules `test_forge_adapter_batch_ops.py::test_no_batch_module_reaches_a_forge_cli_or_triage_forge` (`:427`) |
| artifact kinds only in the registry | `test_tripwire_artifact_kinds.py::test_the_registry_is_the_only_enumeration` (`:97`) |
| the pure driver pass reaches no runner, git, process or clock | `test_triage_batch_drive.py::test_the_pass_module_reaches_no_runner_git_process_or_clock` (`:700`), one path only |

Two gaps, both scoped by design rather than violations: the 40 git-first `subprocess` calls
outside the batch globs have no global guard (the supplement advises against a universal
git abstraction, and this report agrees); and the pure-pass guard names one file, so a
module split out of `batch_drive.py` is unguarded until the guard becomes a
`batch_drive*.py` glob in the same change (section 5.2).

**C3-1 `triage_kanban_cmd.py` imports from `triage_batch_cmd`.** P3. The module docstring
(`commands/triage_kanban_cmd.py:7-8`) says it never imports from `triage_batch_cmd`, so the
import stays one-way; `:355` does, inside `local_ci_none`, and `triage_batch_cmd.py:64` and
`:85-86` import the kanban module at module level. The function-local import avoids an
import-time cycle today. Tracking: #1174 (the import cycle), no second issue.

### Category 4 — oversized modules

**C4-1 Five modules mix CLI, policy and effects (R07, F08).** P3. Sizes and the plan are in
section 5. Guard: `tests/unit/test_tripwire_module_budget.py` (landed in this PR).
Tracking: section 5 issues.

### Category 5 — dead or vestigial code

Proved removable: nothing. A name with no caller found by grep is not proof, so each
candidate is stated with its evidence:

- `plan_ops.tick` and `plan_ops.complete_phase` (`plan_ops.py:671`, `:724`) have no caller
  under `packages/` (grep for both names and for every `plan_ops` importer: `migrate.py`,
  `commands/plan_cmd.py:17-25`, `apply_cmd.py`, `undispatch_cmd.py`,
  `fr_dispatch/__init__.py`, `record/apply.py`, `record/gates.py`, `run_cmd.py:5014` use
  other names). Tests import them 18 and 15 times. Removing them changes a tested surface
  and the write order (design 6.4). Tracking: ISSUE_DESIGN_D.
- VK-era code: the live adapter compatibility is gone; `fr/artifacts/plan_vk_version.py` is
  the operator-authorised archive repair. Kept (section 4).
- Frozen legacy readers (`fr/run/legacy.py`, `fr/record/legacy.py`,
  `fr/acceptance/legacy.py`) serve registered migrations and are hash-pinned
  (`fr/run/legacy.py:167`). Kept.

### Category 6 — test-suite duplication and cost

**C6-1 Record-placement helpers (R05).** P3. `_record_file` is defined eleven times:
`test_migration_record_contract.py:63`, `_delegated.py:27`, `_exit_gates.py:29`,
`_input_unconfirmed.py:26`, `_questions.py:34`, `_shape.py:35`, `_status_split.py:43`,
`_visual.py:27`, `test_record_acceptance_v8.py:138`, `test_record_amendments.py:41`,
`test_record_lens.py:169`. The supplement listed eight; the last three were added after its
commit. Each writes `docs/superpowers/runs/r1.records/<stem>.yaml`; text defaults and stems
differ on purpose. Fix: `tests/unit/record_helpers.write_record(root, text, *, stem=...)`
with explicit historical payloads. Guard: a scoped AST check for a copied placement body.
Recorded weight in `.test_durations`: 115 test entries, 115.3 s in total, for these eleven
modules. Tracking: ISSUE_R05.

**C6-2 `_hermetic_git` fixtures (R06).** P3. The same autouse fixture (set
`GIT_CONFIG_GLOBAL` to the null device and `GIT_CONFIG_NOSYSTEM=1`) is in
`test_gatebackfill_candidates.py:28`, `_delivery.py:31`, `_discharged.py:31`,
`_render.py:19`, and `test_merge_evidence.py:31` (which spells the path `os.devnull`). Two
more fixtures of the same name in `test_isolation_branch_classify.py:36` and
`test_isolation_preserve.py:41` set `HOME` and a per-test config directory: a different
policy, not part of this cluster. Fix: one fixture module, activated explicitly in the five
modules. Guard: AST check that they activate it and hold no copy. Recorded weight: 246
entries, 500.7 s in total, for the five modules; the fixture does not change it. Tracking:
ISSUE_R06.

**C6-3 Expensive single tests (recorded weights only).** The heaviest recorded entries are
`test_dispatch_lint_corpus.py::test_the_dispatch_gate_scores_zero_on_this_repos_own_plans`
(294.2 s), `tests/integration/test_scenarios.py::test_fr_ops_gate_stage` (125.9 s) and
`test_validate_artifacts.py::test_this_repos_own_artifacts_are_structurally_valid`
(122.4 s), out of 15,182 entries. These are profiling targets, not measured current costs.
No issue is filed: no cause was established.

## 4. Duplicates to keep

Each pair below looks like a duplicate and is not: the readers answer different questions.

- **Default-branch readers.** `fr/git.py:179` (`remote_default_ref`) returns a
  remote-tracking ref or `None`/`GitRefusal` and never touches the network; it falls back
  to `main/master/trunk/develop` remote-tracking refs. `fr/triage/gitseam.py:465`
  (`Checkout.default_branch`) repairs a missing `origin/HEAD` with
  `git remote set-head origin --auto` (a network call) and raises. `isolation/local.py:3001`
  (`_resolve_default_branch`) asks the forge adapter and falls back to `main`. One
  replacement would change one caller's failure mode.
- **Repository-root readers.** `commands/common.py:46` (`resolve_repo_root`) honours
  `FR_REPO_ROOT`, falls back to the cwd and resolves symlinks; `isolation/local.py:850`
  (`_main_worktree_root`) returns the main checkout's toplevel even from a linked worktree.
- **Atomic writers.** `fr/artifacts/atomic.py:41` keeps the file's mode and line endings
  and fsyncs; `fr/ops/trust.py:334` writes mode 0600 in a 0700 directory;
  `fr/bindings/catalogue.py:109` swallows every `OSError` (a cache); `fr_claude_cloud/mailbox.py:203`
  skips an unchanged write; `fr/triage/state_ref.py:198` refuses a path outside the state
  directory and sets the executable bit from the ref. Durability, permissions and failure
  differ.
- **Marker and workspace checks.** `isolation/marker.py:121` (`marker_at`) reads the
  marker; `:68` (`marker_mode_holds`) checks its mode; `:142` (`valid_workspace`) adds
  branch drift; `fr/run/workspace.py:53` (`ensure_run_workspace`) matches a run's branch and
  `:115` (`_same_stealth`) keeps stealth sticky. One boolean would relax one of them.
- **Schema numbers.** `FACTS_SCHEMA = 13` (`fr/triage/model.py:73`) versions
  `facts.json`; `FACTS_SCHEMA = 1` (`fr/triage/origins.py:64`) versions
  `origins-facts.json`. Different files, not a duplicate of any artifact version.
- **Legacy and VK readers.** The frozen models (`fr/run/legacy.py`, `fr/record/legacy.py`,
  `fr/acceptance/legacy.py`) must not follow the live vocabulary; `fr/run/legacy.py:167`
  pins their source. `fr/artifacts/plan_vk_version.py` is the one archive repair.
- **The ordered gate tuple** in `fr/triage/lanes.py:78`, `("tester", "devops")`: lanes need
  an order (Tester first, by rule), while `PostMergeGate`'s member order is not a contract
  (spec Design C: nothing reads it). Reading the order from the annotation would make it
  load-bearing.
- **`BoardStatus`** (`fr/triage/kanban.py:69`): base `fr` must not import `fr_dispatch`;
  `test_import_direction.py::test_board_status_equals_session_status` (`:201`) keeps the
  values equal.
- **Naive-as-UTC readers** (`fr/usage/compare.py:173`, `fr/debt/engine.py:310`,
  `fr/usage/backfill.py:165`) versus `parse_aware`: a naive time is UTC for usage and debt
  and unknown (`None`) for triage. Kept apart from `parse_aware`; their copies of each other
  are C2-3.

The `fr journal add --gate` help text was on this list in the spec and moved to C1-3.

## 5. Decomposition plan

The line budget (`tests/unit/test_tripwire_module_budget.py`) holds each module at most at
its budget and the budget at most `MAX_HEADROOM = 400` lines above the module:

| Module | Lines at the report's commit | Budget | Headroom |
|---|---:|---:|---:|
| `commands/run_cmd.py` | 8,862 | 8,900 | 38 |
| `commands/triage_batch_cmd.py` | 7,334 | 7,400 | 66 |
| `isolation/local.py` | 3,164 | 3,200 | 36 |
| `plan_ops.py` | 2,545 | 2,600 | 55 |
| `triage/batch_drive.py` | 2,130 | 2,200 | 70 |

Every slice below lowers its module's budget in the same diff. "Guards to widen" are the
tests that name a file by path and must name the new module too.

### 5.1 `commands/run_cmd.py`

223 top-level functions and 8 classes (`grep -c`); 176 `raise typer.Exit`, 228
`err_console.print`; four `ContextVar`s at `:281` (`_RUN_WRITES`), `:283`
(`_RECORD_ROWS`), `:298` (`_UNOBSERVED`) and `:1242` (`_GATE_DECISIONS`); 32 reads of
`os.environ`.

| Cluster | Lines | Size | Kind | Destination |
|---|---|---:|---|---|
| A write ledger (`ResolveGuard` `:170`, `_RunWrites` `:189`, `_save_run_state` `:369`, `_commits_run_writes` `:455`) | 170-491 | 322 | effects | new `fr/run/writes.py` |
| B manifest and unit lookup, step drift, rebind, `_complete_step` (`derive_run_id` `:544` to `:1084`) | 544-1084 | 541 | mostly pure; `_unit_key` (`:623`) prints and exits | `fr/run/` (new `steps.py`) |
| C gate and question provenance (`_queue_gate_decision` `:1247`, `derive_gate_answer` `:1336`, `_gate_provenance` `:1350`) | 1085-1540 | 456 | decision plus a journal write | `fr/run/provenance.py` (exists) |
| D emitted-artifact parsing and evidence (`_parse_emitted` `:1541`, `_verified_evidence` `:1937`, through `_debt_phrase` `:3915`) | 1541-3922 | 2,382 | decision welded to refusals: 55 `raise typer.Exit` | new `fr/run/evidence/`; lens parts to `fr/lenses/review.py`, walk to `fr/verification` |
| E templates, briefs, tiers, binding guard, dispatch open/close (`_template_context` `:3923` to `_print_member_dispatch` `:5056`) | 3923-5114 | 1,192 | mixed; `_guard_dispatch_binding` (`:4301`) writes | briefs to new `fr/run/brief.py`; the binding guard stays |
| F advance engine (`_advance_group` `:5115`; `advance_cmd` `:6234` to `_advance_step` `:6323`) | 5115-5256, 6234-6510 | 419 | coordinator | stays |
| G `start`, `reshape`, `adopt`, `status`, `cost` (`start_cmd` `:5411` … `_observed_holder` `:6188`) | 5257-6233 | 977 | CLI and rendering | stays |
| H deliver gates (`_repo_relative` `:6856` to `_answered_by_or_exit` `:7562`) | 6856-7576 | 721 | decision plus forge reads and one write | new `fr/run/deliver.py` |
| I resolve (`_resolve_member` `:6511`, `resolve_cmd` `:6665`, `_resolve_body` `:7577`, `resolve_in_process` `:7957`, to `_refactor_gate` `:8169`) | 6511-6855, 7577-8201 | 970 | coordinator | stays |
| J `claim`, idle `check`, `gates` (`_open_dispatch_record` `:8202` to `gates_cmd` `:8818`) | 8202-8862 | 661 | CLI over `fr.run.liveness` | stays |

Corrections to `review-run-cmd`: it counted 223 functions as the whole file (there are also
8 classes), placed D at 1670-3920 (the evidence block starts at `_parse_emitted`, `:1541`,
or at `_EvidenceTarget`, `:1731`), and H ended at 7560 (it ends at `:7576`). Its 55 exits in
D, 176 exits, 228 prints, four context variables and 32 environment reads hold.

Importers, all function-local except the CLI's: `cli.py:55` (`run_app`),
`record/apply.py:207` and `:1668` (`_resolve_manifest_for_state`, `_find_step`,
`_rebind_shape`, `_emitted_plan`, `_item_phase`, `derive_gate_answer`, `_clears_gate`,
`ResolveGuard`, `resolve_in_process`), `verification/baseline.py:178`,
`commands/pickup_cmd.py:290`, `commands/push_cmd.py:119`, `commands/lenses_cmd.py:84`,
`fr/run/adopt.py:915`. Moving A and B into `fr/run` removes most of the reach-in from
`record/apply.py`. Tests: 30 files import the module; 26 `from fr.commands.run_cmd import`
statements; 9 `monkeypatch.setattr(run_cmd, "<name>")` calls (the review's 13 counted other
spellings too).

Slices, in order:

1. **B lookup helpers (M).** Preserve: `_unit_key`'s refusal text and exit 2. Leave the
   moved names importable from `run_cmd`, as it already re-imports `fr.run.liveness`'s
   (`run_cmd.py:85-98`), until `record/apply.py` imports them from `fr/run`.
2. **A write ledger (S).** Preserve: `_commit_run_writes_now` runs before a dispatch brief
   is printed (`:384-398`), and the decorator commits in `finally` on refusals too.
3. **H deliver gates (M).** Preserve: the fixed call order inside `_resolve_body` and the
   `_RECORD_ROWS` hand-off from `resolve_in_process`.
4. **E briefs (M).** `_build_brief`, `_build_member_brief` and the templates; leave
   `_guard_dispatch_binding` (journal decision, then binding, restored on failure).
5. **D evidence (L)**, after design 6.1.
6. **C provenance (M)**, after D establishes the verdict type.

Never moved: the tail of `_resolve_body` (stamp, flushed gate decisions, save, print, usage
capture, commit, then HEAD for the hand-off line) and `resolve_in_process` discarding the
body's first stdout line. Guards to widen: `test_journal_stamp_offset.py:31` names
`commands/run_cmd.py` as a journal writer, so moving C's write adds its new module there.
Tracking: ISSUE_RUNCMD_SLICES.

### 5.2 `commands/triage_batch_cmd.py` with `triage/batch_drive.py`

`triage_batch_cmd.py`, 7,334 lines:

| Cluster | Lines | Size | Kind | Destination |
|---|---|---:|---|---|
| imports and docstring | 1-311 | 311 | — | — |
| factories and claim helpers (`make_client` `:312`, `claim_env` `:318`, `make_checkout` `:501`, `load_runner` `:506`) | 312-627 | 316 | effects | stays (the patched names) |
| `_save` `:628`, `_write` `:675`, `list/create/edit/cancel/suggest` (`:719`-`:1059`) | 628-1059 | 432 | CLI | stays |
| dispatch preflight (`_tracking_gate` `:1060`, `_reservation` `:1101`, `_work_item` `:1162`, `_forge_writes` `:1197`, `_probe` `:1291`) | 1060-1422 | 363 | effects | `fr/triage/batch_dispatch.py` |
| replace and recovery (`_replacement_transaction` `:1423`, `batch_replace_command` `:1645`) | 1423-1711 | 289 | effects | new `fr/triage/batch_replace.py` |
| `batch_dispatch_command` `:1713`, `dispatch_batch` `:1764` | 1712-2042 | 331 | effects | `fr/triage/batch_dispatch.py` |
| adopt (`_pr_time` `:2043`, `adopt_batch` `:2052`, `batch_adopt_command` `:2753`) | 2043-2803 | 761 | effects | new `fr/triage/batch_adopt.py` |
| merge and collected close-out commands (`:2805`, `:3083`), `loop_command` `:3267` | 2804-3348 | 545 | CLI | stays |
| driver support (`recollect` `:3349`, `ci_none_at` `:3389`, `_now` `:3406`, `_sleep` `:3411`, `_pace_forge` `:3424`, `drive_lock` `:3505`, `_checkout_map` `:3568`) | 3349-3730 | 382 | effects | stays (the patched names) |
| `_Driver` | 3731-6935 | 3,205 | effects | `fr/triage/batch_driver_*.py`, after design 6.2 |
| close-out items (`_closeout_item` `:6936`) | 6936-7029 | 94 | effects | with the driver |
| `build_driver` `:7030`, `one_pass` `:7072`, `pass_exit` `:7085`, `batch_drive_command` `:7215` | 7030-7334 | 305 | orchestration and CLI | stays |

Inside `_Driver`: reads and snapshot (`forge_off` `:3874`, `merge_ctx` `:3995`, `snapshot`
`:4143` to `_settle_approvals` `:5072`), pass control (`run_pass` `:5112` to
`_write_board` `:5321`), the action switch (`_act` `:5348`), merge, queue, conflict and
hand-back (`_merge_batch` `:5677` to `_start_fresh` `:6198`), post-merge, close-out and
archive (`_post_merge` `:6216` to `_hand_back_archive` `:6613`), wave export
(`_export_conflict` `:6686` to `_export_merge` `:6840`). It calls `_fail` 29 times,
`_say` 14 times and `_now()` 11 times; `fr_dispatch` appears on 13 lines inside it
(`:4429` to `:6618`), function-local.

`batch_drive.py`, 2,130 lines, is one planner: snapshot and action types (`LivePr` `:149`
to `Summary` `:441`), collected close-out naming (`:636-822`) and steps (`:1037-1194`),
hand-back decisions (`handbacks_since` `:828` to `closeout_handback_decision` `:1020`),
wave export (`finished_waves` `:1219` to `_stale_orphans` `:1431`), queue and merge train
(`_dispatch_key` `:1467` to `_walk_merge_train` `:1604`), and `drive_pass` (`:1732-2066`,
335 lines), which stays whole.

Corrections to `review-triage-batch`: the file is 7,334 lines, not 7,343 (R03 removed
`_parse_at`); several ranges are off by a few lines either way (`dispatch_batch` is at
`:1764`, the review's `:1712` is its command); `_Driver` runs 3731-6935 (3,205 lines), not
3740-6874, and it calls `_say` 14 times, not 15. Its patch count holds within two: 183
`monkeypatch.setattr(triage_batch_cmd, …)`-form calls in tests (`load_runner` 31,
`make_client` 22, `_sleep` 22, `make_checkout` 17, `_now` 14, `_pace_forge` 12,
`recollect` 10), across 40 test files.

Production importers: `triage_drive_cmd.py:184`, `:482`, `:642`, `:670`;
`triage_claim_cmd.py:23`; `triage_cmd.py:932` and `:1101`; `triage_kanban_cmd.py:355`
(C3-1).

Slices, in order:

1. **`batch_drive.py` leaves (S).** Wave export and hand-back decisions to
   `batch_drive_export.py` and `batch_drive_handback.py`, re-exported. Preserve the action
   order in `drive_pass`. Guard to widen: `test_triage_batch_drive.py:700` from one path to
   a `batch_drive*.py` glob, in the same change.
2. **`_Driver` ports (S)**, design 6.2. Nothing moves.
3. **Export executor (M)** (`:6686-6935`) to `batch_driver_export.py`. Preserve
   `_export_refusals`/`_export_failures` and their reset per pass.
4. **Snapshot builder (M)** (`:3874-5111`) to `batch_driver_reads.py`. Preserve the caches
   reset per pass and the ones kept for the process's life.
5. **Adopt (M)** (`:2043-2803`) to `fr/triage/batch_adopt.py`, with `_pr_time` reading
   through `parse_aware` (C2-2). Take the `_ISOLATION_ALLOWED` imports with it.
6. **Executor core (L)**: `run_pass`, `_act`, merge and close-out. Preserve the lease, pass,
   `save_pass` order in `one_pass`, the `--yes` and plan split, `pass_exit`'s codes 0, 1 and
   3, and the claim holds.

New modules under `fr/triage/batch*.py` are covered by the existing batch globs
(`test_forge_adapter_batch_ops.py:380-383`); `_SOFT_POINTS` stays unchanged. Tracking:
ISSUE_TRIAGE_SLICES.

### 5.3 `isolation/local.py`

| Cluster | Lines | Size | Kind | Destination |
|---|---|---:|---|---|
| runner plumbing (`devcontainer_id` `:53`, `subprocess_runner` `:80`, `_home` `:111`, gc spawners `:131`, `:167`) | 53-171 | 119 | effects | new `isolation/runner.py` |
| gc and reap value types (`MergeVerification` `:172` to `_hazard_detail` `:257`) | 172-325 | 154 | pure | new `isolation/reap.py` |
| "did the branch land" analysis (`_archived_path` `:326` to `recorded_start` `:825`) | 326-836 | 511 | git reads | new `isolation/landing.py` |
| network env and branch classification (`_realpath` `:837` to `classify_branch` `:1092`) | 837-1177 | 341 | mostly pure | new `isolation/branchrefs.py` |
| stale VK profile refusal (`:1178`, `:1184`) | 1178-1200 | 23 | decision | stays |
| `LocalWorktreeDevcontainerTarget` | 1201-3164 | 1,964 | effects | stays, less gc (design 6.3) |

Inside the class (80 methods; 53 uses of `self.run`, 40 of `self.repo_root`; three
attributes set at `:1216-1218`): lifecycle and docker (`up` `:1238` to `_ssh_agent_probe`
`:1678`; `_ensure_mounted_env_file` `:3033` to `_shown_container_state` `:3133`), merge
verification and `_reap_hazard` (`:1701-1975`), teardown (`down` `:1976` to
`_teardown_container` `:2115`), garbage collection (`_spawn_gc` `:2149` to
`_sweep_agent_worktrees` `:2644`), worktree provisioning and remote view (`:2658-2872`),
marker write and remove (`:2873-2940`), cold-start base and default branch
(`:2941-3032`), PR lookup (`:3147`, `:3150`).

The review's ranges hold. Its counts: 23 test files import the module, with 28 `from`
statements (`subprocess_runner` 12, `LocalWorktreeDevcontainerTarget` 12, `GcAction` 4,
`ReapRefused` 3); module-level patches are rare (one `monkeypatch.setattr(local,
"branch_changes_present")` in that form). The private methods `_resolve_default_branch`,
`_reap_hazard` and `_pr_from` are named 20, 11 and 13 times in tests, as calls or
replacements; the review's patch counts (9, 8, 7) were not reproduced as such. Importers:
`commands/isolation_cmd.py`, `commands/archive_cmd.py`, `fr_herdr/runner.py:118`
(`_main_worktree_root`, a private name).

Slices: (1) runner plumbing, S; (2) landing analysis, M; (3) branch classification, M;
(4) reap value types, S, each re-exported from `local`; (5) garbage collection, L, design 6.3.
Preserve: the teardown order in `_down_worktree_tail` (guards, stage, container teardown at
`:2070`, verified removal, commit, marker, state) and the early return when the worktree
path exists. Guards to widen: `test_isolation_network_timeouts.py:249-266` scans `local.py`
for forge argv, and `test_vk_compat_removed.py:59` and `:262-270` name the path; each new
module joins both. #1419 (`isolation/types.py`) is not touched by any slice. Tracking:
ISSUE_LOCAL_SLICES.

### 5.4 `plan_ops.py`

| Cluster | Lines | Size | Kind | Destination |
|---|---|---:|---|---|
| A plumbing (`PlanEditError` `:61`, `_stage` `:78`, `_now_iso` `:94`, `_yaml_dump` `:114`, `rewrite_phase_text` `:144`, `PhaseSpec` `:170`) | 46-249 | 204 | I/O and serialisation | stays |
| B create and scaffold (`create` `:250`, `_folder_matches` `:428`, `_build_phase_doc` `:494`) | 250-537 | 288 | decision and file writes | stays |
| C spec "Implementation Plans" table (`_SPEC_TABLE_HEADER_RE` `:538`, `_ensure_section_text` `:586`, `_append_spec_row` `:613`) | 538-670 | 133 | text and one write | new `fr/spec_table.py` |
| D `tick` `:671`, `complete_phase` `:724` | 671-752 | 82 | file writes | retire (design 6.4) |
| E tracking issue (`set_tracking_issue` `:753`, `clear_tracking_issue` `:776`) | 753-805 | 53 | file writes | stays |
| F rework (`rework_create` `:866`, `rework_add_origin` `:981`, `rework_list` `:1016`) | 806-1083 | 278 | decision and writes | stays, later `fr/plan/rework.py` |
| G lint vocabulary (`_TASK_ID_RE` `:1085` to `_trailing_manual_block` `:1335`) | 1084-1361 | 278 | pure | new `fr/plan/review/` |
| H `self_review` `:1362` | 1362-1564 | 203 | pure decision | new `fr/plan/review/` |
| I sub-checks (`_manual_placement_issues` `:1565`, `_spec_journal_entries` `:2129`, `OPS_FR_FLOOR` `:1861`) | 1565-2518 | 954 | decision with reads | new `fr/plan/review/` |
| J `_refactor_justifications` `:2519` | 2519-2545 | 27 | read | `fr/record/gates.py`, its one caller (`gates.py:29`) |

The review's ranges hold. Importers: `migrate.py` (`_stage`, `_SPEC_TABLE_HEADER_RE`,
`_ensure_section_text`, `_append_spec_row`, `PlanEditError`), `commands/plan_cmd.py:17-25`
and `:88`, `commands/apply_cmd.py` and `fr_dispatch/__init__.py` (`set_tracking_issue`),
`commands/undispatch_cmd.py` (`clear_tracking_issue`), `record/apply.py:699`
(`rewrite_phase_text`) and `:720` (`_now_iso`), `record/gates.py:29`,
`commands/run_cmd.py:5014` (`_manual_placement_issues`). Tests: 30 files import it, with 125
`from fr.plan_ops import` statements (the review said 34 files and 144 lines);
`PhaseSpec` 47, `create` 45, `self_review` 29, `PlanEditError` 19, `tick` 18,
`complete_phase` 15, `rework_create` 10. Patched on the module object:
`set_tracking_issue` (`test_v2_apply.py:485`, `:506`, `:579`; `test_tick_workitem.py:511`),
`space_for` (`test_plan_ops_feature_root.py:20`) and `parse` (`test_plan_ops.py:168`).

The three side findings, re-checked:

1. **`plan_ops.tick` and `complete_phase` duplicate the record engine:** confirmed. No
   caller under `packages/` (Category 5); `record/apply.py:801` names `plan_ops.tick`'s
   re-parse as the thing it moved before any byte lands. Design 6.4.
2. **Raw `write_text` in `plan_ops.py`:** confirmed, 14 calls, at `:357`, `:367`, `:368`,
   `:370`, `:383`, `:389`, `:664`, `:717`, `:748`, `:768`, `:793`, `:920`, `:932`, `:998`;
   no `write_text_atomic` (`fr/artifacts/atomic.py:41`). Switching them changes failure
   behaviour (the old file survives a failed write), so it is a behaviour fix in the same
   class as F02 and is not a slice. Tracking: ISSUE_PLANOPS_SLICES records it as excluded.
3. **`triage_kanban_cmd.py` imports from `triage_batch_cmd`:** confirmed, C3-1, #1174.

Slices: (1) J to `fr/record/gates.py`, with `_TASK_ID_RE`, S; (2) G+H+I to
`fr/plan/review/`, M, re-exporting `self_review`, `ReviewIssue`, `_trailing_manual_block`
and `_manual_placement_issues`, merging the two journal reads (C2-4); (3) C to
`fr/spec_table.py`, S, re-exported for `migrate.py`; (4) D, design 6.4, not a refactor;
(5) F to `fr/plan/rework.py`, L, after A moves to a private I/O module, because of the
`space_for` patch. Guards to widen: none pins the file; `docs/explainers/01-fr-goal.md:863`
names `plan_ops.py` for `self_review`, so slice 2 edits that page. Tracking:
ISSUE_PLANOPS_SLICES.

## 6. Designs for the costly parts

### 6.1 Evidence verdicts for `run_cmd.py`

A verifier returns a frozen dataclass instead of printing and exiting:

```python
@dataclass(frozen=True)
class Verdict:
    witness: str | None          # the evidence value, when it holds
    refusal: tuple[str, ...] = ()  # lines, in print order; empty when it holds
    markup: bool = False         # whether the refusal lines carry rich markup
    exit_code: int = 2
    unobserved: str | None = None  # the note `_note_unobserved` records today
    warnings: tuple[str, ...] = ()  # printed before the refusal, in emit order
```

One adapter in the command module prints `warnings`, then `refusal`, with the markup flag,
records `unobserved`, and raises `typer.Exit(exit_code)` when `refusal` is set. Verifiers
move to `fr/run/evidence/` and import no typer and no console.

First two to convert: `_proportionality_witness` (`run_cmd.py:2372`) and `_docs_witness`
(`:2414`). Both are derived witnesses, return one string, refuse with exit 2, and print one
warning through `_witness_base` when `announce` is set. `_proportionality_witness` mixes two
red-markup refusals (`:2387`, `:2396`) with a plain one (`:2405`); the `markup` field exists
for that.

Preservation contract: the refusal wording, markup, line order and exit code of every
converted verifier are byte-identical, and warnings print in the same order relative to the
refusal. Shown by the existing CLI tests that assert refusal text (for example
`test_run_cli.py`), run unchanged, plus one test per converted verifier that compares the
adapter's output for each refusal path with a captured copy taken before the change.
`_UNOBSERVED` stays the channel until every verifier returns a verdict.

### 6.2 Driver ports for `triage_batch_cmd.py`

```python
@dataclass(frozen=True)
class DriverPorts:
    client: Callable[[str], GhClient]
    checkout: Callable[[Path | None], Checkout]
    runner: Callable[[str], Runner]
    now: Callable[[], datetime]
    sleep: Callable[[float], None]
    recollect: Callable[..., Facts]
    say: Callable[[str], None]
    fail: Callable[[str], Exception]
    board: Callable[..., Any]   # triage_kanban_cmd.write_board / publish
```

`build_driver` (`:7030`) fills it, and `_Driver` reads every effect through it instead of
module globals.

Patch locations: during the ports slice they **stay**. `build_driver` fills each field with
a lambda that reads the module global at call time (`lambda *a: make_client(*a)`), so the
183 `monkeypatch.setattr(triage_batch_cmd, …)` calls keep working and no test changes. This
is the supplement's warning about permanent forwarding wrappers, and the answer is that the
lambdas are temporary: each later slice that moves part of `_Driver` out of the command
module changes the tests for that part to pass ports to `build_driver` directly, and
deletes the matching lambdas in the same change. When the last part moves, no forwarding
lambda remains.

Preservation contract: the driver tests' output and effect assertions pass unchanged; the
order lease, pass, `save_pass` in `one_pass` (`:7072`) holds; `pass_exit` (`:7085`) returns
0, 1 and 3 for the same inputs. Shown by the existing `test_triage_batch_drive*` and
`test_triage_drive*` tests, unchanged, plus one test that builds a driver with explicit
ports and runs a pass with no `monkeypatch`.

### 6.3 Garbage collection in `isolation/local.py`

A collaborator, not a mixin. `GcSweeper(target)` holds the gc methods (`_spawn_gc` `:2149`
to `_sweep_agent_worktrees` `:2644`), and `LocalWorktreeDevcontainerTarget.gc` (`:2162`)
delegates to it. A mixin would keep the method resolution order but leave the class as
large as it is.

Contract: the four methods `HostWorktreeTarget` overrides (`hostworktree.py:106`, `:119`,
`:124`, `:128`) stay methods of the target, and the sweeper reaches them through the target:
`_teardown_container` (called from teardown, `local.py:2070`), `_labelled_containers`
(`:2463`), `_sweep_dangling_images` (`:2185`) and `_stale_state_reapable`, which
`_gc_stale_state` already asks of the workspace's own target, not the sweeper's (`:2367-2381`).
The host-wide `flock` (`_acquire_gc_lock`, `:2193`) and the per-workspace isolation of
failures stay. Shown by the existing gc and host-worktree tests unchanged, plus one test that
a `HostWorktreeTarget` sweep calls its own overrides.

### 6.4 Retiring `plan_ops.tick` and `complete_phase`

This is a behaviour change, not a refactor, and needs its own spec. The record engine
builds the ticks in an overlay (`record/apply.py:692-775`), parses a scratch copy before any
byte lands (`_check_plan_parses`, `:799`) and applies the refactor gate (`:782`);
`plan_ops.tick` and `complete_phase` write first (`plan_ops.py:717`, `:748`) and re-parse
after. Routing the 18 + 15 test imports
through the engine changes the write order and adds the refactor gate to callers that never
had it. The spec must state which tests change their expectations and why. Tracking:
ISSUE_DESIGN_D.

## 7. Order and conflicts

| Work | Files touched | Shares files with |
|---|---|---|
| C1-3, C2-2 (`_created_since`), C2-3 | `commands/journal_cmd.py`, `triage/collect.py`, `usage/compare.py`, `usage/backfill.py`, `debt/engine.py` | none of the open fixes |
| R04 | `artifacts/structure.py`, `harness/model.py`, `lenses/model.py` | #1286 (`structure.py`) |
| R05, R06 | `tests/unit/` only | none |
| run_cmd slices A, B, H, E | `commands/run_cmd.py`, `fr/run/`, `record/apply.py` | #1500 (`fr/run/model.py`, `save_run_state`) and F05 (`run_cmd.py:6489`) |
| run_cmd D, C (6.1) | `commands/run_cmd.py`, `fr/run/evidence/` | the slices above |
| triage slices | `commands/triage_batch_cmd.py`, `triage/batch_drive*.py`, `triage/batch_*.py` | #1174 (`triage_kanban_cmd.py`) |
| isolation slices, 6.3 | `isolation/local.py`, new `isolation/*.py` | #1419 (`isolation/types.py`, not edited) |
| plan_ops slices, 6.4 | `plan_ops.py`, `fr/plan/`, `record/gates.py`, `docs/explainers/01-fr-goal.md` | none |
| F01 #1499 | `fr_dispatch/__init__.py` | plan_ops (imports `set_tracking_issue` only) |
| F04 #1501 | `fr_cncd/runner.py` | none |

Order: (1) the small vocabulary and reader work (C1-3, C2-2, C2-3); (2) R04, coordinated with
#1286; (3) R05 and R06; (4) module slices, one per PR, with the driver ports (6.2) before
any part of `_Driver` moves and the verdict type (6.1) before evidence moves. The behaviour
fixes #1499, #1500, #1419 and #1501 land first where they share a file, and later slices
keep their corrected behaviour. Two slices of the same module never run in parallel.

**The issue's third open question** (a size ceiling or case by case): a no-growth budget on
the five named modules, not a ceiling for the codebase. Its cost is stated plainly: once a
module's headroom is used (38 lines for `run_cmd.py`), a feature that adds to it must move
code out or raise the budget in its own diff, and two PRs that each fit the headroom can
together turn `main` red. The failure message names both ways out.

**The issue's second open question** (should the report double as an architecture page):
no. The page gains one short fragment, `docs/triage/derio-net--super-fr/architecture/decomposition.html`,
after `pipeline.html`, that states the five modules, what stays and what moves, and links
here; the inventory stays in this report.

## 8. Issues filed

Every piece of work this PR leaves undone, with the issue that tracks it. "Found" is an
issue that existed; "filed" is one this review opened.

| Work | Issue | |
|---|---|---|
| F01 failed dedup lookup | #1499 | found |
| F02 cursor write | #1500 | found |
| F03 branch slugs | #1419 | found |
| F04 cncd symlinks | #1501 | found |
| F05 unbounded CLI steps | ISSUE_F05 | filed |
| F06 install does not use the tested lock | ISSUE_F06 | filed |
| F07 edit hook without `jq` | ISSUE_F07 | filed |
| F09 plugin lock advisories | ISSUE_F09 | filed |
| Cursor race | ISSUE_RACE | filed |
| R04 strict loader extraction | ISSUE_R04 | filed (backend switch stays #1286) |
| R05 record test helper | ISSUE_R05 | filed |
| R06 hermetic git fixture | ISSUE_R06 | filed |
| `run_cmd.py` cheap slices | ISSUE_RUNCMD_SLICES | filed |
| `triage_batch_cmd.py` and `batch_drive.py` cheap slices | ISSUE_TRIAGE_SLICES | filed |
| `isolation/local.py` cheap slices | ISSUE_LOCAL_SLICES | filed |
| `plan_ops.py` cheap slices | ISSUE_PLANOPS_SLICES | filed |
| Design 6.1 evidence verdicts | ISSUE_DESIGN_A | filed |
| Design 6.2 driver ports | ISSUE_DESIGN_B | filed |
| Design 6.3 gc collaborator | ISSUE_DESIGN_C | filed |
| Design 6.4 retire `tick`/`complete_phase` | ISSUE_DESIGN_D | filed |
| C1-3, C2-2, C2-3 small readers | ISSUE_LEFTOVERS | filed |
| C3-1 kanban import | #1174 | found |
| Comments: the R04 cross-link on #1286, the kanban finding on #1174, this list on #1318 | — | owed, see below |

The plan asked for a comment on #1286, one on #1174 and one on #1318 listing these issues.
This run was told not to comment on existing issues, so those three comments are left to the
PR's author; their text is in the run's journal.
