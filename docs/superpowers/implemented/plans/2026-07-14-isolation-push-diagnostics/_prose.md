# fr-isolation: backend-neutral host-push docs + read-only push preflight diagnostic

Spec: `docs/superpowers/specs/2026-07-14-isolation-push-diagnostics-design.md`

## Why

Issue #377: `fr isolation exec -- git push` fails against a GitLab backend
with an SSH permission error, while the same push from the HOST succeeds.
That's the framework working as designed — push is meant to happen
host-side, so operator credentials never enter the container implicitly —
but the rule (`fr-isolation` SKILL.md's "Exec-bridge discipline") is written
in GitHub-only language ("GitHub interaction", `gh`) even though #372 added
first-class GitLab/Gitea backends, and there is no live diagnostic that tells
an agent WHY a push failed or what to do instead. This plan closes both gaps
without touching runtime auth behavior — no known_hosts provisioning, no
agent forwarding, nothing that puts credentials inside the container.

## Shape of the change

- **Phase 1** rewrites the exec-bridge discipline text to name all three
  backends and cover `git push` over SSH explicitly, then regenerates the
  OpenCode mirror (`scripts/sync-opencode.py`) so both surfaces stay in sync
  per the repo's canonical-source/generated-mirror convention.
- **Phase 2** adds a read-only `fr isolation status --push-check` diagnostic:
  a new `push_check()` method on `LocalWorktreeDevcontainerTarget`
  (`packages/fr/src/fr/isolation/local.py`) reporting the worktree's git
  remotes, whether an SSH agent socket is visible in-container (presence/
  absence only — informational, not an error), and backend-aware guidance
  pointing at the host-side push workflow — wired into the existing `status`
  command in `packages/fr/src/fr/commands/isolation_cmd.py`, mirroring how
  `--stats` already works as an opt-in extra.
- **Phase 3** bumps the version (this changes shipped skill text and CLI
  behavior) and runs the full verification suite before handoff.

## Phase order and why

1. **Docs** first — it's the fix an agent hitting #377's exact symptom needs
   immediately, has no code dependency, and Phase 2's SKILL.md pointer
   ("see `fr isolation status --push-check`") reads correctly once this
   phase lands (the flag doesn't need to exist yet for the doc edit itself,
   but sequencing docs-then-diagnostic keeps the plan's own dependency
   graph honest about what depends on what).
2. **Diagnostic** — TDD across two seams (the `Target` method, then the CLI
   flag), each with its own RED/GREEN task pair, matching this codebase's
   existing `--stats` precedent closely enough that a reviewer can diff the
   two additions side by side.
3. **Version bump + verification** — last, once the diff is final, per
   AGENTS.md's release rule and `superpowers:verification-before-completion`.

## Testing strategy

No live GitLab/SSH server or real devcontainer needed anywhere in this plan
— `push_check()` is a reporting feature over already-mocked seams (the
`Runner` callable for git, `devcontainer exec`, and `fr._hosts.detect_backend`
which needs no network access). Phase 2's tests extend
`tests/unit/test_isolation.py` and `tests/unit/test_isolation_cmd.py`,
already cited by the acceptance matrix's `isolation-suite-lifecycle` row —
no matrix edit needed (see spec §Acceptance rows).

## Non-goals (see spec for full list)

No SSH known_hosts provisioning, no agent forwarding, no
StrictHostKeyChecking changes, no short-lived-credential mechanism, no new
top-level `fr isolation` subcommand. The diagnostic never prints key
material, tokens, or ssh-agent socket paths/contents — presence/absence
only, verified by exact-dict-equality tests (not substring checks) in Phase
2.
