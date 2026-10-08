# 2026-10-07-cloud-triage

Implements `docs/superpowers/specs/2026-10-07-cloud-triage-design.md`: triage,
the runners and the wave driver running in a Claude Code cloud session, as one
more scope beside the host driver.

## Shape

Seven agentic phases, one per independently reviewable ask, in dependency order
(renumbered 2026-10-08 when R22 was added, decision d10):

1. **github-rest** (R1-R3), the skeleton. Everything later talks to GitHub
   through it from the cloud, so it lands first, with fixtures captured live from
   this cloud environment (GraphQL refused) and a contract test against the
   GraphQL backend's records for the same moment.
2. **CI as test evidence** (R22), placed second so phases 3-7 can prove
   themselves with the draft PR's CI rather than a ~20-minute local suite.
3. **State in the workspace, on a ref, behind the privacy guard** (R4-R8).
4. **The lease and the driver adapter** (R9-R13): `drive pass` / `drive record`,
   one policy code path shared with the host loop, the runner chosen by the
   driver rather than the repo.
5. **The claude-cloud runner** (R14-R15): a new workspace package; a mailbox the
   driver's agent executes with its session tools.
6. **Versions and drift** (R16-R18): the `run` kind's 9 -> 10 migration and the
   re-home on an incompatible major.
7. **Workers in the cloud** (R19-R21): the new `agents` artifact kind (decision
   d9), the setup script and install.sh hardening, the worker brief's first
   step, the cloud `post_merge`, the fr-triage skill and its mirrors.

No `[manual]` phase: the two `client-live` walks (Test Plan 16 and 17) are
verification rows, not phases; they run after delivery.

## Notes for the executor

- Run every `fr` command as `uv run fr` inside the workspace.
- Fixtures are captured, never constructed (P1.T3.S1). Third-party privacy: all
  captures are of `derio-net/super-fr`; nothing outside derio-net is recorded.
- Phases 2, 4, 6 and 7 are `hard`: a concurrency path (the lease and its
  compare-and-swap), a migration every cursor goes through, and a new artifact
  kind every fr-enabled repo will carry.
- Phase 6 moves the `run` kind's `current_version`: run
  `uv run fr migrate artifacts --yes` and commit the result in that phase
  (`.claude/rules/artifact-versioning.md`).
- Phase 7 replaces the `.claude/agents/` symlinks this branch committed as an
  experiment with rendered, stamped files.
