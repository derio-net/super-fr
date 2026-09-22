# Journal: opencode-symlink-edit-gate

<!-- fr:journal kind=repro scope=debug id=54a3844624f9 created=2026-09-22T14:57:05 -->
### 54a3844624f9 · repro · Dangling worktree symlink bypasses the OpenCode gate

A valid marked worktree can write through a dangling symlink into the base clone: normalizeTarget only called realpath when existsSync succeeded, leaving dangling link paths attributed to the worktree.

<!-- fr:journal kind=root-cause scope=debug id=06d828688e6c created=2026-09-22T14:57:05 -->
### 06d828688e6c · root-cause · Both gate implementations inspect the symlink parent

OpenCode used existsSync before realpath, which fails for dangling symlinks; the shared Claude/Hermes decision library likewise gated the symlink parent rather than its destination.

<!-- fr:journal kind=finding scope=debug id=5781481fab77 created=2026-09-22T15:49:29 state=fixed -->
### 5781481fab77 · finding [fixed] · Symlink destinations are gated before marker validation

OpenCode now follows symlink chains with lstat/readlink and rejects chains over 40 hops. The shared Claude/Hermes decision library applies equivalent dangling-link-aware normalization. Real linked-worktree tests cover non-dangling and dangling base-clone targets plus an in-worktree symlink.

<!-- fr:journal kind=review scope=debug id=e54d7ffd5762 created=2026-09-22T16:11:03 -->
### e54d7ffd5762 · review · Review found no remaining issues

Reviewed target extraction and normalization against #559 regressions. OpenCode and shared Claude/Hermes paths retain relative resolution, patch parsing, argument collection, and read-only tool behavior; no further findings.
