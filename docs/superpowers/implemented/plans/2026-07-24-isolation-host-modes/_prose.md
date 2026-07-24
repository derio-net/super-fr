# Isolation host modes — external containment & host-env worktrees

Spec: `docs/superpowers/specs/2026-07-24-isolation-host-modes-design.md`.

## Shape

Two new isolation modes decouple workspace isolation (worktree) from
environment provisioning (devcontainer), per the spec's mode taxonomy:

- **host-worktree** (Type 2): `HostWorktreeTarget` — the worktree half of
  `LocalWorktreeDevcontainerTarget` with the devcontainer half removed.
  Activated only by `FR_ISOLATION_TARGET=worktree` (host-level declaration;
  unknown values fail closed). Subclasses the local target to reuse
  `_git_worktree_add`, `_cold_start_base`, marker/state lifecycle; overrides
  `up` (no profile resolution, no `devcontainer up`), `exec` (plain
  subprocess), `restart`/`stats` (refuse — externally owned), `down`
  (PR guard + worktree remove + marker/state retirement, no docker probe),
  and neuters the docker-coupled gc spawn (worktree gc without docker is
  future work, noted in the spec's Non-goals posture — leaks are bounded by
  explicit `down`).
- **external** (Type 1): `ExternalTarget` — adopts a preparer-written
  `.fr-isolation` marker (`mode: external`). `up` validates (toplevel match),
  ensures the requested branch in place (`git switch -c` from the preparer's
  HEAD when needed), records state. `down` retires fr state only — the
  checkout and container belong to the preparer. Selection precedence in
  `isolation_cmd._target()`: valid external marker at cwd toplevel →
  `ExternalTarget`, regardless of `FR_ISOLATION_TARGET`.

Enforcement: the shared decision lib
(`plugins/super-fr/hooks/lib/fr-isolation-decision.sh`) gains the `external`
marker branch — toplevel match AND container evidence (`/.dockerenv`,
`/run/.containerenv`, or `$KUBERNETES_SERVICE_HOST`). One edit covers the
Claude Code and Hermes entrypoints; the OpenCode plugin (`marker.ts`) ports
the same logic with bun tests (package is outside CI — run `bun test`
manually in Phase 4 and record the output).

Tests exploit the seams that exist: the `Runner` seam in
`fr.isolation.local` (assert no `devcontainer`/`docker` argv is ever issued
by the new targets), tmp git repos for marker/worktree behavior, and
`KUBERNETES_SERVICE_HOST` as the injectable container-evidence path for hook
tests (the file probes `/.dockerenv` / `/run/.containerenv` cannot be
created in tests; env evidence exercises the same OR-chain).

## Phase order

1. `HostWorktreeTarget` + `FR_ISOLATION_TARGET` selection (fail-closed).
2. `ExternalTarget` + marker-first selection precedence (touches the same
   `_target()` — serialized after Phase 1).
3. Hook decision lib: `external` validity (+ Hermes entrypoint coverage).
4. OpenCode plugin port of the same logic (after Phase 3 fixes the semantics).
5. Skills/rules/docs (fr-isolation + fr-brainstorming SKILL.md mode-aware —
   mind the 120-line cap; rules + hand-maintained `.claude/rules/` mirror;
   `scripts/sync-opencode.py` regeneration), acceptance row levels/status
   flips, minor version bump (new user-visible workflow capability).

No manual phase: the pod-manifest env-var changes are post-merge operator
steps captured in the spec's Test Plan, not repo work.
