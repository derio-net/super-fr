<!-- fr:journal-schema=4 -->
# Journal: 2026-11-16-architecture-review-sweep

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-16T17:25:08+00:00 input=true -->
### brief · discovery · Operator brief: derio-net/super-fr#1318, title, body and the supplement comment

TITLE: Architectural review + refactoring sweep: find duplicated contracts and mechanisms, consolidate them, guard against drift
STATE: OPEN
LABELS: enhancement

## Why now

#1315 turned out not to be a parser bug. `## Test Plan` is a keyword heading that **five separate readers** each define for themselves: one regex in `fr/spec.py` and four substring literals, among them `fr/acceptance/check.py`'s `TEST_PLAN_MARKER`. All five read a near-miss (`## 6. Test Plan (…)`) as "no Test Plan", silently. No skill states the spelling, and 41 of this repo's ~110 specs use the numbered form. A contract that lives in five places drifted in all five, and nothing noticed.

That is unlikely to be the only case. Other examples found recently:

- **YAML reading:** 113 `yaml.load`/`safe_load` call sites. #1276 added `fr.yamlio` (libyaml + memoised matrix parse) because one test re-parsed the matrix 328 times; #1286 tracks standardising on it.
- **git as a subprocess:** about 103 call sites in 31 files, alongside `fr/triage/gitseam.py`, which exists to be the one git seam for triage. Each call is costly (CI time, #1225) and each re-derives things like the default branch or the toplevel.
- **Closed vocabularies with parallel copies:** status sets, gate names, artifact kinds. The artifact-kind tripwire (`test_tripwire_artifact_kinds.py`) proves the pattern works where it exists.
- **Schema numbers allocated per PR:** parallel PRs collide on `FACTS_SCHEMA` and artifact `current_version` (memory and AGENTS.md: "has now happened twice").
- **Very large modules:** `commands/run_cmd.py` (~7.8k lines), `commands/triage_batch_cmd.py` (~7.3k), `isolation/local.py` (~3k), `plan_ops.py` (~2.5k), `triage/batch_drive.py` (~2.1k). That is about 125k lines of `src` in total.

## Proposal

Two stages, so the review informs the sweep instead of the sweep guessing.

### 1. Architectural review (read-only, produces a report)

A structured review of `packages/*/src` against the architecture `AGENTS.md` describes. Output: a report (committed under `docs/superpowers/audits/`, or an artifact) listing:

1. **Duplicated contracts.** A keyword, literal, regex, vocabulary or schema defined in more than one place: the #1315 class. For each, list where it is defined, who reads it, and whether the copies already disagree.
2. **Duplicated mechanisms.** Two implementations of the same job, for example git/forge access outside their seams, YAML loading, default-branch or toplevel resolution, atomic writes, or "is this a valid workspace" checks.
3. **Seam violations.** Imports or subprocess calls that cross a boundary the architecture says is closed (`fr` never imports `fr_dispatch` except at `_SOFT_POINTS`; git only via `gitseam` in triage; forge writes only through the adapter). Note where a tripwire already exists and where one is missing.
4. **Oversized modules.** Where a file mixes layers (CLI parsing, engine, I/O), propose the split along existing package seams, not new ones.
5. **Dead or vestigial code.** VK-era paths, compatibility shims whose removal is now safe, and readers for artifact versions no repo can still hold.
6. **Test-suite duplication and cost.** Duplicated fixtures and repeated expensive setup (git repos, matrix parses), cross-checked with the CI timing data from #1276.

Each finding gets a severity, a proposed fix, and a "guard": the tripwire or shared helper that stops it from coming back. A refactor without a guard drifts again.

### 2. Refactoring sweep (one PR per finding cluster)

Driven by the report, in priority order. For each cluster:
- consolidate onto one definition or mechanism;
- add the guard (a tripwire test in the style of `test_tripwire_*`, or a single exported helper plus a grep tripwire banning the old pattern);
- change no behaviour (a pure refactor: existing tests must pass unchanged, except tests that pinned the duplication itself);
- one change fragment per PR (`patch`).

Clusters can run as parallel batches or fr-goal runs once the report exists. They are mostly independent, except where two clusters touch the same giant module, which the report should flag.

## Constraints

- Starts after the in-flight work lands (#1315 fix, the cross-org gate-backfill sweep), so the refactor doesn't conflict with it.
- Respect the frozen and generated surfaces: `docs/superpowers/implemented/**` is never rewritten; generated mirrors are regenerated, never hand-edited; artifact-shape changes follow `.claude/rules/artifact-versioning.md`.
- No weakening of gates. Where a refactor touches a gate's logic, its existing tests are the contract.
- CI budget: tripwires must be cheap (grep or AST, no subprocess fan-out).

## Open questions

- Should the review be one deep session or several reviewers by area (`fr/run`, `fr/triage`, `fr/isolation`, packages outside `fr`), merged into one report?
- Should the report double as a refreshed `fr triage architecture` page (`architecture/` fragments)?
- Is there a size ceiling for modules (a tripwire on line count), or is that judged case by case?


--- comments ---
## Comment by an assistant account (name redacted), 2026-11-16T17:14:35Z
## Focused duplication and seams supplement

Reviewed **main at `a4281f855f2c80ecd901e05cafd55a7599f8d801` (v8.0.3)** on 16 November 2026. This supplements the broader principal-engineer audit, which was pinned to `f0a45b5b`; it does not silently carry that older snapshot forward. Source review and inventory were read-only. No fixes, source edits, generated-mirror edits, or archive rewrites were made.

**Recommendation:** proceed with small, guarded consolidation clusters. The strongest opportunities are shared vocabularies, four equivalent timestamp readers, the strict YAML mechanism, and narrowly scoped test helpers. Do not begin with a universal Git abstraction or a line-count-driven split. Several apparent duplicates intentionally encode different policies.

### Current state and inventory

- **#1315 is already fixed.** `fr.spec.find_test_plan_heading` owns heading recognition; callers share it or `test_plan_steps`. The current behavior includes near-miss refusal, fence handling, and reader-specific treatment of archived/invalid headings. Preserve that contract. The shipped-source text tripwire already bans independent heading spellings. [packages/fr/src/fr/spec.py:476–562](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/spec.py#L476-L562) [tests/unit/test_test_plan_heading.py:423–438](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/tests/unit/test_test_plan_heading.py#L423-L438)
- **#1276 already delivered the matrix parsing/cache changes.** `fr.yamlio`, the bounded matrix parse cache with independent returned objects, and the fragment fold cache are present. Do not add another shared mutable matrix cache. Broad reader standardization belongs to the still-open **#1286**. [packages/fr/src/fr/yamlio.py:1–19](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/yamlio.py#L1-L19) [packages/fr/src/fr/acceptance/model.py:419–449](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/acceptance/model.py#L419-L449) [packages/fr/src/fr/acceptance/fold.py:332–368](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/acceptance/fold.py#L332-L368)
- An AST inventory of tracked `packages/*/src/**/*.py` found **415 Python files, 142,530 physical lines**, and **130 direct PyYAML load calls across 87 files**: 125 `safe_load` and 5 `load`. This excludes calls already routed through `fr.yamlio`. The five `load` calls include custom-loader behavior, so “replace all with ordinary safe_load” is not an equivalent change.
- The inventory found **40 direct stdlib subprocess calls with literal Git-first argv across 27 files**. A broader 95-call candidate set includes injected runners and even an argv formatter; it is not 95 subprocess executions. Variable-built argv and dynamic imports require separate inspection. These counts are syntax inventories, not latency or violation counts.
- All **33 static `fr -> fr_dispatch` import statements** found were confined to the three sanctioned command files. No forbidden sibling import was found outside those soft points. Existing package-direction, forge-adapter, forge-write, artifact-kind, and YAML-helper checks passed: **36 tests in 62.63 seconds**, using the current source copy. This is a focused guard result, not a full-suite run.
- Exact normalized function-body comparison, ignoring names/signatures and initial docstrings but retaining variable names/literals, found **5 source duplicate groups and 16 test duplicate groups** above a five-statement/eight-line threshold. These are candidates, not a codebase duplication percentage. Frozen models account for some source matches and should remain independent.

### Behavior-preserving consolidation clusters

All clusters below are **P3 maintainability work**, unless a specific behavior mismatch is discovered during implementation. Current copies generally agree. Each PR needs the stated preservation checks and a cheap recurrence guard.

#### R01 — Derive gate annotations from the existing gate vocabulary

**Definitions/readers:** `fr.gates.Gate` is the six-value canonical exit-gate type. `triage.model.ExitBlock.gates` restates that full set plus `none`; it feeds per-repository gate remaps. `verification.spec_section.GATE_NAMES` already derives the corresponding accepted names from `GATES`. The copies currently agree. [packages/fr/src/fr/gates.py:15–22](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/gates.py#L15-L22) [packages/fr/src/fr/triage/model.py:515–522](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/triage/model.py#L515-L522) [packages/fr/src/fr/verification/spec_section.py:32–46](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/verification/spec_section.py#L32-L46)

**Smallest change:** use `Gate | Literal["none"]` for the triage remap. Consider a canonical `PostMergeGate` type for the tester/devops subset used by spec tags and strategy manifests. **Preserve** accepted values, rejection behavior, `none`, emitted schema, and version-specific strategy validation. Do not widen the post-merge subset to all gates. Workflow `gate: operator` is a separate concept and must remain separate. [packages/fr/src/fr/spec.py:564–565](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/spec.py#L564-L565) [packages/fr/src/fr/verification/model.py:66–83](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/verification/model.py#L66-L83) [packages/fr/src/fr/workflow/model.py:54](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/workflow/model.py#L54)

**Guard:** an in-process type/schema equality test connecting the remap to `GATES | {"none"}`, plus a tag-regex/subset equality test. Prove detection with a synthetic extra value. Existing smoke tests protect canonical sets but do not connect every copied annotation. **Conflict:** serialize with other edits to `triage/model.py` and gate/schema changes.

#### R02 — Remove the adapter's avoidable session-status copy; retain the intentional core boundary

`SessionStatus`, `BoardStatus`, and cloud mailbox `FrStatus` currently contain the same six values. The board copy is deliberate: base `fr` must not depend on optional `fr_dispatch`, and an existing equality guard enforces agreement. The cloud adapter already depends on the dispatch framework, so its extra independent literal is unnecessary. [packages/fr-dispatch/src/fr_dispatch/protocols.py:144–160](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr-dispatch/src/fr_dispatch/protocols.py#L144-L160) [packages/fr/src/fr/triage/kanban.py:69–70](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/triage/kanban.py#L69-L70) [packages/fr-claude-cloud/src/fr_claude_cloud/mailbox.py:43–54](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr-claude-cloud/src/fr_claude_cloud/mailbox.py#L43-L54) [tests/unit/test_import_direction.py:189–198](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/tests/unit/test_import_direction.py#L189-L198)

**Smallest change:** alias/use `SessionStatus` inside the cloud adapter, or extend the existing equality guard to all three if public compatibility requires keeping `FrStatus`. **Preserve** remote-state mapping, especially completed-to-idle, failed-to-blocked, and unknown fallback. Do not create a dependency from base `fr` to the adapter. [packages/fr-claude-cloud/src/fr_claude_cloud/mailbox.py:125–139](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr-claude-cloud/src/fr_claude_cloud/mailbox.py#L125-L139) [packages/fr-claude-cloud/src/fr_claude_cloud/runner.py:115–116](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr-claude-cloud/src/fr_claude_cloud/runner.py#L115-L116)

**Guard:** one cheap vocabulary equality assertion; preserve adapter mapping tests. Separately, add a label-map coverage assertion for `acceptance.report.STATUS_LABEL` against `get_args(Status)`; display labels are a mapping responsibility, not another enum to delete. [packages/fr/src/fr/acceptance/model.py:32–61](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/acceptance/model.py#L32-L61) [packages/fr/src/fr/acceptance/report.py:31–41](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/acceptance/report.py#L31-L41)

#### R03 — Share the four equivalent triage aware-timestamp readers

**Definitions:** command `_parse_at`, batch `_parse_time`, check `_aware`, and views `_parse` have identical runtime bodies. Each returns `None` for missing, malformed, or naive timestamps and preserves an aware timestamp's offset. Consumers use that `None` differently: skip an incomparable age, keep a PR whose time cannot be disproved, use first-seen fallback, or refuse invalid collected time. [packages/fr/src/fr/commands/triage_batch_cmd.py:3611–3618](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/commands/triage_batch_cmd.py#L3611-L3618) [packages/fr/src/fr/triage/batch.py:222–230](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/triage/batch.py#L222-L230) [packages/fr/src/fr/triage/check.py:375–387](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/triage/check.py#L375-L387) [packages/fr/src/fr/triage/views.py:83–99](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/triage/views.py#L83-L99)

**Smallest change:** one pure `fr.triage.timestamps.parse_aware`, migrating all four callers in the same PR. **Preserve caller-specific fallback/refusal behavior.** Do not substitute telemetry or debt readers that treat naive times as UTC; those have a different contract. Six representative cases were executed against the four actual function bodies and agreed: missing, empty, malformed, naive, Z, and nonzero-offset input. This confirms the sample, while body equality supplies the broader static comparison.

**Guard:** one table of those cases, including retained offset, and a single AST scan for another equivalent parser body outside the owner. No subprocess per caller. **Conflict:** do before the large command extraction so both PRs do not move the same helper.

#### R04 — Extract strict duplicate-key detection without changing loader policy

Two `_StrictLoader` implementations live in artifact structure validation and harness parsing. Lenses imports the artifact validator's private loader. Both detectors inspect constructed mapping keys, tolerate unhashable keys during duplicate detection, and delegate to SafeLoader. Their errors deliberately differ: artifact validation retains YAML marks/ConstructorError, while harness parsing raises its own HarnessError wording. [packages/fr/src/fr/artifacts/structure.py:46–90](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/artifacts/structure.py#L46-L90) [packages/fr/src/fr/harness/model.py:153–190](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/harness/model.py#L153-L190) [packages/fr/src/fr/lenses/model.py:18](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/lenses/model.py#L18) [packages/fr/src/fr/lenses/model.py:127](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/lenses/model.py#L127)

**Smallest change:** put the common mechanism in a dependency-light YAML module, with each public reader retaining its error translation. Move the lenses dependency to that shared mechanism. **Preserve** current grammar, duplicate refusal, marks/messages, and unhashable-key behavior. The harness comment's old “heavy artifact imports” rationale is not a current measured cost claim: structure now defers those imports.

**Guard:** a single-owner AST check for the detector and a dependency check preventing low-level YAML code from importing artifact/harness/plan models. Retain current duplicate-key tests. [tests/unit/test_harness_matrix.py:319](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/tests/unit/test_harness_matrix.py#L319) [tests/unit/test_validate_artifacts.py:879](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/tests/unit/test_validate_artifacts.py#L879)

**Relationship to #1286:** do the same-loader extraction separately from a libyaml/backend switch. Ordinary `safe_load` accepts duplicate keys, so making every reader strict changes behavior. Preserve each current `yaml.load` call's custom loader and exception contract. Keep dumper optimization out unless committed outputs remain byte-identical. **Conflict:** one owner for this cluster and #1286's strict-loader part.

#### R05 — Share migration-test file placement, not historical records

Eight modules repeat the same path/mkdir/write/return mechanism for `runs/r1.records/<stem>.yaml`: `test_migration_record_{delegated,visual,input_unconfirmed,questions,shape,contract,status_split}` and `test_record_acceptance_v8`. Their text defaults and versions intentionally differ. Representative definitions and consumers: [tests/unit/test_migration_record_delegated.py:27–32](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/tests/unit/test_migration_record_delegated.py#L27-L32) [tests/unit/test_migration_record_visual.py:27–32](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/tests/unit/test_migration_record_visual.py#L27-L32) [tests/unit/test_migration_record_contract.py:63–68](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/tests/unit/test_migration_record_contract.py#L63-L68) [tests/unit/test_record_acceptance_v8.py:138–143](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/tests/unit/test_record_acceptance_v8.py#L138-L143)

**Smallest change:** `tests.unit.record_helpers.write_record(root, text, *, stem=...)`; make old-version payloads explicit at migrated call sites. **Preserve** exact bytes, destination, independent tmp roots, and the separate migration/refusal/idempotence assertions. Do not replace historical YAML with current-model dumps or share one mutable record across tests.

**Guard:** scoped AST check for copied placement bodies in the migrated modules plus one in-process bytes/path helper check. Existing migration tests remain behavioral evidence. **Expected benefit:** less fixture-policy drift; no speedup is established for this small helper. **Conflict:** test-only, but coordinate with record schema/template work.

#### R06 — Share gate-backfill Git-environment fixtures within their existing scope

Four modules define the same function-scoped autouse `_hermetic_git` fixture setting `GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CONFIG_NOSYSTEM=1`: candidates, delivery, discharged, and render. The repo builder is already shared and creates fresh state. [tests/unit/test_gatebackfill_candidates.py:28–31](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/tests/unit/test_gatebackfill_candidates.py#L28-L31) [tests/unit/test_gatebackfill_delivery.py:31–34](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/tests/unit/test_gatebackfill_delivery.py#L31-L34) [tests/unit/test_gatebackfill_discharged.py:31–34](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/tests/unit/test_gatebackfill_discharged.py#L31-L34) [tests/unit/test_gatebackfill_render.py:19–22](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/tests/unit/test_gatebackfill_render.py#L19-L22) [tests/unit/gatebackfill_fixtures.py:20–58](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/tests/unit/gatebackfill_fixtures.py#L20-L58)

**Smallest change:** one fixture-only module, explicitly activated in exactly those four test modules. **Preserve** per-test restoration and fresh repositories, refs, worktrees, and fake forge state. Do not broaden it into suite-global autouse or move the environment setters solely into the test Git helper: production subprocesses also inherit the fixture environment.

**Guard:** AST assertions for activation/no local copy and a cheap monkeypatch restoration test. **Expected benefit:** consistent isolation policy, not fewer Git subprocesses. No shared session-scoped Git repository or global mutable matrix fixture is recommended.

#### R07 — Extract policy and orchestration along existing seams, in small slices

Current sizes are `run_cmd.py` **8,862**, `triage_batch_cmd.py` **7,343**, `isolation/local.py` **3,164**, `plan_ops.py` **2,545**, and pure `batch_drive.py` **2,130** physical lines. Size is a review signal, not a defect or a reason to flatten distinct contracts.

The clearest existing triage seam is `Snapshot -> drive_pass` for decisions versus `_Driver/build_driver/one_pass` for stateful execution. Cloud drive already calls into the command module for that lifecycle. Keep Typer registration and optional runner loading in sanctioned command points; extract the executor through injected existing ports. Preserve action ordering, claims/leases, state synchronization, reset-per-pass behavior, dry-run/yes, and exit codes. [packages/fr/src/fr/triage/batch_drive.py:1732–1765](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/triage/batch_drive.py#L1732-L1765) [packages/fr/src/fr/commands/triage_batch_cmd.py:3740–3775](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/commands/triage_batch_cmd.py#L3740-L3775) [packages/fr/src/fr/commands/triage_batch_cmd.py:7039–7105](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/commands/triage_batch_cmd.py#L7039-L7105) [packages/fr/src/fr/commands/triage_drive_cmd.py:550–570](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/commands/triage_drive_cmd.py#L550-L570)

For run commands, extract one cohesive evidence-policy or transition slice at a time, retaining the coordinator's save/commit/effect order. Do not create a generic framework or retain permanent forwarding wrappers merely to preserve test monkeypatch locations. Adapt injection points while retaining output/effect assertions. [packages/fr/src/fr/commands/run_cmd.py:1937–1995](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/commands/run_cmd.py#L1937-L1995)

**Guard:** preserve the pure-driver import/time/process ban. Extend the batch seam guard to every extracted executor file: today's `batch*.py`/`triage_batch*.py` globs would not cover an arbitrarily named `drive_executor.py`. Keep lower-level triage free of command imports and runner-package imports; inject ports rather than expanding `_SOFT_POINTS` casually. [tests/unit/test_triage_batch_drive.py:700–723](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/tests/unit/test_triage_batch_drive.py#L700-L723) [tests/unit/test_forge_adapter_batch_ops.py:374–383](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/tests/unit/test_forge_adapter_batch_ops.py#L374-L383) [tests/unit/test_forge_adapter_batch_ops.py:502–532](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/tests/unit/test_forge_adapter_batch_ops.py#L502-L532)

**Conflict:** serialize large command moves with R03, gate changes, and active behavior fixes. One architectural slice per PR, not simultaneous broad sweeps of the same command modules.

### Guard correction, separate from application refactoring

**G01, P3:** `test_import_direction.py` uses a root-import regex and checks that a `find_spec` substring exists somewhere in each soft-point file. It does not establish the full stated control-flow property. A disposable source fixture containing `import os, fr_cncd` is visible to Python's AST but produces no offender from the current regex scanner. This demonstrates a guard blind spot, not a current production seam violation; Ruff would also reject that particular multi-import style. [tests/unit/test_import_direction.py:18–31](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/tests/unit/test_import_direction.py#L18-L31) [tests/unit/test_import_direction.py:85–95](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/tests/unit/test_import_direction.py#L85-L95)

Use one AST pass over all import names and explicit tests for aliases, nested imports, unrelated guard strings, and valid current soft points. Verify sanctioned imports follow the availability/refusal path. Keep intentional entry-point loading allowed and decide any broader dynamic-import policy explicitly. This is a **test/architecture-guard correction**, with planted-source regression cases, and makes no application runtime change.

Existing triage guards are scoped, not a global ban on every direct Git call. The batch glob and Checkout/Worktree import checks cover batch orchestration; `gitseam` has its own restrictions. The global forge tripwire checks direct `fr.gh`/literal gh argv outside named backend files. All passed in the focused run. Do not count sanctioned Git wrappers or optional imports as violations. [tests/unit/test_forge_adapter_batch_ops.py:374–383](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/tests/unit/test_forge_adapter_batch_ops.py#L374-L383) [tests/unit/test_forge_adapter_batch_ops.py:433–476](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/tests/unit/test_forge_adapter_batch_ops.py#L433-L476) [tests/unit/test_tripwire_forge_adapter.py:30–76](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/tests/unit/test_tripwire_forge_adapter.py#L30-L76)

### Apparent duplicates to preserve, or investigate before scheduling

| Candidate | Evidence and disposition |
|---|---|
| Default-branch and repository-root readers | `fr.git.remote_default_ref` is read-only/fail-closed and remote-aware; triage Checkout can repair origin/HEAD via network; isolation can consult the forge then fall back to main. Root readers differ on FR_REPO_ROOT, symlink resolution, cwd fallback, and errors. No equivalent all-purpose replacement was established. Share low-level mechanics only after retaining these explicit policies. [packages/fr/src/fr/git.py:1–12](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/git.py#L1-L12) [packages/fr/src/fr/git.py:111–135](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/git.py#L111-L135) [packages/fr/src/fr/triage/gitseam.py:465–489](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/triage/gitseam.py#L465-L489) [packages/fr/src/fr/isolation/local.py:3001–3030](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/isolation/local.py#L3001-L3030) [packages/fr/src/fr/commands/common.py:46–82](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/commands/common.py#L46-L82) |
| Atomic-write implementations | Artifact text replacement preserves mode/newlines and fsyncs; trust grants require private mode; catalogue cache swallows failures; mailbox avoids unchanged writes; state-ref materialization adds containment and executable modes. These are not interchangeable writers. A shared lower-level primitive may help, but changing durability, permissions, containment, or failures needs a separate behavior contract. [packages/fr/src/fr/artifacts/atomic.py:41–75](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/artifacts/atomic.py#L41-L75) [packages/fr/src/fr/ops/trust.py:334–346](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/ops/trust.py#L334-L346) [packages/fr/src/fr/bindings/catalogue.py:109–122](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/bindings/catalogue.py#L109-L122) [packages/fr-claude-cloud/src/fr_claude_cloud/mailbox.py:202–215](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr-claude-cloud/src/fr_claude_cloud/mailbox.py#L202-L215) [packages/fr/src/fr/triage/state_ref.py:198–218](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/triage/state_ref.py#L198-L218) |
| Marker/workspace checks | `marker_at`, mode corroboration, branch drift, run-branch matching, reuse/entry, and stealth stickiness answer different questions. Current readers already share parts. Replacing all with one boolean can relax checks. Use shared cross-harness test vectors to guard parity, rather than a Python import inside shell/TypeScript. [packages/fr/src/fr/isolation/marker.py:72–159](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/isolation/marker.py#L72-L159) [packages/fr/src/fr/run/workspace.py:53–100](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/run/workspace.py#L53-L100) |
| Schema numbers | Registry record version 12 and `RECORD_SCHEMA_VERSION=12` are a real duplicate, but existing migration tests already assert equality. A lazy getter is lower-value follow-up with import-cycle/public-constant compatibility review. Run already looks up current version lazily. `FACTS_SCHEMA=13` is a separate facts-file schema, not a duplicate artifact version. Do not globally unify numbers or rewrite historical milestones/defaults. Parallel changes to the same current schema still need integration/merge coordination. [packages/fr/src/fr/artifacts/registry.py:590–598](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/artifacts/registry.py#L590-L598) [packages/fr/src/fr/record/model.py:69](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/record/model.py#L69) [packages/fr/src/fr/run/model.py:334–365](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/run/model.py#L334-L365) [packages/fr/src/fr/triage/model.py:72](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/triage/model.py#L72) [tests/unit/test_migration_record_contract.py:74](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/tests/unit/test_migration_record_contract.py#L74) |
| VK and old artifact readers | Current live VK adapter compatibility was removed. Surgical `vk_version` repair and hash-guarded frozen readers still serve registered migrations. No deletion-safe public compatibility cluster was proved. Retain readers until supported input versions and external-consumer obligations explicitly permit removal; grep hits are not dead-code proof. [packages/fr/src/fr/record/legacy.py:1–25](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/record/legacy.py#L1-L25) [packages/fr/src/fr/artifacts/registry.py:481–509](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/artifacts/registry.py#L481-L509) |

### Test cost, cross-checked against #1276

#1276 is a merged PR, not an outstanding parsing fix. Its [operator tester comment](https://github.com/derio-net/super-fr/pull/1276#issuecomment-6584913167) records a 275-second staged release and explicitly leaves the superseded-release proof to still-open #1306. Those are historical reported observations, not measurements from this supplement.

The committed `.test_durations` contains **15,182 entries**. The dispatch corpus node has a recorded **294.1865-second** fallback weight; that is a sensible profiling target, but not proof of its current runtime or cause. Current CI can select newer cached measurements and uses **seven** shards; the release suite uses six. Do not present static sums as a current shard's wall clock or attribute the historical cost to the small helpers proposed above. [.github/workflows/ci.yml:104–120](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/.github/workflows/ci.yml#L104-L120) [.github/workflows/ci.yml:194–216](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/.github/workflows/ci.yml#L194-L216)

Preserve independent test oracles. `test_acceptance_parse_cache.py` deliberately compares against ordinary PyYAML plus model validation; routing that oracle through the implementation would weaken it. The recorded 3.0117-second oracle weight does not justify removing it. Also retain no-libyaml fallback, nested-mutation isolation, repeated-failure, and historical migration tests. [tests/unit/test_acceptance_parse_cache.py:38–87](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/tests/unit/test_acceptance_parse_cache.py#L38-L87) [tests/unit/test_yamlio.py:19–35](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/tests/unit/test_yamlio.py#L19-L35)

### Behavior fixes stay outside the pure-refactor lane

The broader audit demonstrated four boundary failures at its earlier pinned commit: generic tick proceeding after failed duplicate-work lookup, truncating cursor replacement, branch-slug identity collisions, and cncd including outside-file content via plan symlinks. Those findings need their own desired contracts and regression evidence. They must not be silently “preserved” or silently fixed inside R01–R07.

For example, routing cursor writes through the atomic writer changes failure behavior and belongs in the cursor durability fix, not a claim that all existing writers were equivalent. A source check at this supplement's SHA still shows the direct cursor `write_text`. [packages/fr/src/fr/run/model.py:596–601](https://github.com/derio-net/super-fr/blob/a4281f855f2c80ecd901e05cafd55a7599f8d801/packages/fr/src/fr/run/model.py#L596-L601)

Likewise, changing the generic tick's availability-first dedup fallback changes an explicitly tested policy. Keep the desired behavior correction separate from moving code. New timestamp normalization, stricter ordinary YAML, wider gate sets, changed default-branch guessing, shared mutable test state, and skipped public gates are all behavior changes, not cleanup.

### Suggested PR order and answers to the issue's questions

1. **G01 guard correction**, with planted fixtures and no application change. It protects later moves.
2. **R01/R02 vocabulary consolidation** and **R03 timestamp consolidation**, in small PRs. Parallelize only when touched-file sets are disjoint.
3. **R04 strict YAML extraction**, coordinated with #1286. Keep backend/dumper changes and diagnostics compatibility explicit.
4. **R05/R06 test helpers**, preserving function scope and historical payloads. Do not claim runtime improvement without a profile.
5. **R07 orchestration slices**, after the overlapping small changes and relevant behavior fixes settle. Extend guard scope in the same PR as each move.

Use a reviewed artifact/report for this evidence, then a shorter curated `fr triage architecture` fragment if useful; do not put the whole inventory into the architecture overview. Several area reviewers plus one reconciliation pass worked well here. Use module size as a review trigger and an optional no-growth budget for named hotspots, not a universal line ceiling that encourages arbitrary splitting.

Each PR should state its preserved behavior, migrated callers, guard, and touched-file conflicts; add the required patch fragment. Frozen archives stay unchanged and generated mirrors are regenerated. A behavior fix gets its own contract, evidence, and release scope. No new feature or refactor implementation is included in this supplement.

<!-- fr:journal kind=discovery scope=spec id=brief-audit created=2026-11-16T18:03:22+00:00 input=true -->
### brief-audit · discovery · Operator brief, continued: the #1318 comments added after the first read (bug index, full audit parts 1 and 2, pointer comment)

--- comment, 2026-11-16T17:50:33Z (1910 chars) ---
## Confirmed bugs tracked separately from the refactor work

The four confirmed audit bugs now have separate bug tracking. Rechecked against current main at `33e12d678a37a93b7c215ad8ac9f8c070c905090`, using the matching v8.0.3 workspace packages; all four safe reproductions still show the reported behavior.

| Audit finding | Bug issue | Scope |
|---|---|---|
| F01 | #1499 | Generic tick dispatches after an unavailable duplicate-work lookup. |
| F02 | #1500 | A failed cursor save destroys the last valid local cursor. |
| F03 | #1419 | Branch slugs collide, overwrite state, and resolve another branch's workspace. |
| F04 | #1501 | cncd plan-directory symlinks include outside-file text in the dispatch payload. |

Each report contains executable reproduction steps, pinned source evidence, observed versus expected behavior, impact limits, recommended fixes, and regression criteria. #1419 already existed and is actively claimed, so I added the state-overwrite reproduction and criteria there rather than creating a competing duplicate or changing its claim.

**These are behavior-changing fixes, outside R01–R07's behavior-preserving refactor lane.** Use separate fix PRs with explicit corrected contracts and regression evidence. In particular, the dedup test currently endorses the unsafe fallback, so preserving that assertion is not an acceptance criterion for its bug fix.

Keep the fix and refactor PRs separate even where they touch the same helper or command module. Coordinate overlapping paths with the existing owner, land the corrected behavior/guard first where practical, and preserve that corrected behavior in subsequent extractions. No behavior change should be hidden inside YAML, persistence, identity, or orchestration cleanup.

No source changes, live runner calls, real secret transfers, or destructive workspace teardown were performed while reproducing and filing these issues.

--- comment, 2026-11-16T17:52:34Z (41248 chars) ---
<!-- full-principal-audit:f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37:part:1 -->
## Full engineering audit part 1 of 2

Publishing the complete original audit for the implementing agent. **Original assessment: 15 November 2026, commit `f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37`, v8.0.0.** The report text is unabridged across these two comments. Its statements about read-only work and verification describe that original audit session; later issue filing and the supplement are separate work.

The [focused supplement](https://github.com/derio-net/super-fr/issues/1318#issuecomment-6923555343) is pinned to `a4281f85`. The [bug tracking index](https://github.com/derio-net/super-fr/issues/1318#issuecomment-6924421644) records rechecks at `33e12d67`: #1499, #1500, #1419, #1501. Keep those behavior fixes separate from #1318's behavior-preserving refactors. This publication does not refresh the original score or claim to audit current main.

---

# Engineering audit of super-fr

Principal engineer assessment · 15 November 2026 · Read-only review

**Verdict: a capable, thoughtfully engineered automation platform whose safety guarantees are uneven at identity, persistence, and dispatch boundaries.** Retain its core design. Fix the four reproduced defects before expanding unattended operation, then reduce the concentration of workflow policy in the command layer.

The weighted engineering assessment is **3.2 out of 5**, with medium overall confidence. This is an expert assessment, not a measured reliability rate. The repository has substantial behavioral tests, useful pure decision engines, strict typing, and unusually careful recovery mechanisms. Passing tests still coexist with a test that explicitly endorses unsafe dispatch behavior, a cursor writer that can destroy its last valid state, colliding workspace identities, and an overly broad cncd file payload.

## Scope and evidence

Repository: [derio-net/super-fr](https://github.com/derio-net/super-fr). All source conclusions refer to commit **f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37**, version **8.0.0**. The pinned commit was the latest returned by connected GitHub access when this audit began. It is not a promise that the branch still points there when this report is read.

Connected GitHub access established repository metadata, the complete tree, commit identity, and CI job results. A separate detached local clone supplied source inspection and checks. No source, configuration, GitHub issue, pull request, branch, or remote state was changed. Test environments, generated reports, dependency installations, and reproductions were kept outside the clone. The final tracked working-tree check is recorded with the evidence bundle.

Three independent review workstreams covered architecture and state, dispatch and runners, and security and delivery. Their findings were reconciled with source reinspection and safe reproductions. A second challenge pass narrowed the dispatch and cncd impact claims and verified that mutation failures were behavioral assertions. These were separate agent reviews, not a claim of independent human review or different-model consensus.

The audit inspected every major subsystem at the level shown in the coverage map below and traced representative critical paths. It did not inspect every line or every possible state. Evidence labels mean:

| Label | Meaning |
|---|---|
| Reproduced | Executed the actual pinned implementation against a disposable local fixture and observed the stated failure. |
| Static finding | Directly established from source or configuration, without a runtime incident claim. |
| Expert assessment | A reasoned judgment about fitness, change cost, or design. |
| Risk | A credible failure path that was not reproduced end to end. |
| Unknown | Available evidence does not support a conclusion. |

The four defect reproductions used in-memory fake backends, synthetic text, local Git repositories, or a child process with a file-size limit. No live model session, cncd request, Docker operation, deployment, remote mutation, real secret transfer, or destructive workspace teardown was performed.

## Findings at a glance

P0 means emergency action. P1 means a broadly urgent release blocker. P2 means a material defect or risk to address in the next focused maintenance cycle. P3 means planned assurance or maintainability work. There is no demonstrated P0 or generally applicable P1 incident in this audit. Particular deployment conditions can raise the priority of a P2 finding.

| ID | Priority | Finding | Evidence status | Confidence |
|---|---|---|---|---|
| F01 | P2 | Generic tick treats failed duplicate-work lookup as an empty backend and submits again. | Reproduced framework behavior | High |
| F02 | P2 | A failed cursor replacement destroys the last valid local cursor. | Reproduced OS write fault | High |
| F03 | P2 | Valid branch names can share an isolation state and default workspace path. | Reproduced identity collision | High |
| F04 | P2, conditional confidentiality impact | cncd payload follows plan-directory symlinks and includes outside-file text. | Reproduced, including real reachability gate | High |
| F05 | P2 | Workflow CLI steps have no runtime or retained-output bound. | Static risk | High on mechanism; medium on impact |
| F06 | P2 | Consumer installation does not reproduce the release's locked Python dependencies. | Static finding | High |
| F07 | P2 | Claude edit hook emits no deny decision when jq is missing from PATH. | Reproduced process behavior; harness continuation untested | High on hook result |
| F08 | P3 | Workflow policy and side-effect coordination are concentrated in very large command modules. | Measured size plus architectural judgment | High on size; medium on change cost |
| F09 | P3, review promptly | Plugin lock includes transitive versions covered by two moderate dependency advisories. | Scanner result verified against advisory records | High on version match; exploit reachability unverified |

The priorities reflect demonstrated scope, likely exposure, recovery options, and the presence of other guards. The list is not a count of vulnerabilities, and static risks are not counted as reproduced defects.

## Product and architecture

super-fr turns a feature request into an isolated, planned, tested, reviewed pull request. It also manages plans, acceptance evidence, journals, workflow cursors, backlog batches, runner sessions, manual operations, and close-out. Its important consistency boundaries are files, Git history, the forge, and external agent sessions. It therefore faces partial-failure and ownership problems even though it is primarily a local CLI.

The current source has retired VibeKanban support. The repository description returned by GitHub still mentions it, while the recent history records its removal. Treat current code and version 8 documentation as authoritative for supported adapters. See [the retirement commit](https://github.com/derio-net/super-fr/commit/e0390fd8) and [packages/fr-dispatch/src/fr_dispatch/registry.py:1–60](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr-dispatch/src/fr_dispatch/registry.py#L1-L60).

The architectural flow is:

```
Operator and coding harness
    skills, rules, Claude hooks, OpenCode plugin, Hermes integration
                        |
                       fr CLI
                        |
    plans + workflows + run state + journals + acceptance evidence
                        |
    observe live state -> calculate decisions -> apply effects
                        |
        forge adapters      runner protocol      isolation targets
        GitHub/GitLab/tea    cncd/herdr/cloud     worktree/container/external
                        |
           external services, Git and filesystem state
```

This is a conceptual map, not a claim that all effects pass through one universal applier. The plan synchronization engine has a particularly clear render-observe-diff-apply structure. Triage, operations, and other workflows have additional writers through their own adapters.

### Subsystem coverage and judgments

| Subsystem | Representative source and path | Assessment |
|---|---|---|
| Plan parsing and editing | [packages/fr/src/fr/parser.py:259–279](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/parser.py#L259-L279); [packages/fr/src/fr/plan_ops.py:1362–1400](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/plan_ops.py#L1362-L1400) | Closed artifact schemas and explicit edit rules support predictable behavior. Editing and validation policy are substantial and deserve focused regression tests. |
| Forge synchronization | [packages/fr/src/fr/observe.py:43–61](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/observe.py#L43-L61); [packages/fr/src/fr/diff.py:118–249](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/diff.py#L118-L249); [packages/fr/src/fr/apply.py:93–157](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/apply.py#L93-L157) | Strong separation between observation, pure mutation calculation, and execution. Foreign labels and completed-plan creation are explicitly handled. |
| Workflow execution and evidence | [packages/fr/src/fr/workflow/check.py:43–64](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/workflow/check.py#L43-L64); [packages/fr/src/fr/commands/run_cmd.py:6270–6443](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/commands/run_cmd.py#L6270-L6443) | Meaningful state and evidence enforcement, but the command module owns too much policy and coordination. Persistence is weaker than the model's durable-state purpose. |
| Journals and acceptance | [packages/fr/src/fr/journal/model.py:646–719](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/journal/model.py#L646-L719); [packages/fr/src/fr/acceptance/fold.py:332–399](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/acceptance/fold.py#L332-L399) | Effective-state folding, reopening, and branch amendments model real requirements. Preserve these distinctions. Journal write durability needs repair. |
| Triage and batch drive | [packages/fr/src/fr/triage/batch_drive.py:1732–1800](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/triage/batch_drive.py#L1732-L1800); [packages/fr/src/fr/triage/batch.py:514–582](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/triage/batch.py#L514-L582) | A pure planner over observed snapshots is a strong boundary. Batch orchestration and cross-store repair concentrate in the command layer. |
| Dispatch framework | [packages/fr-dispatch/src/fr_dispatch/__init__.py:374–617](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr-dispatch/src/fr_dispatch/__init__.py#L374-L617); [packages/fr-dispatch/src/fr_dispatch/protocols.py:88–104](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr-dispatch/src/fr_dispatch/protocols.py#L88-L104) | Stable work items and real adapter seams are justified. F01 is a narrow but material inconsistency in failure policy. |
| Runner adapters | [packages/fr-cncd/src/fr_cncd/runner.py:85–99](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr-cncd/src/fr_cncd/runner.py#L85-L99); [packages/fr-herdr/src/fr_herdr/runner.py:368–452](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr-herdr/src/fr_herdr/runner.py#L368-L452); [packages/fr-claude-cloud/src/fr_claude_cloud/mailbox.py:1–100](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr-claude-cloud/src/fr_claude_cloud/mailbox.py#L1-L100) | Separate transport, terminal-session, and durable-mailbox models fit genuinely different backends. Current external compatibility is partly an integration assumption. |
| Isolation lifecycle | [packages/fr/src/fr/isolation/types.py:95–177](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/isolation/types.py#L95-L177); [packages/fr/src/fr/isolation/routing.py:24–51](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/isolation/routing.py#L24-L51) | Recorded-mode routing and recovery-aware teardown are good. Lossy branch identity undermines the entry to those protections. |
| Usage, model binding, debt, docs | [packages/fr/src/fr/usage/file.py:9–18](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/usage/file.py#L9-L18); [packages/fr/src/fr/bindings/choose.py:50–58](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/bindings/choose.py#L50-L58); [packages/fr/src/fr/docs/check.py:26–84](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/docs/check.py#L26-L84) | Small focused policies, explicit missing values, and privacy allowlists are examples to follow when extracting run policy. |
| Harness enforcement | [packages/fr-opencode-plugin/src/spawn.ts:1–69](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr-opencode-plugin/src/spawn.ts#L1-L69); [packages/fr-opencode-plugin/src/idle.ts:1–45](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr-opencode-plugin/src/idle.ts#L1-L45); [plugins/super-fr/hooks/fr-isolation-required.sh:24–37](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/plugins/super-fr/hooks/fr-isolation-required.sh#L24-L37) | Delegating domain judgments to fr limits drift. Hook/parser failure behavior remains uneven across entry points. |
| Manual operations and trust | [packages/fr/src/fr/commands/ops_cmd.py:224–240](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/commands/ops_cmd.py#L224-L240); [packages/fr/src/fr/ops/apply.py:206–265](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/ops/apply.py#L206-L265); [packages/fr/src/fr/ops/probe.py:36–61](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/ops/probe.py#L36-L61) | Operator-local trust, preflight confirmations, dependency ordering, explicit unavailable states, and bounded noninteractive probes are sound. Actual privileged operations were not run. |
| Artifact migration, settings, placement | [packages/fr/src/fr/artifacts/trigger.py:590–635](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/artifacts/trigger.py#L590-L635); [packages/fr/src/fr/settings/load.py:372–412](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/settings/load.py#L372-L412); [packages/fr/src/fr/placement/move.py:1147–1177](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/placement/move.py#L1147-L1177) | Migration locking, per-key configuration provenance, and verification before placement switching address real consistency needs. Live placement moves and migration recovery were not exercised here. |
| Install, release, operations | [scripts/install.sh:8–63](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/scripts/install.sh#L8-L63); [.github/workflows/ci.yml:19–37](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/.github/workflows/ci.yml#L19-L37); [.github/workflows/release.yml:82–139](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/.github/workflows/release.yml#L82-L139) | Serious staging, locking, release checks, and diagnostics. Installation dependency resolution differs from the tested lock. |

### Critical path 1 — plan to forge

The parser produces a validated plan. Observation reads tracked issue and linked-PR state. Rendering derives desired issue state from local progress and accepted work. The diff emits typed mutations. Apply executes those mutations or returns a dry run. Labels outside owned namespaces remain untouched, and locally completed undispatched phases are suppressed rather than recreated. [packages/fr/src/fr/diff.py:159–219](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/diff.py#L159-L219) [packages/fr/src/fr/apply.py:93–157](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/apply.py#L93-L157)

This division is clean architecture in the useful sense: decisions can be exercised without network access, while effects have a constrained interface. The design does not need more enterprise layering. Its limits are GitHub-shaped vocabulary and sequential observations per phase. A new forge is possible but not merely a one-method adapter replacement across the whole product.

### Critical path 2 — workflow advance and resolve

Advance reads a cursor and workflow manifest, checks gates and active attempts, persists a new hold, and emits an agent brief. CLI steps execute directly, and their exit status controls progression. Resolve verifies required evidence and records completion. Those checks are substantive enforcement, not merely prose instructions. [packages/fr/src/fr/commands/run_cmd.py:6270–6443](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/commands/run_cmd.py#L6270-L6443) [packages/fr/src/fr/commands/run_cmd.py:1937–1995](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/commands/run_cmd.py#L1937-L1995)

The transaction boundary is less clear than the type boundary. A transition can involve cursor bytes, a Git commit, evidence files, and live session state. F02 concerns the write mechanism. A separate, unverified concurrency risk concerns two commands reading the same pending state before either persists a hold. Atomic replacement would protect file integrity but would not, by itself, prevent lost updates or duplicate briefs.

### Critical path 3 — triage batch to runner

The pure batch driver takes facts and time and returns ordered actions. The command resolves configuration, reservations, gates, claims, dispatch, and bookkeeping. It acknowledges partial success when a backend launch succeeds but local event recording fails and gives a repair instruction. This is careful handling of irreversible effects. [packages/fr/src/fr/triage/batch_drive.py:1732–1800](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/triage/batch_drive.py#L1732-L1800) [packages/fr/src/fr/commands/triage_batch_cmd.py:1763–1967](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/commands/triage_batch_cmd.py#L1763-L1967)

The principal triage dispatch path calls the duplicate-work lookup directly and aborts if it raises. F01 affects the generic tick fallback, so it must not be attributed to every dispatch entry point. [packages/fr/src/fr/commands/triage_batch_cmd.py:1900–1945](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/commands/triage_batch_cmd.py#L1900-L1945)

### Critical path 4 — isolation and cleanup

The backend for an existing workspace comes from its recorded mode, not a changed ambient environment. Teardown checks dirty or unlanded content, stages preservation, verifies removal, and retains a recovery copy when later bookkeeping fails. Host-worktree mode sensibly reuses lifecycle logic without pretending to provide container-level separation. [packages/fr/src/fr/isolation/routing.py:24–51](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/isolation/routing.py#L24-L51) [packages/fr/src/fr/isolation/local.py:2038–2108](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/isolation/local.py#L2038-L2108)

F03 occurs earlier, during identity selection. Correct cleanup guards cannot make a colliding state key identify the requested workspace. The audit demonstrated wrong state resolution, not destruction of a different real worktree.

### Critical path 5 — trusted manual operations and artifact relocation

Manual operation selection computes a fingerprint and requires an operator-local trust record before status, apply, or attestation executes repository-authored probes. The trust record lives outside the checkout; a PR-carried journal entry cannot grant trust. Referenced commands, configuration, and the committed code tree contribute to the fingerprint. Noninteractive probes use a bounded timeout and an explicit environment. The environment is not a filesystem sandbox, and trusted repository-authored code still has the operator's operating-system access. [packages/fr/src/fr/commands/ops_cmd.py:112–132](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/commands/ops_cmd.py#L112-L132) [packages/fr/src/fr/commands/ops_cmd.py:224–240](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/commands/ops_cmd.py#L224-L240) [packages/fr/src/fr/ops/trust.py:1–17](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/ops/trust.py#L1-L17) [packages/fr/src/fr/ops/probe.py:1–9](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/ops/probe.py#L1-L9)

Apply orders operations before executing them, checks unselected prerequisites, checks required confirmations before a nonterminal run, stops on failure, and rechecks outcomes after execution. An unchecked prior apply does not silently become verified completion. Interactive operations deliberately attach the operator's terminal and have no automatic timeout. That exception is reasonable for human-driven work and is distinct from F05's automatic CLI-step capture. The gate sequencer records completion host-side rather than accepting a PR-controlled journal as authority. [packages/fr/src/fr/ops/apply.py:206–265](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/ops/apply.py#L206-L265) [packages/fr/src/fr/ops/apply.py:285–337](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/ops/apply.py#L285-L337) [packages/fr/src/fr/ops/probe.py:77–105](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/ops/probe.py#L77-L105) [packages/fr/src/fr/ops/gate.py:1–24](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/ops/gate.py#L1-L24)

Artifact migration refuses inappropriate automatic commits and locks the Git common directory before migration and commit. Settings expose per-key provenance and distinguish pending edits from the selected source. Placement moves compare destination bytes, effective acceptance folds, and structural validation before switching the placement. This is appropriate safety work for relocatable Git artifacts. It also illustrates why F02 and F04 are inconsistencies: atomic replacement and path-aware validation already exist in neighboring subsystems. No actual migration, placement move, or manual operation was performed during this audit. [packages/fr/src/fr/artifacts/trigger.py:590–635](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/artifacts/trigger.py#L590-L635) [packages/fr/src/fr/settings/load.py:372–412](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/settings/load.py#L372-L412) [packages/fr/src/fr/placement/move.py:1147–1177](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/placement/move.py#L1147-L1177)

### Architectural evolution

Adding another runner is reasonably local because entry-point registration and optional protocols correspond to existing distinct backends. Adding another harness requires hook wiring, session detection, transcript reading, mirrored rules, and parity evidence. Generated mirrors and tripwires reduce drift, but current event and terminal behavior still needs live verification.

A new evidence kind or delivery gate is more expensive. It can touch a large command module, evidence derivation, persistence, rollback, reporting, and tests. This is the strongest simplification opportunity. Extract typed evidence decisions and state transitions into cohesive modules. Keep a small explicit coordinator for effects. Splitting the same functions into many arbitrary files would not solve the ownership problem.

Git-backed plans, journals, and acceptance fragments are proportionate for reviewable developer workflows. A central service or database would add synchronization and deployment costs without evidence that current scale requires it. The immediate need is reliable file replacement and explicit ownership, not a storage-platform rewrite.

## Detailed findings

### F01 — Failed dedup lookup permits another generic dispatch

**P2 · Reproduced framework defect · High confidence.**

`tick` catches a failure from `existing_dispatches`, records an error, and substitutes an empty set. It then calls `dispatch` for work whose backend state is unknown. For run and spec items, the backend lookup can be the only duplicate-submission protection. [packages/fr-dispatch/src/fr_dispatch/__init__.py:508–518](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr-dispatch/src/fr_dispatch/__init__.py#L508-L518) [packages/fr-dispatch/src/fr_dispatch/__init__.py:549–568](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr-dispatch/src/fr_dispatch/__init__.py#L549-L568)

The safe fixture used the real tick and manifest parser with an in-memory runner. The first call submitted one stable run ID. The second call made the duplicate lookup raise a timeout. Both calls returned `synced=1`, and the runner recorded the same ID twice. The retry also returned an error, so this is not a silent success; nevertheless, an error did not prevent the fresh allocation.

```
first call:  synced=1, errors=0
retry:       synced=1, errors=1, "dedup fetch failed"
allocations: ["audit/repo/run/same-run", "audit/repo/run/same-run"]
```

An existing behavioral test explicitly requires this fallback and asserts that dispatch occurs. It is mechanically meaningful testing of the wrong general safety contract. [tests/unit/test_tick_workitem.py:671–684](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/tests/unit/test_tick_workitem.py#L671-L684)

The availability-first choice can be reasonable when every backend independently enforces idempotency. cncd declares a server upsert contract, and cloud pending requests have local reuse protections. The general runner interface does not establish that guarantee for all adapters. Herdr allocation has additional external behavior that was not exercised here. The audit therefore does not claim two paid sessions were actually launched, or that the primary triage dispatch has this failure.

Defer fresh allocations when backend duplicate state is unavailable. Preserve retry on the next tick and report the reason. Alternatively, require and test an authoritative backend idempotency key for every adapter before permitting this fallback. A contract test should submit once, fail the next lookup, retry, and prove that the allocation count remains one.

### F02 — Cursor write failure destroys the last valid local state

**P2 · Reproduced OS fault · High confidence.**

`save_run_state` replaces the cursor with `Path.write_text`, which truncates before a full replacement has succeeded. [packages/fr/src/fr/run/model.py:596–601](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/run/model.py#L596-L601)

A disposable fixture created a valid 134-byte cursor. A child process then set its OS file-size limit to 64 bytes and called the actual save function. The write raised an `OSError`; the original file was now 64 bytes, and the real loader rejected it as invalid YAML.

```
child_exit: 23
before_bytes: 134
after_bytes: 64
original_preserved: false
load result: RunStateError, invalid YAML
```

This proves loss of the latest valid local cursor under a write failure. It does not establish a historical incident or its frequency. An older committed cursor can be recovered from Git, but uncommitted progress is not preserved and normal resume fails.

The repository already has an atomic writer for this class of failure. Reuse it rather than introducing another abstraction. Journal append also reads and rewrites the whole file through `write_text`, so it shares the mechanism; that path was identified statically rather than counted as another separately reproduced defect. [packages/fr/src/fr/artifacts/atomic.py:1–25](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/artifacts/atomic.py#L1-L25) [packages/fr/src/fr/artifacts/atomic.py:41–75](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/artifacts/atomic.py#L41-L75) [packages/fr/src/fr/journal/model.py:878–886](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/journal/model.py#L878-L886)

Verify that interrupted replacement leaves the old cursor and journal readable and unchanged. Include failed temporary writes and failed replace operations. Review filesystem durability requirements separately from cross-process ownership.

### F03 — Lossy branch encoding aliases workspace state

**P2 · Reproduced identity defect · High confidence.**

`branch_slug` replaces `/` with `__`. Both `feat/a` and `feat__a` are valid Git branch names, but they yield the same slug. The slug selects the state file and default worktree directory. Saving state overwrites the shared file, and loading by branch does not compare the stored branch with the requested branch. [packages/fr/src/fr/isolation/types.py:95–102](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/isolation/types.py#L95-L102) [packages/fr/src/fr/isolation/types.py:146–177](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/isolation/types.py#L146-L177)

The fixture verified both names with Git, saved distinct state records, then loaded `feat/a`. It received the branch and workspace recorded for `feat__a`.

```
same_state_path: true
requested branch: feat/a
loaded branch: feat__a
loaded workspace: workspace-two
```

The CLI accepts this loaded state without an identity comparison. Creation also has an early return when the default worktree path already exists. Those paths strengthen the practical relevance of the collision, but no destructive teardown of a real wrong workspace was attempted. [packages/fr/src/fr/commands/isolation_cmd.py:178–204](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/commands/isolation_cmd.py#L178-L204) [packages/fr/src/fr/isolation/local.py:2711–2713](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/isolation/local.py#L2711-L2713)

Use a reversible encoding or a readable slug plus a hash of the exact branch string. Refuse a loaded identity mismatch immediately. Define migration or backward-compatible reads for existing records. Verify the encoding over generated valid branch names, including slash and underscore combinations, and assert that state for one branch cannot be returned for another.

### F04 — cncd includes text outside the validated plan directory

**P2 · Reproduced payload inclusion · High confidence; severity depends on trust boundaries.**

`build_ingest_payload` reads every plan-directory child for which `is_file()` is true. That follows symlinks. The parser reads expected plan artifacts but does not reject an unrelated symlink. The transport posts the constructed payload. [packages/fr-cncd/src/fr_cncd/runner.py:85–99](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr-cncd/src/fr_cncd/runner.py#L85-L99) [packages/fr/src/fr/parser.py:259–279](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/parser.py#L259-L279) [packages/fr-cncd/src/fr_cncd/runner.py:155–162](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr-cncd/src/fr_cncd/runner.py#L155-L162)

A valid plan fixture contained an extra symlink to synthetic text outside the plan. Parsing succeeded and the payload included that text. The challenge fixture committed the symlink in a disposable Git repository and passed the actual apply reachability check and cncd preflight and routing checks. No network request was sent.

```
Git checkout established: true
missing required reachable paths: []
cncd preflight: no refusal
can_dispatch: true
outside synthetic value in payload: true
network calls: 0
```

Local inclusion is demonstrated. Actual network disclosure was not executed. Impact requires cncd dispatch, a readable target, and a receiving control plane outside the relevant confidentiality boundary. A normal issue title does not create this path. Less-trusted plan content processed by a more privileged dispatcher raises the severity. Even in a fully trusted deployment, accidental auxiliary-file inclusion can transfer unintended data.

Verbatim auxiliary files may be intentional, so removing every non-schema filename without defining attachments could break supported behavior. Establish an explicit attachment policy. Refuse symlinks and non-regular files, bind selected real paths to the plan root, and bound file and payload sizes. Prefer validated artifacts plus declared attachments. Tests should assert refusal and zero transport calls for outside symlinks, unintended hidden files, and oversized content.

### F05 — CLI steps have unbounded runtime and captured output

**P2 · Static reliability and resource risk.**

The workflow executor uses `subprocess.run(..., shell=True, capture_output=True, text=True)` without a timeout. It then persists complete stdout in the cursor. A command that never exits can block the advancing process indefinitely. Large output can grow memory and the tracked cursor. [packages/fr/src/fr/commands/run_cmd.py:6436–6443](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/commands/run_cmd.py#L6436-L6443)

The risk follows directly from the API call, but no representative hang, memory limit breach, or latency regression was measured. Long-running verification may be legitimate. Operator-authored command templates also explain shell execution; shell use alone is not an injection finding because substituted values are quoted. [packages/fr/src/fr/commands/run_cmd.py:3889–3911](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/commands/run_cmd.py#L3889-L3911)

Add an explicit per-step or workflow deadline, process-group cancellation semantics, a bounded diagnostic tail, and a separate log artifact. Represent timeout and cancellation outcomes in state. Allow documented opt-in for unusually long tasks rather than imposing an arbitrary short universal timeout.

### F06 — Installed dependencies can differ from release-tested dependencies

**P2 · Static reproducibility gap · High confidence.**

The normal installer uses `uv tool install --force` against workspace distributions without supplying the workspace lock or release constraints. The core package's five external direct runtime requirements have lower bounds only. The same source release can therefore resolve a different dependency set on a later installation. Optional installation of `@devcontainers/cli` is unversioned. [scripts/install.sh:874–903](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/scripts/install.sh#L874-L903) [packages/fr/pyproject.toml:6–12](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/pyproject.toml#L6-L12) [scripts/install.sh:1074–1083](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/scripts/install.sh#L1074-L1083)

This does not prove an incompatibility or vulnerable installation. Broad library requirements are common and allow fixes to flow. The concern is an integrated automation product whose tested lock and delivered environment diverge. Its staged install checks mitigate some failures but do not establish equality with release CI.

Generate release-specific constraints, test a fresh consumer install against them, and record resolved versions. Keep flexible library metadata if desired. Pin or document and test the supported devcontainer CLI range. Advisory results for this audit's lock cannot certify every dependency set the installer may resolve.

### F07 — Claude edit hook loses its decision without jq on PATH

**P2 · Reproduced enforcement-process gap · High confidence on process behavior.**

The Claude edit hook invokes bare `jq` before calling shared decision logic. With a valid Edit payload and a stripped PATH containing only `dirname` and `cat`, it exits 127 and emits no deny JSON. No edit was attempted. The source itself describes the resulting behavior as fail-open. [plugins/super-fr/hooks/fr-isolation-required.sh:24–37](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/plugins/super-fr/hooks/fr-isolation-required.sh#L24-L37)

Actual Claude continuation after that failure was not exercised, so the demonstrated result is the missing decision, not a completed unauthorized edit. Installation normally requires jq, which reduces exposure. Service PATH differences still matter, and the shared library already resolves parsers through absolute paths. [plugins/super-fr/hooks/lib/fr-isolation-decision.sh:19–45](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/plugins/super-fr/hooks/lib/fr-isolation-decision.sh#L19-L45)

Route entry parsing through the existing resilient parser mechanism and make failure behavior explicit. Verify a valid protected edit produces a deny decision under a stripped service PATH. Treat this as reliability of a discipline guard. The hooks have deliberate bypasses and do not promise containment against hostile code.

### F08 — Command modules concentrate policy and transaction coordination

**P3 · Architectural assessment supported by measurements.**

`run_cmd.py` has 8,773 physical lines, and `triage_batch_cmd.py` has 7,343. Together they account for 11.3% of production Python physical lines. The issue is the mixture of responsibilities, not a file-length rule. Evidence interpretation, transitions, side-effect ordering, persistence, commit behavior, diagnostics, and CLI presentation appear together. [packages/fr/src/fr/commands/run_cmd.py:1937–1995](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/commands/run_cmd.py#L1937-L1995) [packages/fr/src/fr/commands/run_cmd.py:7488–7545](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/commands/run_cmd.py#L7488-L7545) [packages/fr/src/fr/commands/triage_batch_cmd.py:1422–1475](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/commands/triage_batch_cmd.py#L1422-L1475)

Recent history also repeatedly touches these files. Within the last 100 reachable commits, `run_cmd.py` appeared in 14 commit file lists and `triage_batch_cmd.py` in 13. This is a bounded churn sample, not a defect-density estimate or a causal claim.

The realistic cost is adding a delivery evidence requirement or changing dispatch recovery without overlooking another effect or rollback rule. Extract cohesive evidence-policy and state-transition functions with typed inputs and results. Keep effect ordering visible in a small coordinator. Avoid a generic workflow framework or a cosmetic file split that preserves the same hidden dependencies.



--- comment, 2026-11-16T17:52:39Z (36102 chars) ---
<!-- full-principal-audit:f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37:part:2 -->
## Full engineering audit part 2 of 2

Publishing the complete original audit for the implementing agent. **Original assessment: 15 November 2026, commit `f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37`, v8.0.0.** The report text is unabridged across these two comments. Its statements about read-only work and verification describe that original audit session; later issue filing and the supplement are separate work.

The [focused supplement](https://github.com/derio-net/super-fr/issues/1318#issuecomment-6923555343) is pinned to `a4281f85`. The [bug tracking index](https://github.com/derio-net/super-fr/issues/1318#issuecomment-6924421644) records rechecks at `33e12d67`: #1499, #1500, #1419, #1501. Keep those behavior fixes separate from #1318's behavior-preserving refactors. This publication does not refresh the original score or claim to audit current main.

---

## Test effectiveness

### What the suite demonstrably does well

The suite contains many tests of externally observable state, negative paths, and persistence. It is not fairly characterized as mostly testing theater. Examples include preserving operator labels after a real render-diff-apply sequence, reopening a mailbox from disk and preserving a pending request ID, refusing workflow dependency cycles, and respecting an operator gate in CLI liveness output. [tests/unit/test_v2_apply.py:116–159](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/tests/unit/test_v2_apply.py#L116-L159) [tests/unit/test_claude_cloud_mailbox.py:130–166](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/tests/unit/test_claude_cloud_mailbox.py#L130-L166) [tests/unit/test_workflow_check.py:77–86](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/tests/unit/test_workflow_check.py#L77-L86) [tests/unit/test_run_idle.py:125–140](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/tests/unit/test_run_idle.py#L125-L140)

Herdr tests cover bounded retries, cleanup, and absence of prompt delivery after repeated launch failure. Recovery tests inspect checkpoints and ownership behavior rather than merely checking that a function ran. Fakes are appropriate for paid or interactive backends, provided they are complemented by contract and live compatibility evidence. [tests/unit/test_fr_herdr_runner.py:453–476](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/tests/unit/test_fr_herdr_runner.py#L453-L476)

The suite also encodes architectural rules. Package-import tests constrain the base, framework, and adapters and include tests that their own tripwires reject representative violations. Generated mirror and registration tests protect shipped integration consistency. Regex import scans are useful but narrower than a complete dependency graph. [tests/unit/test_import_direction.py:20–103](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/tests/unit/test_import_direction.py#L20-L103)

### What passing tests do not establish

The clearest counterexample is F01. Its test observes dispatch and the error accurately but approves the wrong fallback. Increasing line coverage would strengthen confidence in that behavior without making it safe. Requirements and failure-policy review remain necessary.

Global fixtures deliberately replace live model probes, rate-limit reads, label synchronization, ambient sessions, and migration behavior. This protects the operator and makes tests deterministic. It also means most tests do not prove real entry-point migration, current service behavior, or credential routing. Dedicated tests must restore those boundaries explicitly. The fixtures document this responsibility, which is a strength. [tests/conftest.py:76–96](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/tests/conftest.py#L76-L96) [tests/conftest.py:163–190](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/tests/conftest.py#L163-L190) [tests/conftest.py:285–305](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/tests/conftest.py#L285-L305)

Some prose and source-text tripwires verify delivery or architectural constraints rather than runtime business behavior. They provide real value when preventing generated-content drift. They should not be counted as evidence that an interactive agent actually obeys a prompt or that a live external API remains compatible.

Important missing or insufficiently established properties are failure-preserving cursor writes, collision-free branch identity, payload path confinement, and the safe duplicate-lookup contract. Concurrent advance/resolve ownership remains an unverified gap. Property-based tests are especially suitable for identity encodings and journal event sequences; no repository-wide generative-testing result was established here.

### Controlled mutation experiments

The audit changed four functions only in process memory. It never edited repository source. Each selected test set first passed against the original implementation. The mutated run then failed on the intended behavioral assertion, rather than collection or fixture errors. An independent reviewer checked those logs.

| Mutation | Selected requirement | Observed result |
|---|---|---|
| Treat every label as managed. | Operator-owned label survives synchronization. | Test fails because `good-first-issue` disappears. |
| Return no workflow cycles. | Mutually dependent steps are rejected. | Test fails because no cycle is reported. |
| Ignore later journal resolution states. | Resolved/deferred findings leave the open state. | Two tests fail on handoff/effective-state results. |
| Always report no pending operator gate. | A gated run is not reported as idle and advanceable. | CLI test fails on exit code, idle flag, and reason. |

**Four deliberately selected mutations were detected by five selected tests.** This is positive local evidence, not a representative sample, a full mutation score, or proof that other critical faults will be caught. No surviving-mutant distribution was measured. The scripts and all eight baseline/mutated logs are included in the evidence bundle.

### Local and remote verification results

| Check | Local result | Scope |
|---|---|---|
| Ruff lint | Pass | All packages and tests, no cache writes in the clone. |
| Ruff formatting | Pass; 1,221 files already formatted | Check-only operation. |
| Strict mypy | Pass; 415 source files | All five Python source trees. |
| Unit collection | 15,782 tests collected | Python 3.13.13. Collection is not execution. |
| Broad unit run | 904 passed, then interrupted; 224.68 seconds | Deliberately bounded, exit code 2 from interruption. Not a full-suite pass. |
| Focused critical-path run | 458 passed; 321.99 seconds | Twelve test modules spanning tick, journal, runners, synchronization, workflow validation, idle gates, acceptance folding, and import direction. |
| Plugin typecheck | Pass | Exact source tree copied outside the clone, locked Bun dependencies. |
| Plugin tests | 292 passed, 0 failed; 75.60 seconds | Sixteen test files, 572 expectations, Bun 1.3.11. No live OpenCode session. |
| Targeted mutation checks | Four mutants detected; all baselines pass | Five selected tests, in-memory changes only. |

The focused Python run measured 20,563 covered statements out of 64,810 in the whole configured Python source denominator, or 31.73%. It exercised a deliberately small test subset, so that percentage is not the repository's full-suite coverage and must not be compared with the full-suite CI floor. Branch coverage was not enabled. The broad and focused executions overlap, so their pass counts must not be added into a distinct-test total.

Tests ran with network restricted. Python children used offline dependency settings, and the completed focused run put the audit environment's executables first on PATH. The first isolated plugin copy lacked repository-relative hook paths; its failures were fixture-layout errors, not product findings. The final plugin run used a complete copy of the pinned source layout and passed. No installation, hook registration, or live runner was exercised on the operator's environment.

The pinned GitHub CI run completed successfully, including lint, strict type checking, Python 3.11 and 3.14 test legs with seven shards each, coverage combination, split-completeness checks, artifact validation, and two OpenCode version jobs. The change-fragment job was skipped on the main-branch push by its own condition. [Pinned CI run](https://github.com/derio-net/super-fr/actions/runs/43710966002).

The full workflow ran from 11:51:52 to 11:57:57 UTC, 365 seconds. Individual successful test jobs took 168 to 323 seconds including their job setup and other steps. These are recorded workflow durations, not application performance benchmarks or a long-term CI reliability rate. The first run page also contains many ci-budget workflow runs; those were not counted as independent full-suite successes.

Coverage configuration measures statements and enforces an aggregate 75% floor. It does not enable branch coverage in the inspected configuration. A successful coverage job establishes that its configured floor passed, but the precise overall percentage was not retrieved and is not invented here. [pyproject.toml:56–62](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/pyproject.toml#L56-L62) [.github/workflows/ci.yml:218–236](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/.github/workflows/ci.yml#L218-L236)

## Quantitative assessment

The reproducible stdlib metrics script enumerated tracked files at the pinned commit and parsed production Python under `packages/*/src`. Generated assets, docs, shell scripts, and TypeScript are excluded from Python size distributions. Physical lines include comments and blanks. Test definitions exclude parametrization multiplicity and are not a quality score.

| Metric | Value | Interpretation and limit |
|---|---:|---|
| Tracked files | 3,997 | Includes extensive docs, mirrors, fixtures, and historical artifacts. |
| Production Python files | 415 | Five Python package source trees. |
| Production Python physical lines | 142,146 | Size of the Python implementation, not executable statement count. |
| Production file lines, median / p90 / p95 / maximum | 193 / 703 / 1,110 / 8,773 | Most files are moderate; a few coordination files dominate. |
| Function definitions | 5,754 | Includes methods and nested definitions. |
| Function lines, median / p90 / p95 / maximum | 10 / 38 / 57 / 330 | A generally small-function style coexists with concentrated complex coordinators. |
| AST decision proxy, median / p90 / p95 / maximum | 3 / 11 / 15 / 116 | Branch-node heuristic, including nested definitions; not a calibrated McCabe or cognitive-complexity measure. |
| Python test files | 806 | Includes test support modules under tests. |
| Test function definitions | 12,148 unit; 322 integration | Definitions, not executions or independent requirements. |
| Unit tests collected locally | 15,782 | Includes parametrization, on Python 3.13.13 in this environment. |
| Direct external runtime dependencies of fr | 5 | Typer, PyYAML, Rich, Pydantic, Packaging. |
| Exported external runtime lock entries | 16 | Includes Windows-only colorama; 15 applicable entries scanned locally. |

The largest Python files are `run_cmd.py` at 8,773 lines, `triage_batch_cmd.py` at 7,343, `isolation/local.py` at 3,164, `plan_ops.py` at 2,545, and `triage/batch_drive.py` at 2,130. Decision-proxy hotspots include `drive_pass` at line 1732 with 116 and `_acceptance_writes` at line 1227 with 102. These are candidates for careful review, not automatic refactor mandates. The pure driver has substantial domain complexity that a cosmetic split would not remove. [packages/fr/src/fr/triage/batch_drive.py:1732–1800](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/triage/batch_drive.py#L1732-L1800) [packages/fr/src/fr/record/apply.py:1227–1280](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/record/apply.py#L1227-L1280)

Absolute import counts show the expected framework-to-core and adapter-to-framework relationships, plus optional core command imports of the dispatch framework. This does not prove a package cycle or its absence: dynamic and relative imports and runtime loading need a complete graph. No complete internal cycle count or duplication percentage was produced. Reporting either as zero would be misleading.

The last-100-commit source churn sample places `gate_cmd.py` first with 20 appearances, followed by gate-backfill candidates with 15, `run_cmd.py` with 14, and tracker/triage modules with 13. Recent commits include frequent release and close-out changes. This supports targeting high-change policy code for boundary review, but it cannot establish deployment frequency, escaped defect rate, or bus factor.

## Performance and scalability

**Assessment: reasonable for developer-workflow scale; low confidence beyond that scale.** No representative production workload, p95 application latency, throughput, peak memory, startup distribution, or recovery-time benchmark was measured. CI elapsed times and a static complexity proxy do not substitute for these metrics.

Several choices are sound. Tick snapshots capacity and existing work once per batch, reducing repeated backend reads. Lifecycle subprocesses have finite timeouts. Acceptance reconstruction batches Git blob reads rather than spawning a process per blob. The deterministic driver can be tested and profiled without network effects. [packages/fr-dispatch/src/fr_dispatch/__init__.py:486–518](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr-dispatch/src/fr_dispatch/__init__.py#L486-L518) [packages/fr-dispatch/src/fr_dispatch/lifecycle.py:33–62](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr-dispatch/src/fr_dispatch/lifecycle.py#L33-L62) [packages/fr/src/fr/acceptance/fold.py:155–173](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/acceptance/fold.py#L155-L173)

The likely scale boundaries are specific:

- Observation reads tracked issue and linked-PR state per phase. The number of remote operations grows with tracked phases, and remote latency can dominate pure calculations. This is a source-supported scaling concern, not a measured N+1 latency incident. [packages/fr/src/fr/observe.py:43–61](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/observe.py#L43-L61)
- Herdr session listing scans agents for each tab, and some status queries scan tabs per item. At high cardinality these become repeated linear or quadratic work. Normal terminal-session counts may make this irrelevant compared with subprocess latency. [packages/fr-herdr/src/fr_herdr/runner.py:209–212](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr-herdr/src/fr_herdr/runner.py#L209-L212) [packages/fr-herdr/src/fr_herdr/runner.py:316–329](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr-herdr/src/fr_herdr/runner.py#L316-L329)
- cncd serializes the whole plan folder per phase submission. For P phases and B bytes of folder content, aggregate payload work can be proportional to P times B. Path policy and payload limits are more urgent than compression or caching. [packages/fr-cncd/src/fr_cncd/runner.py:85–99](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr-cncd/src/fr_cncd/runner.py#L85-L99)
- Mailbox collection and YAML replacement favor simplicity at small scale. Large histories can increase scan and rewrite work. There is no evidence here that a database would repay its operational cost.
- F05 supplies a clearer resource hazard than these algorithmic observations: an unbounded subprocess can block progress or retain arbitrary output regardless of normal plan size.

The next measurement should run a representative plan and batch at documented small, typical, and large sizes with fake remote latency and then an authorized staging backend. Record call counts, wall time, memory, payload bytes, and timeout/recovery outcomes. Optimize the dominant cost only after that measurement. Add per-run API budget evidence and keep unknown/unavailable measurements distinct from zero.

## Security and dependencies

This is a risk-oriented source audit, not a penetration test. The relevant trust boundaries are operator-authored executable configuration, potentially less-trusted repository or forge content, ambient filesystem and credentials, external runners, and generated reports.

Positive controls include quoted template substitutions, argv-based forge calls, finite gh timeouts, safe YAML loading, enterprise-host trust checks before credential routing, escaped board text and HTTPS link restrictions, and an allowlist of usage fields persisted to shared artifacts. These controls address concrete classes of failure. They should remain centralized. [packages/fr/src/fr/commands/run_cmd.py:3889–3911](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/commands/run_cmd.py#L3889-L3911) [packages/fr/src/fr/gh.py:105–208](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/gh.py#L105-L208) [packages/fr/src/fr/yamlio.py:12–19](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/yamlio.py#L12-L19) [packages/fr/src/fr/triage/render.py:404–430](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/triage/render.py#L404-L430) [packages/fr/src/fr/usage/file.py:9–18](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/usage/file.py#L9-L18)

The strongest demonstrated confidentiality concern is F04. Merely seeing `shell=True` is not an additional injection vulnerability when the manifest is intended executable configuration and substituted values are quoted. Likewise, host-worktree isolation and discipline hooks do not claim a hostile-code security sandbox. Assess privileges of the runner environment accordingly.

The Python runtime lock was exported without development or workspace distributions. `pip-audit` checked the 15 entries applicable on this platform and returned no known vulnerabilities. Windows-only colorama was excluded by its environment marker. The scan used exact names and versions without dependency resolution; it did not install or execute repository code. This is advisory-database evidence at audit time, not proof of absence of vulnerabilities or a result for every future consumer install.

**F09 is a confirmed dependency-version finding with unverified product exploitability.** Bun's audit reported two moderate advisories. The checked lock contains `glob` 13.0.5 and a nested 10.5.0, plus `minimatch` 10.2.5 and a nested 9.0.9. These match the published affected ranges. The direct development dependency `@opencode/plugin` 2.1.0 pulls in `@opencode/util`, and another path through `@opencode/ai`, Google authentication, and rimraf supplies nested versions. The host also supplies an OpenCode peer dependency, so the development graph is not proof that the plugin ships all of these packages into every runtime. [packages/fr-opencode-plugin/package.json:14–21](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr-opencode-plugin/package.json#L14-L21) [packages/fr-opencode-plugin/bun.lock:294](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr-opencode-plugin/bun.lock#L294) [packages/fr-opencode-plugin/bun.lock:360](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr-opencode-plugin/bun.lock#L360) [packages/fr-opencode-plugin/bun.lock:532](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr-opencode-plugin/bun.lock#L532) [packages/fr-opencode-plugin/bun.lock:560](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr-opencode-plugin/bun.lock#L560)

| Advisory | Affected locked packages | Published concern and scope |
|---|---|---|
| [GHSA-3g3m-2fjr-6pw4](https://github.com/advisories/GHSA-3g3m-2fjr-6pw4) | glob 13.0.5 and 10.5.0 | Moderate availability issue: cancelled traversal can continue filesystem work. The record lists a fix in 14.0.2. |
| [GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249) | minimatch 10.2.5 and 9.0.9 | Moderate resource-consumption issue with attacker-influenced patterns. The record lists a fix in 11.0.1. |

No advisory proof of concept was run against super-fr, and no attacker-controlled pattern or traversal path was established through its plugin. Update the upstream dependency graph or select compatible patched resolutions, then rerun type checking, the plugin suite, and the live compatibility probe. Do not force a major-version override without compatibility evidence. The raw scan and dependency paths are in the evidence archive. These two dependency records do not change the count of four reproduced product boundary defects.

The committed Dependabot configuration schedules GitHub Actions updates. It does not configure Python or npm ecosystem updates, and no committed runtime-advisory CI gate was found in the inspected workflows. Repository-level alert settings may exist and were not established by this review. Automate advisory scanning and triaged exceptions for the installed release environment, including JavaScript and external CLIs. [.github/dependabot.yml:1–9](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/.github/dependabot.yml#L1-L9)

cncd authentication and transport safety depend partly on its external deployment. The adapter accepts a configured URL and forward-auth identity; localhost or trusted-network HTTP may be intended. No authentication bypass is established without the server and proxy configuration. The public product root is MIT licensed. A complete transitive license compatibility review was not performed.

Main CI does not declare a top-level explicit permissions policy in the inspected file. Effective token permissions depend on repository and organization defaults. Some release paths explicitly reduce credential exposure, which is good. Least-privilege declarations would make the guarantee auditable. Branch protection could not be read through the connected integration: GitHub returned 403. That is an access limitation, not evidence that protection is absent. [.github/workflows/ci.yml:1–37](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/.github/workflows/ci.yml#L1-L37) [.github/workflows/release.yml:103–139](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/.github/workflows/release.yml#L103-L139)

An escaped issue URL interpolated by the architecture report does not reuse the board's HTTPS gate. A dangerous scheme is a defense-in-depth concern if the cache is untrusted, but normal forge API URLs do not establish an attacker-controlled path. This was deliberately excluded from the demonstrated vulnerability list. [packages/fr/src/fr/triage/architecture.py:234–237](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/packages/fr/src/fr/triage/architecture.py#L234-L237)

## Operations and developer experience

The repository's CI is substantially stronger than a minimal green test badge. It tests the Python floor and newest declared leg, proves shard completeness, combines coverage once, checks artifact structure from an installed CLI, typechecks the plugin, probes real OpenCode delivery in dedicated jobs, validates version lockstep, checks docs currency, and builds the site. The aggregate `ci-ok` job rejects failed or cancelled dependencies. [.github/workflows/ci.yml:76–171](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/.github/workflows/ci.yml#L76-L171) [.github/workflows/ci.yml:268–309](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/.github/workflows/ci.yml#L268-L309) [.github/workflows/ci.yml:374–384](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/.github/workflows/ci.yml#L374-L384)

Release staging and tests separate preparation from publication and reduce credential access in suite jobs. The pinned commit's release runs were successful in the queried snapshot. That supports this release's gate completion, not long-term delivery reliability. Installer locks, staging, stale-lock recovery, and preservation of active executable links demonstrate attention to operational reality. [.github/workflows/release.yml:82–139](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/.github/workflows/release.yml#L82-L139) [scripts/install.sh:8–63](https://github.com/derio-net/super-fr/blob/f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37/scripts/install.sh#L8-L63)

Developer onboarding has extensive current command documentation and explicit test-isolation fixtures. The cost is a large amount of coupled policy documentation and generated mirrors. Technical drift checks help, but source-text agreement cannot prove clarity or live agent compliance. A focused domain glossary for cursor, attempt, finding, acceptance row, gate, claim, and session would reduce the learning burden if maintained beside the types.

Diagnosis benefits from explicit refusal messages, unknown states, partial-success records, journals, and run cost data. Recovery is uneven: sophisticated terminal replacement has checkpoints and locks while ordinary cursor writes still truncate. F02 and F06 are therefore operational priorities, not merely internal style issues.

No rollback or deployment recovery drill was run. External service health, production monitoring, backup retention, actual model/session startup compatibility, and service-level objectives remain unknown. This product is primarily a local workflow tool, so lack of a web-service tracing stack is not itself a defect.

## Engineering scorecard

The requested weights are unchanged. Fractional scores express judgment within the 0–5 rubric: 0 critical, 1 poor, 2 below standard, 3 solid, 4 strong, 5 exceptional. A category score does not mean its percentage of code is correct. Unknowns lower confidence, not automatically the score.

| Category | Weight | Score | Confidence | Main support and limitation |
|---|---:|---:|---|---|
| Architecture and design | 20% | 3.5 | Medium-high | Pure planners, typed mutation data, real adapter seams, justified Git artifacts. Command-layer ownership and transaction boundaries need improvement. |
| Code quality and maintainability | 15% | 3.0 | High on measured structure; medium on future cost | Lint, formatting, and strict typing pass; small median function size. High-change command hotspots concentrate policy and effects. No calibrated duplication/cognitive-complexity result. |
| Correctness and reliability | 15% | 2.5 | High on four local defects; medium overall | Explicit holds, recovery checkpoints, and failure modeling are strengths. Four boundary defects are reproduced; live incident frequency and concurrency behavior remain unknown. |
| Test effectiveness | 20% | 3.5 | Medium-high | Strong behavioral and negative tests, four targeted mutants detected, serious CI. One test pins unsafe failure semantics; overall mutation effectiveness and branch coverage are not established. |
| Performance and scalability | 10% | 3.0, provisional | Low | Batch reads and capacity bounds fit developer workflows. No representative latency, throughput, or memory workload; unbounded CLI execution is a concern. |
| Security | 10% | 3.0 | Medium | Quoting, safe deserialization, host gating, output escaping, privacy allowlists. Conditional cncd inclusion defect and install drift remain; no penetration or deployment review. |
| Operability and developer experience | 10% | 3.5 | Medium-high | Extensive CI, release staging, diagnostics, installer recovery, documentation. Durability, dependency reproduction, and hook PATH behavior weaken the guarantees. |

Weighted result: **3.175 out of 5**, rounded to **3.2 out of 5**, or **63.5 out of 100** before rounding. The scale is ordinal judgment with explicit weights, not a statistically calibrated investment rating. No category merits 5 from this evidence. Performance remains particularly uncertain because workload data is unavailable.

## Prioritized roadmap

Effort ranges are planning estimates for an engineer familiar with the code, including focused verification. They are not measured delivery commitments and should be revised after reproducing the finding locally.

| Sequence | Work | Impact and acceptance evidence | Estimated effort | Change risk |
|---|---|---|---|---|
| 1 | Correct F01 duplicate-lookup semantics. | Lookup failure defers allocation; retry preserves one stable allocation. Exercise generic run/spec paths and adapters. | 0.5–2 days | Low-medium; changes an explicitly tested policy. |
| 2 | Reuse atomic replacement for cursors and journal writes. | A failed write preserves exact old readable bytes. Cover interrupted temp write and replacement failure. | 1–2 days | Low-medium; preserve permissions and existing serialization. |
| 3 | Fix isolation identity and migration. | Distinct valid branches never alias. A stored/requested identity mismatch refuses safely. Existing records remain recoverable. | 1–3 days | Medium; state naming affects existing workspaces. |
| 4 | Define cncd artifact/attachment confinement. | Outside symlinks and unintended files cannot enter payload; refusal makes no network call. Document attachments and size limits. | 1–3 days | Medium; preserve intentional files-win behavior. |
| 5 | Bound CLI execution and diagnostics. | Controlled hanging/noisy children produce explicit timeout/cancel outcomes, bounded cursor size, and retrievable logs. | 2–4 days | Medium; cancellation and legitimate long tasks need care. |
| 6 | Align consumer dependency resolution with release verification; add advisory automation. | Two fresh constrained installs yield the tested package set; advisory results are recorded and exceptions triaged. | 1–3 days | Low-medium; packaging changes affect onboarding. |
| 7 | Repair jq PATH handling using the existing parser mechanism. | Protected Edit payload yields a deny decision with stripped service PATH. Include real harness compatibility when available. | 0.5–1 day | Low; avoid inconsistent duplicate parser logic. |
| 8 | Establish ownership semantics for concurrent run commands. | Deterministic competing advance/resolve test proves no lost update or double brief. Add per-run locking or version checks only as required. | 2–4 days | Medium; ordering and recovery behavior are central. |
| 9 | Extract evidence policy and transition calculation from command hotspots. | Existing behaviors survive; new evidence types can be added without editing CLI/persistence/presentation together. | 1–2 weeks in small slices | Medium; avoid a wholesale rewrite. |
| 10 | Add sampled mutation and representative workload checks. | Repeatable defect-detection and call/resource evidence for high-risk paths; inspect surviving meaningful mutations. | 2–5 days initially | Low if advisory before gating. |

Include F09 in item 6. Triage the two moderate transitive advisories promptly, while keeping exploit reachability separate from the confirmed affected-version result.

Work items 1–4 are the immediate maintenance batch because they address demonstrated boundary failures. Restrict or supervise the affected features until their contract tests pass. Deployments with less-trusted plan authors and privileged cncd dispatch should treat item 4 as a release blocker for that use case. Work items 5–8 strengthen the operating contract. The architecture refactor follows those repairs so it is guided by observed responsibilities and preserved behavior.

Leave the successful designs intact: typed mutation data, pure batch decisions, explicit unknown values, effective-state journal folding, acceptance fragments, optional runner protocols, generated mirrors, and failure-aware recovery. A rewrite or broad “Clean Architecture” conversion is not supported by the findings.

## Unknowns and follow-up evidence

The audit does not establish a full-suite local pass, an overall mutation score, exact aggregate CI coverage percentage, complete module-cycle count, duplication ratio, long-term flake rate, long-term CI failure rate, production defect rate, representative application latency, peak memory, or recovery-time objectives. Each needs a measurement with an explicit scope and denominator.

It also does not establish current external cncd/herdr/cloud behavior, production credential privileges, branch protection, rollback effectiveness, or every installed dependency combination. The connected integration could not read branch protection. Tests were run with network restricted, and live paid/interactive effects were deliberately kept out of the audit.

The preceding limits do not invalidate the four reproduced defects. They limit claims about exposure, frequency, and deployment severity. Source-supported concurrency and resource risks remain separately labeled until controlled end-to-end experiments establish their behavior.

## Principal engineer verdict

I would accept long-term technical responsibility for this codebase with a focused maintenance commitment. Its domain model contains real engineering insight: unknown evidence is not zero, a resolved finding is not deleted history, an external session is not a local cursor, and a backend launch is not the same event as successful bookkeeping. Those distinctions make the product more credible than a collection of prompts wrapped around shell commands.

I would approve controlled operator-supervised use and require the four reproduced boundary defects to be resolved before making broader unattended-reliability claims. The core problem is inconsistent application of safety policy. Some difficult recovery paths are careful and explicit, while simpler shared paths still assume an empty backend, a collision-free slug, a complete write, or an innocuous directory child.

The best next investment is a small set of consistent guarantees: preserve old durable bytes on failure, preserve exact identity, treat unavailable duplicate state as unknown, and serialize only intended artifacts. Then separate policy from effects in the command layer. That sequence improves reliability and maintainability without replacing the product's sound core architecture.

## Reproduction and evidence

The companion evidence archive contains the metrics and mutation scripts, baseline and mutated logs, four defect reproductions, the additional cncd gate challenge, static-check logs, completed local test results, advisory output, condensed GitHub CI evidence, source-line validation, and repository status. Scripts create disposable fixtures; some require macOS or another POSIX system and the package/test dependencies. The cursor fault experiment uses `fork` and `RLIMIT_FSIZE` in a child only.

The HTML report is self-contained and its source links use the pinned full commit. Local logs are audit evidence rather than proof that future commits or remote deployments behave identically.


--- comment, 2026-11-16T17:53:07Z (2126 chars) ---
## Complete audit for the implementing agent

The **entire original principal-engineer audit is now posted here**, unabridged across two comments:

1. [Full audit part 1](https://github.com/derio-net/super-fr/issues/1318#issuecomment-6924468522): verdict, scope, architecture and critical paths, subsystem assessment, and detailed findings F01–F09.
2. [Full audit part 2](https://github.com/derio-net/super-fr/issues/1318#issuecomment-6924470527): test effectiveness and mutation experiments, quantitative metrics, performance, security/dependencies, CI/operations, confidence-rated scorecard, roadmap, unknowns, and principal-engineer verdict.

**Read alongside the [focused duplication-and-seams supplement](https://github.com/derio-net/super-fr/issues/1318#issuecomment-6923555343).** That supplement is the implementation-oriented review for this issue and records already-completed work, preservation contracts, recurrence guards, and touched-file conflicts.

Snapshot boundaries:
- Original full audit: **15 November 2026, `f0a45b5bdab08e8a0b1cdb5947f65cf2fa2b4c37`, v8.0.0**.
- Focused #1318 supplement: `a4281f855f2c80ecd901e05cafd55a7599f8d801`.
- Four bug reproductions rechecked: `33e12d678a37a93b7c215ad8ac9f8c070c905090`, matching v8.0.3 packages.

The original 3.2/5 assessment and test results belong to the original snapshot; publishing them does not re-audit current main. Full local suite completion and repository-wide mutation effectiveness were not claimed.

**Implementation boundary:** #1318's refactors preserve behavior. Corrected behavior belongs in the separate bug issues #1499, #1500, #1419, and #1501, with their own regression criteria. See the [bug tracking index](https://github.com/derio-net/super-fr/issues/1318#issuecomment-6924421644). Coordinate overlapping code changes with their owners.

All 117 pinned source citations remain in the full text. The separate bug issues contain executable safe reproductions. Raw logs, the inventory/mutation scripts, and the original evidence archive remain in the audit artifacts; this publication supplies the complete report text directly on GitHub.

<!-- fr:journal kind=decision scope=spec id=d-run-scope created=2026-11-16T18:33:29+00:00 decided_by=operator -->
### d-run-scope · decision · Run scope: the report plus the first guarded clusters (G01, R01, R02, R03)

Asked what this one-PR run delivers out of #1318's review and multi-PR sweep. The
operator chose "Report + first guarded clusters": the audit report, and in the same PR
the import-direction guard fix (G01), the gate and session-status vocabularies (R01,
R02) and the shared triage timestamp reader (R03). The remaining clusters are filed
as issues.

<!-- fr:journal kind=decision scope=spec id=d-prior-audit created=2026-11-16T18:33:29+00:00 decided_by=operator -->
### d-prior-audit · decision · The report reconciles the full audit, posted on #1318, with the supplement and the current code

Asked how to treat the broader audit the supplement cites. The operator chose to
supply it, then posted it on #1318 in two comments, with a bug index linking #1499,
#1500, #1419 and #1501 for F01–F04. Those four are behaviour fixes and stay out of
this PR. The audit text is recorded as the `brief-audit` entry.

<!-- fr:journal kind=decision scope=spec id=d-other-findings created=2026-11-16T18:33:29+00:00 decided_by=operator -->
### d-other-findings · decision · F05, F06, F07, F09 and the cursor race: re-check, and file an issue for each one still present and untracked

The operator chose "Re-check and file issues". The report records each one's status
at its commit. For each still present, the run looks for an existing issue by that
finding's own terms and files one only if none exists. No fix lands in this PR.

<!-- fr:journal kind=decision scope=spec id=d-decomposition created=2026-11-16T18:33:29+00:00 decided_by=operator -->
### d-decomposition · decision · Module decomposition: plan the cheap slices and design the costly parts in the report; split nothing in this PR

Asked for a size rule, the operator first asked for an architectural examination of
the five largest modules, to be reported back if too costly. Four read-only reviews
found a cheap part and a costly part in each. The operator then chose "Plan the
costly parts too": the report plans the cheap slices and also designs the costly work
(typed verdicts for run_cmd's evidence verifiers, the port-based move of the triage
driver core, isolation's garbage collection, plan_ops tick retirement), each filed as
its own issue with a preservation contract. The agent read this as building on the
recommended option and so including the no-growth line budget on the five files; the
operator was told and did not object.

<!-- fr:journal kind=decision scope=spec id=d-architecture-fragment created=2026-11-16T18:33:29+00:00 decided_by=operator -->
### d-architecture-fragment · decision · The architecture page gains one short authored fragment

The operator chose "Report plus one short fragment". The agent had wrongly said the
repo has no architecture fragments; they exist under
docs/triage/derio-net--super-fr/architecture/, so this adds one fragment and one
manifest entry to the existing page.

<!-- fr:journal kind=decision scope=spec id=d-verification created=2026-11-16T18:33:29+00:00 gate=developer decided_by=operator -->
### d-verification · decision · Verification: candidate strategy, CI tests as the contract for each row, nothing owed after merge

The operator chose "Candidate build, tests as contract". The run keeps the workflow's
`candidate` strategy; each row is `verify: none` with the CI test that proves it. The
gate is `developer`, so no tester or devops gate holds the close-out.

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-16T18:33:29+00:00 lens=tests step=brainstorm -->
### lens-tests-1 · lens · Every deliverable is a guard; each must be shown to fail on a planted violation, not only to pass

<!-- fr:journal kind=finding scope=spec id=sr-1 created=2026-11-16T18:40:23+00:00 state=open review_scope=in -->
### sr-1 · finding [open] (reviewer: in scope) · Design B's soft-point predicate does not prove R8, and silently drops the find_spec check

R8 says the guard proves no fr_dispatch import is at module level; Design B tested "not a
direct child of the module". A module-level `try:` or `if cond:` import is not a direct
child and runs at import time, so it passes. Two soft points carry module-level
`if TYPE_CHECKING:` imports of fr_dispatch (commands/triage_kanban_cmd.py:76-78,
commands/triage_batch_cmd.py:298-300), so "inside a function" alone would fail today.
Design B also dropped the existing `importlib.util.find_spec("fr_dispatch")` presence
check (tests/unit/test_import_direction.py:86) without naming it.

<!-- fr:journal kind=finding scope=spec id=sr-2 created=2026-11-16T18:40:23+00:00 state=open review_scope=in -->
### sr-2 · finding [open] (reviewer: in scope) · Existing planted fixtures are not parseable Python, so 'offender tests keep their assertions' does not hold as written

`test_a_third_fr_dispatch_import_is_refused` (tests/unit/test_import_direction.py:74-76)
writes files whose only line is an indented import; `ast.parse` raises on each. The spec
did not say what the helper does with an unparseable file; skipping it would turn a
syntax error into a pass. R14's exception did not cover the edits R8 makes to this file.

<!-- fr:journal kind=finding scope=spec id=sr-3 created=2026-11-16T18:40:23+00:00 state=open review_scope=in -->
### sr-3 · finding [open] (reviewer: in scope) · The fr.triage import checks stay on a regex with the same blind spot G01 closes

`_FR_TRIAGE_IMPORT_RE` (tests/unit/test_import_direction.py:139-160, 183-187) misses
`import os, fr.triage` and `from fr import triage`. A helper returning only root modules
cannot serve these two tests, and the spec did not mention them.

<!-- fr:journal kind=finding scope=spec id=sr-4 created=2026-11-16T18:40:23+00:00 state=open review_scope=in -->
### sr-4 · finding [open] (reviewer: in scope) · The annotation forms Design C prescribes would change pydantic error text and schema, against R9 and R14

`Gate | Literal["none"]` and `Literal["none"] | PostMergeGate` are unions of two
literals, which typing does not flatten. The reviewer reasoned from reading that pydantic
validates such a union branch by branch (triage/model.py:519-521,
verification/model.py:75). Also `StepGate`'s member order flips, harmlessly
(spec.py:564).

<!-- fr:journal kind=finding scope=spec id=sr-5 created=2026-11-16T18:40:23+00:00 state=open review_scope=in -->
### sr-5 · finding [open] (reviewer: in scope) · A fifth hand-written copy of the step-tag vocabulary is not named

`ops/stub.py:22-24` `_LEAD_RE` restates the tag alternatives of `_TAG_RE`. Also
`triage/lanes.py:78` (an ordered tuple, Tester first by rule) and
`commands/journal_cmd.py:219` (help text), reasonable to keep but not recorded.

<!-- fr:journal kind=finding scope=spec id=sr-6 created=2026-11-16T18:40:23+00:00 state=open review_scope=in -->
### sr-6 · finding [open] (reviewer: in scope) · R12's zero-headroom budget lets two green PRs turn main red, and brings back same-line conflict churn

Budgets starting at the line count make every PR that adds a line to run_cmd.py edit the
same table line. Two PRs that each add 10 lines and set the same budget merge cleanly and
leave the module over it; two PRs that each remove 30 lines leave the budget 60 above
the module, past the 50 slack. Both pass alone and fail on main, where the release
suite then blocks.

<!-- fr:journal kind=finding scope=spec id=sr-7 created=2026-11-16T18:40:23+00:00 state=open review_scope=in -->
### sr-7 · finding [open] (reviewer: in scope) · The line budget is listed as an operator decision; the journal records it as the agent's reading

Background item 4 said flatly that the budget lands here. `d-decomposition` records it
as the agent's reading that the operator did not object to. The two-sided rule, the
slack figure and the starting headroom appear nowhere in the journal.

<!-- fr:journal kind=finding scope=spec id=sr-8 created=2026-11-16T18:40:23+00:00 state=open review_scope=in -->
### sr-8 · finding [open] (reviewer: in scope) · R11's scan has no planted-violation case and cannot see the near-duplicates that already exist

The row's test only passes; it never shows the scan firing. With names kept, a copy that
renames a variable is invisible. `_pr_time` (commands/triage_batch_cmd.py:2042-2048)
and `_created_since` (triage/collect.py:1106-1112) implement the same or a close
contract with a different body. Verified as holding: the four bodies are identical apart
from docstrings, and no test or other module references the four names.

<!-- fr:journal kind=finding scope=spec id=sr-9 created=2026-11-16T18:40:23+00:00 state=open review_scope=in -->
### sr-9 · finding [open] (reviewer: in scope) · R13's test would stay green with the decomposition entry removed or its file missing

`resolve_manifest` records an absent named file in `Resolved.missing` and does not
raise (triage/fragments.py:211-214). "Validates every fragment it names" does not prove
the decomposition fragment is there.

<!-- fr:journal kind=finding scope=spec id=sr-10 created=2026-11-16T18:40:23+00:00 state=open review_scope=in -->
### sr-10 · finding [open] (reviewer: in scope) · After the alias, the three-name equality test cannot fail for FrStatus

Once `FrStatus = SessionStatus`, comparing their values is a tautology; what can regress
is a separate literal coming back. Verified as holding: `FrStatus` is used only inside
mailbox.py, the adapter already depends on fr_dispatch, and `STATUS_LABEL`'s nine keys
equal `Status`'s nine values today.

<!-- fr:journal kind=finding scope=spec id=sr-11 created=2026-11-16T18:40:23+00:00 state=open review_scope=in -->
### sr-11 · finding [open] (reviewer: in scope) · R1 and R7 leave three points where two implementers would diverge

(a) R7 said both "one issue per remaining cluster (R04, R05, R06)" and "comment on
#1286 for the strict YAML loader, file no second issue"; the supplement treats R04 as
separate from #1286's backend switch. (b) R1 required a severity with no scale. (c)
R1-R7 were said to be checked by spec review, which happens before the report exists.
Leaving R1-R7 without acceptance rows is consistent with the repo's rule.

<!-- fr:journal kind=finding scope=spec id=sr-12 created=2026-11-16T18:40:23+00:00 state=open review_scope=in -->
### sr-12 · finding [open] (reviewer: in scope) · R6's ports contract contradicts the supplement the report must reconcile

R6 fixed "tests' patches of the command module keep working" as a preservation
contract; the supplement's R07 advises against keeping forwarding wrappers only to
preserve monkeypatch locations. R2 requires each supplement item to be re-checked, so
the report would have had to disagree with its own requirement.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-11-16T18:40:23+00:00 -->
### spec-review · review · independent spec review: 12 findings

Decisions d-run-scope, d-prior-audit, d-other-findings, d-architecture-fragment and
d-verification are honoured as written (R1-R7, R13, Verification). d-decomposition is
honoured except for sr-7. The reviewer ran nothing; sr-4's pydantic behaviour was from
reading. Verified by reading: fr/gates.py:15-20; triage/model.py:519-521;
spec.py:564-565 and its users fr/ops/holds.py:21, fr/ops/testplan.py:13;
verification/model.py:75-82; fr_claude_cloud/mailbox.py:44, 48-54, 125-127; the four
timestamp readers and their callers; tests/unit/test_import_direction.py;
commands/apply_cmd.py:136-170, 555-561; acceptance/report.py:31-41 against
acceptance/model.py:32-42; triage/fragments.py:100-109, 162-228; the architecture
manifest; the five line counts; run/model.py:600; commands/run_cmd.py:6489-6491;
hooks/fr-isolation-required.sh:26, 37; commands/triage_kanban_cmd.py:355.

<!-- fr:journal kind=finding scope=spec id=sr-1-resolved created=2026-11-16T18:40:23+00:00 state=fixed resolves=sr-1 -->
### sr-1-resolved · finding [fixed] · resolves sr-1: Design B's soft-point predicate does not prove R8, and silently drops the find_spec check

R8 and Design B now allow an fr_dispatch import only inside a function body or under `if TYPE_CHECKING:`, keep the find_spec check as a call in the tree, and plant a module-level `try` and plain `if` import in a soft point.

<!-- fr:journal kind=finding scope=spec id=sr-2-resolved created=2026-11-16T18:40:23+00:00 state=fixed resolves=sr-2 -->
### sr-2-resolved · finding [fixed] · resolves sr-2: Existing planted fixtures are not parseable Python, so 'offender tests keep their assertions' does not hold as written

Design B rewrites the fixtures as an import inside a `def` and lets a SyntaxError fail the test; R8 says an unparseable file fails the guard; R14's exception now covers the rewrite of this test file.

<!-- fr:journal kind=finding scope=spec id=sr-3-resolved created=2026-11-16T18:40:23+00:00 state=fixed resolves=sr-3 -->
### sr-3-resolved · finding [fixed] · resolves sr-3: The fr.triage import checks stay on a regex with the same blind spot G01 closes

R8 covers the two fr.triage checks; the helper returns the full dotted module and a from-import's names, `_FR_TRIAGE_IMPORT_RE` is dropped, and both blind-spot forms are planted cases.

<!-- fr:journal kind=finding scope=spec id=sr-4-resolved created=2026-11-16T18:40:23+00:00 state=fixed resolves=sr-4 -->
### sr-4-resolved · finding [fixed] · resolves sr-4: The annotation forms Design C prescribes would change pydantic error text and schema, against R9 and R14

Confirmed by running pydantic on this branch: the union form reports two errors (the first `Input should be 'none'`) and an `anyOf` schema; the nested form `Literal["none", PostMergeGate]` reports the one error and the `enum` schema of today, in today's order. Design C now prescribes the nested form, records that result, and notes the harmless StepGate order flip.

<!-- fr:journal kind=finding scope=spec id=sr-5-resolved created=2026-11-16T18:40:23+00:00 state=fixed resolves=sr-5 -->
### sr-5-resolved · finding [fixed] · resolves sr-5: A fifth hand-written copy of the step-tag vocabulary is not named

R9 and Design C add `ops/stub.py`'s `_LEAD_RE`, built from the vocabulary and covered by the guard test; `triage/lanes.py:78` and the journal help text go to the report's duplicates-to-keep list.

<!-- fr:journal kind=finding scope=spec id=sr-6-resolved created=2026-11-16T18:40:23+00:00 state=fixed resolves=sr-6 -->
### sr-6-resolved · finding [fixed] · resolves sr-6: R12's zero-headroom budget lets two green PRs turn main red, and brings back same-line conflict churn

R12 and Design F: budgets start at the line count rounded up to the next 100 (36 to 70 lines of headroom) and the lower bound is 400 lines, so ordinary PRs change no budget and several trimming PRs cannot push it out of range. Design F states the residual case (two PRs whose additions together exceed the headroom) and that the report records the cost.

<!-- fr:journal kind=finding scope=spec id=sr-7-resolved created=2026-11-16T18:40:23+00:00 state=fixed resolves=sr-7 -->
### sr-7-resolved · finding [fixed] · resolves sr-7: The line budget is listed as an operator decision; the journal records it as the agent's reading

Background item 4 now calls the budget the agent's reading that the operator did not object to; R12 says its bounds, headroom and figure are design choices of the spec.

<!-- fr:journal kind=finding scope=spec id=sr-8-resolved created=2026-11-16T18:40:23+00:00 state=fixed resolves=sr-8 -->
### sr-8-resolved · finding [fixed] · resolves sr-8: R11's scan has no planted-violation case and cannot see the near-duplicates that already exist

R11 and Design E: the scan is a function over source text that normalises local names, tested on a planted copy and a planted renamed copy; `_pr_time` and `_created_since` are named as different-body implementations the report must list with a disposition.

<!-- fr:journal kind=finding scope=spec id=sr-9-resolved created=2026-11-16T18:40:23+00:00 state=fixed resolves=sr-9 -->
### sr-9-resolved · finding [fixed] · resolves sr-9: R13's test would stay green with the decomposition entry removed or its file missing

R13, Design G and the Verification row: the test asserts `missing` is empty, every fragment validates, and `decomposition.html` is resolved directly after `pipeline.html`.

<!-- fr:journal kind=finding scope=spec id=sr-10-resolved created=2026-11-16T18:40:23+00:00 state=fixed resolves=sr-10 -->
### sr-10-resolved · finding [fixed] · resolves sr-10: After the alias, the three-name equality test cannot fail for FrStatus

R10, Design D and the Verification row: assert `FrStatus is SessionStatus`; keep the value comparison for `BoardStatus` only.

<!-- fr:journal kind=finding scope=spec id=sr-11-resolved created=2026-11-16T18:40:23+00:00 state=fixed resolves=sr-11 -->
### sr-11-resolved · finding [fixed] · resolves sr-11: R1 and R7 leave three points where two implementers would diverge

R7: R04 gets its own issue for the same-loader extraction, cross-linked with #1286; only #1174 is comment-only. R1 names the P0-P3 scale. The rows section says the report and issues are checked by the lens review and the PR review.

<!-- fr:journal kind=finding scope=spec id=sr-12-resolved created=2026-11-16T18:40:23+00:00 state=fixed resolves=sr-12 -->
### sr-12-resolved · finding [fixed] · resolves sr-12: R6's ports contract contradicts the supplement the report must reconcile

R6 now preserves what the driver's tests assert about output and effects, and has the design state whether patch locations move or stay.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-16T18:40:27+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  architecture-page-shows-decomposition: none
  gate-annotations-follow-vocabulary: none
  hotspot-modules-cannot-grow: none
  import-guard-reads-syntax-tree: none
  session-status-one-vocabulary: none
  triage-timestamps-one-reader: none
row_kinds:
  architecture-page-shows-decomposition: none
  gate-annotations-follow-vocabulary: none
  hotspot-modules-cannot-grow: none
  import-guard-reads-syntax-tree: none
  session-status-one-vocabulary: none
  triage-timestamps-one-reader: none
run_gate: developer
run_kind: candidate
```
