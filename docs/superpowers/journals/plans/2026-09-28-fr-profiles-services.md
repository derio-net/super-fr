# Journal: 2026-09-28-fr-profiles-services

<!-- fr:journal kind=decision scope=plan id=p1-host-source created=2026-09-28T20:39:57+00:00 phase=1 -->
### p1-host-source · decision · ResolvedService carries host_source separately from source (phase 1)

`fr.services.model.ResolvedService(type, host, source, host_source)`. `source` is the
provenance of the TYPE; `host_source` of the host (None when there is no host). They
differ in real cases: a v1 file with `backend:` but no `host:` has a legacy type and
an origin-derived (default) host; a declared tracker of the forge's type borrows the
forge host (host_source default). `_hosts.declared_host` returns the host only when
`host_source in (declared, legacy)`, preserving gh#486's provenance rule — keying it
off `source` alone would have started warning on derived hosts.

<!-- fr:journal kind=decision scope=plan id=p1-lenient-resolve created=2026-09-28T20:39:57+00:00 phase=1 -->
### p1-lenient-resolve · decision · resolve_services(lenient=True) backs the never-raising forge consumers (phase 1)

`resolve_services(root)` raises `ServicesError` (a ValueError) on an unreadable file,
an unknown/deferred type, a cross-forge tracker, a missing required host or an invalid
v1 file. `_hosts.detect_backend/declared_host/host_for` call it with `lenient=True`:
unreadable file = absent, an invalid block falls back to the next tier, and an invalid
v1 file (ProfilesV1 is extra="forbid") falls back to its raw `backend:`/`host:` when
those are in-vocabulary — so an extra top-level key in someone's v1 file does not
silently change their backend. `_hosts` imports `fr.services.resolve` lazily (inside
`_forge`) because resolve imports `_hosts`' origin helpers; `_origin_hostname` was
renamed to public `origin_hostname`.

<!-- fr:journal kind=decision scope=plan id=p1-v2-undeclared-ci created=2026-09-28T20:39:57+00:00 phase=1 -->
### p1-v2-undeclared-ci · decision · A v2 file with no `ci:` block resolves ci through the raw probe (source default) (phase 1)

§3.B step 2's last branch (forge's own pipeline type if `ci_config` finds one, else
`none`) is used for BOTH "no file" and "v2 file without `ci:`". A file counts as v2 when
it has `schema_version >= 2` or any of `forge:`/`ci:`/`tracking:`. Top-level
`backend:`/`host:` in a v2 file are IGNORED by the resolver (the phase-2 validator is
what should refuse them as leftovers).

<!-- fr:journal kind=discovery scope=plan id=p1-detect-ci-details created=2026-09-28T20:39:57+00:00 phase=1 -->
### p1-detect-ci-details · discovery · detect_ci conservatism and the unknown-host warning text (phase 1)

`fr.services.detect.detect_ci` treats an unparseable or non-mapping `.gitlab-ci.yml` as
`real` (it cannot be shown to be fr's scaffold) and ignores hidden `.template` keys as
non-jobs besides the listed keywords. For Gitea it classifies whichever directory
`ci_config` picked first (`.gitea/workflows` wins over `.github/workflows`).
`_hosts.detect_backend`'s unknown-origin warning still says "Declare it as
`backend: gitlab`" (pinned by test__hosts.py::TestDetectBackendWarnsOnce); once the
phase-2 migration exists that advice should become `forge: {type: gitlab}` —
phase 2/6 should update the string and that test together.

<!-- fr:journal kind=discovery scope=plan id=p1-read-only-prose created=2026-09-28T20:39:57+00:00 phase=1 -->
### p1-read-only-prose · discovery · Adding `services` to READ_ONLY_COMMANDS also needed the rule prose + OpenCode mirror (phase 1)

`test_migration_trigger.py::test_the_rule_prose_names_every_read_only_command` reads
`.claude/rules/artifact-versioning.md`, so the Exempt-commands paragraph now names
`services`; that rule is mirrored to `.opencode/instructions/artifact-versioning.md`
(regenerated with scripts/sync-opencode.py; sync-hermes was already in sync).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-09-28T20:39:57+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

skeleton — the full model lands in T2

<!-- fr:journal kind=finding scope=plan id=p1r-forge-only created=2026-09-28T20:57:59+00:00 phase=1 state=open review_scope=in -->
### p1r-forge-only · finding [open] (reviewer: in scope) · Forge wrappers resolved all three services (CI probe + unconditional git remote per call) (phase 1)

Reviewer: _hosts._forge called resolve_services, so detect_backend/declared_host/host_for each ran a CI disk probe and git remote even with a declared forge; client_for calls all three. Verified at _hosts.py:172-178 / resolve.py:116,159.

<!-- fr:journal kind=finding scope=plan id=p1r-lenient-raise created=2026-09-28T20:57:59+00:00 phase=1 state=open review_scope=in -->
### p1r-lenient-raise · finding [open] (reviewer: in scope) · Lenient mode let UnicodeDecodeError escape detect_backend / fr services (phase 1)

_read_config caught only OSError/YAMLError where the old code caught Exception; _gitlab_presence read_text on a non-UTF-8 .gitlab-ci.yml escaped too.

<!-- fr:journal kind=finding scope=plan id=p1r-warning-advice created=2026-09-28T20:57:59+00:00 phase=1 state=open review_scope=in -->
### p1r-warning-advice · finding [open] (reviewer: in scope) · Unknown-origin warning advised `backend: gitlab`, which a v2 file ignores (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1r-v1-stamp created=2026-09-28T20:57:59+00:00 phase=1 state=open review_scope=in -->
### p1r-v1-stamp · finding [open] (reviewer: in scope) · Frozen ProfilesV1 refused an explicit `schema_version: 1` (phase 1)

Must be fixed before the SHA pin ships on main.

<!-- fr:journal kind=finding scope=plan id=p1r-tests created=2026-09-28T20:57:59+00:00 phase=1 state=open review_scope=in -->
### p1r-tests · finding [open] (reviewer: in scope) · Misnamed unknown-key test (used an unknown value); lenient v1-extra-key / cross-forge / hostless cases untested (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1r-later-tests created=2026-09-28T20:57:59+00:00 phase=1 state=open review_scope=out -->
### p1r-later-tests · finding [open] (reviewer: out of scope) · Test Plan items owned by the migration phase: exempt commands on an unmigrated v1 file (source legacy), legacy ci == migrated ci (phase 1)

Not caused by phase 1: they need phase 2's migration. Carried into phase 2's brief.

<!-- fr:journal kind=discovery scope=plan id=p1r-journal-supersede created=2026-09-28T20:57:59+00:00 phase=1 -->
### p1r-journal-supersede · discovery · Supersedes p1-detect-ci-details / p1-lenient-resolve (phase 1)

After 20ef096c: the unknown-origin warning advises `forge: {type: gitlab}` (not `backend:`), and _hosts calls resolve_forge(..., lenient=True), which never probes CI and runs git remote only when the forge type or host is undeclared — not resolve_services.

<!-- fr:journal kind=review scope=plan id=p1-review created=2026-09-28T20:57:59+00:00 phase=1 -->
### p1-review · review · Phase 1 review: 6 findings (5 in scope, fixed in 20ef096c; 1 out of scope) (phase 1)

Independent reviewer over 26c415a8^..e1f7f66c against spec R1/R2/R7 §3.A-C/§3.F and plan 01.yaml: no critical bugs; precedence, source/host_source, detect_ci rules, #795 refusals, tracking-vs-forge and host-required rules match the spec; no import cycle; the artifact-versioning.md edit is required by test_the_rule_prose_names_every_read_only_command.
Findings p1r-forge-only, p1r-lenient-raise, p1r-warning-advice, p1r-v1-stamp, p1r-tests verified against the code and fixed test-first in 20ef096c (full suite 7001 passed). p1r-later-tests is out of scope (phase 2).

<!-- fr:journal kind=finding scope=plan id=p1r-forge-only-resolved created=2026-09-28T20:57:59+00:00 phase=1 state=fixed resolves=p1r-forge-only -->
### p1r-forge-only-resolved · finding [fixed] · resolves p1r-forge-only: Forge wrappers resolved all three services (CI probe + unconditional git remote per call) (phase 1)

20ef096c: resolve_forge (forge-only, git remote only when type/host undeclared, never CI); _hosts uses it; TestForgeOnly makes origin/CI probes fail if called.

<!-- fr:journal kind=finding scope=plan id=p1r-lenient-raise-resolved created=2026-09-28T20:57:59+00:00 phase=1 state=fixed resolves=p1r-lenient-raise -->
### p1r-lenient-raise-resolved · finding [fixed] · resolves p1r-lenient-raise: Lenient mode let UnicodeDecodeError escape detect_backend / fr services (phase 1)

20ef096c: lenient _read_config catches Exception, strict wraps it as ServicesError; UnicodeDecodeError in _gitlab_presence reads as real; tests for both.

<!-- fr:journal kind=finding scope=plan id=p1r-warning-advice-resolved created=2026-09-28T20:57:59+00:00 phase=1 state=fixed resolves=p1r-warning-advice -->
### p1r-warning-advice-resolved · finding [fixed] · resolves p1r-warning-advice: Unknown-origin warning advised `backend: gitlab`, which a v2 file ignores (phase 1)

20ef096c: warning now advises `forge: {type: gitlab}` (or gitea); TestDetectBackendWarnsOnce asserts it.

<!-- fr:journal kind=finding scope=plan id=p1r-v1-stamp-resolved created=2026-09-28T20:57:59+00:00 phase=1 state=fixed resolves=p1r-v1-stamp -->
### p1r-v1-stamp-resolved · finding [fixed] · resolves p1r-v1-stamp: Frozen ProfilesV1 refused an explicit `schema_version: 1` (phase 1)

20ef096c: ProfilesV1.schema_version: Literal[1] | None; pin recomputed; tests accept 1, refuse 2.

<!-- fr:journal kind=finding scope=plan id=p1r-tests-resolved created=2026-09-28T20:57:59+00:00 phase=1 state=fixed resolves=p1r-tests -->
### p1r-tests-resolved · finding [fixed] · resolves p1r-tests: Misnamed unknown-key test (used an unknown value); lenient v1-extra-key / cross-forge / hostless cases untested (phase 1)

20ef096c: renamed to test_an_unknown_backend_value_is_refused, real unknown-key test added, TestForgeConsumersAreLenient covers the lenient cases.

<!-- fr:journal kind=finding scope=plan id=p1r-later-tests-resolved created=2026-09-28T20:57:59+00:00 phase=1 state=open resolves=p1r-later-tests out_of_scope=true -->
### p1r-later-tests-resolved · finding [out-of-scope] · resolves p1r-later-tests: Test Plan items owned by the migration phase: exempt commands on an unmigrated v1 file (source legacy), legacy ci == migrated ci (phase 1)

Needs the phase-2 migration to exist; phase 2's brief carries both tests.

<!-- fr:journal kind=decision scope=plan id=p2-render-shared created=2026-09-28T21:23:14+00:00 phase=2 -->
### p2-render-shared · decision · fr.services.render.render_services is the ONE text renderer of the service blocks (phase 5 reuses it) (phase 2)

`render_services({"forge": {...}, "ci": {...}, "tracking": {...}}, newline=...)`
returns the three blocks as text in forge/ci/tracking order, `type` first, the
caller's newline style, scalars plain when YAML reads them back unchanged else
JSON-double-quoted. The 1 -> 2 migration appends it; phase 5's `fr init scaffold`
should call it rather than yaml.safe_dump. `fr.artifacts.profiles_services.v1_services(root,
backend, host)` computes what a v1 `backend:`/`host:` pair stands for (forge from
backend else origin inference, host only when declared; ci via
`fr.services.detect.detected_ci_type`; tracking = forge type) — the scaffold's
"migrate a v1 file in process" path can call `rewrite_to_services(path)` then
`artifact_kind("profiles").write_version(path, 2)`, exactly what the runner does.

<!-- fr:journal kind=decision scope=plan id=p2-wholly-v2 created=2026-09-28T21:23:14+00:00 phase=2 -->
### p2-wholly-v2 · decision · What the migration treats as an already-v2 (crash-window) body, and what it refuses (phase 2)

Wholly v2 = no top-level backend/host, at least one service block, and every
present block validates through the live ForgeService/CiService/TrackingService;
then `fn` returns and the runner stamps. A file carrying BOTH backend/host and a
service block is refused (half-merged). A v1 file ProfilesV1 rejects (unknown key,
out-of-vocabulary backend) is refused. After the textual rewrite the new text is
re-parsed and must equal {old keys minus backend/host} | services, else refused
(catches flow-style documents). Every refusal leaves the file byte-identical.

<!-- fr:journal kind=decision scope=plan id=p2-validator-v1 created=2026-09-28T21:23:14+00:00 phase=2 -->
### p2-validator-v1 · decision · validate_profiles checks a v1 file through ProfilesV1; cross-service rules only when a forge block is declared (phase 2)

At v2 (is_version_two) it checks each present block through the live models
(unknown/deferred types name #795), leftover top-level backend/host, and runs
validate_services only when `forge:` is declared and every present block parsed
(undeclared ci/tracking default to the forge's own, which always passes). Without
a declared forge the host-required rule cannot be decided offline, so it is not
checked. `fr validate artifacts` reports a v1 file as stale and does not reach
the structure check; the v1 branch is exercised by calling the validator directly.

<!-- fr:journal kind=discovery scope=plan id=p2-no-change-fragment created=2026-09-28T21:23:14+00:00 phase=2 -->
### p2-no-change-fragment · discovery · The branch has no .changes fragment yet (phase 2)

`.changes/` holds only README.md on this branch; the PR changes packages/*/src,
so the change-fragment CI job will fail until a `.changes/feat-batch-service-split-2.yaml`
is added (minor — new artifact kind, `fr services`). Owed before delivery; the
release note must carry the §3.D stated risk (an older fr reading a migrated file
falls back to origin inference — wrong for self-hosted GitLab/Gitea).

<!-- fr:journal kind=discovery scope=plan id=p2-scaffold-writes-v1 created=2026-09-28T21:23:14+00:00 phase=2 -->
### p2-scaffold-writes-v1 · discovery · fr init scaffold still writes an unstamped v1 file, which is now stale on arrival (phase 2)

Until phase 5 moves `fr init scaffold` to the nested shape, a freshly scaffolded
repo's fr-profiles.yaml is version 1 and the CLI-entry gate will want to migrate
it. The suite skips the gate (conftest), so nothing here goes red.

<!-- fr:journal kind=finding scope=plan id=p1r-later-tests-resolved-2 created=2026-09-28T21:23:14+00:00 phase=2 state=fixed resolves=p1r-later-tests -->
### p1r-later-tests-resolved-2 · finding [fixed] · resolves p1r-later-tests: Test Plan items owned by the migration phase: exempt commands on an unmigrated v1 file (source legacy), legacy ci == migrated ci (phase 2)

tests/unit/test_migration_profiles_services.py: test_the_exempt_commands_run_over_an_unmigrated_v1_file
(services --json / status / isolation status with the gate live and non-interactive:
no refusal, file byte-identical, services shows forge+ci source legacy),
test_a_gated_command_refuses_over_an_unmigrated_v1_file, and
test_the_legacy_resolved_ci_is_what_the_migration_writes (5 repos: legacy ci ==
migrated ci; resolution unchanged across the migration).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-09-28T21:23:14+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

validate_profiles reuses _load_mapping/_loc and the live service models + validate_services; the only duplication left (pydantic error formatting) mirrors _model_problems but needs the service-name prefix, so there was nothing worth extracting

<!-- fr:journal kind=finding scope=plan id=p2r-fallback-declared created=2026-09-28T21:38:02+00:00 phase=2 state=open review_scope=in -->
### p2r-fallback-declared · finding [open] (reviewer: in scope) · Migration wrote the github FALLBACK as a declared forge for an unknown or missing origin (phase 2)

profiles_services.py:104 — flipped the source default->declared and silenced detect_backend's unknown-forge warning.

<!-- fr:journal kind=finding scope=plan id=p2r-validator-no-forge created=2026-09-28T21:38:02+00:00 phase=2 state=open review_scope=in -->
### p2r-validator-no-forge · finding [open] (reviewer: in scope) · Validator's cross-service checks ran only with a declared forge: (phase 2)

structure.py:520-531 — a cross-forge tracker or hostless gitlab-ci with no forge: passed validate but was refused by strict resolve; R3 is fail-closed.

<!-- fr:journal kind=finding scope=plan id=p2r-unknown-keys created=2026-09-28T21:38:02+00:00 phase=2 state=open review_scope=in -->
### p2r-unknown-keys · finding [open] (reviewer: in scope) · v2 validation accepted unknown top-level keys (e.g. `trackng:`) (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2r-flow-branch created=2026-09-28T21:38:02+00:00 phase=2 state=open review_scope=in -->
### p2r-flow-branch · finding [open] (reviewer: in scope) · Reachable YAMLError branch marked no-cover; message pointed at the wrong branch (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2r-mixed-message created=2026-09-28T21:38:02+00:00 phase=2 state=open review_scope=in -->
### p2r-mixed-message · finding [open] (reviewer: in scope) · Invalid service block with no legacy key refused as 'mixes version-1 backend:/host:' (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2r-edge-tests created=2026-09-28T21:38:02+00:00 phase=2 state=open review_scope=in -->
### p2r-edge-tests · finding [open] (reviewer: in scope) · Missing migration tests: BOM, nested host:, quoted/indented backend:, continuation line, empty file, flow-style (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2r-splitlines created=2026-09-28T21:38:02+00:00 phase=2 state=open review_scope=out -->
### p2r-splitlines · finding [open] (reviewer: out of scope) · str.splitlines splits on \x0c/\x1c/U+2028, so a comment fragment could in theory be dropped (phase 2)

Unrealistic; the same text-surgery pattern predates this change in the registry's stamp writer.

<!-- fr:journal kind=decision scope=plan id=p2r-lone-host created=2026-09-28T21:38:02+00:00 phase=2 -->
### p2r-lone-host · decision · A v1 file with host: and no backend: migrates to a declared github forge (phase 2)

Deviation accepted during the r1 fix: `fr init scaffold --host X` with the default backend never wrote `backend: github`, so a lone host: is fr's own declaration of a GitHub Enterprise forge, and the v1 resolver already reads it as github.

<!-- fr:journal kind=review scope=plan id=p2-review created=2026-09-28T21:38:02+00:00 phase=2 -->
### p2-review · review · Phase 2 review: 7 findings (6 in scope, fixed in 478273ed; 1 out of scope) (phase 2)

Independent reviewer over 2e1d3240, 5b5db21f, 2c0d0b9e against spec R3 §3.C-D, plan 02.yaml and .claude/rules/artifact-versioning.md. All artifact-versioning obligations met (registry-only stamp, imported migration, validator via ArtifactKind.validate, pinned frozen reader on the single hop, in-memory build + single atomic write, byte-identical refusals, crash-window handling, chain [2], duplicate keys); CRLF/BOM/nested-host/crash-window line surgery verified by reading. The six in-scope findings were fixed test-first in 478273ed (full suite 7076 passed); p2r-splitlines is out of scope.

<!-- fr:journal kind=finding scope=plan id=p2r-fallback-declared-resolved created=2026-09-28T21:38:02+00:00 phase=2 state=fixed resolves=p2r-fallback-declared -->
### p2r-fallback-declared-resolved · finding [fixed] · resolves p2r-fallback-declared: Migration wrote the github FALLBACK as a declared forge for an unknown or missing origin (phase 2)

478273ed: forge:/tracking: declared only when the type is known (backend:, recognised origin or host, or a lone host: -> github); otherwise omitted, source stays default and the warning fires; tests for unknown and no origin.

<!-- fr:journal kind=finding scope=plan id=p2r-validator-no-forge-resolved created=2026-09-28T21:38:02+00:00 phase=2 state=fixed resolves=p2r-validator-no-forge -->
### p2r-validator-no-forge-resolved · finding [fixed] · resolves p2r-validator-no-forge: Validator's cross-service checks ran only with a declared forge: (phase 2)

478273ed: with no forge:, the validator derives it via resolve_forge(lenient=True) and runs validate_services; tests for a cross-forge tracker and hostless gitlab-ci.

<!-- fr:journal kind=finding scope=plan id=p2r-unknown-keys-resolved created=2026-09-28T21:38:02+00:00 phase=2 state=fixed resolves=p2r-unknown-keys -->
### p2r-unknown-keys-resolved · finding [fixed] · resolves p2r-unknown-keys: v2 validation accepted unknown top-level keys (e.g. `trackng:`) (phase 2)

478273ed: top-level keys outside the v2 set are reported; test with `trackng:`.

<!-- fr:journal kind=finding scope=plan id=p2r-flow-branch-resolved created=2026-09-28T21:38:02+00:00 phase=2 state=fixed resolves=p2r-flow-branch -->
### p2r-flow-branch-resolved · finding [fixed] · resolves p2r-flow-branch: Reachable YAMLError branch marked no-cover; message pointed at the wrong branch (phase 2)

478273ed: pragma removed, messages and docstring corrected, flow-style refusal tested.

<!-- fr:journal kind=finding scope=plan id=p2r-mixed-message-resolved created=2026-09-28T21:38:02+00:00 phase=2 state=fixed resolves=p2r-mixed-message -->
### p2r-mixed-message-resolved · finding [fixed] · resolves p2r-mixed-message: Invalid service block with no legacy key refused as 'mixes version-1 backend:/host:' (phase 2)

478273ed: the mixed message only when a legacy key is present; otherwise _service_problems names the invalid block; test ci: {type: travis}.

<!-- fr:journal kind=finding scope=plan id=p2r-edge-tests-resolved created=2026-09-28T21:38:02+00:00 phase=2 state=fixed resolves=p2r-edge-tests -->
### p2r-edge-tests-resolved · finding [fixed] · resolves p2r-edge-tests: Missing migration tests: BOM, nested host:, quoted/indented backend:, continuation line, empty file, flow-style (phase 2)

478273ed: BOM, nested host:, continuation line, empty file, quoted/indented/flow-style refusal tests added.

<!-- fr:journal kind=finding scope=plan id=p2r-splitlines-resolved created=2026-09-28T21:38:02+00:00 phase=2 state=open resolves=p2r-splitlines out_of_scope=true -->
### p2r-splitlines-resolved · finding [out-of-scope] · resolves p2r-splitlines: str.splitlines splits on \x0c/\x1c/U+2028, so a comment fragment could in theory be dropped (phase 2)

Pre-existing text-surgery pattern (registry stamp writer); not caused by this change and not realistic input.

<!-- fr:journal kind=decision scope=plan id=p3-ci-reason-seam created=2026-09-28T21:49:13+00:00 phase=3 -->
### p3-ci-reason-seam · decision · fr.acceptance.ci.ci_reason/ci_active resolve the ci service leniently; init takes ci_type/tracking_type (phase 3)

`ci_reason(root)` (None = active) calls `resolve_services(root, lenient=True)` (lazy import: resolve imports
acceptance.ci). Declared `ci: {type: none}` refuses `ci` rows naming the declaration; undeclared none keeps
#787's no_ci_message. `record/apply._no_ci_reason` delegates to it. `scaffold.init(..., ci_type=None,
tracking_type=None, no_ci_reason=None)`: with ci_type None it is the old backend path (test_acceptance_init_no_ci
unchanged). `SCAFFOLD_PATHS` is now keyed by ci TYPE, plus `DEBT_PLATFORM` (github-actions->github, ...).
`init_cmd` resolves strictly (ServicesError -> exit 2), refuses `--with-ci` only when ci is DECLARED none, and
maps undeclared/legacy none + --with-ci to the forge's own ci type.

<!-- fr:journal kind=discovery scope=plan id=p3-debt-fragments created=2026-09-28T21:49:13+00:00 phase=3 -->
### p3-debt-fragments · discovery · Debt step is @@DEBT_COMMENT@@/@@DEBT_STEP@@ tokens in each template; render_workflow(ci_type, debt=) (phase 3)

With debt=True each render is byte-identical to the pre-phase template (verified against HEAD). Omission prints
a `no debt` notice and drops the sentence from the rule's CI bullet. The github template's `issues: write`
permission is left in place when the step is omitted.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-09-28T21:49:13+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

scaffold.py had no backend-keyed leftovers no caller uses: backend still drives the no-declaration path and the no-CI message; the per-backend workflow dict was replaced by WORKFLOW_TEMPLATES keyed by ci type.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-09-28T21:49:13+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

the debt step was split into fragments as part of the GREEN itself; nothing further to clean.

<!-- fr:journal kind=finding scope=plan id=p3r-lenient-ci-gate created=2026-09-28T21:58:27+00:00 phase=3 state=open review_scope=in -->
### p3r-lenient-ci-gate · finding [open] (reviewer: in scope) · A malformed ci: declaration silently allowed `ci` rows (phase 3)

acceptance/ci.py:76 resolved leniently, so an invalid ci: block fell through to the raw ci_config probe; init refused the same file strictly.

<!-- fr:journal kind=finding scope=plan id=p3r-issues-write created=2026-09-28T21:58:27+00:00 phase=3 state=open review_scope=in -->
### p3r-issues-write · finding [open] (reviewer: in scope) · github-actions template kept `issues: write` with the debt step omitted (least privilege) (phase 3)

scaffold.py:125-127.

<!-- fr:journal kind=finding scope=plan id=p3r-fr-only-message created=2026-09-28T21:58:27+00:00 phase=3 state=open review_scope=in -->
### p3r-fr-only-message · finding [open] (reviewer: in scope) · Refusal said 'no CI config' when fr's own acceptance scaffold was found and discounted (phase 3)

ci.py:81 / scaffold.py:505. The reviewer tagged this OUT of scope (rare path: gated commands migrate v1 first). Reclassified IN by the orchestrator: the fr-only discount that makes the message false is introduced by this change, and exempt/ungated paths still reach it.

<!-- fr:journal kind=finding scope=plan id=p3r-golden-tests created=2026-09-28T21:58:27+00:00 phase=3 state=open review_scope=in -->
### p3r-golden-tests · finding [open] (reviewer: in scope) · No byte-equality test for the unchanged debt=True renders; '@@' leakage and the notice assertion unpinned (phase 3)

tests/unit/test_acceptance_services.py:115-139.

<!-- fr:journal kind=review scope=plan id=p3-review created=2026-09-28T21:58:27+00:00 phase=3 -->
### p3-review · review · Phase 3 review: 4 findings, all fixed in 867e43ab (phase 3)

Independent reviewer over e89b1168 against spec R4 §3.B/§3.E and plan 03.yaml: debt=True renders verified byte-identical to main by hand, no token leaks, #787's no-profiles behaviour unchanged, --with-ci per §3.E, lazy import cycle safe. Findings p3r-lenient-ci-gate, p3r-issues-write, p3r-golden-tests (in) and p3r-fr-only-message (reviewer: out; reclassified in, see its body) fixed in 867e43ab; full suite 7109 passed.

<!-- fr:journal kind=finding scope=plan id=p3r-lenient-ci-gate-resolved created=2026-09-28T21:58:27+00:00 phase=3 state=fixed resolves=p3r-lenient-ci-gate -->
### p3r-lenient-ci-gate-resolved · finding [fixed] · resolves p3r-lenient-ci-gate: A malformed ci: declaration silently allowed `ci` rows (phase 3)

867e43ab: ci_reason resolves strictly; ServicesError becomes the refusal naming .devcontainer/fr-profiles.yaml; tests for scalar none, unknown type, jenkins.

<!-- fr:journal kind=finding scope=plan id=p3r-issues-write-resolved created=2026-09-28T21:58:27+00:00 phase=3 state=fixed resolves=p3r-issues-write -->
### p3r-issues-write-resolved · finding [fixed] · resolves p3r-issues-write: github-actions template kept `issues: write` with the debt step omitted (least privilege) (phase 3)

867e43ab: @@DEBT_PERMS@@ token; debt=False grants contents: read only; debt=True byte-identical (golden).

<!-- fr:journal kind=finding scope=plan id=p3r-fr-only-message-resolved created=2026-09-28T21:58:27+00:00 phase=3 state=fixed resolves=p3r-fr-only-message -->
### p3r-fr-only-message-resolved · finding [fixed] · resolves p3r-fr-only-message: Refusal said 'no CI config' when fr's own acceptance scaffold was found and discounted (phase 3)

867e43ab: ci_none_reason names the discounted fr-only scaffold and points at declaring ci:; tests for refusal and init output.

<!-- fr:journal kind=finding scope=plan id=p3r-golden-tests-resolved created=2026-09-28T21:58:27+00:00 phase=3 state=fixed resolves=p3r-golden-tests -->
### p3r-golden-tests-resolved · finding [fixed] · resolves p3r-golden-tests: No byte-equality test for the unchanged debt=True renders; '@@' leakage and the notice assertion unpinned (phase 3)

867e43ab: golden fixtures from origin/main for 3 renders + 2 bullets, '@@' absent in all 6 renders, exact notice list.

<!-- fr:journal kind=decision scope=plan id=p4-strict-write-paths created=2026-09-28T22:06:48+00:00 phase=4 -->
### p4-strict-write-paths · decision · require_tracker resolves strictly; apply/dispatch refuse a malformed tracking block (phase 4)

`fr.services.require_tracker(repo_root)` calls `resolve_services` strict. `tracking: {type: none}`
raises `TrackerRequiredError` (a ServicesError); an invalid declaration raises the plain ServicesError.
`fr apply --yes` (top of `_apply_one`, before build_plan_report's observe) and `fr triage batch
dispatch --yes` (before make_client; reads the checkout's path, so it also covers --repair) exit 2 on
either. Dry runs do not refuse: apply adds a `warning:` line and a json warning; dispatch prints a warning.

<!-- fr:journal kind=decision scope=plan id=p4-closeout-strict-warn created=2026-09-28T22:06:48+00:00 phase=4 -->
### p4-closeout-strict-warn · decision · The closeout brief resolves strictly but warns instead of refusing on a malformed declaration (phase 4)

The brief is read-only and read by a fresh session after merge, so it must stay usable; but lenient
mode would silently read a malformed tracking block as "has a tracker" and print issue-filing lines.
So closeout_brief resolves strictly: none -> no `file an issue` / `--tracked-by` lines and a line saying
out-of-scope findings stay recorded in the journal and PR body; invalid -> a loud WARNING line, default
lines kept.

<!-- fr:journal kind=discovery scope=plan id=p4-apply-root created=2026-09-28T22:06:48+00:00 phase=4 -->
### p4-apply-root · discovery · apply's repo root comes from the plan dir, dispatch's from the checkout (phase 4)

`_apply_one` uses `resolve_repo_root(plan_dir.resolve())` (honours VK_REPO_ROOT); `fr triage collect`
is untouched (asserted by source inspection only, since it never calls require_tracker).
`fr.services/__init__` now re-exports ServicesError, TrackerRequiredError, require_tracker.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t1 created=2026-09-28T22:06:48+00:00 phase=4 -->
### no-refactor-p4-t1 · discovery · no-refactor-because P4.T1 (phase 4)

one small shared helper (require_tracker) and three call sites; nothing duplicated to fold
