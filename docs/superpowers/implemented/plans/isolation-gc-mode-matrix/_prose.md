# Isolation GC mode matrix

Implements `docs/superpowers/specs/2026-07-27-isolation-gc-mode-matrix-design.md`
(derio-net/super-fr#423).

The reconciler already had the right conservative semantics; what it lacked was
mode coverage and ownership-proving discovery. The plan therefore widens the
existing sweep rather than writing a second one: phase 1 makes discovery prove
fr ownership (state files, not `git worktree list`), phases 2–3 make the two
docker-less modes participate, phase 4 stabilises the CLI/JSON contract for
unattended automation, and phase 5 makes the shipped guidance match.
