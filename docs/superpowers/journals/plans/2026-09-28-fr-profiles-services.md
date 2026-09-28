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
