<!-- fr:journal-schema=3 -->
# Journal: 2026-10-30-opencode-duplicate-plugin-registration

<!-- fr:journal kind=repro scope=debug id=1398c04529aa created=2026-10-30T20:59:35+00:00 -->
### 1398c04529aa · repro · Global and repo plugin definitions collide before setup

Coordinator supplied authenticated /api/plugin evidence captured 2026-10-30 21:48 CET: installed global super-fr active; repository fr-isolation-required.ts failed Duplicate plugin ID: super-fr on clean RC14 be4f159 and older rehearsal. No shared API was queried by this implementation session. Synthetic registration regression run through isolation: bun test test/registration.test.ts reports 1 pass / 3 fail, both discovery orders failing Duplicate plugin ID: super-fr. Repo-only control also fails the distinct-source-ID contract. Python dependency bootstrap completed before this journal command; container-only Bun 1.3.1 downloaded to /tmp/fr-plugin-tools, no host installation.
