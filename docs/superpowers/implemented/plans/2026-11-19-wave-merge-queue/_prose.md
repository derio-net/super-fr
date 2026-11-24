# Wave merge queue — implementation plan

Spec: `docs/superpowers/specs/2026-11-19-wave-merge-queue-design.md` (R1–R36), issue #1576.

## Shape

Seven agentic phases, each one independently reviewable ask, in dependency order:

1. **State model and approval by content** (skeleton). Judgements schema 13 (the
   `queues:` list and its snake_case event kinds), `Checkout.patch_id`, and the
   content-pinned `approval_verdict`. Every later phase reads these models.
2. **The pure planner** `fr.triage.wave_queue`: wave choice, slots and depth, the
   longest green prefix, foreign moves, ejection, drain, stall proposals and the cap
   exemption. No git and no forge, so every rule is unit-tested.
3. **The executor** `fr.triage.queue_exec`: building into slots, the atomic leased
   landing push, `land: merge`, checks on combinations, `post_merge` once per
   landing, forge read-back and held reasons, and crash resumption.
4. **The hold handshake**: the driver's hold states, `fr release status`, and this
   repo's `release.py`/`release.yml`.
5. **One merge path**: close-out, archive, export and housekeeping PRs become
   entries; the old train, the forge-queue mode and `batch merge`'s own loop are
   removed.
6. **Gates and the wave close-out**: the DevOps barrier through labels,
   one close-out per wave, `fr migrate artifacts --path`,
   `fr validate artifacts --allow-migratable`, and queue CI triggers on this repo.
7. **The operator's view**: `defer`/`requeue`, the queue line, the Needs, the PR
   marker comment, the wave report, the skill and docs, and this repo's `queue:`
   config, which turns the queue on here.

## Risks

- Phase 2 wires the planner into `drive_pass` before phase 3 executes it. Between
  those two commits the driver only reports, so never cut a release between them.
  The whole plan ships in one PR.
- Phase 5 deletes the old merge paths. Its tests must keep every behaviour the
  spec keeps (approval voiding, conflict and red budgets, version slots).
- The live proof is the post-merge row `wave-queue-live-wave`, walked on the next
  wave on this repo after merge (gate: tester).
