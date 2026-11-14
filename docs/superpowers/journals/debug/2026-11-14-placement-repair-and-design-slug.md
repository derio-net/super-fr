<!-- fr:journal-schema=4 -->
# Journal: 2026-11-14-placement-repair-and-design-slug

<!-- fr:journal kind=repro scope=debug id=6554b123e916 created=2026-11-14T01:19:24+00:00 -->
### 6554b123e916 · repro · fr repair --yes crashes under quiet and stealth: paths_dirty runs git in the product workspace

Reproduced read-only against the stealth walk workspace: `paths_dirty(<product workspace>, <tracking clone>/…/docs/superpowers)` runs `git -C <product workspace> status --porcelain -- <path outside it>`; git exits 128 and `subprocess.run(check=True)` raises an uncaught CalledProcessError. The quiet `fr` worktree is outside the product worktree too, so the same happens there.

<!-- fr:journal kind=repro scope=debug id=c66868cf85fd created=2026-11-14T01:19:26+00:00 -->
### c66868cf85fd · repro · stealth walk: fr plan self-review finds no row citing the spec though three rows cite spec:<stem>-design#R<n>

Reproduced in-process on main (= rc5) against the stealth plan: three `## Verification` grammar errors (rows citing the spec: none) and 'phase 1/2 serves no ask'. The plan parses with a RELATIVE spec_path and the product checkout as repo_root despite the absolute `spec:` in _meta.yaml, and the fold returns all three rows.

<!-- fr:journal kind=ruled-out scope=debug id=47837ccefc7f created=2026-11-14T01:19:27+00:00 -->
### 47837ccefc7f · ruled-out · the absolute spec ref in _meta.yaml is not the cause of the stealth self-review failure

fr.parser.parse resolves it below the plan's layout root (resolve_spec_ref_below) and records spec_path relative to the feature root, so every self-review check gets the same relative path it would get from a bare filename.

<!-- fr:journal kind=ruled-out scope=debug id=2a30d6146da8 created=2026-11-14T01:19:28+00:00 -->
### 2a30d6146da8 · ruled-out · the stealth placement is not the cause of the self-review failure

load_spec_matrix from the stealth workspace returns all three rows of the feature's fragment. The quiet walk passes only because its rows spell the origin spec:2026-11-13-whisper#R<n> (stem minus -design); the stealth rows spell spec:2026-11-13-textkit-whisper-cli-design#R<n>.

<!-- fr:journal kind=root-cause scope=debug id=335db4371b34 created=2026-11-14T01:19:30+00:00 -->
### 335db4371b34 · root-cause · origin_fragment compares a logical spec slug verbatim with the stem minus -design, while resolve_logical accepts both spellings

requirements.origin_fragment matches a logical origin only when fragment_slug_for_spec(spec path) == logical.slug, and fragment_slug_for_spec strips `-design`, so spec:<stem>-design never matches. fr.acceptance.logical.candidates looks for <slug>-design.md AND <slug>.md, so the same origin resolves and `fr acceptance check`, add and the step record all accept it. Two definitions of a spec's logical slug disagree; every reader of rows_citing / is_cited silently sees no row. Not placement-specific.

<!-- fr:journal kind=root-cause scope=debug id=0227e3f82f2c created=2026-11-14T01:19:31+00:00 -->
### 0227e3f82f2c · root-cause · paths_dirty asks the repo_root checkout about paths another checkout holds

archive.paths_dirty takes the product checkout as the home of every path. Under quiet and stealth the superpowers dir sits in the fr worktree / tracking clone, a different working tree (stealth: a different repository), so the pathspec is outside the repository; git exits 128 and check=True turns that into a traceback rather than a refusal.

<!-- fr:journal kind=finding scope=debug id=f-paths-dirty created=2026-11-14T01:24:58+00:00 state=fixed -->
### f-paths-dirty · finding [fixed] · paths_dirty asks each path's own checkout; a git failure is GitStatusError, and fr repair refuses (exit 2) on it

archive.paths_dirty groups paths by the checkout holding them (repo_root for a path below it, else the nearest existing directory), and raises GitStatusError (an ArchiveError) instead of CalledProcessError. fr repair --yes guards the superpowers dir AND the repo's plan-config.yaml, and prints a refusal on GitStatusError. Pinned by tests/unit/test_placement_repair_and_design_slug.py (paths_dirty_reads_a_path_held_by_another_checkout, refuses_rather_than_raising, fr_repair_yes_under_quiet_*), red before the fix with the walk's exact CalledProcessError.

<!-- fr:journal kind=finding scope=debug id=f-plan-config-home created=2026-11-14T01:25:00+00:00 state=fixed -->
### f-plan-config-home · finding [fixed] · fr repair read plan-config.yaml from the quiet/stealth feature root; it is repo configuration in the product checkout

Found auditing the other repair steps: repair_repo stripped dead keys from kind_dir('superpowers')/plan-config.yaml, i.e. the feature root under quiet/stealth, though plan-config is a REPO_CONFIG_KINDS kind read from the product checkout. repair.plan_config_path names it. The migration runner (_quiet_fr_root, _quiet_feature_groups) and fr validate artifacts were already placement-aware; fr archive moves nothing off-product (R25), so its paths_dirty callers only run under repo, where the change is behaviour-preserving.

<!-- fr:journal kind=finding scope=debug id=f-design-slug created=2026-11-14T01:25:01+00:00 state=fixed -->
### f-design-slug · finding [fixed] · a logical spec slug has one spelling: readers compare spec_slug(), writers store canonical()

fr.acceptance.logical.spec_slug (stem minus -design) and canonical(). requirements.origin_fragment and record apply's fragment choice compare spec_slug(logical.slug), as amend.py already did; record apply (fr acceptance add, set-status, step records, --origin corrections) stores canonical(to_logical(ref)), so a new spec:<stem>-design row lands in the run's own <stem>.yaml fragment. Rows already committed with the -design spelling (the live stealth walk's) now match. The frozen matrix_fragments migration's to_logical is untouched. Pinned by the design-slug tests in the same file.
