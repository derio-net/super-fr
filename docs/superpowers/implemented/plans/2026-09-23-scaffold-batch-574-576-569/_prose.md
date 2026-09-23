# Scaffold batch — gh#574, gh#576, gh#569

Spec: `docs/superpowers/specs/2026-09-23-scaffold-batch-574-576-569-design.md`.

Three bugs, one theme: fr accepts input, reports success, and does nothing
useful with it. This plan fixes all three and delivers them in one PR.

**Phase 1 (walking skeleton)** adds the smallest real piece: an optional
`IsolationState.target` field and a pure `recorded_mode(state)`. Nothing routes
through them yet. It proves the test/CI loop on a change that everything in
phase 2 builds on.

**Phase 2 (#569)** makes every command that addresses an existing workspace
choose its backend from that workspace's recorded mode:

- the addressing commands are `exec`, `restart`, `status`, `down` in all three
  forms, and `verify-merge`;
- that includes the reap sibling of gc and the background gc it spawns, which
  the spec review showed would otherwise leak containers or crash docker-less
  sweeps;
- `FR_ISOLATION_TARGET` keeps meaning only where no workspace exists: `up`, gc
  discovery, and a reaped `verify-merge`.

**Phases 3–4 (#574)** make `fr init scaffold` refuse any tool it cannot honour:

- they add the `--feature` escape and the java/maven mapping (Maven implies
  Java), plus `@version`;
- they detect the project's Java major from version files and `pom.xml`;
- they teach the fr-init interview to confirm that major from the project
  notes.

**Phase 5 (#576)** replaces the hardcoded amd64 glab/tea installs with
per-architecture pins and a POSIX-sh renderer:

- an unsupported architecture fails by name;
- a weekly workflow checks that the pinned assets still hash to what fr
  expects.

**Phase 6** is delivery:

- live proofs on this arm64 host, through `fr isolation exec`, as the issues'
  Acceptance lists ask;
- acceptance-matrix flips;
- prose currency;
- the minor version bump.

Ordering: phases 2, 3 and 5 depend only on phase 1 and touch disjoint files
(`isolation_cmd`/`local`/`routing` vs `scaffold`'s tool half vs `scaffold`'s
host-CLI half). Phase 4 builds on phase 3's resolver. Phase 6 needs everything.
All phases run serially in the one shared workspace.
