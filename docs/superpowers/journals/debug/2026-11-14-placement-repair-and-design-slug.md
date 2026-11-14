<!-- fr:journal-schema=4 -->
# Journal: 2026-11-14-placement-repair-and-design-slug

<!-- fr:journal kind=repro scope=debug id=6554b123e916 created=2026-11-14T01:19:24+00:00 -->
### 6554b123e916 · repro · fr repair --yes crashes under quiet and stealth: paths_dirty runs git in the product workspace

Reproduced read-only against the stealth walk workspace: `paths_dirty(<product workspace>, <tracking clone>/…/docs/superpowers)` runs `git -C <product workspace> status --porcelain -- <path outside it>`; git exits 128 and `subprocess.run(check=True)` raises an uncaught CalledProcessError. The quiet `fr` worktree is outside the product worktree too, so the same happens there.
