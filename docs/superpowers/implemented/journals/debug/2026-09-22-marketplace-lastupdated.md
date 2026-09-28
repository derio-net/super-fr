# Journal: 2026-09-22-marketplace-lastupdated

<!-- fr:journal kind=repro scope=debug id=493ecab1216f created=2026-09-22T20:09:47 -->
### 493ecab1216f · repro · /plugin: 'Marketplace configuration file is corrupted: derio-net--super-fr.lastUpdated: Invalid input'

Right after re-running `scripts/install.sh` (fr 4.17.0), `/plugin` refused the whole marketplace registry. `~/.claude/plugins/known_marketplaces.json` showed the entries Claude Code writes itself carrying `lastUpdated`, while `derio-net--super-fr` (and `derio-net--blog-craft`, whose installer lives in its own repo) had only `source` + `installLocation`.

<!-- fr:journal kind=root-cause scope=debug id=04a2ffbec320 created=2026-09-22T20:09:48 -->
### 04a2ffbec320 · root-cause · install.sh replaces its registry entry wholesale without lastUpdated

`scripts/install.sh` writes `.[$name] = {"source":$src,"installLocation":$loc}`. That follows the AGENTS.md invariant to write the keys you own unconditionally, and correctly so, but as a wholesale replacement. It therefore also deletes any `lastUpdated` Claude Code had written, on every install. Claude Code's registry schema now requires the field, and one invalid entry invalidates the file. The operator's machine was repaired by hand first (backup kept), adding `lastUpdated` to both derio-net entries.

<!-- fr:journal kind=finding scope=debug id=f-lastupdated created=2026-09-22T20:09:48 state=fixed -->
### f-lastupdated · finding [fixed] · The registry entry is written complete, with lastUpdated

The entry now includes `lastUpdated` (the install time, in UTC with milliseconds, the format Claude Code itself writes). Pinned by `test_install_marketplace_namespace.py::TestInstallsUnderOwnName::test_registered_entry_carries_the_fields_claude_code_requires`: red first (keys `{source, installLocation}`), now green. Not fixed here: blog-craft's installer, which is a separate repo.
