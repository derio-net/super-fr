# fr-profiles services — implementation plan

Spec: `docs/superpowers/specs/2026-09-28-fr-profiles-services-design.md`
(#774 step 1; step 2 is #795).

## Shape

Phase 1 is the walking skeleton: `fr services` over today's flat files proves
the resolver end to end before anything depends on it, and it lands the whole
read side (model, frozen v1 reader, offline ci detection, forge consumers
rerouted). Phases 2–5 then hang off it:

- **2** makes fr-profiles an artifact kind — the migration and validator the
  artifact-versioning rule requires in the same PR, plus this repo's own file
  migrated with `fr migrate artifacts --yes`.
- **3** moves the CI consumers (#787's `ci_config` seam) onto the ci service.
- **4** switches off every issue path under `tracking: none`.
- **5** teaches `fr init scaffold` to write and detect the services (needs 2's
  migration and block renderer).
- **6** is prose: skills, README, mirrors (both sync scripts), change fragment.

3 and 4 depend only on 1; they are independent of each other and of 2.

## Risks

- `detect_backend` has many callers (isolation, hostclient, acceptance); its
  signature stays fixed so none of them change.
- The migration must keep every non-service byte of a hand-edited file; it is
  text-level, not a yaml round trip.
- An older `fr` reading a migrated file loses a self-hosted forge (spec §3.D
  risk) — the change fragment's summary says so.
