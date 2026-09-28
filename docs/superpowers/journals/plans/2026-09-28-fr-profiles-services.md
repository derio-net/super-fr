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
