<!-- fr:journal-schema=4 -->
# Journal: 2026-11-14-placement-repair-and-design-slug

<!-- fr:journal kind=repro scope=debug id=6554b123e916 created=2026-11-14T01:19:24+00:00 -->
### 6554b123e916 · repro · fr repair --yes crashes under quiet and stealth: paths_dirty runs git in the product workspace

Reproduced read-only against the stealth walk workspace: `paths_dirty(<product workspace>, <tracking clone>/…/docs/superpowers)` runs `git -C <product workspace> status --porcelain -- <path outside it>`; git exits 128 and `subprocess.run(check=True)` raises an uncaught CalledProcessError. The quiet `fr` worktree is outside the product worktree too, so the same happens there.

<!-- fr:journal kind=repro scope=debug id=c66868cf85fd created=2026-11-14T01:19:26+00:00 -->
### c66868cf85fd · repro · stealth walk: fr plan self-review finds no row citing the spec though three rows cite spec:<stem>-design#R<n>

Reproduced in-process on main (= rc5) against the stealth plan: three `## Verification` grammar errors (rows citing the spec: none) and 'phase 1/2 serves no ask'. The plan parses with a RELATIVE spec_path and the product checkout as repo_root despite the absolute `spec:` in _meta.yaml, and the fold returns all three rows.
