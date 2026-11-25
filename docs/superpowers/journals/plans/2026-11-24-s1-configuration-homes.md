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

<!-- fr:journal kind=decision scope=plan id=p4-cross-space-cases created=2026-11-25T07:02:51+00:00 phase=4 -->
### p4-cross-space-cases · decision · A cross-space hop creates the configuration branch with every pending file, else removes a file already there, else opens a pull request and keeps the product file (phase 4)

fr/config/migrate.py move_across (spec R10, R11; carried discovery p2-phase4-migration-creates-config).
1. No `fr-config` / `<branch>-config` yet: the hop CREATES it as one orphan commit holding the
   settings (the old switch's bytes, R6; the legacy copy stays as it is) and every file the
   migration would move there (`pending_files`: the R9 kinds at their old paths, quiet's R11
   `.fr/` files, a profiles file only when already at version 2, at 3), pushed plainly before
   any product file is removed; a refused push removes nothing (quiet.create_config_branch /
   stealth.create_config_branch). Only clean tracked files ride along, so an uncommitted edit
   is never pushed.
2. The branch holds the file with the same bytes: the product file is removed (in the
   product's one `chore(fr): migrate` commit). Other bytes: R12's refusal, naming both.
3. The branch exists without the file: fr opens a pull request (`fr.config.change.open_change`,
   honouring git.pr) and refuses that artifact naming the URL; the product file stays until the
   change merges and the migration runs again. A foreign branch is refused
   (quiet._check_config_refs / stealth.check_config_branch) before anything is written.
`settings-location` 1 -> 2 runs the same creation from the old switch (via the runner's
MIGRATING_ROOT, since its file sits in the `fr` worktree); a branch already holding identical
settings reads as migrated (the old file is R6's legacy copy, not R12's second file).

<!-- fr:journal kind=decision scope=plan id=p4-config-kinds-model created=2026-11-25T07:02:51+00:00 phase=4 -->
### p4-config-kinds-model · decision · Moved kinds are location-stamped; R12 lets a destination holding the expected bytes finish the move (phase 4)

`ArtifactKind.locators` (oldest first) and `roots(repo_root, index)` say where each locator is
globbed (the newest one in the configuration space); `location_stamp` reads the newest matching
locator, `no_stamp_write` is the no-op writer. A relocating `SchemaMigration` names its
`destination` up front (so R12 and the uncommitted veto are checked at plan time) and may set
`expected` bytes (profiles 2 -> 3 writes its stamp). A destination that exists with exactly the
expected bytes is a move that already happened (a crash, or the branch created carrying it), so
it is finished, not refused. `quiet-config` is stamped by checkout (HEAD `fr-config`: 2) since
both ends are `.fr/<file>`. A hop that leaves its file untouched (`settings-location`) stages
nothing (`PlannedAction.untouched`).

<!-- fr:journal kind=decision scope=plan id=p4-profiles-refuse-whole-file created=2026-11-25T07:02:51+00:00 phase=4 -->
### p4-profiles-refuse-whole-file · decision · Under quiet/stealth the profile declarations are read from the protected tip or refused whole (phase 4)

Review p4-sec-profiles. `.fr/profiles.yaml` decides secrets env-files, mounts, `ops: true` and the
forge/CI/tracking services fr trusts; no subset is safe to take from an unreviewed branch, so
`profiles_config` reads it with `protection.read_checked` (require_protected at the fetched tip)
and an unprotected branch refuses the whole file. Under repo, and for the old product path
(R13), nothing changes.

<!-- fr:journal kind=decision scope=plan id=p4-scaffold-declaration-path created=2026-11-25T07:02:51+00:00 phase=4 -->
### p4-scaffold-declaration-path · decision · fr init scaffold writes .fr/profiles.yaml at 3, the old path at 2 while only that exists, and refuses under quiet/stealth once the branch holds it (phase 4)

§E's quiet/stealth pull request for the declaration is not built (no phase of this plan names it):
under quiet/stealth scaffold keeps writing the product's old `.devcontainer/fr-profiles.yaml` at
version 2 while the configuration branch has no declarations (the migration carries it), and
refuses once it has them, naming the pull request path. `fr repair` and `fr migrate v1-to-v2`
likewise leave a plan-config that lives on the configuration branch alone (repairable_plan_config).

<!-- fr:journal kind=decision scope=plan id=p4-owed-key created=2026-11-25T07:02:51+00:00 phase=4 -->
### p4-owed-key · decision · s1-refuse-old-paths carries owed_key issue:derio-net/super-fr#1653 (phase 4)

The plan's `fr journal add` command lacked the `owed_key:` body line every owed entry needs; the
entry is filed under #1653 at deliver, so its key is that issue (no Test Plan step or row owes
the refusal itself).

<!-- fr:journal kind=discovery scope=plan id=p4-messages-name-old-paths created=2026-11-25T07:02:51+00:00 phase=4 -->
### p4-messages-name-old-paths · discovery · User-facing messages and docstrings still name .devcontainer/fr-profiles.yaml and docs/superpowers/plan-config.yaml (phase 7) (phase 4)

acceptance/ci.py, acceptance/local.py, services/resolve.py, services/require.py, run/closeout.py,
_hosts.py, hostclient.py, commands/acceptance_cmd.py and the skills name the old declaration path
in refusals; tests assert some of them. The readers use the new path; the words are phase 7's
(spec §H) together with the pages.

<!-- fr:journal kind=discovery scope=plan id=p4-stealth-product-deletion created=2026-11-25T07:02:51+00:00 phase=4 -->
### p4-stealth-product-deletion · discovery · Under stealth the product's migrate commit deletes paths stealth.FR_OWNED_PATHS lists (phase 4)

A stealth target holding an old-path file (docs/superpowers/models.yaml, .devcontainer/fr-profiles.yaml)
gets a product commit deleting it; the stealth push guard refuses any commit touching an fr-owned
prefix, so `fr push` may refuse that deletion. A stealth target should carry no such file (R24),
so this is rare; not changed here.

<!-- fr:journal kind=finding scope=plan id=p4-stealth-coverage-one-kind created=2026-11-25T07:02:51+00:00 phase=4 state=open review_scope=in -->
### p4-stealth-coverage-one-kind · finding [open] (reviewer: in scope) · P4.T2.S1's stealth leg is covered for one kind (models-config), not per kind (phase 4)

tests/unit/test_migration_config_kinds.py runs every R9 kind under repo and quiet, and under
stealth only models-config (the cross-space path is kind-generic: StealthWriter + move_across).
Parametrizing the stealth test over FILES is the fix if the reviewer wants each kind walked.

<!-- fr:journal kind=discovery scope=plan id=p4-import-cycle created=2026-11-25T07:02:51+00:00 phase=4 -->
### p4-import-cycle · discovery · config_migration imported fr.settings at module level, an import cycle through fr.isolation.types (phase 4)

Collecting tests/unit/test_ops_profile.py (fr.isolation.scaffold first) failed with a partially
initialised fr.isolation.types; fixed in 3293ec854 by importing SettingsError late.

<!-- fr:journal kind=finding scope=plan id=p4-sec-symlink created=2026-11-25T07:02:51+00:00 phase=4 state=fixed review_scope=in -->
### p4-sec-symlink · finding [fixed] (reviewer: in scope) · A cross-space hop read old paths from the working tree, so a symlink to ~/.ssh/... was pushed onto the configuration branch (phase 4)

Self-raised from the automated security review of the committed phase-4 code (HIGH). Fixed in
3f11fc9cc: `refuse_link` refuses a symlink at the path or any directory between, and a path
resolving outside the checkout; `source_text` pushes a tracked file's committed blob and refuses
an uncommitted edit; pending_files refuses the whole creation on a symlink. relocate_file
refuses a symlinked source too. Tests: test_under_quiet_a_symlinked_old_path_is_refused_and_nothing_is_pushed,
test_a_symlink_among_the_pending_files_refuses_the_creation,
test_a_cross_space_hop_pushes_the_committed_bytes_and_refuses_a_dirty_file.

<!-- fr:journal kind=finding scope=plan id=p4-sec-profiles created=2026-11-25T07:02:51+00:00 phase=4 state=fixed review_scope=in -->
### p4-sec-profiles · finding [fixed] (reviewer: in scope) · profiles_config read .fr/profiles.yaml from the quiet/stealth configuration checkout unguarded (phase 4)

Self-raised from the security review (MEDIUM). Fixed in 3f11fc9cc (decision
p4-profiles-refuse-whole-file). Test: test_quiet_profile_declarations_are_read_through_the_protection_guard.

<!-- fr:journal kind=finding scope=plan id=p4-sec-manifest-tip created=2026-11-25T07:02:51+00:00 phase=4 state=fixed review_scope=in -->
### p4-sec-manifest-tip · finding [fixed] (reviewer: in scope) · resolve_workflow checked the branch's protection and then read the working-tree manifest (phase 4)

Self-raised from the security review (MEDIUM). Fixed in 3f11fc9cc: `fr.config.space.read_checked_bytes`
reads a workflow manifest, a verification strategy (resolve_strategy and strategy_identity) and the
profile declarations from `protection.read_checked` at the fetched tip whenever they sit in a
quiet/stealth configuration space; under repo and at R13's product path, the file as it is.
Test: test_a_quiet_manifest_is_read_from_the_checked_tip_not_the_working_tree.

<!-- fr:journal kind=finding scope=plan id=p5-exec-manifests-guard-resolved created=2026-11-25T07:02:51+00:00 phase=4 state=fixed resolves=p5-exec-manifests-guard -->
### p5-exec-manifests-guard-resolved · finding [fixed] · resolves p5-exec-manifests-guard: workflow kind:cli run: and verification install/scenario argv become configuration-branch executables once phase 5 moves them into .fr/; they must pass require_protected (whole argv, not only a .fr/ argv[0]) (phase 4)

Closed in phase 4 (3f11fc9cc). The guard is at the manifest, not at argv[0]: a workflow
manifest or verification strategy resolved from a quiet/stealth configuration space is read
only from the protected branch's fetched, reviewed tip (`read_checked_bytes` ->
`protection.read_checked`, which runs `require_protected`), so every `kind: cli` `run:` argv
`fr run advance` executes and every `install`/`scenario` argv the walk renders comes from a
reviewed, protected manifest as a whole; an unprotected branch refuses the whole manifest.
Under repo nothing changes.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t1 created=2026-11-25T07:02:51+00:00 phase=4 -->
### no-refactor-p4-t1 · discovery · no-refactor-because P4.T1 (phase 4)

the relocation is one runner path (_relocate) and one disk helper (relocate_file) shared by every relocating hop; R12's check is one function (both_paths_refusal) used at plan and apply time, so there was nothing duplicated to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t2 created=2026-11-25T07:02:51+00:00 phase=4 -->
### no-refactor-p4-t2 · discovery · no-refactor-because P4.T2 (phase 4)

every moved kind is generated from the one MOVED table in fr.config.migrate (registry entries and hops alike), and every reader resolves through fr.config.space.located, so no per-kind copy was left to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t3 created=2026-11-25T07:02:51+00:00 phase=4 -->
### no-refactor-p4-t3 · discovery · no-refactor-because P4.T3 (phase 4)

legacy() is one function behind located(); the owed entry is a journal write, so there was no code to clean

<!-- fr:journal kind=decision scope=plan id=p4-verify-before-unlink created=2026-11-25T07:20:16+00:00 phase=4 -->
### p4-verify-before-unlink · decision · A cross-space move unlinks only after the fetched configuration tip holds the exact bytes (p4-r1) (phase 4)

move_across re-fetches after create/ensure and reads the blob at the configuration branch's fetched tip: absent proposes (case 3), other bytes are R12, only the same bytes unlink. A stealth create-only push that loses its lease raises BranchRaceError (fr.settings); ensure_space and write_target_settings re-fetch and read what stands. A branch that still does not appear after creation refuses. Tests: tests/unit/test_config_move_verified.py (lost lease, exists() race, untracked old path).

<!-- fr:journal kind=decision scope=plan id=p4-legacy-by-tip created=2026-11-25T07:29:56+00:00 phase=4 -->
### p4-legacy-by-tip · decision · Under quiet/stealth R13's old-path fallback is decided by the configuration branch's fetched tip (p4-r2) (phase 4)

fr.config.space.located: while the configuration branch has a fetched tip (branch_fetched), the product's old path is ignored and one notice names it (R4), so a feature branch adding docs/superpowers/workflows/<x>.yaml cannot shadow the space. Only while no configuration branch exists may an old file be read, and only when its bytes equal the product default branch's committed ones (read_at_default); an uncommitted or feature-branch-only edit is ignored. Executable/trust content from an old path never runs unguarded: read_checked_bytes refuses it (p4-r3 then degrades it to the shipped one). Re-closes p5-exec-manifests-guard for this path. Tests: tests/unit/test_config_legacy_by_tip.py (incl. test_quiet_old_path_shadow).

<!-- fr:journal kind=decision scope=plan id=p4-degraded-not-lockout created=2026-11-25T07:38:12+00:00 phase=4 -->
### p4-degraded-not-lockout · decision · Unprotected workflows, strategies and profiles degrade, never lock out (p4-r3) (phase 4)

Under quiet/stealth the repo's workflow shapes, verification strategies and profiles.yaml are executable/trust configuration (R7 amended). Not enforced: they degrade, never lock out (fr.config.degraded). A repo shape/strategy is ignored and the shipped one used, reason said once (usable_bytes). profiles.yaml keeps schema_version, default, profiles and each profile's purpose; drops and names each profile's secrets and ops, the forge/ci/tracking blocks (type/host overrides decide where credentials go), v1 backend/host and any unknown key (read_profiles). Mounts and post-create/initialize commands live in devcontainer.json in the product (spec §E), not in profiles.yaml, so nothing there to drop. The forge client the protection read builds sees only the degraded profiles (no recursion, and an unprotected forge.host never picks the forge that answers). A failed protection read or tip fetch still refuses an executor (profiles_config strict); fr services (READ_ONLY) passes unknown_ok and shows the degraded view saying 'protection unknown'. R13 old-path executable/trust content degrades the same way. isolation up, services and ops keep working on a free-plan private repo. Tests: tests/unit/test_config_degraded.py (real protection answers: local origin = not enforced, fake forge serving the captured approved ruleset).

<!-- fr:journal kind=decision scope=plan id=p4-v1-profiles-one-move created=2026-11-25T08:03:41+00:00 phase=4 -->
### p4-v1-profiles-one-move · decision · A v1 profiles file moves across spaces in one hop with its final v3 bytes (p4-r4) (phase 4)

Under quiet/stealth the 2->3 relocation builds the pushed bytes in memory from the COMMITTED file (fr.artifacts.profiles_services.services_text, then schema_version: 3; fr.config.migrate.profiles_body). A working tree that differs only by fr's own in-flight 1->2 rewrite (same text, runner's stamp 2) is accepted; any other difference is an operator edit and refuses as uncommitted. pending_files carries a v1 file at v3, so the configuration branch is created with the final bytes. Tests: test_config_profiles_v1_across.py.

<!-- fr:journal kind=decision scope=plan id=p4-config-checkout-by-structure created=2026-11-25T08:03:43+00:00 phase=4 -->
### p4-config-checkout-by-structure · decision · A configuration checkout is told by structure, never by a -config name (p4-r5) (phase 4)

_config_checkout: quiet's fr-config worktree (HEAD refs/heads/fr-config at fr.config.space.quiet_checkout's path) or the migrating product's own quiet/stealth configuration space (MIGRATING_ROOT -> space_root). A product clone named ci-config finishes its profiles crash window in place. Tests: test_config_checkout_by_structure.py, stealth case in test_config_stealth_keeps_product.py.

<!-- fr:journal kind=decision scope=plan id=p4-stealth-keeps-product-file created=2026-11-25T08:03:45+00:00 phase=4 -->
### p4-stealth-keeps-product-file · decision · Under stealth the migration keeps the product file; supersedes discovery p4-stealth-product-deletion (p4-r6) (phase 4)

Relocating hops declare SchemaMigration.keeps (stealth): the file goes to the tracking repo's <branch>-config, the product file stays (a v1 profiles file is restored to its committed bytes after fr's in-flight rewrite), fr prints once 'git -C <product> rm -- <rel>', commit_migration stages nothing for it, and a kept copy whose bytes the configuration branch's fetched tip holds is not owned by its kind (fr.config.migrate.moved_owns/kept_copy), so it never reads as stale. Spec R10 amended. Discovery p4-stealth-product-deletion is superseded. Tests: test_config_stealth_keeps_product.py.

<!-- fr:journal kind=decision scope=plan id=p4-quiet-worktree-current created=2026-11-25T08:03:46+00:00 phase=4 -->
### p4-quiet-worktree-current · decision · A quiet move refuses a dirty or diverged fr-config worktree before any unlink (p4-r7) (phase 4)

QuietWriter.refresh calls fr.placement.quiet.require_current_config_worktree: after the fast-forward, the worktree must be exactly origin/fr-config with nothing uncommitted or untracked; otherwise SettingsError naming the path, the state and the remedy (PR to fr-config, stash -u, or reset --keep). Only the migration writer refuses; other readers keep the silent fast-forward. Tests: test_config_quiet_worktree_state.py.

<!-- fr:journal kind=decision scope=plan id=p4-import-first created=2026-11-25T08:03:48+00:00 phase=4 -->
### p4-import-first · decision · The moved-kinds table is built on first use (p4-r8) (phase 4)

fr.config.migrate.MOVED became all_moved() (cached), so importing fr.config.migrate first no longer runs fr.artifacts' registry against a half-initialised module. test_config_import_first.py imports each S1 module first in a fresh python -I.

<!-- fr:journal kind=decision scope=plan id=p4-repos-sync-config-space created=2026-11-25T08:03:50+00:00 phase=4 -->
### p4-repos-sync-config-space · decision · fr repos sync reads plan-config through the space and proposes under quiet/stealth (p4-r9) (phase 4)

located() decides the file (old path counts as existing); --force under repo writes .fr/plan-config.yaml and removes the old file (never both, R12); under quiet/stealth fr proposes it as a PR via the configuration writer (fr.config.change, git.pr honoured) or prints REFUSED naming fr migrate artifacts --yes when no configuration branch exists; it never writes the configuration checkout. Security follow-up: every read/write/delete of an old-path or config file goes through fr.config.space.link_problem (lstat of each parent, resolved path inside the checkout). Tests: test_repos_sync_config_space.py, test_repos_cmd.py, test_config_symlinked_parents.py.

<!-- fr:journal kind=decision scope=plan id=p4-owed-names-release created=2026-11-25T08:03:52+00:00 phase=4 -->
### p4-owed-names-release · decision · s1-refuse-old-paths names the release, its detection and R16's env vars (p4-r10) (phase 4)

The owed entry's body now says: the first minor release after the one that ships S1, detected by fr's own version against the release carrying S1's fragment, ends old paths, the legacy settings copy and FR_SHIPPED_WORKFLOWS_DIR/VERIFICATIONS_DIR/LENSES_DIR. owed_key unchanged (the orchestrator repoints it at deliver).

<!-- fr:journal kind=decision scope=plan id=p4-change-pr-dedup created=2026-11-25T08:03:54+00:00 phase=4 -->
### p4-change-pr-dedup · decision · Configuration changes are named by kind and never re-proposed every command (p4-r12) (phase 4)

change_branch -> fr-config-change/<kind>-<hash> (kind: the path below .fr/). Before pushing, open_change reads earlier PRs from that head (fr.config.change.prs_for_head): an OPEN one is reused (URL returned, nothing pushed), one CLOSED unmerged refuses with its URL and 'fr migrate artifacts --yes --repropose' (FR_CONFIG_REPROPOSE=1). Security follow-up: an earlier PR counts only when its head is in the target repo (isCrossRepository False, then pr_view), it merges into the configuration branch, and, when open, origin's head holds the path with exactly the bytes; a fork PR with the same head name is ignored. Tests: test_config_change_pr_dedup.py.

<!-- fr:journal kind=decision scope=plan id=p4-tests-added created=2026-11-25T08:03:55+00:00 phase=4 -->
### p4-tests-added · decision · Missing p4 tests added (p4-r11) (phase 4)

Stealth profiles walk (v1->v3, structure check, crash window on the config clone): test_config_stealth_keeps_product.py. Guard wiring through resolve_workflow, resolve_strategy and run_cmd._resolve_manifest_checked_schema (the function fr run advance resolves its shape with) under quiet with real protection answers (local origin = not enforced; fake forge client serving the captured approved ruleset via protection._default_client): test_config_degraded.py. Fallback bypass: test_config_legacy_by_tip.py. Lost lease: test_config_move_verified.py. A full fr run advance CLI walk under quiet was not built (cursor + fr worktree fixtures); the advance path is exercised at its resolver.

<!-- fr:journal kind=review scope=plan id=review-p4 created=2026-11-25T08:19:19+00:00 phase=4 -->
### review-p4 · review · Phase 4 adversarial review (relocation framework, moved kinds, cross-space migration, dogfood) (phase 4)

Independent adversarial reviewer read 956538f..HEAD against §D, R9-R14 and the artifact-versioning
rule: compliant (profiles 2->3 relocating hop, seven new kinds at 2, every hop asserted, no collision).
Reproduced content loss on a lost stealth lease and an old-path shadow bypassing the guard. Eleven
in-scope findings and one out-of-scope (fixed here too), plus two automated security-review follow-ups
(fork PR trusted by head name; symlinked-parent unlink). All fixed in dfb201a31..c0e1e7d06 with spec
amendments to R7, R10 and R13. Selection 3234 passed / 2 failed (pre-existing in test_services_cli.py,
fixed by c0e1e7d06) / 1 skipped; ruff, mypy, fr validate artifacts (171 valid) clean.

<!-- fr:journal kind=finding scope=plan id=p4-r1 created=2026-11-25T08:19:19+00:00 phase=4 state=open review_scope=in -->
### p4-r1 · finding [open] (reviewer: in scope) · move_across unlinked the product file without verifying the destination landed (stealth lost lease swallowed, ensure_space exists() race) (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r2 created=2026-11-25T08:19:19+00:00 phase=4 state=open review_scope=in -->
### p4-r2 · finding [open] (reviewer: in scope) · R13 fallback let a product-side old path override the configuration space and bypass read_checked under quiet/stealth (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r3 created=2026-11-25T08:19:19+00:00 phase=4 state=open review_scope=in -->
### p4-r3 · finding [open] (reviewer: in scope) · the profiles/workflow/strategy guard exceeded spec R7 and locked free-plan quiet/stealth repos out of isolation up, services and ops (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r4 created=2026-11-25T08:19:19+00:00 phase=4 state=open review_scope=in -->
### p4-r4 · finding [open] (reviewer: in scope) · quiet/stealth v1 profiles: 2->3 refused fr's own uncommitted 1->2 rewrite and missed the creation (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r5 created=2026-11-25T08:19:19+00:00 phase=4 state=open review_scope=in -->
### p4-r5 · finding [open] (reviewer: in scope) · _config_checkout decided by a -config directory name (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r6 created=2026-11-25T08:19:19+00:00 phase=4 state=open review_scope=in -->
### p4-r6 · finding [open] (reviewer: in scope) · stealth migrate auto-committed a deletion of an FR_OWNED path on the target branch, which the stealth push refuses (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r7 created=2026-11-25T08:19:19+00:00 phase=4 state=open review_scope=in -->
### p4-r7 · finding [open] (reviewer: in scope) · a diverged or dirty fr-config worktree was silently skipped, leaving an uncommitted product deletion (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r8 created=2026-11-25T08:19:19+00:00 phase=4 state=open review_scope=in -->
### p4-r8 · finding [open] (reviewer: in scope) · importing fr.config.migrate first failed with a circular import (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r9 created=2026-11-25T08:19:19+00:00 phase=4 state=open review_scope=in -->
### p4-r9 · finding [open] (reviewer: in scope) · fr repos sync ignored the old plan-config path and wrote the fr-config worktree directly under quiet (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r10 created=2026-11-25T08:19:19+00:00 phase=4 state=open review_scope=in -->
### p4-r10 · finding [open] (reviewer: in scope) · owed s1-refuse-old-paths named no release and omitted R16's env vars (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r11 created=2026-11-25T08:19:19+00:00 phase=4 state=open review_scope=in -->
### p4-r11 · finding [open] (reviewer: in scope) · no stealth profiles walk, guard wiring tested only with read_checked mocked, no tests for the fallback bypass or the lost lease (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r12 created=2026-11-25T08:19:19+00:00 phase=4 state=open review_scope=out -->
### p4-r12 · finding [open] (reviewer: out of scope) · change_branch named every change settings-<hash>, and a closed-unmerged config PR was re-proposed on every command (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r1-resolved created=2026-11-25T08:19:19+00:00 phase=4 state=fixed resolves=p4-r1 -->
### p4-r1-resolved · finding [fixed] · resolves p4-r1: move_across unlinked the product file without verifying the destination landed (stealth lost lease swallowed, ensure_space exists() race) (phase 4)

dfb201a31: unlink only once the re-fetched tip holds the exact bytes; absent -> propose, differing -> refuse (R12), never appearing -> refuse; a lost stealth lease raises BranchRaceError and is re-fetched as existing. Tests: lost lease, exists() race, untracked old path.

<!-- fr:journal kind=finding scope=plan id=p4-r2-resolved created=2026-11-25T08:19:19+00:00 phase=4 state=fixed resolves=p4-r2 -->
### p4-r2-resolved · finding [fixed] · resolves p4-r2: R13 fallback let a product-side old path override the configuration space and bypass read_checked under quiet/stealth (phase 4)

7205bd1a7 and b95c44316: a fetched configuration branch makes the product old path ignored (notice); with none, the old file is read only at the default branch's committed bytes and old-path executable content never runs; spec R13 amended; re-closes p5-exec-manifests-guard for this path.

<!-- fr:journal kind=finding scope=plan id=p4-r3-resolved created=2026-11-25T08:19:19+00:00 phase=4 state=fixed resolves=p4-r3 -->
### p4-r3-resolved · finding [fixed] · resolves p4-r3: the profiles/workflow/strategy guard exceeded spec R7 and locked free-plan quiet/stealth repos out of isolation up, services and ops (phase 4)

1f4c10a03: fr/config/degraded.py: unprotected repo workflows/strategies fall back to the shipped ones, profiles.yaml keeps only schema_version, default, profiles and purpose and names what it drops; a failed protection read still refuses executors; fr services shows the degraded view with protection unknown; spec R7 amended.

<!-- fr:journal kind=finding scope=plan id=p4-r4-resolved created=2026-11-25T08:19:19+00:00 phase=4 state=fixed resolves=p4-r4 -->
### p4-r4-resolved · finding [fixed] · resolves p4-r4: quiet/stealth v1 profiles: 2->3 refused fr's own uncommitted 1->2 rewrite and missed the creation (phase 4)

6edcc584e: v1 -> v3 bytes are built in memory from the committed file and the configuration branch is created with them; fr's own in-flight rewrite is accepted, an operator edit still refused.

<!-- fr:journal kind=finding scope=plan id=p4-r5-resolved created=2026-11-25T08:19:19+00:00 phase=4 state=fixed resolves=p4-r5 -->
### p4-r5-resolved · finding [fixed] · resolves p4-r5: _config_checkout decided by a -config directory name (phase 4)

07abd65fb: a configuration checkout is recognised by structure (HEAD on refs/heads/fr-config at the computed path, or the migrating product's own space); the ci-config case passes.

<!-- fr:journal kind=finding scope=plan id=p4-r6-resolved created=2026-11-25T08:19:19+00:00 phase=4 state=fixed resolves=p4-r6 -->
### p4-r6-resolved · finding [fixed] · resolves p4-r6: stealth migrate auto-committed a deletion of an FR_OWNED path on the target branch, which the stealth push refuses (phase 4)

a2ed5010f: under stealth the product file stays, fr prints the exact git rm once, nothing is staged on the target branch; spec R10 amended; discovery p4-stealth-product-deletion superseded.

<!-- fr:journal kind=finding scope=plan id=p4-r7-resolved created=2026-11-25T08:19:19+00:00 phase=4 state=fixed resolves=p4-r7 -->
### p4-r7-resolved · finding [fixed] · resolves p4-r7: a diverged or dirty fr-config worktree was silently skipped, leaving an uncommitted product deletion (phase 4)

d88c216f0: require_current_config_worktree refuses a dirty or diverged fr-config worktree before any unlink, naming the state and the remedy.

<!-- fr:journal kind=finding scope=plan id=p4-r8-resolved created=2026-11-25T08:19:19+00:00 phase=4 state=fixed resolves=p4-r8 -->
### p4-r8-resolved · finding [fixed] · resolves p4-r8: importing fr.config.migrate first failed with a circular import (phase 4)

9f8f58d94: the moved-kinds table is built on first use; a test imports each new module first in a fresh python -I interpreter.

<!-- fr:journal kind=finding scope=plan id=p4-r9-resolved created=2026-11-25T08:19:19+00:00 phase=4 state=fixed resolves=p4-r9 -->
### p4-r9-resolved · finding [fixed] · resolves p4-r9: fr repos sync ignored the old plan-config path and wrote the fr-config worktree directly under quiet (phase 4)

959df32b9 and faf1deaca: resolution through located(); under quiet/stealth a PR through the configuration writer (git.pr honoured) or a refusal naming fr migrate artifacts --yes; never writes the configuration checkout; every old-path read, move and unlink checks for linked parents (link_problem).

<!-- fr:journal kind=finding scope=plan id=p4-r10-resolved created=2026-11-25T08:19:19+00:00 phase=4 state=fixed resolves=p4-r10 -->
### p4-r10-resolved · finding [fixed] · resolves p4-r10: owed s1-refuse-old-paths named no release and omitted R16's env vars (phase 4)

e27835234: the owed entry names the first minor after S1's release, how fr detects it, and R16's old FR_SHIPPED_* variables; the orchestrator files a dedicated issue at deliver and repoints owed_key.

<!-- fr:journal kind=finding scope=plan id=p4-r11-resolved created=2026-11-25T08:19:19+00:00 phase=4 state=fixed resolves=p4-r11 -->
### p4-r11-resolved · finding [fixed] · resolves p4-r11: no stealth profiles walk, guard wiring tested only with read_checked mocked, no tests for the fallback bypass or the lost lease (phase 4)

Stealth profiles walk (transform, structure check, crash window), guard wiring through resolve_workflow, resolve_strategy and run_cmd's manifest resolver with real protection answers (local origin and a fake forge serving the captured ruleset), the fallback bypass and the lost lease are tested; the CLI-level fr run advance walk is left to the phase-7 candidate scenario.

<!-- fr:journal kind=finding scope=plan id=p4-r12-resolved created=2026-11-25T08:19:19+00:00 phase=4 state=fixed resolves=p4-r12 -->
### p4-r12-resolved · finding [fixed] · resolves p4-r12: change_branch named every change settings-<hash>, and a closed-unmerged config PR was re-proposed on every command (phase 4)

25a68541e and f24f3f028: change branches are fr-config-change/<kind>-<hash>; an open PR is reused only when its head is in the target repo, its base is the configuration branch and its head holds the exact bytes; a closed-unmerged one refuses once with its URL and --repropose; a same-named fork PR is ignored.

<!-- fr:journal kind=finding scope=plan id=p4-stealth-coverage-one-kind-resolved created=2026-11-25T08:19:19+00:00 phase=4 state=fixed resolves=p4-stealth-coverage-one-kind -->
### p4-stealth-coverage-one-kind-resolved · finding [fixed] · resolves p4-stealth-coverage-one-kind: P4.T2.S1's stealth leg is covered for one kind (models-config), not per kind (phase 4)

Covered by p4-r11's fix: the stealth profiles walk adds the kind whose stealth path differs, beside models-config.

<!-- fr:journal kind=decision scope=plan id=p5-defaults-env-order created=2026-11-25T08:40:39+00:00 phase=5 -->
### p5-defaults-env-order · decision · An explicit shipped_root replaces both variables; FR_SHIPPED_DEFAULTS_DIR/<kind> precedes the per-kind variable, which prints one notice per process (phase 5)

`fr._shipped.shipped_dirs(kind, packaged=, shipped_root=)` builds
`[$FR_SHIPPED_DEFAULTS_DIR/<kind>, $FR_SHIPPED_<KIND>_DIR, wheel fr/defaults/<kind>,
marketplace plugins/super-fr/defaults/<kind>]`; the repo `.fr/<kind>/` is prepended by the
workflow and verification resolvers (still read through `fr.config.degraded`, so an
unprotected quiet/stealth configuration branch falls back to this shipped walk), never by
lenses. An explicit `shipped_root` (tests) replaces both variables, as it replaced the one
variable before. A per-kind variable still resolves (R16) and prints, once per process per
variable, a stderr notice naming FR_SHIPPED_DEFAULTS_DIR (the R13 notice pattern); the
refusal is s1-refuse-old-paths' (R14). An unknown kind is a ValueError.

<!-- fr:journal kind=decision scope=plan id=p5-workflow-check-walk created=2026-11-25T08:40:39+00:00 phase=5 -->
### p5-workflow-check-walk · decision · fr workflow check now resolves through the same walk as fr run start (phase 5)

`fr workflow check` passed `default_shipped_workflows_dir()` (the env dir, else the
marketplace clone) as an explicit shipped_root, which put the marketplace clone before the
wheel for `check` only. It now passes no root, so `check` and `run start` search the one
`fr._shipped` order. Its empty-`--all` refusal names $FR_SHIPPED_DEFAULTS_DIR.

<!-- fr:journal kind=discovery scope=plan id=p5-pages-name-old-homes created=2026-11-25T08:40:39+00:00 phase=5 -->
### p5-pages-name-old-homes · discovery · Pages and two skills still name plugins/super-fr/{workflows,verifications,lenses}/ and the per-kind variables (phase 7) (phase 5)

docs/explainers/01-fr-goal.md, index.md, why-fr.md, docs/reference/workflow-shapes.md,
docs/review-lenses.md and docs/verification-strategies.md cite the old homes in prose and in
`covers:` globs (now matching nothing); the fr-goal and fr-acceptance skills name
$FR_SHIPPED_WORKFLOWS_DIR (still honoured). Phase 7 (spec §H) owns the pages, the covers
globs and the skills; AGENTS.md was updated here. .test_durations keeps the three deleted
tripwires' keys until the next refresh (only shard balance).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t1 created=2026-11-25T08:40:39+00:00 phase=5 -->
### no-refactor-p5-t1 · discovery · no-refactor-because P5.T1 (phase 5)

the three trees and their copies are now one tree and one copy, written by one sync script and guarded by one tripwire, so no per-kind copy was left to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t2 created=2026-11-25T08:40:39+00:00 phase=5 -->
### no-refactor-p5-t2 · discovery · no-refactor-because P5.T2 (phase 5)

fr._shipped.shipped_dirs(kind) is the one walk every resolver calls; the per-kind env/plugin_rel/packaged arguments it took before are derived from the kind, so nothing duplicated remained

<!-- fr:journal kind=review scope=plan id=review-p5 created=2026-11-25T09:09:22+00:00 phase=5 -->
### review-p5 · review · Phase 5 review (shipped defaults in one tree, one sync, one tripwire, one resolver order) (phase 5)

Independent reviewer read db114e4..HEAD against §F, R15-R17 and the amended R7/R13. Resolver order
matches the spec; only the repo candidate goes through fr.config.degraded, so the degraded fallback
lands on env/wheel/marketplace, never a repo path. Built and installed the wheel in an empty HOME:
4 lenses, 4 verifications and 2 workflows resolve from it; install.sh delivers the whole defaults/
tree. Three in-scope findings, fixed in 6082427e6..ad4930512 (acceptance check back from 64 to 58
errors, none naming the old tripwire); one out of scope, carried by owed s1-refuse-old-paths.
Selection 2412 passed / 9 skipped; ruff, mypy, sync-defaults --check clean.

<!-- fr:journal kind=finding scope=plan id=p5-r1 created=2026-11-25T09:09:22+00:00 phase=5 state=open review_scope=in -->
### p5-r1 · finding [open] (reviewer: in scope) · six acceptance rows cited the deleted test_tripwire_shipped_workflows.py, adding six unresolved-ref errors (phase 5)

<!-- fr:journal kind=finding scope=plan id=p5-r2 created=2026-11-25T09:09:22+00:00 phase=5 state=open review_scope=in -->
### p5-r2 · finding [open] (reviewer: in scope) · dead per-kind shipped constants and a helper with no production caller (phase 5)

<!-- fr:journal kind=finding scope=plan id=p5-r3 created=2026-11-25T09:09:22+00:00 phase=5 state=open review_scope=in -->
### p5-r3 · finding [open] (reviewer: in scope) · sync-defaults-data printed wrote for a deleted stale copy; the lens not-found error omitted FR_SHIPPED_LENSES_DIR (phase 5)

<!-- fr:journal kind=finding scope=plan id=p5-r4 created=2026-11-25T09:09:22+00:00 phase=5 state=open review_scope=out -->
### p5-r4 · finding [open] (reviewer: out of scope) · about 20 test sites still set the old FR_SHIPPED_*_DIR variables (phase 5)

<!-- fr:journal kind=finding scope=plan id=p5-r1-resolved created=2026-11-25T09:09:22+00:00 phase=5 state=fixed resolves=p5-r1 -->
### p5-r1-resolved · finding [fixed] · resolves p5-r1: six acceptance rows cited the deleted test_tripwire_shipped_workflows.py, adding six unresolved-ref errors (phase 5)

6082427e6..e6826bcbd: fr acceptance amend drop-level/add-level on the six rows, repointed at named tests in test_tripwire_shipped_defaults.py; fr acceptance check errors 64 -> 58, none for the old file. Three notes still name the old file because amend cannot reword a note; left for the next status move.

<!-- fr:journal kind=finding scope=plan id=p5-r2-resolved created=2026-11-25T09:09:22+00:00 phase=5 state=fixed resolves=p5-r2 -->
### p5-r2-resolved · finding [fixed] · resolves p5-r2: dead per-kind shipped constants and a helper with no production caller (phase 5)

ad4930512 and 0455c728a: the five dead constants and default_shipped_workflows_dir() removed, the lens message builds its path from _shipped.PACKAGED_DEFAULTS_DIRNAME.

<!-- fr:journal kind=finding scope=plan id=p5-r3-resolved created=2026-11-25T09:09:22+00:00 phase=5 state=fixed resolves=p5-r3 -->
### p5-r3-resolved · finding [fixed] · resolves p5-r3: sync-defaults-data printed wrote for a deleted stale copy; the lens not-found error omitted FR_SHIPPED_LENSES_DIR (phase 5)

23e62fc17 and 0455c728a: the sync prints removed <path>, the lens error names both $FR_SHIPPED_DEFAULTS_DIR/lenses and $FR_SHIPPED_LENSES_DIR, each asserted by a test.

<!-- fr:journal kind=finding scope=plan id=p5-r4-resolved created=2026-11-25T09:09:22+00:00 phase=5 state=open resolves=p5-r4 out_of_scope=true -->
### p5-r4-resolved · finding [out-of-scope] · resolves p5-r4: about 20 test sites still set the old FR_SHIPPED_*_DIR variables (phase 5)

The old variables are honoured until R14's release by design; those tests set them deliberately or incidentally and move when owed entry s1-refuse-old-paths ends the variables.

<!-- fr:journal kind=decision scope=plan id=p6-move-staged-and-locked created=2026-11-25T10:29:35+00:00 phase=6 -->
### p6-move-staged-and-locked · decision · The S1 move stages, verifies, installs and only then retires the clone copy, under a per-scope OS lock and the mover's own drive.lock (phase 6)

`fr.triage.state_home.settle` runs from `state_dir` (prepare) whenever the working
directory's (or `--workspace`'s) clone holds `.fr/triage-state/<scope>/`. Under
`~/.cache/fr/triage-locks/move-<scope>.lock` (`fr.file_lock.exclusive_file_lock`, polled
up to 60 s, so a second mover waits and then finds nothing to move) it takes
`<cache>/drive.lock` itself (rule 1: a live holder, any pid, refuses "stop the driver
first"; a stale one is replaced), so no driver of any fr version starts mid-move. The
clone copy minus `merge/` is copied to `.<scope>.s1-stage-*` beside the cache, verified
by a sha256 inventory, `git init`ed, renamed into place (an empty cache is set aside
and deleted; an older one becomes `<scope>.pre-s1`, `-2`... when taken) and verified
again; only then are the `merge/` worktrees removed (`git worktree remove --force` in
the repo that registered each, then prune), the copy renamed to `.<scope>.s1-moved-*`
and deleted, and the exclude line removed once no scope's copy is left. A crash leaves
the clone copy whole or the cache whole; the rerun meets the installed cache as rule
5 (identical durable files) and removes the copy. Leftover stage/aside dirs are cleared
at the next move. Readers with no clone copy take no lock: a no-clone command racing the
two renames of a first move can recreate an empty cache, which makes the install refuse
("re-created while the triage state moved") with the clone copy unchanged.

<!-- fr:journal kind=decision scope=plan id=p6-old-fr-after-move created=2026-11-25T10:29:35+00:00 phase=6 -->
### p6-old-fr-after-move · decision · An fr below S1 after the move is loud, never silent; restart the driver after upgrading (phase 6)

An old driver holds `drive.lock` in the cache dir (every fr version writes it there), so
the move refuses while it runs. An old fr that runs after the move finds no clone copy,
imports the cache's durable files into a new one (its `import_legacy`) and writes there;
every S1 command from that clone then refuses: rule 1 while that driver runs, rule 5
(differing durable files, naming both directories) after it stops. The move's notice
says to restart any running `fr triage batch drive` with the new fr and run no older fr
on the host. Tested in `test_an_old_fr_resurrecting_the_clone_copy_is_loud_never_silent`.

<!-- fr:journal kind=decision scope=plan id=p6-schema-1-refuses-the-key created=2026-11-25T10:29:35+00:00 phase=6 -->
### p6-schema-1-refuses-the-key · decision · Settings schema 1 refuses triage.state_repo set, not an empty triage section (phase 6)

R20 says a file that sets the key declares `schema: 2`. `Settings` accepts schema 1 or
2 and refuses `triage.state_repo` under 1; an empty `triage:` (what uncommenting the
`fr settings init` file gives, `state_repo: null`) sets no key and stays valid at 1, so
`test_the_commented_file_uncommented_still_parses_to_the_defaults` holds. Schema 3+ is
refused with the existing "newer than this fr" message.

<!-- fr:journal kind=decision scope=plan id=p6-declared-read-on-settle-only created=2026-11-25T10:29:35+00:00 phase=6 -->
### p6-declared-read-on-settle-only · decision · triage.state_repo is read by an explicit collect only and carried by the loops (facts schema 17) (phase 6)

`collect_into` reads the one-repo scope's `.fr/settings.yaml` through the forge
(`collect.read_declared_state_repo`: `forge_ref` picks the default branch or `fr-config`;
from `fr-config` the key counts only when `protection.branch_protection` is Enforced,
else it is ignored with `ignored_line`; any read or parse failure is said once and reads
as no declaration, never a failed collect) only with `settle=True`; the drive and watch
loops carry the previous facts' value, so a paced pass spends no read on it. Facts
schema 17 adds `state_repo_declared`; `fr triage check` compares it with
`scope-durable.yaml` (`state repo mismatch` set, JSON `state_repo_mismatch`).

<!-- fr:journal kind=decision scope=plan id=p6-stealth-local-tracking-stays-local created=2026-11-25T10:29:35+00:00 phase=6 -->
### p6-stealth-local-tracking-stays-local · decision · A stealth workspace whose tracking repo is no forge repo leaves the state local (phase 6)

R19's stealth rule takes the marker's tracking repo as `OWNER/REPO`
(`state_home.stealth_tracking`). A local-path tracking repo cannot hold a state ref
(`state_remote` names a forge URL), and falling through to the one-repo rule would push
`fr-triage/<id>` to the product repo stealth keeps clean, so the collect warns and
records no state repo (a declared one still wins). A stealth marker without its tracking
ref refuses the collect.

<!-- fr:journal kind=discovery scope=plan id=p6-preview-reads-cache-only created=2026-11-25T10:29:35+00:00 phase=6 -->
### p6-preview-reads-cache-only · discovery · A replacement preview on an unmoved host reads the cache only and reports no facts (phase 6)

`batch replace` without `--yes` resolves with `prepare=False`, which moves nothing, so on
a host whose state is still in a clone it says "no facts at ~/.cache/fr/triage/<scope>/";
any preparing command (collect, batch list) moves it first. Returning the clone path from
a pure resolution would break the act path, which keys its scope lock and sync on that
path before preparing.

<!-- fr:journal kind=discovery scope=plan id=p6-docs-owed-p7 created=2026-11-25T10:29:35+00:00 phase=6 -->
### p6-docs-owed-p7 · discovery · Pages and skill prose still place triage state in <workspace>/.fr/triage-state (phase 7) (phase 6)

The fr-triage skill, `docs/explainers/fr-triage.md`, `docs/cloud-setup.md` and AGENTS.md's
fr/triage paragraph describe the workspace state directory; the CLI help, module
docstrings and `fr skills` line were updated here. Phase 7 owns the pages.

<!-- fr:journal kind=finding scope=plan id=p6-product-push-tripwire-red created=2026-11-25T10:29:35+00:00 phase=6 state=open review_scope=in -->
### p6-product-push-tripwire-red · finding [open] (reviewer: in scope) · test_tripwire_product_push fails on fr.placement.quiet.create_config_branch (from ddb60c607, phase 4) (phase 6)

`tests/unit/test_tripwire_product_push.py::test_every_git_push_site_is_pinned` reports a
new `git push` site `('fr.placement.quiet', 'create_config_branch')`, added by
ddb60c607 (phase 4). Not touched by phase 6; it needs routing through
`fr.git_policy.product.push_product_branch` or an argued allowlist entry.

<!-- fr:journal kind=finding scope=plan id=p6-scenario-fakes-lacked-fr-config created=2026-11-25T10:29:35+00:00 phase=6 state=fixed review_scope=in -->
### p6-scenario-fakes-lacked-fr-config · finding [fixed] (reviewer: in scope) · Two cloud-triage scenario fakes failed on phase 1's fr-config probe; fixed here (phase 6)

`cloud-triage-driver-lease.sh` and `cloud-triage-version-drift.sh` failed (exit 2,
"fake gh: no capture for ... contents/.fr/settings.yaml?ref=fr-config") before this
phase: the scenario tier is not run locally. Their fake `gh` now answers that read with
the captured contents 404 (`repo_contents_docs_no-such-path.error.json`, derived only in
its path, said in each fake's header). All 11 triage scenarios were run against this
worktree's fr and pass, with the three cloud-triage ones updated for the cache home
(one HOME per simulated host).

<!-- fr:journal kind=finding scope=plan id=p6-sec-symlinked-state-dirs created=2026-11-25T10:29:35+00:00 phase=6 state=fixed review_scope=in -->
### p6-sec-symlinked-state-dirs · finding [fixed] (reviewer: in scope) · The move followed a symlinked .fr or .fr/triage-state into state outside the clone; fixed (phase 6)

Automated security review of 27752be54: `settle` checked only `copy.is_symlink()`, so a
symlinked `.fr` or `.fr/triage-state` (to the cache, or to another clone's state) let the
rename and rmtree delete state outside the checkout. Fixed in 32bd81861: before any
rename, delete, tidy or worktree removal, `.fr`, `.fr/triage-state` and the scope dir
pass `fr.config.space.link_problem` (lstat at every step, resolved inside the clone), and
`_overlap` refuses a copy that is, holds or sits in the cache, and a cache inside the
clone (a dotfiles-repo home). Tests: symlinked `.fr` and `.fr/triage-state` (nothing
deleted), a symlinked parent with no copy (no tidy), a copy resolving to the cache, a
cache inside the clone, and `_overlap`'s rules.

<!-- fr:journal kind=lens scope=plan id=lens-security-3 created=2026-11-25T10:29:35+00:00 phase=6 lens=security step=implement-phase -->
### lens-security-3 · lens · a new trust input: a repo's triage.state_repo decides where private issue data is pushed, and a move that deletes state directories (phase 6)

<!-- fr:journal kind=lens scope=plan id=lens-errors-3 created=2026-11-25T10:29:35+00:00 phase=6 lens=errors step=implement-phase -->
### lens-errors-3 · lens · a multi-step filesystem move with crash windows, two locks and refusals that must leave a whole copy (phase 6)

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p6-t1 created=2026-11-25T10:29:35+00:00 phase=6 -->
### no-refactor-p6-t1 · discovery · no-refactor-because P6.T1 (phase 6)

state_dir shrank to one resolution path (cache, or --dir); the legacy import and the clone exclude it replaced were deleted rather than kept beside it, and state_ref/_sync_with_ref needed no change because they already took the state directory's own toplevel as the object store

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p6-t2 created=2026-11-25T10:29:35+00:00 phase=6 -->
### no-refactor-p6-t2 · discovery · no-refactor-because P6.T2 (phase 6)

the move was written as one new module (fr/triage/state_home.py) with each R18 rule a named step (_hold_driver_lock, _install, _retire, _tidy, _compare); git calls went into gitseam as three small helpers, so nothing duplicated was left to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p6-t3 created=2026-11-25T10:29:35+00:00 phase=6 -->
### no-refactor-p6-t3 · discovery · no-refactor-because P6.T3 (phase 6)

the forge-side settings read mirrors read_config_lenient's ref choice and protection guard in one function beside it, sharing its say-once set; decide_state_repo gained two keyword rules ahead of the existing ones without restructuring them

<!-- fr:journal kind=finding scope=plan id=p6-product-push-tripwire-red-resolved created=2026-11-25T11:06:01+00:00 phase=6 state=fixed resolves=p6-product-push-tripwire-red -->
### p6-product-push-tripwire-red-resolved · finding [fixed] · resolves p6-product-push-tripwire-red: test_tripwire_product_push fails on fr.placement.quiet.create_config_branch (from ddb60c607, phase 4) (phase 6)

Pinned (fr.placement.quiet, create_config_branch) in FR_BRANCH_PUSHERS with its reason: the creation of fr-config (S1 R10), one orphan commit, a plain never-forced push, refused when the branch exists. test_tripwire_product_push.py green (bec21cf4f).

<!-- fr:journal kind=decision scope=plan id=p6-older-cache-from-outside created=2026-11-25T11:06:44+00:00 phase=6 -->
### p6-older-cache-from-outside · decision · An older (pre-S1) cache is made an S1 repository only by the R18 move (phase 6)

A cache holding files and no .git (an fr below S1's) is never git-init'd in place (state_home.refuse_older, called by state_dir and ensure_repo). From a working directory with no clone copy, fr refuses and names the remedies: run from the clone whose .fr/triage-state/<scope>/ holds the live state (the move keeps the cache as <scope>.pre-s1); if no clone holds one, move the cache into a clone's .fr/triage-state/ and run from there; or --dir <cache> to use it unsynced. Review p6-r2.

<!-- fr:journal kind=decision scope=plan id=p6-stealth-ignores-declared created=2026-11-25T11:07:03+00:00 phase=6 -->
### p6-stealth-ignores-declared · decision · Under stealth the product repo's triage.state_repo is never read; the tracking repo wins (phase 6)

A settle collect from a stealth workspace does not read the product repo's .fr/settings.yaml for triage.state_repo (triage_cmd._declared_state_repo). decide_state_repo now puts the stealth tracking repo before any declaration; a declaration is only read from the operator's stealth configuration space (state_home.stealth_declared_state_repo), at its configuration branch tip and behind R7's require_protected guard, and matters only when the tracking repo is no forge repo. leak_risk still judges every push. Spec R20 amended (spec journal). Review p6-r5.

<!-- fr:journal kind=decision scope=plan id=p6-rc6-tombstone created=2026-11-25T11:07:05+00:00 phase=6 -->
### p6-rc6-tombstone · decision · A retired clone copy leaves a tombstone file an fr below S1 fails on (phase 6)

The installed pre-S1 state_dir (read from its source): the target is the clone's .fr/triage-state/<scope>; it imports the cache's durable files only when the target does not exist, and every state read (load_judgements, load_facts) raises TriageError on OSError. So the move now leaves a regular file at that path (first line fr-triage-state-moved, naming the cache): an older fr imports nothing and fails on its first read (Not a directory), and its writers' mkdir fails, instead of silently re-creating a copy. S1 recognises the tombstone (state_home.is_tombstone) and passes it by; a regular file without the marker is still refused. Rule 4 consequence: the exclude line stays while the tombstone is there (it keeps it out of git) and goes once the operator deletes it and no other worktree holds a .fr/triage-state/. The crash window between the copy's retirement and the tombstone's write is covered by p6-r1's rule 5 (carry files the cache lacks, refuse any divergence). The move notice tells the operator to upgrade every fr on the host and restart any driver before the next fr command. Review p6-r8.

<!-- fr:journal kind=decision scope=plan id=p6-move-lock-shared created=2026-11-25T11:07:07+00:00 phase=6 -->
### p6-move-lock-shared · decision · State-dir writers hold the move lock shared for the process; worktrees are never force-removed (phase 6)

state_dir(prepare=True) takes the scope's move lock (triage-locks/move-<scope>.lock) shared after settling and holds it until exit (state_home.hold_shared; the suite drops it per test); a mover takes it exclusive, dropping its own shared hold first, and _install re-reads the cache's kind and inventory right before its rename. Rule 3: every worktree registered under the copy (any depth) is checked with gitseam.worktree_unsafe (local changes, or HEAD commits no branch, tag or remote holds) and refuses the move by name; a clean one is removed with a plain git worktree remove. Reviews p6-r4, p6-r7.

<!-- fr:journal kind=review scope=plan id=review-p6 created=2026-11-25T11:19:00+00:00 phase=6 -->
### review-p6 · review · Phase 6 adversarial review (triage state in the cache repo, the R18 move, the state repo setting) (phase 6)

Independent adversarial reviewer read 69b62bf..HEAD against R18-R20 with HOME in a scratch dir and the
operator's real cache listed before and after (unchanged). Reproduced three losses on the operator's
real host shape (pre-S1 cache with a live drive.lock, live state in the clone): rule 5 deleting non-ref
files, a pre-S1 cache git-initialised from outside a clone, and the shared exclude line removed while a
linked worktree held private state. Ten in-scope findings, all fixed in bec21cf4f..4b371b158 with spec
amendments to R18 and R20; the open finding p6-product-push-tripwire-red resolved. Selection 4156
passed / 8 skipped, triage scenarios 19/19, product-push tripwire green, ruff and mypy clean.

<!-- fr:journal kind=finding scope=plan id=p6-r1 created=2026-11-25T11:19:00+00:00 phase=6 state=open review_scope=in -->
### p6-r1 · finding [open] (reviewer: in scope) · rule 5 deleted the clone copy after comparing REF_FILES only, losing scope.yaml, driver files, pacing, .state-ref, closeout-wait/ (phase 6)

<!-- fr:journal kind=finding scope=plan id=p6-r2 created=2026-11-25T11:19:00+00:00 phase=6 state=open review_scope=in -->
### p6-r2 · finding [open] (reviewer: in scope) · state_dir git-initialised a pre-S1 cache from any cwd with no clone copy, defeating .pre-s1 and serving stale state (phase 6)

<!-- fr:journal kind=finding scope=plan id=p6-r3 created=2026-11-25T11:19:00+00:00 phase=6 state=open review_scope=in -->
### p6-r3 · finding [open] (reviewer: in scope) · _tidy removed the shared info/exclude line while linked worktrees still held private triage state (phase 6)

<!-- fr:journal kind=finding scope=plan id=p6-r4 created=2026-11-25T11:19:00+00:00 phase=6 state=open review_scope=in -->
### p6-r4 · finding [open] (reviewer: in scope) · _retire force-removed or rmtree'd kept merge worktrees and copied other worktree scratch dirs into the cache broken (phase 6)

<!-- fr:journal kind=finding scope=plan id=p6-r5 created=2026-11-25T11:19:00+00:00 phase=6 state=open review_scope=in -->
### p6-r5 · finding [open] (reviewer: in scope) · under stealth triage.state_repo was read from the product default branch and won over the tracking repo (phase 6)

<!-- fr:journal kind=finding scope=plan id=p6-r6 created=2026-11-25T11:19:00+00:00 phase=6 state=open review_scope=in -->
### p6-r6 · finding [open] (reviewer: in scope) · the stale drive.lock takeover lacked drive_lock's put-theirs-back check (phase 6)

<!-- fr:journal kind=finding scope=plan id=p6-r7 created=2026-11-25T11:19:00+00:00 phase=6 state=open review_scope=in -->
### p6-r7 · finding [open] (reviewer: in scope) · non-mover cache writers took no lock and could be trashed by _install mid-move (phase 6)

<!-- fr:journal kind=finding scope=plan id=p6-r8 created=2026-11-25T11:19:00+00:00 phase=6 state=open review_scope=in -->
### p6-r8 · finding [open] (reviewer: in scope) · an fr below S1 silently resurrected the clone copy after the move (phase 6)

<!-- fr:journal kind=finding scope=plan id=p6-r9 created=2026-11-25T11:19:00+00:00 phase=6 state=open review_scope=in -->
### p6-r9 · finding [open] (reviewer: in scope) · test_tripwire_product_push red on quiet.create_config_branch (phase 6)

<!-- fr:journal kind=finding scope=plan id=p6-r10 created=2026-11-25T11:19:00+00:00 phase=6 state=open review_scope=in -->
### p6-r10 · finding [open] (reviewer: in scope) · the PROTECTED_SOURCES guard was in-process only, reset by monkeypatch.undo() and blind to the HOME-leak class (phase 6)

<!-- fr:journal kind=finding scope=plan id=p6-r1-resolved created=2026-11-25T11:19:00+00:00 phase=6 state=fixed resolves=p6-r1 -->
### p6-r1-resolved · finding [fixed] · resolves p6-r1: rule 5 deleted the clone copy after comparing REF_FILES only, losing scope.yaml, driver files, pacing, .state-ref, closeout-wait/ (phase 6)

9f9477cb3: rule 5 compares the full inventory except worktree scratch dirs, locks, facts.json and top-level pages; clone-only files are carried into the cache, never over an existing one; any difference refuses naming the files.

<!-- fr:journal kind=finding scope=plan id=p6-r2-resolved created=2026-11-25T11:19:00+00:00 phase=6 state=fixed resolves=p6-r2 -->
### p6-r2-resolved · finding [fixed] · resolves p6-r2: state_dir git-initialised a pre-S1 cache from any cwd with no clone copy, defeating .pre-s1 and serving stale state (phase 6)

9f9477cb3 and 4b371b158: a pre-S1 cache is never git-initialised in place; state_dir refuses from outside a clone naming the remedies; only the move sets it aside as .pre-s1; a test reproduces the operator's host shape (decision p6-older-cache-from-outside).

<!-- fr:journal kind=finding scope=plan id=p6-r3-resolved created=2026-11-25T11:19:00+00:00 phase=6 state=fixed resolves=p6-r3 -->
### p6-r3-resolved · finding [fixed] · resolves p6-r3: _tidy removed the shared info/exclude line while linked worktrees still held private triage state (phase 6)

9f9477cb3: _tidy keeps the shared exclude line, and says so, while any worktree of the common dir still has .fr/triage-state/.

<!-- fr:journal kind=finding scope=plan id=p6-r4-resolved created=2026-11-25T11:19:00+00:00 phase=6 state=fixed resolves=p6-r4 -->
### p6-r4-resolved · finding [fixed] · resolves p6-r4: _retire force-removed or rmtree'd kept merge worktrees and copied other worktree scratch dirs into the cache broken (phase 6)

9f9477cb3: every registered worktree under the copy is found at any depth; one with local changes or unreachable HEAD commits refuses the move by name; clean ones get a plain git worktree remove; scratch dirs are never copied; prune after.

<!-- fr:journal kind=finding scope=plan id=p6-r5-resolved created=2026-11-25T11:19:00+00:00 phase=6 state=fixed resolves=p6-r5 -->
### p6-r5-resolved · finding [fixed] · resolves p6-r5: under stealth triage.state_repo was read from the product default branch and won over the tracking repo (phase 6)

3e9407e59: under stealth the product repo never names the state repo; the tracking repo wins; a declaration counts only from the operator's stealth configuration space behind require_protected; spec R20 amended (decision p6-stealth-ignores-declared).

<!-- fr:journal kind=finding scope=plan id=p6-r6-resolved created=2026-11-25T11:19:00+00:00 phase=6 state=fixed resolves=p6-r6 -->
### p6-r6-resolved · finding [fixed] · resolves p6-r6: the stale drive.lock takeover lacked drive_lock's put-theirs-back check (phase 6)

9f9477cb3: the mover re-reads a moved-aside stale drive.lock and puts it back if another starter took it over.

<!-- fr:journal kind=finding scope=plan id=p6-r7-resolved created=2026-11-25T11:19:00+00:00 phase=6 state=fixed resolves=p6-r7 -->
### p6-r7-resolved · finding [fixed] · resolves p6-r7: non-mover cache writers took no lock and could be trashed by _install mid-move (phase 6)

9f9477cb3: state_dir(prepare=True) holds the move lock shared, movers exclusive; _install re-reads the cache's kind and inventory before its rename and refuses on change (decision p6-move-lock-shared).

<!-- fr:journal kind=finding scope=plan id=p6-r8-resolved created=2026-11-25T11:19:00+00:00 phase=6 state=fixed resolves=p6-r8 -->
### p6-r8-resolved · finding [fixed] · resolves p6-r8: an fr below S1 silently resurrected the clone copy after the move (phase 6)

9f9477cb3: the move leaves a marked tombstone file at the clone path, so an fr below S1 imports nothing and fails loudly on its first read; S1 passes the tombstone by; the notice says to upgrade every fr and restart any driver first (decision p6-rc6-tombstone, spec R18 amended).

<!-- fr:journal kind=finding scope=plan id=p6-r9-resolved created=2026-11-25T11:19:00+00:00 phase=6 state=fixed resolves=p6-r9 -->
### p6-r9-resolved · finding [fixed] · resolves p6-r9: test_tripwire_product_push red on quiet.create_config_branch (phase 6)

bec21cf4f: create_config_branch is in FR_BRANCH_PUSHERS with its reason (fr-config creation, R10, plain orphan push that refuses when the branch exists); the tripwire passes.

<!-- fr:journal kind=finding scope=plan id=p6-r10-resolved created=2026-11-25T11:19:00+00:00 phase=6 state=fixed resolves=p6-r10 -->
### p6-r10-resolved · finding [fixed] · resolves p6-r10: the PROTECTED_SOURCES guard was in-process only, reset by monkeypatch.undo() and blind to the HOME-leak class (phase 6)

c75054f8f: a session-scoped autouse fixture sets HOME and GIT_CONFIG_GLOBAL in os.environ before any test, so subprocesses inherit it and undo() cannot restore the real home, and fails the session naming any new entry in the real ~/.cache/fr/triage/.

<!-- fr:journal kind=finding scope=plan id=p7-scenario-profiles-blocks-every-hop created=2026-11-25T13:25:22+00:00 phase=7 state=fixed review_scope=in -->
### p7-scenario-profiles-blocks-every-hop · finding [fixed] (reviewer: in scope) · Under quiet/stealth one profiles file its own hop refuses made every cross-space hop fail (pending_files let UnmigratableProfilesError escape) (phase 7)

Found by tests/scenarios/config-homes.sh. fr.config.migrate.pending_files caught only SettingsError around profiles_body; services_text raises UnmigratableProfilesError (an ArtifactMigrationError), so a version-2 profiles file with no service block failed models, plan-config, workflows and the settings hop too. Fixed in 57974e3a7: the catch takes both, the profiles hop alone refuses. Test: test_migration_config_kinds.py::test_under_quiet_an_unmigratable_profiles_file_holds_back_only_itself.

<!-- fr:journal kind=finding scope=plan id=p7-scenario-symlinked-home created=2026-11-25T13:25:22+00:00 phase=7 state=fixed review_scope=in -->
### p7-scenario-symlinked-home · finding [fixed] (reviewer: in scope) · settings-location raised ValueError for every quiet repo when HOME is reached through a symlink (phase 7)

Found by the scenario (macOS mktemp HOME under /var -> /private/var). _config_settings_for_legacy compared the old switch's unresolved path with git's real --show-toplevel and then called relative_to. Fixed in 57974e3a7 by resolving both. Test: test_migration_config_kinds.py::test_settings_location_works_when_home_is_reached_through_a_symlink.

<!-- fr:journal kind=finding scope=plan id=p7-scenario-commit-hint-outside-repo created=2026-11-25T13:25:22+00:00 phase=7 state=fixed review_scope=in -->
### p7-scenario-commit-hint-outside-repo · finding [fixed] (reviewer: in scope) · fr migrate artifacts --yes under quiet printed a git add naming fr-config worktree paths, which git refuses as outside the repository (phase 7)

Fixed in 57974e3a7: migrate_cmd._commit_paths splits the product's own paths (printed in the git add) from the configuration-checkout ones (named as already committed and pushed). Test: tests/unit/test_migrate_cmd_commit_hint.py.

<!-- fr:journal kind=finding scope=plan id=p7-scenario-exec-bit-lost created=2026-11-25T13:25:22+00:00 phase=7 state=fixed review_scope=in -->
### p7-scenario-exec-bit-lost · finding [fixed] (reviewer: in scope) · fr-config's creation and a proposed change committed every file 100644, so a moved .fr/candidate-install stopped being executable (phase 7)

Found by the scenario (the brainstorm resolve warned the moved install was not executable). quiet._orphan_commit and change._commit_on hard-coded 100644. Fixed in acaf94ff2: pending_files records the executable sources, and an `executable` set (or flag, for a proposal) reaches _orphan_commit, stealth._create_branch and _commit_on. Tests: test_migration_config_kinds.py::test_under_quiet_an_executable_file_keeps_its_mode_on_fr_config and ::test_a_proposed_executable_keeps_its_mode.

<!-- fr:journal kind=finding scope=plan id=p7-scenario-empty-old-dir-notice created=2026-11-25T13:25:22+00:00 phase=7 state=fixed review_scope=in -->
### p7-scenario-empty-old-dir-notice · finding [fixed] (reviewer: in scope) · Every command after the quiet migration still said it was ignoring the emptied docs/superpowers/workflows/ (phase 7)

fr.config.space.located treated an existing empty old directory as an old path to ignore. Fixed in acaf94ff2 (_holds_anything). Test: test_config_legacy_by_tip.py::test_an_empty_old_directory_left_by_the_migration_says_nothing.

<!-- fr:journal kind=decision scope=plan id=p7-scenario-forge-shape created=2026-11-25T13:25:22+00:00 phase=7 -->
### p7-scenario-forge-shape · decision · The scenario reaches real protection answers with a GitHub-spelled origin served by a fake ssh and a fake gh replaying the captured rules replies (phase 7)

fr asks the forge only for an origin it can name (git remote get-url, which applies insteadOf, so URL rewriting cannot fake it). The quiet product's origin is git@github.com:example-org/demo.git; GIT_SSH_COMMAND=tests/scenarios/fixtures/config-homes/bin/fake-ssh runs git's upload/receive-pack against a local bare repo, and fixtures/config-homes/bin/gh replays tests/fixtures/github_rest/rules/pull-request-approved.json (enforced) and free-plan.error.json (the free-plan 403), any other call failing loudly (an unreadable answer). No reply is constructed. The CLI-level `fr run start`/`advance` walk under quiet that p4-r11 left to this scenario runs once per answer: the repo's fr-goal is ignored under the free-plan 403 (the shipped shape's spec-review follows brainstorm) and used when enforced (plan follows). The migration is committed by the CLI-entry gate in a workspace, since the explicit `fr migrate artifacts --yes` never commits.

<!-- fr:journal kind=decision scope=plan id=p7-rows-to-ci created=2026-11-25T13:25:22+00:00 phase=7 -->
### p7-rows-to-ci · decision · The six S1 rows move not-implemented -> ci, with their unit refs and the int ref test_scenarios.py#test_config_homes (phase 7)

Their unit tests run in CI and the scenario runs in CI's scenario tier (CI runs every test). Not walked: the deliver walk of the candidate strategy earns that. cloud-triage-state-ref was amended (drop two workspace tests phase 6 deleted, add test_triage_state_home.py's two) so its refs resolve. The three notes naming the deleted test_tripwire_shipped_workflows.py stay: none of their rows moved.

<!-- fr:journal kind=discovery scope=plan id=p7-acceptance-check-main-rows created=2026-11-25T13:25:22+00:00 phase=7 -->
### p7-acceptance-check-main-rows · discovery · fr acceptance check --no-fetch reports 136 errors, all from rows origin/main added for features this branch has not merged (25 rows: ci-economy, triage-hardening, intake, show-me, ...) (phase 7)

origin/main is not an ancestor of the branch; those rows cite specs and tests that exist only on main. None names an S1 row or this feature's fragment. Merging main into the branch before deliver clears them; it is the orchestrator's call (executors never move to other commits).

<!-- fr:journal kind=finding scope=plan id=p7-commit-notice-counts-paths created=2026-11-25T13:25:22+00:00 phase=7 state=open review_scope=out -->
### p7-commit-notice-counts-paths · finding [open] (reviewer: out of scope) · The gate's `fr: migrated and committed <n> artifact(s)` counts paths, so a rename of 7 artifacts says 14 (phase 7)

fr.artifacts.trigger._commit_notice uses len(outcome.paths); a rename stages both sides. Pre-S1 behaviour, cosmetic; the commit subject is right (7 artifacts).

<!-- fr:journal kind=discovery scope=plan id=p7-writing-standard-checked created=2026-11-25T13:25:22+00:00 phase=7 -->
### p7-writing-standard-checked · discovery · The edited pages pass scripts/check-writing-standards.sh against the pinned blog-craft (17 + 14 checked, 0 FAIL) (phase 7)

Fetched at .github/blog-craft.ref. The checker does not split a sentence that starts with a lowercase word (`fr ...`), so such sentences were reworded; one existing FAIL in docs/verification-strategies.md (phase 3's paragraph) was rewritten with them.

<!-- fr:journal kind=lens scope=plan id=lens-tests-1 created=2026-11-25T13:25:22+00:00 phase=7 lens=tests step=implement-phase -->
### lens-tests-1 · lens · a candidate scenario built on a fake ssh transport and a fake gh replaying captures, standing in for a forge-protected configuration branch (phase 7)

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p7-t1 created=2026-11-25T13:25:22+00:00 phase=7 -->
### no-refactor-p7-t1 · discovery · no-refactor-because P7.T1 (phase 7)

the scenario is one script over _common.sh's helpers plus two fixture programs (a fake gh replaying the captured rules replies, a fake ssh); the four product fixes it forced were one-line catches or a threaded mode flag at the one creation path, so nothing duplicated was left to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p7-t2 created=2026-11-25T13:25:22+00:00 phase=7 -->
### no-refactor-p7-t2 · discovery · no-refactor-because P7.T2 (phase 7)

prose, front matter and generated mirrors only, plus message strings; the mirrors are regenerated by their sync scripts, so there was no code to clean

<!-- fr:journal kind=finding scope=plan id=p7-commit-notice-counts-paths-resolved created=2026-11-25T15:59:21+00:00 state=fixed resolves=p7-commit-notice-counts-paths -->
### p7-commit-notice-counts-paths-resolved · finding [fixed] · resolves p7-commit-notice-counts-paths: The gate's `fr: migrated and committed <n> artifact(s)` counts paths, so a rename of 7 artifacts says 14

a08dbae95: the notice takes the commit subject's artifact count (a move is one artifact); pinned by test_migration_trigger.py::test_the_commit_notice_counts_artifacts_as_the_commit_subject_does

<!-- fr:journal kind=review scope=plan id=review-p7 created=2026-11-25T15:59:23+00:00 phase=7 -->
### review-p7 · review · Phase 7 review: the candidate walk, pages, skills, rules and mirrors (phase 7)

Independent read-only review of b3392d8..ad20405e4 (a first reviewer died in a host
reboot; this is the rerun). Six findings, all in scope: one deterministic test failure
caused by S1's .fr/profiles.yaml (p7-r1), the P7.T2.S2 tick claiming a green fast tier
that never finished (p7-r2), the exec bit read from the working tree while the bytes
come from HEAD (p7-r3), scaffold help naming the old profiles path (p7-r4), the
isolation rules overclaiming that fr-config only changes through a pull request (p7-r5),
and four weak scenario assertions (p7-r6).
Clean: the scenario passes on the installed candidate and exercises all six S1 rows in
repo, quiet and stealth, with fr run start/advance under quiet; the fake gh replays the
captured approved and free-plan replies; every row level ref exists and `ci` is honest
(CI's full lane runs the scenario tier); page claims match the code; mirrors, harness
parity and fr docs check are clean; no third-party identity.
Fast tier: it did not finish on this host (stopped at 59%, 15 F/E marks unnamed). The
fixer's sweeps over every test file naming a path S1 moved found five S1 failures
(p7-r1 and four host tests), now fixed; the rest are unidentified. CI's test shards are
the suite evidence for this phase, not a local run.

<!-- fr:journal kind=finding scope=plan id=p7-r1 created=2026-11-25T15:59:23+00:00 phase=7 state=open review_scope=in -->
### p7-r1 · finding [open] (reviewer: in scope) · test_ops_gate_review fails: the ops gate's profile diff now names .fr/profiles.yaml (phase 7)

<!-- fr:journal kind=finding scope=plan id=p7-r2 created=2026-11-25T15:59:23+00:00 phase=7 state=open review_scope=in -->
### p7-r2 · finding [open] (reviewer: in scope) · P7.T2.S2 ticked although its --fr-scope green condition was not met (phase 7)

<!-- fr:journal kind=finding scope=plan id=p7-r3 created=2026-11-25T15:59:23+00:00 phase=7 state=open review_scope=in -->
### p7-r3 · finding [open] (reviewer: in scope) · A moved file's executable bit comes from the working tree, its bytes from HEAD (phase 7)

<!-- fr:journal kind=finding scope=plan id=p7-r4 created=2026-11-25T15:59:23+00:00 phase=7 state=open review_scope=in -->
### p7-r4 · finding [open] (reviewer: in scope) · fr init scaffold help still names fr-profiles.yaml (phase 7)

<!-- fr:journal kind=finding scope=plan id=p7-r5 created=2026-11-25T15:59:23+00:00 phase=7 state=open review_scope=in -->
### p7-r5 · finding [open] (reviewer: in scope) · Isolation rules claim fr-config changes only as a pull request; a direct push is possible (phase 7)

<!-- fr:journal kind=finding scope=plan id=p7-r6 created=2026-11-25T15:59:23+00:00 phase=7 state=open review_scope=in -->
### p7-r6 · finding [open] (reviewer: in scope) · Scenario: some assertions are weaker than they read (phase 7)

<!-- fr:journal kind=finding scope=plan id=p7-r1-resolved created=2026-11-25T15:59:23+00:00 phase=7 state=fixed resolves=p7-r1 -->
### p7-r1-resolved · finding [fixed] · resolves p7-r1: test_ops_gate_review fails: the ops gate's profile diff now names .fr/profiles.yaml (phase 7)

eb69baab1, 0b2b39f58: the expectation carries .fr/profiles.yaml; 8830abf17: four host tests that S1's legacy-location notice broke write .fr/profiles.yaml. Sweeps of every test file naming a moved path found no other failure.

<!-- fr:journal kind=finding scope=plan id=p7-r2-resolved created=2026-11-25T15:59:23+00:00 phase=7 state=fixed resolves=p7-r2 -->
### p7-r2-resolved · finding [fixed] · resolves p7-r2: P7.T2.S2 ticked although its --fr-scope green condition was not met (phase 7)

The claim is corrected here: no complete local fast-tier run exists for this phase; the failures that could be identified (p7-r1 and four host tests) are fixed, and CI's test shards are the suite evidence.

<!-- fr:journal kind=finding scope=plan id=p7-r3-resolved created=2026-11-25T15:59:23+00:00 phase=7 state=fixed resolves=p7-r3 -->
### p7-r3-resolved · finding [fixed] · resolves p7-r3: A moved file's executable bit comes from the working tree, its bytes from HEAD (phase 7)

704117a98: a tracked file's mode comes from git ls-tree HEAD; lstat only for untracked files; test with core.fileMode=false fails before, passes after.

<!-- fr:journal kind=finding scope=plan id=p7-r4-resolved created=2026-11-25T15:59:23+00:00 phase=7 state=fixed resolves=p7-r4 -->
### p7-r4-resolved · finding [fixed] · resolves p7-r4: fr init scaffold help still names fr-profiles.yaml (phase 7)

ad16282f2: scaffold help names the profile declarations (.fr/profiles.yaml); docs/reference/cli.md regenerated.

<!-- fr:journal kind=finding scope=plan id=p7-r5-resolved created=2026-11-25T15:59:23+00:00 phase=7 state=fixed resolves=p7-r5 -->
### p7-r5-resolved · finding [fixed] · resolves p7-r5: Isolation rules claim fr-config changes only as a pull request; a direct push is possible (phase 7)

4f30e0443: both rule files say fr's own changes go through a pull request and only the forge's rule stops a direct push; OpenCode and Hermes mirrors regenerated.

<!-- fr:journal kind=finding scope=plan id=p7-r6-resolved created=2026-11-25T15:59:23+00:00 phase=7 state=fixed resolves=p7-r6 -->
### p7-r6-resolved · finding [fixed] · resolves p7-r6: Scenario: some assertions are weaker than they read (phase 7)

1a7fa90d4: grep fr's own refusal wording; the unreadable case stays synthetic with a comment (both captured errors classify as not enforced, no 5xx captured); the cache is asserted a standalone repo with no state-repo branch or remote, as designed; every gate call checks its exit code.

<!-- fr:journal kind=review scope=plan id=review-lenses created=2026-11-25T17:37:21+00:00 -->
### review-lenses · review · Lens review of S1 configuration homes: docs-accuracy, errors, security, tests

Four read-only reviewers, one per lens, over the whole feature diff (merge base 11c158e4).
Security found no bypass of the edit gate, allowlist or marker self-protection, or of the
fr-config and stealth config-clone write targets (case-folding, segments, symlinks, hard
links, non-ASCII names; bash and TS agree). It raised four trust-model findings. Errors
raised ten, docs-accuracy four, tests six (one out of scope).
Every in-scope finding is fixed with a test written first (1e17b090c..f6f2e5683). The spec
is amended 2026-11-25 at R6, R7, section C, R10 and R20. Three tests that S1 broke in
test_merge_train_label_board.py were found and fixed on the way (288befc2c).
An independent adversarial verifier then checked the fixes: 22 of 23 closed;
l-security-r2 was half closed (an untracked old-path file still moved from disk) and it
raised three smaller gaps (validate-plans fail-open when fr fails, the CI HEAD fallback in
the default-ref comparison, stealth's absent sync state not validating the switch). All
four are fixed (2d81ff235, 6583f7496, 9607b17f9, f6f2e5683).

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1 created=2026-11-25T17:37:21+00:00 state=open review_scope=in -->
### l-docs-accuracy-r1 · finding [open] (reviewer: in scope) · fr-isolation.md says fr refuses all unprotected executable config; guarded ci.yaml and triage.yaml keys are ignored, not refused

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2 created=2026-11-25T17:37:21+00:00 state=open review_scope=in -->
### l-docs-accuracy-r2 · finding [open] (reviewer: in scope) · fr-init page and skill misdescribe scaffold under quiet and stealth

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r3 created=2026-11-25T17:37:21+00:00 state=open review_scope=in -->
### l-docs-accuracy-r3 · finding [open] (reviewer: in scope) · fr-isolation.md says the migration always creates the config branch first

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r4 created=2026-11-25T17:37:21+00:00 state=open review_scope=in -->
### l-docs-accuracy-r4 · finding [open] (reviewer: in scope) · repos_cmd.py docstring names the old plan-config path

<!-- fr:journal kind=finding scope=plan id=l-errors-r1 created=2026-11-25T17:37:21+00:00 state=open review_scope=in -->
### l-errors-r1 · finding [open] (reviewer: in scope) · A partly failed fr settings init (config branch pushed, legacy refused) cannot be retried

<!-- fr:journal kind=finding scope=plan id=l-errors-r2 created=2026-11-25T17:37:21+00:00 state=open review_scope=in -->
### l-errors-r2 · finding [open] (reviewer: in scope) · Quiet fr-config creation never raises BranchRaceError

<!-- fr:journal kind=finding scope=plan id=l-errors-r3 created=2026-11-25T17:37:21+00:00 state=open review_scope=in -->
### l-errors-r3 · finding [open] (reviewer: in scope) · change._forge_prs_for_head swallows every forge error

<!-- fr:journal kind=finding scope=plan id=l-errors-r4 created=2026-11-25T17:37:21+00:00 state=open review_scope=in -->
### l-errors-r4 · finding [open] (reviewer: in scope) · open_change's git timeouts escape as raw TimeoutExpired

<!-- fr:journal kind=finding scope=plan id=l-errors-r5 created=2026-11-25T17:37:21+00:00 state=open review_scope=in -->
### l-errors-r5 · finding [open] (reviewer: in scope) · A failed read of triage.state_repo settles the state repo durably

<!-- fr:journal kind=finding scope=plan id=l-errors-r6 created=2026-11-25T17:37:21+00:00 state=open review_scope=in -->
### l-errors-r6 · finding [open] (reviewer: in scope) · The stealth-declared triage.state_repo path is unreachable

<!-- fr:journal kind=finding scope=plan id=l-errors-r7 created=2026-11-25T17:37:21+00:00 state=open review_scope=in -->
### l-errors-r7 · finding [open] (reviewer: in scope) · degraded.read_profiles reads a failed fetch as no profiles

<!-- fr:journal kind=finding scope=plan id=l-errors-r8 created=2026-11-25T17:37:21+00:00 state=open review_scope=in -->
### l-errors-r8 · finding [open] (reviewer: in scope) · settings sync preview ignores failed fetch and git log

<!-- fr:journal kind=finding scope=plan id=l-errors-r9 created=2026-11-25T17:37:21+00:00 state=open review_scope=in -->
### l-errors-r9 · finding [open] (reviewer: in scope) · settings sync --yes forge-read failure names no remedy

<!-- fr:journal kind=finding scope=plan id=l-errors-r10 created=2026-11-25T17:37:21+00:00 state=open review_scope=in -->
### l-errors-r10 · finding [open] (reviewer: in scope) · A failed fast-forward of the fr-config worktree is silent

<!-- fr:journal kind=finding scope=plan id=l-security-r1 created=2026-11-25T17:37:21+00:00 state=open review_scope=in -->
### l-security-r1 · finding [open] (reviewer: in scope) · Enforced accepted an approval a later push keeps

<!-- fr:journal kind=finding scope=plan id=l-security-r2 created=2026-11-25T17:37:21+00:00 state=open review_scope=in -->
### l-security-r2 · finding [open] (reviewer: in scope) · The migration seeded fr-config from HEAD, not the default branch

<!-- fr:journal kind=finding scope=plan id=l-security-r3 created=2026-11-25T17:37:21+00:00 state=open review_scope=in -->
### l-security-r3 · finding [open] (reviewer: in scope) · ci_evidence read guarded keys without fetching or checking origin

<!-- fr:journal kind=finding scope=plan id=l-security-r4 created=2026-11-25T17:37:21+00:00 state=open review_scope=in -->
### l-security-r4 · finding [open] (reviewer: in scope) · _forge_open_pr reused an open PR with no repo or base check

<!-- fr:journal kind=finding scope=plan id=l-tests-r1 created=2026-11-25T17:37:21+00:00 state=open review_scope=in -->
### l-tests-r1 · finding [open] (reviewer: in scope) · validate-plans.sh fell back to the product's old plan-config under quiet and stealth

<!-- fr:journal kind=finding scope=plan id=l-tests-r2 created=2026-11-25T17:37:21+00:00 state=open review_scope=in -->
### l-tests-r2 · finding [open] (reviewer: in scope) · Row s1-switch-moved cited no OpenCode or Hermes test

<!-- fr:journal kind=finding scope=plan id=l-tests-r3 created=2026-11-25T17:37:21+00:00 state=open review_scope=in -->
### l-tests-r3 · finding [open] (reviewer: in scope) · The protected-clone guard did not reach child processes

<!-- fr:journal kind=finding scope=plan id=l-tests-r4 created=2026-11-25T17:37:21+00:00 state=open review_scope=in -->
### l-tests-r4 · finding [open] (reviewer: in scope) · config-homes.sh never asserted its gh log

<!-- fr:journal kind=finding scope=plan id=l-tests-r5 created=2026-11-25T17:37:21+00:00 state=open review_scope=in -->
### l-tests-r5 · finding [open] (reviewer: in scope) · test_the_cache_lives_in_memory_only grepped source

<!-- fr:journal kind=finding scope=plan id=l-tests-r6 created=2026-11-25T17:37:21+00:00 state=open review_scope=out -->
### l-tests-r6 · finding [open] (reviewer: out of scope) · fr.repos.DEFAULT_MANIFEST takes Path.home() at import

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1-resolved created=2026-11-25T17:37:21+00:00 state=fixed resolves=l-docs-accuracy-r1 -->
### l-docs-accuracy-r1-resolved · finding [fixed] · resolves l-docs-accuracy-r1: fr-isolation.md says fr refuses all unprotected executable config; guarded ci.yaml and triage.yaml keys are ignored, not refused

9142cc137: the page separates what fr refuses (candidate install, ops.yaml) from what it ignores (guarded ci.yaml and triage.yaml keys).

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2-resolved created=2026-11-25T17:37:21+00:00 state=fixed resolves=l-docs-accuracy-r2 -->
### l-docs-accuracy-r2-resolved · finding [fixed] · resolves l-docs-accuracy-r2: fr-init page and skill misdescribe scaffold under quiet and stealth

2f53f39bb, 9142cc137: scaffold under quiet refuses and names the manual pull request; under stealth it refuses before writing.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r3-resolved created=2026-11-25T17:37:21+00:00 state=fixed resolves=l-docs-accuracy-r3 -->
### l-docs-accuracy-r3-resolved · finding [fixed] · resolves l-docs-accuracy-r3: fr-isolation.md says the migration always creates the config branch first

9142cc137, 24d62e86f, 2d81ff235: the page lists the three branch cases, and says only committed default-branch bytes move and untracked files never do.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r4-resolved created=2026-11-25T17:37:21+00:00 state=fixed resolves=l-docs-accuracy-r4 -->
### l-docs-accuracy-r4-resolved · finding [fixed] · resolves l-docs-accuracy-r4: repos_cmd.py docstring names the old plan-config path

573ee39f0: repos_cmd.py and repos.py docstrings name .fr/plan-config.yaml.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1-resolved created=2026-11-25T17:37:21+00:00 state=fixed resolves=l-errors-r1 -->
### l-errors-r1-resolved · finding [fixed] · resolves l-errors-r1: A partly failed fr settings init (config branch pushed, legacy refused) cannot be retried

5efc1011c: sync has an absent state that lands the legacy copy with --yes --expect <tip>; init in that state prints the command; end-to-end tests for quiet and stealth. f6f2e5683 validates the stealth switch first (verifier v-r4).

<!-- fr:journal kind=finding scope=plan id=l-errors-r2-resolved created=2026-11-25T17:37:21+00:00 state=fixed resolves=l-errors-r2 -->
### l-errors-r2-resolved · finding [fixed] · resolves l-errors-r2: Quiet fr-config creation never raises BranchRaceError

b453fc8af: a refused push re-probes and raises BranchRaceError when origin now has fr-config.

<!-- fr:journal kind=finding scope=plan id=l-errors-r3-resolved created=2026-11-25T17:37:21+00:00 state=fixed resolves=l-errors-r3 -->
### l-errors-r3-resolved · finding [fixed] · resolves l-errors-r3: change._forge_prs_for_head swallows every forge error

7b2088573: only UnsupportedForgeOperation means no earlier proposals; other forge errors refuse.

<!-- fr:journal kind=finding scope=plan id=l-errors-r4-resolved created=2026-11-25T17:37:21+00:00 state=fixed resolves=l-errors-r4 -->
### l-errors-r4-resolved · finding [fixed] · resolves l-errors-r4: open_change's git timeouts escape as raw TimeoutExpired

7b2088573: git timeouts in open_change become a SettingsError saying nothing changed.

<!-- fr:journal kind=finding scope=plan id=l-errors-r5-resolved created=2026-11-25T17:37:21+00:00 state=fixed resolves=l-errors-r5 -->
### l-errors-r5-resolved · finding [fixed] · resolves l-errors-r5: A failed read of triage.state_repo settles the state repo durably

6788f085f: StateRepoUnread; the collect warns and does not settle.

<!-- fr:journal kind=finding scope=plan id=l-errors-r6-resolved created=2026-11-25T17:37:21+00:00 state=fixed resolves=l-errors-r6 -->
### l-errors-r6-resolved · finding [fixed] · resolves l-errors-r6: The stealth-declared triage.state_repo path is unreachable

ac7b220dc: under stealth no triage.state_repo is read (R20 amended); the dead path is removed.

<!-- fr:journal kind=finding scope=plan id=l-errors-r7-resolved created=2026-11-25T17:37:21+00:00 state=fixed resolves=l-errors-r7 -->
### l-errors-r7-resolved · finding [fixed] · resolves l-errors-r7: degraded.read_profiles reads a failed fetch as no profiles

04aa86f0e: {} only when origin says the branch is absent or no clone exists; else refuse or 'protection unknown'.

<!-- fr:journal kind=finding scope=plan id=l-errors-r8-resolved created=2026-11-25T17:37:21+00:00 state=fixed resolves=l-errors-r8 -->
### l-errors-r8-resolved · finding [fixed] · resolves l-errors-r8: settings sync preview ignores failed fetch and git log

91b80881a: failed fetch labels 'label unknown' with a warning; failed git log refuses; post-push fetch failure updates the tracking ref.

<!-- fr:journal kind=finding scope=plan id=l-errors-r9-resolved created=2026-11-25T17:37:21+00:00 state=fixed resolves=l-errors-r9 -->
### l-errors-r9-resolved · finding [fixed] · resolves l-errors-r9: settings sync --yes forge-read failure names no remedy

ad3489be2: the refusal names the preview and --expect <tip>.

<!-- fr:journal kind=finding scope=plan id=l-errors-r10-resolved created=2026-11-25T17:37:21+00:00 state=fixed resolves=l-errors-r10 -->
### l-errors-r10-resolved · finding [fixed] · resolves l-errors-r10: A failed fast-forward of the fr-config worktree is silent

0ca6f3e96: a failed ff-only names the worktree, the reason and the stash command.

<!-- fr:journal kind=finding scope=plan id=l-security-r1-resolved created=2026-11-25T17:37:21+00:00 state=fixed resolves=l-security-r1 -->
### l-security-r1-resolved · finding [fixed] · resolves l-security-r1: Enforced accepted an approval a later push keeps

1e17b090c: enforced also needs dismiss_stale_reviews_on_push or require_last_push_approval on the same rule; the captured approved reply (both false) is now the negative case; the enforced fixture is that capture with one value flipped, said in the README; R7 and section C amended; the trusted-on-adoption limit is stated beside BYPASS_LIMIT.

<!-- fr:journal kind=finding scope=plan id=l-security-r2-resolved created=2026-11-25T17:37:21+00:00 state=fixed resolves=l-security-r2 -->
### l-security-r2-resolved · finding [fixed] · resolves l-security-r2: The migration seeded fr-config from HEAD, not the default branch

4382127dd: tracked files move with the default ref's bytes and mode; 2d81ff235: an untracked file is refused (verifier v-r1, reproduced then fixed); 9607b17f9: the CI HEAD fallback is never a default ref (v-r3). R10 amended.

<!-- fr:journal kind=finding scope=plan id=l-security-r3-resolved created=2026-11-25T17:37:21+00:00 state=fixed resolves=l-security-r3 -->
### l-security-r3-resolved · finding [fixed] · resolves l-security-r3: ci_evidence read guarded keys without fetching or checking origin

218c5f0a1: _at_tip fetches the tip with fetch_tip (origin checked) once protected; a failure refuses.

<!-- fr:journal kind=finding scope=plan id=l-security-r4-resolved created=2026-11-25T17:37:21+00:00 state=fixed resolves=l-security-r4 -->
### l-security-r4-resolved · finding [fixed] · resolves l-security-r4: _forge_open_pr reused an open PR with no repo or base check

d47cf978a: open_pr_in_repo, and a found PR into another base refuses.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1-resolved created=2026-11-25T17:37:21+00:00 state=fixed resolves=l-tests-r1 -->
### l-tests-r1-resolved · finding [fixed] · resolves l-tests-r1: validate-plans.sh fell back to the product's old plan-config under quiet and stealth

8b479d384: under quiet and stealth the old plan-config is never read; repo still reads it, tested by its effect; 6583f7496: an unknown placement is treated as not repo when origin has fr or fr-config (v-r2); also fixes a BSD sed crash.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2-resolved created=2026-11-25T17:37:21+00:00 state=fixed resolves=l-tests-r2 -->
### l-tests-r2-resolved · finding [fixed] · resolves l-tests-r2: Row s1-switch-moved cited no OpenCode or Hermes test

2db984e: s1-switch-moved cites test_isolation_decision_cases.py, test_hermes_isolation_hook_edits.py and the OpenCode decision-cases.test.ts and marker.test.ts.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3-resolved created=2026-11-25T17:37:21+00:00 state=fixed resolves=l-tests-r3 -->
### l-tests-r3-resolved · finding [fixed] · resolves l-tests-r3: The protected-clone guard did not reach child processes

11f64204d: FR_TRIAGE_PROTECTED_SOURCES, set by conftest; a real child process refuses the move.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4-resolved created=2026-11-25T17:37:21+00:00 state=fixed resolves=l-tests-r4 -->
### l-tests-r4-resolved · finding [fixed] · resolves l-tests-r4: config-homes.sh never asserted its gh log

4b5fd150b: gh.log is emptied before fr run start and must hold the rules route.

<!-- fr:journal kind=finding scope=plan id=l-tests-r5-resolved created=2026-11-25T17:37:21+00:00 state=fixed resolves=l-tests-r5 -->
### l-tests-r5-resolved · finding [fixed] · resolves l-tests-r5: test_the_cache_lives_in_memory_only grepped source

95a147310: a behaviour test in child processes with a fresh HOME and cwd.

<!-- fr:journal kind=finding scope=plan id=l-tests-r6-resolved created=2026-11-25T17:37:21+00:00 state=open resolves=l-tests-r6 out_of_scope=true -->
### l-tests-r6-resolved · finding [out-of-scope] · resolves l-tests-r6: fr.repos.DEFAULT_MANIFEST takes Path.home() at import

DEFAULT_MANIFEST in fr/repos.py predates S1; S1 did not change how it is computed, and its test sets FR_REPOS_MANIFEST. Filed at deliver.
