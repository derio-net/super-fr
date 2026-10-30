<!-- fr:journal-schema=3 -->
# Journal: 2026-10-30-opencode-duplicate-plugin-registration

<!-- fr:journal kind=repro scope=debug id=1398c04529aa created=2026-10-30T20:59:35+00:00 -->
### 1398c04529aa · repro · Global and repo plugin definitions collide before setup

Coordinator supplied authenticated /api/plugin evidence captured 2026-10-30 21:48 CET: installed global super-fr active; repository fr-isolation-required.ts failed Duplicate plugin ID: super-fr on clean RC14 be4f159 and older rehearsal. No shared API was queried by this implementation session. Synthetic registration regression run through isolation: bun test test/registration.test.ts reports 1 pass / 3 fail, both discovery orders failing Duplicate plugin ID: super-fr. Repo-only control also fails the distinct-source-ID contract. Python dependency bootstrap completed before this journal command; container-only Bun 1.3.1 downloaded to /tmp/fr-plugin-tools, no host installation.

<!-- fr:journal kind=root-cause scope=debug id=68fd84b9b3f8 created=2026-10-30T20:59:58+00:00 -->
### 68fd84b9b3f8 · root-cause · Duplicate filtering precedes setup; explicit config can select source guards

Read official V2 build/plugins and plugins docs plus pinned 2.1.4 commit 68bc26b7da1990ce10ffecfbc1e09eb13aa5d824 packages/core/src/config/plugin/source.ts, plugin/supervisor.ts, plugin/module.ts and plugin.ts. source.scan emits all discovered entries before explicit configured operations. supervisor.resolve filters disabled IDs before duplicate detection; duplicate later occurrence becomes a failed inventory entry before setup. Registry inventory is updated only after setup, so checking ctx.plugin.list inside setup is not a reliable election. Existing idle/nag shared state cannot prevent registration failure. Hypothesis: a distinct repo-only development ID plus explicit -super-fr in repository config selects exactly one real source implementation independently of discovery order, preserving repo-only guards and global installs outside this repo. Do not change installed global definition or add setup no-ops. Regression controls are synthetic, not a supported-server smoke.
