<!-- fr:journal-schema=3 -->
# Journal: 2026-11-12-remove-vk-compat

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-12T15:43:42+00:00 input=true -->
### operator-brief · discovery · The operator's brief, as typed

"remove the vk compatibility code via /fr-goal."

Earlier in the same session, about the wording cleanup that preceded this
(#1416): "vk references must be removed. There is no vk anymore. Only fr."
and "The vk I was referring to was not the VK runner, but the original vk
command and relevant wording".

<!-- fr:journal kind=decision scope=spec id=d1-vk-version-removed-with-migration created=2026-11-12T15:43:42+00:00 decided_by=operator -->
### d1-vk-version-removed-with-migration · decision · vk_version is removed with a migration that also strips the archive

Asked: keep the inert `vk_version` plan field, stop writing it, or remove
it with a migration. Operator: "3 and the migration also removes the field
from the archives. Do we have other such inert fields?" This overrides the
artifact-versioning rule's "archived artifacts are frozen" for this one
repair. Answer to the side question, from the code: `vk_version` is the
only field in an artifact model marked inert.

<!-- fr:journal kind=decision scope=spec id=d2-env-vars-hard-rename created=2026-11-12T15:43:42+00:00 decided_by=operator -->
### d2-env-vars-hard-rename · decision · VK_REPO_ROOT and VK_INSTALL_SKIP_PREFLIGHT are hard-renamed to FR_*

Operator chose the hard rename with no fallback for the old names.

<!-- fr:journal kind=decision scope=spec id=d3-up-branch-required created=2026-11-12T15:43:42+00:00 decided_by=operator -->
### d3-up-branch-required · decision · fr isolation up requires --branch

Operator chose to make `--branch` required over renaming the `vk-iso/work` default.

<!-- fr:journal kind=decision scope=spec id=d4-old-install-paths-removed created=2026-11-12T15:43:42+00:00 decided_by=operator -->
### d4-old-install-paths-removed · decision · Every old-install path goes, wrapper recognition included

Operator confirmed every machine and consumer repo is past the rename:
the installer purges, `fr init migrate` and the `superpowers-for-vk`
validator-wrapper recognition are all removed.

<!-- fr:journal kind=decision scope=spec id=d5-major-bump created=2026-11-12T15:43:42+00:00 decided_by=operator -->
### d5-major-bump · decision · The change fragment declares a major bump

Operator chose major, following the repo's rule for breaking CLI and plan-schema changes.

<!-- fr:journal kind=decision scope=spec id=d6-verification-ci-tests created=2026-11-12T15:43:42+00:00 decided_by=operator -->
### d6-verification-ci-tests · decision · Verified by unit tests in CI; no walk, no post-merge gate

Operator chose CI tests only. Each row is `none` with its reason; the run's gate is none.

<!-- fr:journal kind=finding scope=spec id=sr-1 created=2026-11-12T15:51:37+00:00 state=open review_scope=in -->
### sr-1 · finding [open] (reviewer: in scope) · §3.D: the extra_locators seam does not exist, and the spec does not say which of the runner's four enumerations take it

`Repair` has no `extra_locators`. `plan_migrations`, `is_stale`, `inspection_failures` and `run_migrations`
(artifacts/runner.py) each walk `iter_paths_of` (which skips the archive) and funnel through `_actions_for`,
which stamp-checks first. If `is_stale` does not see the archive the gate never fires for a repo whose only
carriers are archived, and R11 holds only for a typed `fr migrate artifacts --yes`.

<!-- fr:journal kind=finding scope=spec id=sr-2 created=2026-11-12T15:51:37+00:00 state=open review_scope=in -->
### sr-2 · finding [open] (reviewer: in scope) · Making the archive visible to the gate lets a frozen file refuse every gated command, and parses every archived _meta.yaml on every invocation

`applies` as specified is one `yaml.safe_load` per archived plan before every non-exempt command. An archived
file that is invalid YAML or unrewritable becomes a permanent failed action, so `is_stale` is true forever and
the gate refuses in the refuse and opt-out rows. The spec must state the intended behaviour and the risk.

<!-- fr:journal kind=finding scope=spec id=sr-3 created=2026-11-12T15:51:37+00:00 state=open review_scope=in -->
### sr-3 · finding [open] (reviewer: in scope) · R10's rewrite rule corrupts the case it names: a block scalar's header line matches the pattern

Removing the one column-0 line of `vk_version: >-` leaves the continuation lines behind. Same for a multi-line
quoted scalar and a duplicated key. Build in memory, re-parse, require equality with the original minus the
key, raise before writing otherwise; use `read_verbatim`/`split_lines`, not `read_text` (CRLF, BOM).

<!-- fr:journal kind=finding scope=spec id=sr-4 created=2026-11-12T15:51:37+00:00 state=open review_scope=in -->
### sr-4 · finding [open] (reviewer: in scope) · The spec states its tests nowhere

The tests exist only as one-line reasons under `## Verification`; nothing states the cases R2, R5, R7, R8, R9,
R13 and R15 are checked by, and sr-3's edge cases have no home. The reviewer asked for a `## Test Plan`.

<!-- fr:journal kind=finding scope=spec id=sr-5 created=2026-11-12T15:51:37+00:00 state=open review_scope=in -->
### sr-5 · finding [open] (reviewer: in scope) · R2 falsifies a merged acceptance row and has no row of its own

Row `vk-legacy-fallbacks-removed` (status ci) asserts an unmigrated repo fails loudly pointing at
`fr init migrate`. After R2 the config's env file is simply created. tests/unit/test_isolation.py pins the error.

<!-- fr:journal kind=finding scope=spec id=sr-6 created=2026-11-12T15:51:37+00:00 state=open review_scope=in -->
### sr-6 · finding [open] (reviewer: in scope) · R6: dropping `superpowers-for-vk@` from the sibling-repo grep changes installer output, a pinned test seeds that id, and the row's wording is untrue

Without the grep alternative a machine whose only purged id is `superpowers-for-vk@derio-net` gets a false
sibling-repo note. The bare-org purge still drops the id, so "performs no purge for them" is not literally
true. Two comments name it, not one; test_install_marketplace_namespace.py seeds and asserts on the id.

<!-- fr:journal kind=finding scope=spec id=sr-7 created=2026-11-12T15:51:37+00:00 state=open review_scope=in -->
### sr-7 · finding [open] (reviewer: in scope) · R3: shipped guidance still tells the user to run bare `fr isolation up`, which will exit 2

No caller breaks, but remedy messages in isolation_cmd.py, sessions.py, local.py, the two Hermes hooks, the
OpenCode plugin and the golden fixture guard-verdicts.yaml recommend the bare command.

<!-- fr:journal kind=finding scope=spec id=sr-8 created=2026-11-12T15:51:37+00:00 state=open review_scope=in -->
### sr-8 · finding [open] (reviewer: in scope) · R7, R9, R11: tests that pin the old behaviour are not named

test_plan_validator_wrapper_rename.py's PRE_SWEEP_WRAPPER case; three tests asserting `vk_version` parses and
an unknown-key test that would pass for the wrong reason; the four archive-exclusion tests stay green only if
`iter_paths_of` is untouched and CEILING_REPAIR declares no extra locator.

<!-- fr:journal kind=finding scope=spec id=sr-9 created=2026-11-12T15:51:37+00:00 state=open review_scope=in -->
### sr-9 · finding [open] (reviewer: in scope) · §2 and §5 say 42 archived plans carry the key; 33 archived `_meta.yaml` files do

The other archive hits are phase YAML and prose, which the repair does not reach; R12's "carry no vk_version"
must mean the `_meta.yaml` key.

<!-- fr:journal kind=finding scope=spec id=sr-10 created=2026-11-12T15:51:37+00:00 state=open review_scope=in -->
### sr-10 · finding [open] (reviewer: in scope) · R14 is garbled, and R14/R15 miss text this change makes false

R14's last clause reads as one more item to change. The "archives are never migrated" claim is also in
registry.py, runner.py, parser.py and spec.py; render.py names `vk-ready`; types.py says "must update your
vk_version"; bump-version.py's comment. The fr-vk package's label wording needs a stated disposition.

<!-- fr:journal kind=finding scope=spec id=sr-11 created=2026-11-12T15:51:37+00:00 state=open review_scope=in -->
### sr-11 · finding [open] (reviewer: in scope) · R9 changes behaviour for a historical read (`fr status`) and has no acceptance row

Archived plans are parsed by `compute_status` and gate backfill; both catch the error, so an un-repaired
archived plan reports as missing, and `fr status` is gate-exempt so it never triggers the repair.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-11-12T15:51:37+00:00 -->
### spec-review · review · independent spec review: 11 findings, all in scope

Decisions d1–d6 are all honoured; the spec decides nothing against them. test_tripwire_artifact_kinds.py does
not refuse a `Repair.extra_locators` tuple of path globs. Every file, helper and constant the spec names was
found at a file:line; no other vk-command residue in packages/fr/src, scripts/, plugins/ or .github/ beyond
sr-6, sr-7 and sr-10. Raised: sr-1 … sr-11.

<!-- fr:journal kind=finding scope=spec id=sr-1-resolved created=2026-11-12T15:51:37+00:00 state=fixed resolves=sr-1 -->
### sr-1-resolved · finding [fixed] · resolves sr-1: §3.D: the extra_locators seam does not exist, and the spec does not say which of the runner's four enumerations take it

§3.D now names the helper and a table of what each of the four walks does with archive paths; `iter_paths_of` is untouched; is_stale sees repairable archived carriers.

<!-- fr:journal kind=finding scope=spec id=sr-2-resolved created=2026-11-12T15:51:37+00:00 state=fixed resolves=sr-2 -->
### sr-2-resolved · finding [fixed] · resolves sr-2: Making the archive visible to the gate lets a frozen file refuse every gated command, and parses every archived _meta.yaml on every invocation

The predicate tests raw bytes before parsing; R12 and §3.D say an unreadable or unrewritable archived file is reported and holds nothing; §5 adds the daemon-checkout and cost risks.

<!-- fr:journal kind=finding scope=spec id=sr-3-resolved created=2026-11-12T15:51:37+00:00 state=fixed resolves=sr-3 -->
### sr-3-resolved · finding [fixed] · resolves sr-3: R10's rewrite rule corrupts the case it names: a block scalar's header line matches the pattern

R10 and §3.D: read_verbatim/split_lines, exactly one whole top-level line, re-parse and compare before writing, raise otherwise; §6 lists the CRLF, BOM, no-final-newline, block-scalar, multi-line, duplicate-key and flow-mapping cases.

<!-- fr:journal kind=finding scope=spec id=sr-4-resolved created=2026-11-12T15:51:37+00:00 state=fixed resolves=sr-4 -->
### sr-4-resolved · finding [fixed] · resolves sr-4: The spec states its tests nowhere

Added §6 'Cases the unit tests cover', one line per requirement. Not under the `## Test Plan` heading: fr reads that heading as the operator's post-merge rows, and this run has none (decision d6).

<!-- fr:journal kind=finding scope=spec id=sr-5-resolved created=2026-11-12T15:51:37+00:00 state=fixed resolves=sr-5 -->
### sr-5-resolved · finding [fixed] · resolves sr-5: R2 falsifies a merged acceptance row and has no row of its own

R2 states the file is created; R18 and §3.A amend row vk-legacy-fallbacks-removed and replace the pinned test.

<!-- fr:journal kind=finding scope=spec id=sr-6-resolved created=2026-11-12T15:51:37+00:00 state=fixed resolves=sr-6 -->
### sr-6-resolved · finding [fixed] · resolves sr-6: R6: dropping `superpowers-for-vk@` from the sibling-repo grep changes installer output, a pinned test seeds that id, and the row's wording is untrue

R6 reworded to what is true (no code or text naming the retired tool; the generic bare-org purge is unchanged); §3.A states and accepts the note consequence, names both comments and the test edits; the row is reworded.

<!-- fr:journal kind=finding scope=spec id=sr-7-resolved created=2026-11-12T15:51:37+00:00 state=fixed resolves=sr-7 -->
### sr-7-resolved · finding [fixed] · resolves sr-7: R3: shipped guidance still tells the user to run bare `fr isolation up`, which will exit 2

R17 and §3.B: every remedy message names `fr isolation up --branch <branch>`, hooks, plugin and golden fixtures included.

<!-- fr:journal kind=finding scope=spec id=sr-8-resolved created=2026-11-12T15:51:37+00:00 state=fixed resolves=sr-8 -->
### sr-8-resolved · finding [fixed] · resolves sr-8: R7, R9, R11: tests that pin the old behaviour are not named

§3.A and §3.D name the tests that invert or go; §3.D says CEILING_REPAIR declares no extra locator and iter_paths_of is untouched; §6 adds the counterpart test.

<!-- fr:journal kind=finding scope=spec id=sr-9-resolved created=2026-11-12T15:51:37+00:00 state=fixed resolves=sr-9 -->
### sr-9-resolved · finding [fixed] · resolves sr-9: §2 and §5 say 42 archived plans carry the key; 33 archived `_meta.yaml` files do

§2 and §5 say 33 `_meta.yaml` files; R13 scopes the claim to the `_meta.yaml` key.

<!-- fr:journal kind=finding scope=spec id=sr-10-resolved created=2026-11-12T15:51:37+00:00 state=fixed resolves=sr-10 -->
### sr-10-resolved · finding [fixed] · resolves sr-10: R14 is garbled, and R14/R15 miss text this change makes false

R15 lists every place; R19 states what stays, the fr-vk package's label wording included.

<!-- fr:journal kind=finding scope=spec id=sr-11-resolved created=2026-11-12T15:51:37+00:00 state=fixed resolves=sr-11 -->
### sr-11-resolved · finding [fixed] · resolves sr-11: R9 changes behaviour for a historical read (`fr status`) and has no acceptance row

§2 and §3.D state the pre-migration behaviour of `fr status` and gate backfill; R13 requires every archived plan here to parse; new row archived-plans-readable-after-repair.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-12T15:51:38+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  archived-plans-readable-after-repair: none
  fr-repo-root-override: none
  init-migrate-removed: none
  installer-names-no-vk-residue: none
  isolation-up-requires-branch: none
  plan-vk-version-repaired: none
row_kinds:
  archived-plans-readable-after-repair: none
  fr-repo-root-override: none
  init-migrate-removed: none
  installer-names-no-vk-residue: none
  isolation-up-requires-branch: none
  plan-vk-version-repaired: none
run_gate: none
run_kind: candidate
```

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-12-remove-vk-compat-p2 created=2026-11-12T15:53:43+00:00 -->
### phase-split-2026-11-12-remove-vk-compat-p2 · decision · ask: the vk_version plan key and its archive-reaching repair (R9-R13) are a separate ask from the removals and renames, and change the migration runner

Phase 1 is deletions and mechanical renames; phase 2 changes PlanMeta, adds a repair and a runner seam every command's gate passes through. They are reviewable independently.

<!-- fr:journal kind=decision scope=spec id=tier-2026-11-12-remove-vk-compat-p2 created=2026-11-12T15:53:45+00:00 -->
### tier-2026-11-12-remove-vk-compat-p2 · decision · hard: phase 2 changes the migration runner and the CLI-entry gate's staleness test, a path every caller relies on

Per fr-plan's tier rule: a change to a gate or migration path.
