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

<!-- fr:journal kind=decision scope=plan id=p2-up-creates-config-space created=2026-11-25T01:53:05+00:00 phase=2 -->
### p2-up-creates-config-space · decision · fr isolation up and run start create the configuration branch from the old switch (phase 2)

Phase 1's `fr.config.space` refuses under quiet/stealth while the configuration space
is missing, so an existing quiet repo (switch only at `origin/fr:settings.yaml`) or
stealth run (no `<branch>-config`) would refuse every configuration read. A fetching
`fr isolation up` / `fr run start` therefore creates it: `quiet.ensure_config_branch`
pushes an orphan `fr-config` whose tree is `.fr/settings.yaml` holding the old file's
bytes (plain push, never forced; a lost creation race keeps the other clone's branch),
then `ensure_config_worktree` makes `~/.cache/fr/worktrees/<repo>/fr-config`.
`stealth.ensure_config_clone` (from `enter`) creates `<branch>-config` on the tracking
repo (an empty-tree orphan when the target has no settings file, else carrying
`<target>/settings.yaml` as `<target>/.fr/settings.yaml`), clones
`stealth--<slug>-config`, and carries the old file when a branch exists without it.
`--no-fetch` never pushes. Only the settings file moves here; the product's other
`.fr/` files move with the R11 migration (phase 4).

<!-- fr:journal kind=discovery scope=plan id=p2-phase4-settings-already-moved created=2026-11-25T01:53:05+00:00 phase=4 -->
### p2-phase4-settings-already-moved · discovery · The settings-location hop meets an fr-config that already holds the settings (phase 4)

After phase 2, every quiet repo that ran a fetching `fr isolation up`/`fr run start`
(and every stealth target entered) already has `.fr/settings.yaml` on the
configuration branch with the same bytes as the old file, and fr keeps writing both
(R6). Phase 4's `settings-location` kind must read that state as migrated (the old
file is the R6 legacy copy, not a second file for R12's both-paths refusal), or R12
refuses every quiet repo.

<!-- fr:journal kind=discovery scope=plan id=p2-memory-ref created=2026-11-25T01:53:05+00:00 phase=2 -->
### p2-memory-ref · discovery · SWITCH_REF also named the memory branch; MEMORY_REF names it now (phase 2)

`paths.SWITCH_REF` (`refs/remotes/origin/fr`) was used both as the switch and as the
memory branch's tracking ref (quiet FETCH_REFSPEC, worktree creation, fast-forward,
`merged.pushed_ref`, `archive_cmd._unpushed`, `placement.move` copy/verify). Moving
SWITCH_REF to `origin/fr-config` would have pointed those at the configuration branch,
so `paths.MEMORY_REF` now names `origin/fr` for them, and `LEGACY_SWITCH_REF` is that
same ref for the R13 fallback.

<!-- fr:journal kind=decision scope=plan id=p2-hooks-blob-compare created=2026-11-25T01:53:05+00:00 phase=2 -->
### p2-hooks-blob-compare · decision · The hooks compare the two switches by blob, as fr compares bytes (phase 2)

`_fr_read_switch` (bash) and `readSwitch` (marker.ts) take `rev-parse --verify` of both
`<ref>:<path>` locations; two blobs that both exist and differ read as the text
`placement: two switches that differ`, which `_fr_switch_enabled`/`switchEnabled` call
fr-enabled and the write-target check never calls canonical quiet: the base clone is
gated and no `fr`/`fr-config` worktree is a write target (fail closed, R6). A blob
compare matches Python's byte compare exactly (a text compare after `$(...)` would
ignore trailing newlines). Write targets: the `fr` or `fr-config` worktree at exactly
`$HOME/.cache/fr/worktrees/<main>/<branch>` on `refs/heads/<branch>`; the stealth
configuration clone named `stealth--*-config` on `<tracking branch>-config` beside a
valid stealth workspace naming its origin. The allowlist is `.fr/isolation-allow` in
the working tree, `.fr-isolation-allow` only while it is absent; neither is read from
a ref.

<!-- fr:journal kind=finding scope=plan id=p2-config-writes-not-prs created=2026-11-25T01:53:05+00:00 phase=2 state=open review_scope=in -->
### p2-config-writes-not-prs · finding [open] (reviewer: in scope) · write_settings pushes the configuration branch directly; spec §B wants a pull request for every change after creation (phase 2)

Spec §B: "fr creates either one ... at the migration (§D) or at `fr settings init` ...
and opens a pull request for every later change". Phase 2's writer creates the branch
(init, up, migration) with a plain or compare-and-swap push, and also rewrites an
existing `fr-config` with a direct fast-forward push (`fr placement move` switching to
quiet or back to repo, `write_settings` on an existing branch). No plan step builds the
pull-request path. Once phase 3 makes protection of `fr-config` matter, a protected
branch refuses those direct pushes (fr reports the refusal; nothing is forced). Decide
whether `write_settings` on an existing configuration branch opens a PR (and which
phase builds it) or whether the spec's sentence is amended to the creation-only case.

<!-- fr:journal kind=lens scope=plan id=lens-security-1 created=2026-11-25T01:53:05+00:00 phase=2 lens=security step=implement-phase -->
### lens-security-1 · lens · a guard change on three harnesses (edit gate write targets, switch reads, allowlist) and new pushes to origin at isolation up (phase 2)

<!-- fr:journal kind=lens scope=plan id=lens-errors-1 created=2026-11-25T01:53:05+00:00 phase=2 lens=errors step=implement-phase -->
### lens-errors-1 · lens · new network paths (fr-config / <branch>-config creation races, refused pushes, rollbacks) at isolation up and settings writes (phase 2)

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-11-25T01:53:05+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

the switch read is one function (quiet._read over switch_texts) and the worktree helpers were folded into _ensure_linked/_fast_forward_linked while writing GREEN, so ensure_worktree and the new ensure_config_worktree already share one body

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-11-25T01:53:05+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

write_settings is one dispatcher over two per-placement writers (quiet.write_switch over write_branch_file, stealth.write_target_settings over _commit_file); init --quiet, init --stealth, plain init and placement move all call it, so no second writer was left to fold

<!-- fr:journal kind=decision scope=plan id=p2-create-at-init-and-migration created=2026-11-25T03:20:17+00:00 phase=2 -->
### p2-create-at-init-and-migration · decision · fr creates fr-config / <branch>-config only at the migration and at fr settings init (phase 2)

Spec §B, review p2-r3 (orchestrator decision). Entering a workspace fetches and never pushes: a fetching `fr isolation up` / `fr run start` no longer calls `quiet.ensure_config_branch`, and stealth `enter` only adopts an existing `<branch>-config` (`stealth.adopt_config_clone`); `up --no-fetch` pushes nothing under quiet or stealth (p2-r4). Until the space exists, a configuration read refuses and names `fr migrate artifacts --yes` and `fr settings init --quiet` / `--stealth <repo>@<branch>` (`ConfigSpace._missing`). `fr settings init --quiet` on a repo whose switch is only `origin/fr:settings.yaml` creates `fr-config` holding those bytes; `init --stealth` with only the old `<target>/settings.yaml` carries it onto a new orphan `<branch>-config`. Replaces p2-up-creates-config-space.

<!-- fr:journal kind=decision scope=plan id=p2-up-creates-config-space-replaced created=2026-11-25T03:20:19+00:00 phase=2 -->
### p2-up-creates-config-space-replaced · decision · p2-up-creates-config-space is replaced by p2-create-at-init-and-migration (phase 2)

The earlier decision (up and run start create the configuration branch from the old switch) contradicted spec §B and pushed on every workspace entry (review p2-r3, p2-r4). It no longer holds; see p2-create-at-init-and-migration. p2-phase4-settings-already-moved is void with it: no quiet repo or stealth target gets a configuration branch from `up` any more.

<!-- fr:journal kind=decision scope=plan id=p2-config-changes-by-pr created=2026-11-25T03:20:21+00:00 phase=2 -->
### p2-config-changes-by-pr · decision · Every change to an existing configuration branch is a pull request; the old copy follows only by fr settings sync --yes (phase 2)

Spec §B, R6; review p2-r1, p2-r7 (orchestrator decision, revised after a security review). Creation (`fr settings init`, the migration) writes `fr-config` / `<branch>-config` and then the old copy directly; the old-copy write (`quiet.write_legacy`, `stealth.write_legacy_target`) fetches `fr` (stealth: syncs the tracking clone) just before committing, rebases fr's own unpushed commits onto it and retries a push refused as not a fast-forward up to 3 times; a retry with the configuration branch already current lands only the old copy. Every later change (`write_settings`, `placement.move._settle_switch`) commits on `fr-config-change/<slug>` (slug = hash of path and bytes, so a retry reuses it) from the configuration branch's tip, pushes it and opens a pull request through the forge client (`fr.config.change.open_pr`; stealth: on the tracking repo), prints its URL and writes no old copy; `fr placement move` pauses on it. No reader writes the old copy: an auto-sync on read would copy a push made straight to an unprotected configuration branch and erase the one signal of it. Readers refuse whenever the two differ; when the old copy is an earlier first-parent version of the new file the refusal says so and names `fr settings sync` (preview: both refs, the commits between, each marked whether it merged a `fr-config-change/*` branch) and `fr settings sync --yes` (the robust old-copy write). `settings` stays in READ_ONLY_COMMANDS: `sync --yes` writes only the old settings file on `fr` / the tracking branch, which is no registered artifact kind. The hooks' deny names `fr settings sync`.

<!-- fr:journal kind=decision scope=plan id=p2-gate-config-tree created=2026-11-25T03:20:23+00:00 phase=2 -->
### p2-gate-config-tree · decision · The edit gate refuses a configuration checkout whose tree is not .fr/ (checked cheaply in both engines) (phase 2)

Review p2-r2. fr refuses to adopt or push a `fr-config` / `<branch>-config` whose tree holds anything outside `.fr/` (stealth: `<one segment>/.fr/`) or that shares history with the product's branches (`quiet.refuse_foreign_config`, from the fr-config worktree, `write_branch_file` and the stealth configuration clone). The structural write-target rule asks the tree half too, since it is one `git ls-tree -r --name-only HEAD` in both bash (`_fr_config_tree_ok`) and marker.ts (`configTreeOk`); an empty or unreadable tree is refused by both. The history half stays fr's: the hooks do not walk history.

<!-- fr:journal kind=discovery scope=plan id=p2-phase4-migration-creates-config created=2026-11-25T03:20:25+00:00 phase=4 -->
### p2-phase4-migration-creates-config · discovery · The migration creates the configuration branch before removing product files (phase 4)

Decision p2-create-at-init-and-migration: entering a workspace no longer creates `fr-config` / `<branch>-config`, so phase 4's migration is where every existing quiet repo and stealth target gets one. It must create the configuration branch (an orphan whose tree is `.fr/`, stealth `<target-dir>/.fr/`; `quiet.ensure_config_branch` / `write_settings` do the settings file) and push it BEFORE it removes any product file (R10), accept one that already holds identical settings (a `fr settings init` ran first, so the old file is R6's legacy copy and not a second file for R12), and refuse a foreign one (`quiet.refuse_foreign_config`). This replaces p2-phase4-settings-already-moved, whose premise (up created the branch) no longer holds.

<!-- fr:journal kind=discovery scope=plan id=p2-phase3-sync-needs-protection created=2026-11-25T03:20:28+00:00 phase=3 -->
### p2-phase3-sync-needs-protection · discovery · fr settings sync may run without the operator only on a forge-protected configuration branch (phase 3)

Decision p2-config-changes-by-pr: no reader writes the old settings copy, because on an unprotected `fr-config` a direct push looks like a merged review. Once phase 3's `require_protected` / branch-protection reader exists, fr may bring the old copy in step without `fr settings sync --yes` ONLY when the configuration branch is forge-protected with a pull-request rule; an unprotected or unreadable answer keeps requiring the explicit command.

<!-- fr:journal kind=decision scope=plan id=p2-sync-expect-and-second-parent created=2026-11-25T03:28:22+00:00 phase=2 -->
### p2-sync-expect-and-second-parent · decision · fr settings sync writes only from the previewed tip, and labels a merge by its second parent alone (phase 2)

Security review of `fr settings sync` (amends p2-config-changes-by-pr). The preview fetches the switch branches and `fr-config-change/*` (stealth: into the configuration clone from the tracking repo) and prints the configuration branch's tip, its settings blob, and every first-parent commit since the old copy's version with its sha and second-parent sha; a commit is labelled a merge of a change branch only when that second parent is the tip of a fetched `refs/remotes/origin/fr-config-change/*` ref, never by its subject, and the label is information, not an authorization. `--yes` requires `--expect <tip>` and refuses (exit 2, nothing written) without it or when the tip after its own fetch differs, naming the preview to run again.

<!-- fr:journal kind=decision scope=plan id=p2-config-pr-honours-git-pr created=2026-11-25T03:43:09+00:00 phase=2 -->
### p2-config-pr-honours-git-pr · decision · The configuration change's PR honours git.pr exactly as fr pr create does (phase 2)

Orchestrator decision. `fr.config.change.open_change` reads `git.pr` from the product checkout's settings (`pr_policy`; under stealth the target workspace's, while the PR goes to the tracking repo). Under `ask` it calls `fr.git_policy.ask.require_approval(kind=pr, branch=fr-config-change/<slug>)` with the run's approval journal before committing or pushing anything; a missing approval refuses (SettingsError, nothing pushed, run the command again once approved), and an approved request is consumed after the PR opens. Under `auto` it opens as before. The schema's `git.pr` takes only `auto` and `ask` (AUTO_ASK), so there is no `off` path to build; if `off` is ever added, the PR open is where it must print the pushed branch and the command to open it.

<!-- fr:journal kind=review scope=plan id=review-p2 created=2026-11-25T03:57:01+00:00 phase=2 -->
### review-p2 · review · Phase 2 adversarial review (configuration branch, the switch, the edit gate on three harnesses) (phase 2)

Independent adversarial reviewer read e297636..HEAD against §B, R5, R6, R8 and R13, attacked the
edit gate with structural forgeries (wrong branch, wrong path, fr at fr-config's path, primary
checkout, same-basename foreign worktree, differing switches, symlinked allowlist): all held, bash and
TS identical. Reproduced three real defects in scratch repos (legacy-push race lockout, foreign
fr-config adoption, allowlist self-unlock). Seven in-scope findings, all fixed in 6a01ea762..aa5c5c255,
plus three automated security-review revisions (marker protection and file identity; no auto-sync of
the legacy copy; second-parent labelling and --expect on fr settings sync) and the configuration PR
honouring git.pr. Targeted selection 3009 passed / 9 skipped, bun 399/0, tsc, ruff, mypy, parity clean.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-25T03:57:01+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · the legacy fr push lost a race with any artifact push, leaving differing switches on origin and a permanent lockout (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-25T03:57:01+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · a fetching up adopted a foreign origin or local fr-config, committed onto product history and pushed it; the gate then treated that checkout as a write target (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-25T03:57:01+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · fetching up / run start / stealth enter pushed a new branch to origin, which spec §B does not provide for (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-11-25T03:57:01+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · under stealth up --no-fetch still pushed (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-11-25T03:57:01+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · the moved allowlist could unlock itself through an old .fr/** glob (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-11-25T03:57:01+00:00 phase=2 state=open review_scope=in -->
### p2-r6 · finding [open] (reviewer: in scope) · the bash/TS parity drift test pinned only the switch location strings, not the decision logic (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r7 created=2026-11-25T03:57:01+00:00 phase=2 state=open review_scope=in -->
### p2-r7 · finding [open] (reviewer: in scope) · later changes to fr-config were direct pushes, not the pull request spec §B requires (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-25T03:57:01+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: the legacy fr push lost a race with any artifact push, leaving differing switches on origin and a permanent lockout (phase 2)

447350b3b/623b5e593 and the write_legacy rewrite: the legacy write fetches, rebases fr's own commits and retries a non-fast-forward up to 3 times; a retry with fr-config current lands only the legacy copy; no reader writes the copy, a lagging one is brought in step only by fr settings sync --yes --expect <tip>, and every refusal names both refs and the remedy.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-25T03:57:01+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: a fetching up adopted a foreign origin or local fr-config, committed onto product history and pushed it; the gate then treated that checkout as a write target (phase 2)

929ad1ac4: quiet.refuse_foreign_config refuses a config branch whose tree holds anything outside .fr/ (stealth <dir>/.fr/) or that shares history with the product, at the worktree, write_branch_file and the stealth clone; the gate also checks the tree shape in bash and TS (decision p2-gate-config-tree).

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-25T03:57:01+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: fetching up / run start / stealth enter pushed a new branch to origin, which spec §B does not provide for (phase 2)

d97afe310: entering a workspace fetches and never creates; fr settings init and the migration (phase 4, discovery p2-phase4-migration-creates-config) create the space; decision p2-create-at-init-and-migration replaces p2-up-creates-config-space.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-11-25T03:57:01+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: under stealth up --no-fetch still pushed (phase 2)

d97afe310: with creation gone, tests show up --no-fetch (quiet, with and without fr-config) and stealth up leave every ref on origin and the tracking repo unchanged.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-11-25T03:57:01+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: the moved allowlist could unlock itself through an old .fr/** glob (phase 2)

6a01ea762 and 32a23dab0: no allowlist exempts either allowlist file or the .fr-isolation marker; names compared ASCII-folded, empty/./.. segments refused, file identity (dev+inode) compared, non-ASCII names at the top level or in .fr fail closed; identical in both engines, tested through the real hooks and bun.

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-11-25T03:57:01+00:00 phase=2 state=fixed resolves=p2-r6 -->
### p2-r6-resolved · finding [fixed] · resolves p2-r6: the bash/TS parity drift test pinned only the switch location strings, not the decision logic (phase 2)

f4a29583a: tests/fixtures/isolation-decision-cases.json drives both the bash library (pytest) and marker.ts (bun); a one-sided logic mutation failed one suite each way.

<!-- fr:journal kind=finding scope=plan id=p2-r7-resolved created=2026-11-25T03:57:01+00:00 phase=2 state=fixed resolves=p2-r7 -->
### p2-r7-resolved · finding [fixed] · resolves p2-r7: later changes to fr-config were direct pushes, not the pull request spec §B requires (phase 2)

8b7a28a57 and aa5c5c255: a change to an existing configuration branch commits on fr-config-change/<slug>, pushes it and opens a PR through the forge client (stealth: the tracking repo), honouring git.pr ask as fr pr create does; spec R6/§B amended (decision q-legacy-sync-after-pr).

<!-- fr:journal kind=finding scope=plan id=p2-config-writes-not-prs-resolved created=2026-11-25T03:57:01+00:00 phase=2 state=fixed resolves=p2-config-writes-not-prs -->
### p2-config-writes-not-prs-resolved · finding [fixed] · resolves p2-config-writes-not-prs: write_settings pushes the configuration branch directly; spec §B wants a pull request for every change after creation (phase 2)

Answered by p2-r7's fix: decision p2-config-changes-by-pr, commits 8b7a28a57 and aa5c5c255.

<!-- fr:journal kind=decision scope=plan id=p3-protected-means-pr-and-no-rewrite created=2026-11-25T04:52:07+00:00 phase=3 -->
### p3-protected-means-pr-and-no-rewrite · decision · Enforced means pull_request, non_fast_forward and deletion rules on the exact branch (phase 3)

`fr.config.protection.branch_protection` reads `GET repos/<repo>/rules/branches/<b>` (the
branch's effective rules, `GhClient.branch_rules`) and answers `Enforced` only when the
list holds a `pull_request`, a `non_fast_forward` and a `deletion` rule: a force-push or a
deletion would replace or remove what was reviewed (orchestrator brief). The free-plan 403
(`FREE_PLAN_RULESETS_NOTICE`, recognised through `ForgeError` wrapping too), an `HTTP 404`,
`[]`, a partial list, an unparseable reply and a forge whose adapter raises
`UnsupportedForgeOperation` (GitLab, Gitea) or has no `branch_rules` are `NotEnforced(reason)`.
Every other failure (5xx, 401, a non-plan 403, network, a host gh is not logged into) is
`ProtectionReadError`, never cached, and refuses. Under quiet the target is `fr-config` on
origin's slug (a non-forge origin is not enforced); under stealth `<branch>-config` on the
tracking repo (a local tracking path is not enforced). Fixtures: `tests/fixtures/github_rest/rules/`
(captured 2026-11-25; the one third-party reply redacted, said in its README).

<!-- fr:journal kind=decision scope=plan id=p3-cache-by-forge-identity created=2026-11-25T04:52:07+00:00 phase=3 -->
### p3-cache-by-forge-identity · decision · The protection cache is keyed by forge identity and host, and cleared per command and per collect (phase 3)

Orchestrator note from an automated security review: a cache keyed on `(repo, branch)` let
one forge's answer stand for another's (a GitHub Enterprise host and github.com, or a glab
client, with the same slug), a fail-open. `_CACHE` is keyed `(adapter class[:backend],
host, repo.lower(), branch)`, seeing through triage's `ClientForge`; it lives in memory only,
`fr.cli.main` clears it at every command's start and `collect_into` at every collect (so
every driver pass), and tests clear it per test. Test:
`test_two_forges_with_the_same_slug_get_their_own_answers`.

<!-- fr:journal kind=decision scope=plan id=p3-guarded-triage-keys created=2026-11-25T04:52:07+00:00 phase=3 -->
### p3-guarded-triage-keys · decision · The guarded triage keys are post_merge, version, mirrors, pr_authors, queue, exit and export (phase 3)

`GUARDED_TRIAGE_KEYS` are the `.fr/triage.yaml` keys that run a command (`post_merge`, the
`version` set/relock commands, `mirrors`) or decide whose PRs are trusted or how they merge
(`pr_authors`, the merge `queue`, the `exit` gate remap, the `export` PR the driver lands).
Each one's absence is the safe default (no command, the viewer only, no queue so nothing
lands, the strategies' own gates, no export). `merge_method`, `defaults.launch`,
`post_merge_restart` and the thresholds stay readable from an unprotected branch. Readers:
collect's `read_config_lenient` drops them from an unprotected `fr-config` (said once per
repo and reason) and refuses that repo on a failed protection read; `verification.rows.load_remap`
ignores `exit:` with the reason; the driver's freshness check reads the configuration
branch and leaves the guarded keys out of the comparison when collect dropped them.

<!-- fr:journal kind=decision scope=plan id=p3-executors-guarded created=2026-11-25T04:52:07+00:00 phase=3 -->
### p3-executors-guarded · decision · Where each executor asks (phase 3)

`fr verification walk`: `run_walk` asks before `_contract` when the install or scenario program
is a `.fr/` path (and again wherever a program is resolved into the space), and runs it from the configuration space (`effective.install_path`, also used
by `install_problem`); `run_walk(forge=...)` takes the client. The driver: `_post_merge`
returns `post_merge held: <reason>` before running; `_queue_refusal` holds a repo whose config declares a `queue:`
(`queue-held`) right after the forge refusal, before the base rules, covering gate_checks,
the version commands and post_merge; `queue_exec.required_names` refuses gate_checks after
reading them. `fr ops`: `load_ops_config` refuses a present `.fr/ops.yaml`; the ops gate's
`queue_configured` refuses a `queue:` it would release to. Under repo none asks.

<!-- fr:journal kind=decision scope=plan id=p3-sync-without-expect-only-when-protected created=2026-11-25T04:52:07+00:00 phase=3 -->
### p3-sync-without-expect-only-when-protected · decision · Only fr settings sync gains a no-confirmation path; readers never auto-sync (phase 3)

Discovery p2-phase3-sync-needs-protection. `fr settings sync --yes` without `--expect` now
writes the old copy from the configuration branch's tip when `require_protected` passes
for `fr-config` (stealth: `<branch>-config`), printing that it did; otherwise it refuses,
naming the reason and the preview plus `--yes --expect <tip>` (exit 2, nothing written).
Readers still refuse while the copies differ and write nothing: a configuration read must
not have side effects (`fr.config.space.config_space`) or push from a hook's context, and
this keeps the hooks unchanged (they keep naming `fr settings sync`). The smaller change.

<!-- fr:journal kind=finding scope=plan id=p3-stealth-protection-from-product-forge created=2026-11-25T04:52:07+00:00 phase=3 state=fixed review_scope=in -->
### p3-stealth-protection-from-product-forge · finding [fixed] (reviewer: in scope) · Under stealth the driver asked the product repo's client for the tracking repo's protection (phase 3)

Automated security review (orchestrator). `refusal_at(checkout.path, self.client(facts,
repo), ...)` in the driver's post_merge and merge-queue guards passed the product repo's
client, but under stealth the configuration branch lives in the tracking repo, possibly on
another forge, so the answer could come from the wrong forge's rules. Fixed in 1dd0cf180:
`protection_of` never asks a given client under stealth and builds the tracking repo's
own (`_default_client`); a given client is used only under quiet, where `fr-config` is on
the product's origin. Test:
`test_under_stealth_the_tracking_repos_forge_answers_never_the_given_client`.

<!-- fr:journal kind=finding scope=plan id=p3-walk-scenario-program-unguarded created=2026-11-25T04:52:07+00:00 phase=3 state=fixed review_scope=in -->
### p3-walk-scenario-program-unguarded · finding [fixed] (reviewer: in scope) · The walk guarded only install[0], yet resolved any template program into the configuration space (phase 3)

Automated security review (orchestrator). `render_template` sent every repo-relative
argv[0] that `in_space` names (a scenario template's program too) to the configuration
space, while `_protected` checked only `manifest.install[0]`. Fixed in 1dd0cf180: the
up-front check covers the install and scenario templates' programs (before the install
runs), and `_program`, where the path is resolved, asks `require_protected` for any
program in the space, so no caller reaches it unguarded. Test:
`test_a_scenario_program_in_the_configuration_space_is_refused_before_anything_runs`.

<!-- fr:journal kind=discovery scope=plan id=p3-rules-hide-bypass-actors created=2026-11-25T04:52:07+00:00 phase=3 -->
### p3-rules-hide-bypass-actors · discovery · rules/branches does not say who may bypass the rule (phase 3)

The effective-rules route lists rule types, not a ruleset's bypass actors or enforcement
exemptions, so a ruleset requiring pull requests that lets an admin or an app bypass it
still reads as `Enforced`. Reading `rulesets/<id>` for `bypass_actors` needs admin on a
repo ruleset and is not readable for org rulesets with a plain token; left out of S1.

<!-- fr:journal kind=discovery scope=plan id=p3-docs-owed-p7 created=2026-11-25T04:52:07+00:00 phase=3 -->
### p3-docs-owed-p7 · discovery · The pages describing quiet, walk, ops and triage config owe the protection rule (phase 3)

This phase changed paths covered by `docs/verification-strategies.md`, `docs/ops.md`,
the triage and isolation explainers and `docs/reference/`; the protection rule and its
fix line belong in them with phase 7's page update (as p1-docs-stale-owed-p7).

<!-- fr:journal kind=lens scope=plan id=lens-security-2 created=2026-11-25T04:52:07+00:00 phase=3 lens=security step=implement-phase -->
### lens-security-2 · lens · a trust boundary: which configuration-branch keys run commands or decide merges, and the forge-protection read that gates them (phase 3)

<!-- fr:journal kind=lens scope=plan id=lens-errors-2 created=2026-11-25T04:52:07+00:00 phase=3 lens=errors step=implement-phase -->
### lens-errors-2 · lens · new forge reads whose failure must refuse, never read as unprotected or protected (phase 3)

<!-- fr:journal kind=finding scope=plan id=sec-1-self-attesting-config-branch-resolved created=2026-11-25T04:52:07+00:00 phase=3 state=fixed resolves=sec-1-self-attesting-config-branch -->
### sec-1-self-attesting-config-branch-resolved · finding [fixed] · resolves sec-1-self-attesting-config-branch: A self-declared fr-config branch must not supply executable or trust keys unless its protection is enforced (phase 3)

Fixed in a8d58494e (the protection read) and a7355fac8 (the guards). Every reader that takes
executable or trust keys from a configuration branch asks first: collect's
`read_config_lenient` (forge side) drops `GUARDED_TRIAGE_KEYS` (post_merge, version,
mirrors, pr_authors, queue, exit, export) from an fr-config without an enforced
pull-request rule, saying the reason once, and refuses that repo when the read fails;
the local executors (walk, driver post_merge, the queue and its gate_checks, ops, the ops
gate, the exit remap) refuse or ignore with the reason. Tests:
`test_forge_side_triage_config_follows_the_quiet_switch` (flipped: no post_merge, no
pr_authors), `..._from_a_protected_fr_config_supplies_every_key`,
`..._refuses_when_the_protection_read_fails`, and `tests/unit/test_config_protection_executors.py`.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-25T04:52:07+00:00 phase=3 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: triage collect's read_config_lenient takes post_merge, version commands and pr_authors from a self-declared unprotected fr-config; phase 3's guard must cover trust keys and the forge-side reader, and flip test_forge_side_triage_config_follows_the_quiet_switch (phase 3)

Same fix as sec-1-self-attesting-config-branch: `read_config_lenient` no longer takes
post_merge, the version commands or pr_authors from a self-declared unprotected
fr-config; `test_forge_side_triage_config_follows_the_quiet_switch` is flipped and a
protected-branch test supplies them (a7355fac8).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-11-25T04:52:07+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

the rules route was folded into GhClient.branch_rules while writing GREEN: RealGhRestClient.required_check_names and base_rules now read it there, so the one rules read has no second copy left to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-11-25T04:52:07+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

every executor calls the one guard (require_protected, or refusal_at over it) and every reader of .fr/triage.yaml drops the same GUARDED_TRIAGE_KEYS through without_guarded; there was no per-executor copy of the rule left to fold

<!-- fr:journal kind=decision scope=plan id=p3-guarded-ci-keys created=2026-11-25T05:17:31+00:00 phase=3 -->
### p3-guarded-ci-keys · decision · ci.yaml's gate_checks, tests and fast_tier are guarded keys, ignored when unprotected (extends p3-guarded-triage-keys) (phase 3)

Review p3-r1 (orchestrator decision). Under quiet and stealth, `.fr/ci.yaml`'s `gate_checks` (chooses what CI must prove), `tests` (relaxes deliver's suite evidence to CI) and `fast_tier` (a command fr puts into an executor's brief) are trust/executable configuration, `fr.run.ci_evidence.GUARDED_CI_KEYS`, beside `GUARDED_TRIAGE_KEYS`. `ci_evidence._at_tip` is the one choke point every ci.yaml read under a configuration space passes (load_gate_checks, declared_tests_mode, declared_fast_tier, declared_gates): when the file sets any of the three it asks `protection_of`; not enforced reads the file as absent and says once (stderr, per product checkout and reason) that a local full-suite log is owed at deliver, no fast_tier reaches a brief, and the base's required checks are the gate set (verify_ci, settle and the PR body already fall back to them); a failed protection read refuses (CiEvidenceRefused, so the brief exits 2). A file setting none of them asks nothing. Under repo nothing changes. The merge queue's `required_names` keeps refusing (not ignoring) an unprotected gate_checks, as before. Spec R7 says so in one sentence.

<!-- fr:journal kind=decision scope=plan id=p3-enforced-needs-approval created=2026-11-25T05:17:44+00:00 phase=3 -->
### p3-enforced-needs-approval · decision · Enforced also needs a pull-request rule with at least one approving review; fr says it cannot see bypass actors (amends p3-protected-means-pr-and-no-rewrite) (phase 3)

Review p3-r3 (orchestrator decision). `protection._judge` answers Enforced only when, beside pull_request, non_fast_forward and deletion, at least one returned pull_request rule has an integer `required_approving_review_count >= 1` (every rule GitHub returns applies, so one suffices; a missing, non-integer, boolean or negative count is none: 'the pull-request rule requires no approving review'). Fixtures: the new capture `pull-request-approved.json` (1 approval, redacted) is the positive case; `pull-request.json` (0) is now a negative. The limit of p3-rules-hide-bypass-actors is stated, not solved: `protection.BYPASS_LIMIT` ('fr reads the branch's rules and cannot see bypass actors, so keep the ruleset's bypass list empty') is in every fix text (so every not-enforced refusal and ignored line), in `fr settings sync --yes`'s claim (now 'the forge's rules ... require an approved pull request and block force-pushes and deletion (...)' instead of 'forge-protected'), in spec §C and in docs/verification-strategies.md's install-contract section; the remaining pages stay owed to phase 7 (p3-docs-owed-p7). Review p3-r5 rides with it: an empty rules reply says 'no ruleset on this branch (classic branch protection is not read; protect it with a ruleset)'.

<!-- fr:journal kind=decision scope=plan id=p3-run-the-checked-tip created=2026-11-25T05:25:36+00:00 phase=3 -->
### p3-run-the-checked-tip · decision · A guarded executor runs exactly the fetched, reviewed tip of the configuration branch (phase 3)

Review p3-r2, p3-r4 (orchestrator decision). `fr.config.protection.require_checked_tip(space, client, what, *, working_tree, no_fetch=False, command=None)`: under repo nothing; else `require_protected`, then `fetch_tip` (`git fetch origin +refs/heads/<config branch>:refs/remotes/origin/<config branch>` in the product clone under quiet, in the configuration clone under stealth; once per command, cleared by `forget()`; a failed fetch refuses `UncheckedTipError`, a ProtectionError, naming `<command> --no-fetch` only for a command that has one; `no_fetch=True` skips it and says the tip may be stale), then with `working_tree=True` the configuration checkout (quiet fr-config worktree, stealth configuration clone) must exist, be clean (`status --porcelain --untracked-files=all --ignored=matching`) and have HEAD at the fetched tip; otherwise one refusal names every difference (the dirty paths, N commits ahead, N behind) and its remedy (move the edit to a pull request and stash it; open a PR then `reset --keep`; `merge --ff-only`). Behind refuses too, as decided: fr does not fast-forward on the operator's behalf here (`fr isolation up` still fast-forwards a clean worktree). Wired: the walk's `_protected` and per-program `_program` (re-checked when each program runs), `ops.load._protected` (load_ops_config), `verification.rows` load_remap (`refusal_at(..., working_tree=True)`, still lenient: the remap is ignored with the reason). Blob readers fetch and read the fetched tip: the merge queue's `queue_exec.required_names` (`working_tree=False`) and the ops gate's `queue_configured` (`fetch_tip`, protection still asked only when `queue:` is present). Unchanged, and why: the driver's `post_merge` and queue-wide refusal run commands from the forge-collected facts (read through the forge API at the configuration branch, i.e. origin's tip, then checked fresh against the pass's fetch), so no local checkout is run; `ci_evidence._at_tip` (p3-guarded-ci-keys) reads the last-fetched remote-tracking ref, which only origin writes, so at worst a stale reviewed tip, never unreviewed content. Tests: `tests/unit/test_config_protection_executors.py` (dirty, untracked, ahead, behind, failed fetch, --no-fetch, clean run, ops, exit remap, stealth clone); test helpers now commit the executable bit on fr-config and build a real fr-config worktree.

<!-- fr:journal kind=finding scope=plan id=p5-exec-manifests-guard created=2026-11-25T05:25:38+00:00 phase=5 state=open review_scope=in -->
### p5-exec-manifests-guard · finding [open] (reviewer: in scope) · workflow kind:cli run: and verification install/scenario argv become configuration-branch executables once phase 5 moves them into .fr/; they must pass require_protected (whole argv, not only a .fr/ argv[0]) (phase 5)

Carried from phase 3's adversarial review (p3-r6, out of phase 3's scope). Once phase 5 moves workflow manifests and verification strategies into the configuration space, two command surfaces read from it: a workflow step's `kind: cli` `run:` argv, executed by `fr run advance` (packages/fr/src/fr/commands/run_cmd.py ~6633-6649), and a strategy manifest's `install`/`scenario` argv, rendered and run by the walk (packages/fr/src/fr/verification/walk.py ~378-393, `_protected`/`_program`, which today guard only an argv[0] inside `.fr/`). A manifest read from the configuration branch makes the WHOLE argv executable configuration (`sh -c ...` or any PATH program with attacker-chosen arguments), so under quiet and stealth both must pass `require_protected` / `require_checked_tip` (p3-run-the-checked-tip) on the manifest's source whenever it is the configuration space, not only when argv[0] is a `.fr/` path.

<!-- fr:journal kind=decision scope=plan id=p3-execute-the-exported-tip created=2026-11-25T05:35:10+00:00 phase=3 -->
### p3-execute-the-exported-tip · decision · A guarded program runs from the fetched tip exported to a private directory; guarded files are read at that tip; fetches come only from the repository whose rules were read (amends p3-run-the-checked-tip) (phase 3)

Security review of p3-run-the-checked-tip (orchestrator decision). `git status` can be blinded (assume-unchanged, skip-worktree, core.fileMode=false), so the clean/at-tip check of the configuration checkout proved nothing and is DROPPED, not kept as a warning: the checkout's state no longer matters for anything fr runs or trusts. (1) `fr.config.tip.export_checked(space, client, what)`: require_protected, fetch_tip, then `git archive <fetched tip sha> -- <space.prefix>` extracted (tarfile filter=data, file modes kept) into a fresh `mkdtemp` directory chmod 0700, cached per (repo, sha, prefix), removed by `protection.forget()` and at exit; one stderr line names the tip sha it runs. The walk's `_program` runs a configuration-space argv[0] from there (asked once before anything runs, again per program); under repo the working tree runs as before. (2) `protection.read_checked(space, client, name, what, guarded=...)`: fetch_tip, `at_default` (the fetched tip), require_protected when the text holds something guarded; used by load_ops_config, load_remap (still lenient: ignored with the reason), the merge queue's required_names and the ops gate's queue_configured. ops and the remap skip the fetch only when neither the last fetched tip nor the checkout has the file. (3) `fetch_tip` first runs `_check_origin`: under quiet the product clone's origin owner/repo must equal `_target`'s; under stealth the configuration clone's origin must be the tracking repo (same URL via stealth._same_repo, or same host and owner/repo); otherwise UncheckedTipError naming both and `git remote set-url`; a target no forge protects refuses with the protection fix text before any fetch. `require_checked_tip` and `refusal_at(working_tree=)` are removed. Tests: tests/unit/test_config_protection_executors.py (assume-unchanged edit runs the tip, local commit ahead runs the tip, a merged change is fetched and run, export mode 0700 and exec bit kept and removed, failed fetch, --no-fetch, quiet origin mismatch, stealth tip read, stealth clone origin pointing elsewhere refused, ops and exit remap read at the tip).

<!-- fr:journal kind=review scope=plan id=review-p3 created=2026-11-25T05:51:10+00:00 phase=3 -->
### review-p3 · review · Phase 3 adversarial review (forge protection for executable and trust configuration) (phase 3)

Independent adversarial reviewer read d454de2..HEAD against §C and R7. No fail-open in
protection.py (_classify, _judge, _ask); cache key and lifetime sound; fixtures match the parser and
the third-party capture is redacted; mutation checks of the ops, walk, exit-remap and collect guards
each turned a test red. Five in-scope findings, all fixed in 3d2aa2939..86efa719d (plus two automated
security-review points: index-flag-blind status check replaced by executing an exported tip, and the
stealth fetch source verified against the repo whose rules were read). One out-of-scope finding carried
to phase 5 as p5-exec-manifests-guard. Selection 5499 passed / 17 skipped; ruff, mypy clean.

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-11-25T05:51:10+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · deliver's CI evidence took gate_checks/tests:ci and the fast_tier command from the configuration branch with no require_protected (phase 3)

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-11-25T05:51:10+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · protection was asked of origin's branch while walk/ops/exit-remap ran the local, agent-editable config checkout (phase 3)

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-11-25T05:51:10+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · Enforced accepted a pull_request rule with 0 required approvals, and invisible bypass actors were never stated (phase 3)

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-11-25T05:51:10+00:00 phase=3 state=open review_scope=in -->
### p3-r4 · finding [open] (reviewer: in scope) · guarded reads used the last-fetched remote-tracking config ref, so unreviewed pre-protection content passed (phase 3)

<!-- fr:journal kind=finding scope=plan id=p3-r5 created=2026-11-25T05:51:10+00:00 phase=3 state=open review_scope=in -->
### p3-r5 · finding [open] (reviewer: in scope) · classic branch protection read as no rules with ruleset-only fix text (phase 3)

<!-- fr:journal kind=finding scope=plan id=p3-r6 created=2026-11-25T05:51:10+00:00 phase=3 state=open review_scope=out -->
### p3-r6 · finding [open] (reviewer: out of scope) · workflow kind:cli run: and verification argv become configuration-branch executables once phase 5 moves them into .fr/ (phase 3)

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-11-25T05:51:10+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: deliver's CI evidence took gate_checks/tests:ci and the fast_tier command from the configuration branch with no require_protected (phase 3)

db7c9aca1: ci_evidence._at_tip is the single quiet/stealth reader of .fr/ci.yaml; a file setting gate_checks, tests or fast_tier needs an enforced configuration branch, else it reads as absent with the reason (deliver owes a local full-suite log, no fast_tier in any brief); a failed protection read refuses; spec R7 names the keys (decision p3-guarded-ci-keys).

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-11-25T05:51:10+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: protection was asked of origin's branch while walk/ops/exit-remap ran the local, agent-editable config checkout (phase 3)

e8f31dc78 and 86efa719d: guarded executors run the fetched tip's .fr/ exported by git archive into a private 0700 dir (fr.config.tip.export_checked), and guarded files are read at the fetched tip (protection.read_checked); the local checkout's state no longer matters, an assume-unchanged edit runs the tip's content (decision p3-execute-the-exported-tip).

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-11-25T05:51:10+00:00 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: Enforced accepted a pull_request rule with 0 required approvals, and invisible bypass actors were never stated (phase 3)

3d2aa2939: enforced needs a pull_request rule with required_approving_review_count >= 1 (new captured, redacted positive fixture; the 0-approval capture is a negative); every fix text, fr settings sync, spec §C and docs/verification-strategies.md say fr cannot see bypass actors and the operator must keep the bypass list empty (decision p3-enforced-needs-approval).

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-11-25T05:51:10+00:00 phase=3 state=fixed resolves=p3-r4 -->
### p3-r4-resolved · finding [fixed] · resolves p3-r4: guarded reads used the last-fetched remote-tracking config ref, so unreviewed pre-protection content passed (phase 3)

e8f31dc78 and 86efa719d: guarded paths fetch the configuration branch first, from the repository whose rules were read (origin slug verified under quiet, tracking repo under stealth, mismatch refuses); a failed fetch refuses and --no-fetch says the tip may be stale.

<!-- fr:journal kind=finding scope=plan id=p3-r5-resolved created=2026-11-25T05:51:10+00:00 phase=3 state=fixed resolves=p3-r5 -->
### p3-r5-resolved · finding [fixed] · resolves p3-r5: classic branch protection read as no rules with ruleset-only fix text (phase 3)

a89d4a781: an empty rules reply says no ruleset on this branch, that classic branch protection is not read, and to protect it with a ruleset.

<!-- fr:journal kind=finding scope=plan id=p3-r6-resolved created=2026-11-25T05:51:10+00:00 phase=3 state=open resolves=p3-r6 out_of_scope=true -->
### p3-r6-resolved · finding [out-of-scope] · resolves p3-r6: workflow kind:cli run: and verification argv become configuration-branch executables once phase 5 moves them into .fr/ (phase 3)

Today workflows and verification manifests still resolve from the product checkout, so phase 3 does not cause it; it becomes real when phase 5 moves them into .fr/, and is carried as the open in-scope phase-5 finding p5-exec-manifests-guard.
