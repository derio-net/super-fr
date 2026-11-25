<!-- fr:journal-schema=4 -->
# Journal: 2026-11-24-s1-configuration-homes

<!-- fr:journal kind=finding scope=plan id=sec-1-self-attesting-config-branch created=2026-11-24T21:06:33+00:00 phase=3 state=open -->
### sec-1-self-attesting-config-branch · finding [open] · A self-declared fr-config branch must not supply executable or trust keys unless its protection is enforced (phase 3)

Automated security review of phase 1's commit (space.py forge_ref, triage/collect.py): the forge-side reader takes .fr/triage.yaml from fr-config when that branch's own settings say placement: quiet, so anyone able to push a branch named fr-config could redirect post_merge commands and the pr_authors trust list. Default-branch opt-in is not available under quiet by design (D12, R5), and self-attestation of the switch predates S1 (origin/fr). Phase 3 closes it: R7's guard must cover trust keys as well as executable ones (pr_authors, and any key that decides whose PRs are trusted or merged), and every reader that takes such keys from a configuration branch asks require_protected first; when not enforced, those keys come from nowhere (ignored, with the reason), never from the unprotected branch. Test: a pushed fr-config with no pull_request rule yields no post_merge and no pr_authors from it.

<!-- fr:journal kind=decision scope=plan id=p1-placement-read created=2026-11-24T23:31:33+00:00 phase=1 -->
### p1-placement-read · decision · config_space reads the placement with outside_repo, not space_for (phase 1)

`config_space(root)` decides the placement with `fr.artifacts.paths.outside_repo` (the
stealth marker, then the `origin/fr` switch) rather than calling `space_for`. `space_for`
under quiet needs a non-detached HEAD to name the feature and, with `create=True`, makes
the `fr` worktree; under stealth it checks the tracking repo is reachable. A
configuration read must have no side effects and must work in a detached CI checkout, so
it takes only the placement. The quiet `fr-config` worktree and the stealth
`stealth--<slug>-config` clone paths are computed in `fr.config.space` alone
(`quiet_checkout`, `stealth_checkout`); P2 creates them. Under quiet, reads at
`origin/fr-config` run in the product clone (the worktree will be a linked worktree of
it); under stealth they run in the configuration clone and read as absent until it exists.

<!-- fr:journal kind=decision scope=plan id=p1-repo-semantics created=2026-11-24T23:31:33+00:00 phase=1 -->
### p1-repo-semantics · decision · Under repo the moved readers keep their own git reads and error semantics (phase 1)

`run/ci_evidence.py`, `lenses/rules.py` and `triage/queue_exec.py` each had their own
answer for an unreadable ref (`load_gate_checks` reads an unfetched `origin/<base>` as
None; `base_config_text` raises `LensError`; `_ci_yaml_at_head` reads only git's
"path does not exist" words as absent). `at_pair`/`at_default` under `repo` use
`show_at_commit`/`read_at_default`, which raise on any ls-tree failure. To keep "under
repo nothing a user sees changes", these readers take `config_space(root)` and use
`at_pair`/`at_default` when `space.ref` is set (quiet, stealth), and keep their own reads
under `repo`. `settings/check.py` and `record/pr_body.py`'s lens-config note do use
`at_default`/`at_pair` under every placement, where the semantics already matched.

<!-- fr:journal kind=decision scope=plan id=p1-tripwire-scope created=2026-11-24T23:31:33+00:00 phase=1 -->
### p1-tripwire-scope · decision · The config-space tripwire also counts named path constants and defaults (phase 1)

The spec names the constructions as literals passed to `Path(...)`, `/`, `open`,
`read_text`, `show_at_commit` or a `git show` list. Most `.fr` readers built their path
from a module constant (`CONFIG_PATH = ".fr/docs.yaml"`), which that narrow rule never
sees, so `tests/unit/test_tripwire_config_space.py` flags every path-shaped string literal
(`.fr` or `.fr/<path>`, no whitespace or colon) outside a message: a docstring, an
f-string, and the arguments of print/echo/logger calls and exception constructors are
skipped. The named constants now come from `fr.config.space` (`rel(...)`, `SPACE_DIR`,
`PRODUCT_TRIAGE_STATE`), and the scan lists none outside the allowed modules.

<!-- fr:journal kind=decision scope=plan id=p1-forge-ref-lenient created=2026-11-24T23:31:33+00:00 phase=1 -->
### p1-forge-ref-lenient · decision · forge_ref reads a failed fr-config read as no switch (phase 1)

`fr.config.space.forge_ref(client, repo)` returns `fr-config` only when that branch's
`.fr/settings.yaml` holds the canonical `placement: quiet` line. An absent branch, a
forge without `read_file_at_ref` (glab/tea raise `UnsupportedForgeOperation`) or any
other read error returns None, the default branch, which is what every forge-side reader
read before S1. The policy reader (`settings/remote.py`) still fails closed on its own
read of the chosen ref. The probe costs one extra forge read per repo per collect and
per policy read (`test_triage_facts_schema3.py` and `triage_fixtures.anchor_reads` now
count it).

<!-- fr:journal kind=discovery scope=plan id=p1-docs-stale-owed-p7 created=2026-11-24T23:31:33+00:00 phase=1 -->
### p1-docs-stale-owed-p7 · discovery · fr docs check lists pages whose covered code this phase touched (phase 1)

`uv run fr docs check` reports stale pages: `docs/docs-currency.md` (docs/load.py),
`docs/explainers/fr-devops-gate.md` (ops/gate.py), `docs/explainers/fr-triage.md`
(triage/*), `docs/herdr-control-sessions.md` and others. Phase 7 owns S1's pages
(spec §H); until then deliver's docs evidence refuses, so P7 must edit those pages or
move their `reviewed` stamps.

<!-- fr:journal kind=discovery scope=plan id=p1-not-moved-yet created=2026-11-24T23:31:33+00:00 phase=1 -->
### p1-not-moved-yet · discovery · Readers of the R9 kinds and executable configuration are not on the resolver yet (phase 1)

Phase 1 moved the readers its plan names. Still reading the product checkout: the R9
kinds (`workflow/resolve.py`, `verification/resolve.py`, `fr/models.py`,
`tracker/model.py`, `plan_config.py`, `services/resolve.py`, profiles) whose files P4
moves; `verification/walk.py`'s `.fr/candidate-install` run and `triage/gitseam.py`'s
commands (executable configuration, P3's protection guard); `fr settings paths` and
`fr.artifacts.paths.kind_dir` for the moved kinds. Their path literals now come from
`fr.config.space`, so the tripwire stays green while they move.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-24T23:31:33+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

at_pair was written in T2's GREEN with the rest of ConfigSpace; the three readers moved onto it each gained one small branch for quiet/stealth and kept their repo-path error semantics, so there was no duplication left to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-24T23:31:33+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

each reader's change was one line (the file path comes from config_space(root).file); forge_ref is one function shared by the forge-side readers, and tracker/github reaches it through settings/remote's client_policy, so nothing was left to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-24T23:31:33+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

the replacements were constants pointed at fr.config.space (rel, SPACE_DIR, PRODUCT_TRIAGE_STATE); the tripwire's scanner is one function with its message exclusions as data

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-11-25T00:25:30+00:00 phase=1 -->
### review-p1 · review · Phase 1 review (the configuration space, the moved readers, the ast tripwire) (phase 1)

Independent reviewer read d3eec17..HEAD against R1-R4 and decisions p1-repo-semantics and
p1-tripwire-scope. The resolver is sound and under repo the readers keep their own git reads
and error handling. Seven in-scope findings: one (p1-r1) moved to phase 3 beside sec-1, five
fixed in 4b2b60c17..8e38ce78a, one refuted. Targeted tests 51/51; after the fixes 83/83 on
config_space, tripwire and triage drift, 948/948 on the quiet/lens/ci/queue/stealth/pr_body set.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-25T00:25:30+00:00 phase=3 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · triage collect's read_config_lenient takes post_merge, version commands and pr_authors from a self-declared unprotected fr-config; phase 3's guard must cover trust keys and the forge-side reader, and flip test_forge_side_triage_config_follows_the_quiet_switch (phase 3)

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-25T00:25:30+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · forge_ref's catch-all read every forge error (5xx, rate limit, auth, bug) as no switch (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-25T00:25:30+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · under quiet/stealth a config space not yet created read as no configuration: lens rules, docs.yaml and gate_checks vanished (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-25T00:25:30+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · config_space() under repo can raise SettingsError into docs/debt/ops/lenses/verification readers whose callers never expected it (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-25T00:25:30+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · the config-space tripwire skipped every f-string, so Path(f'{root}/.fr/x') and f'{rev}:.fr/x' passed (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-11-25T00:25:30+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · forge_ref tests covered only a 404 and a repo switch; no non-404 error, no forge without read_file_at_ref, no _lens_config_changed test (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-11-25T00:25:30+00:00 phase=1 state=open review_scope=in -->
### p1-r7 · finding [open] (reviewer: in scope) · under repo every triage collect and remote policy read makes one extra fr-config probe per repo (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-25T00:25:30+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: forge_ref's catch-all read every forge error (5xx, rate limit, auth, bug) as no switch (phase 1)

4b2b60c17: only a not-found, an UnsupportedForgeOperation (direct or as a ForgeError's cause) or a forge with no read_file_at_ref is no switch; any other error propagates. The probed text is validated by fr.placement.quiet.parse_switch_text, the same check the local switch reader uses; read_config_lenient turns a SettingsError into a TriageError naming the repo, which collect already skips or refuses.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-25T00:25:30+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: under quiet/stealth a config space not yet created read as no configuration: lens rules, docs.yaml and gate_checks vanished (phase 1)

2f4df4f0c: at_default/at_pair raise SettingsError naming the missing space (stealth config clone, origin/fr-config, origin/<branch>-config) and the remedy; lens rules refuse with LensError, declared_gates with CiEvidenceRefused, the queue's required_names with TriageError reported once per repo by the drive loop. repo is unchanged.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-25T00:25:30+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: config_space() under repo can raise SettingsError into docs/debt/ops/lenses/verification readers whose callers never expected it (phase 1)

b71a8b047: docs/load, debt/engine, ops/load and lenses/resolve translate SettingsError into DocsEnvError, DebtConfigError, OpsLoadError and LensError; verification/rows.load_remap stays lenient and returns the reason. One test per reader family with a malformed origin/fr switch.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-25T00:25:30+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: the config-space tripwire skipped every f-string, so Path(f'{root}/.fr/x') and f'{rev}:.fr/x' passed (phase 1)

a14c733eb: an f-string whose literal parts name .fr as a path segment is a construction, exempt only inside a message call; fixture cases pin both shapes. It found ops_gate_cmd.HostCheckout.queue_configured, now read through config_space with a quiet behaviour test.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-11-25T00:25:30+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: forge_ref tests covered only a 404 and a repo switch; no non-404 error, no forge without read_file_at_ref, no _lens_config_changed test (phase 1)

4b2b60c17 and 980f04111 add the non-404, glab/tea/no-reader, wrapped-unsupported and malformed-switch cases, and _lens_config_changed under repo (same text, changed, absent, no merge-base) and quiet.

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-11-25T00:25:30+00:00 phase=1 state=refuted resolves=p1-r7 -->
### p1-r7-resolved · finding [refuted] · resolves p1-r7: under repo every triage collect and remote policy read makes one extra fr-config probe per repo (phase 1)

Spec R3/§A places forge readers on the default branch or fr-config by the remote switch, which fr cannot know without reading it; one 404 per repo per collect is the cost of that design, recorded in p1-forge-ref-lenient, and nothing a user sees in output changes.
