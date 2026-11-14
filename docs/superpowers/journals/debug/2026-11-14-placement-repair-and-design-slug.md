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
