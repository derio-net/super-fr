# Journal: 2026-07-23-marketplace-config-clobber

<!-- fr:journal kind=repro scope=debug id=repro-1 created=2026-07-23T17:52:26 -->
### repro-1 · repro · super-fr and blog-craft installers mutually evict each other from the derio-net marketplace

Both repos ship an install.sh that claims the SAME Claude Code marketplace
identity `derio-net` and the SAME on-disk tree
`~/.claude/plugins/marketplaces/derio-net`, then populate it with
`rsync -a --delete <own repo root>/ $MARKETPLACE_DIR/`.

- super-fr `scripts/install.sh:27,280-281`
- blog-craft `scripts/install.sh:22,146-147`

Repro (no synthetic setup needed — the host is in the failed state now):
1. Run blog-craft `scripts/install.sh`  -> marketplaces/derio-net holds blog-craft;
   its `.claude-plugin/marketplace.json` lists ONLY plugin `blog-craft`.
2. Run super-fr `scripts/install.sh`    -> `--delete` wipes that tree; manifest now
   lists ONLY `super-fr` + `super-fr-dispatch`.
3. `blog-craft@derio-net` is still enabled in settings.json and still present in
   installed_plugins.json, but no longer resolvable from the marketplace manifest.

Observed host state 2026-07-23:
- marketplaces/derio-net/ contains super-fr's tree (packages/, uv.lock, AGENTS.md)
- its marketplace.json lists super-fr + super-fr-dispatch only
- installed_plugins.json still has `blog-craft@derio-net` (installed 2026-07-20)
  -> cache/derio-net/blog-craft/current   [DANGLING]
- settings.json enabledPlugins["blog-craft@derio-net"] = true  [DANGLING]
- blog-craft skills still load only because a SECOND, legacy marketplace named
  `blog-craft` (directory source -> the live repo) is also registered.

<!-- fr:journal kind=root-cause scope=debug id=rc-1 created=2026-07-23T17:54:03 -->
### rc-1 · root-cause · Two repos claim one marketplace identity; the installer that runs last rsync --delete's the other out

A Claude Code marketplace name is a 1:1 namespace over a single source repo.
Its manifest — `plugins/marketplaces/<name>/.claude-plugin/marketplace.json` —
is ONE file listing ALL plugins of that marketplace, and it can only be
authored by one repo.

super-fr and blog-craft both hardcode `derio-net` as that name:

  super-fr   install.sh:27   MARKETPLACE_DIR=.../marketplaces/derio-net
  blog-craft install.sh:22   MARKETPLACE_DIR=.../marketplaces/derio-net

and both populate it with `rsync -a --delete <own repo root>/ $MARKETPLACE_DIR/`
(super-fr:280, blog-craft:146). `--delete` is total: it does not merge manifests,
it replaces the whole tree. So the loser's plugins vanish from the manifest while
their `enabledPlugins` + `installed_plugins.json` entries survive — a dangling
reference, not a clean uninstall.

Note blog-craft is the party in the wrong: its OWN `.claude-plugin/marketplace.json`
declares `"name": "blog-craft"`, contradicting the `derio-net` key its installer
registers. super-fr's manifest declares `"name": "derio-net"` — self-consistent.

<!-- fr:journal kind=finding scope=debug id=find-1 created=2026-07-23T17:54:04 state=open -->
### find-1 · finding [open] · Compounding: skip-if-present registry writes let a wrong source repo persist

Both installers guard the registry write with `if ! jq -e .["derio-net"]` —
first-writer-wins. So whichever repo registered `derio-net` FIRST owns the
`source.repo` pointer forever, even after the other repo wins the directory race.

Live consequence: `known_marketplaces.json["derio-net"].source.repo` is
`derio-net/super-fr` while blog-craft (if it installed last) would own the
directory. A `/plugin marketplace update derio-net` then re-fetches super-fr from
GitHub and silently evicts blog-craft a second time — with no installer run at all.

Fix: an installer must write its OWN key unconditionally, not skip when present.

<!-- fr:journal kind=finding scope=debug id=find-2 created=2026-07-23T17:54:06 state=open -->
### find-2 · finding [open] · Worse blast radius: blog-craft --uninstall deregisters the whole derio-net marketplace

blog-craft `scripts/install.sh:64-71` on `--uninstall` runs

    jq "del(.[\"derio-net\"])"                      known_marketplaces.json
    jq "del(.extraKnownMarketplaces[\"derio-net\"])" settings.json

i.e. uninstalling blog-craft deregisters the ENTIRE derio-net marketplace,
taking `super-fr@derio-net` and `super-fr-dispatch@derio-net` down with it.
Same root cause (shared namespace), larger blast radius than the reported bug.
An uninstaller must only remove keys it owns.

<!-- fr:journal kind=finding scope=debug id=fix-super-fr created=2026-07-23T18:04:29 state=fixed -->
### fix-super-fr · finding [fixed] · super-fr side: assert own registry keys, warn before reclaiming, report orphans non-destructively

super-fr keeps the `derio-net` name — it is the self-consistent owner — and
gains three guards in `scripts/install.sh`:

1. **Registry writes are unconditional** (was skip-if-present). A wrong
   `source.repo` left by another repo is now corrected on every install, closing
   the `/plugin marketplace update derio-net` re-eviction path. Prints
   "Reclaimed derio-net ... (was <repo>)" when it actually changed something.
2. **Foreign-occupant warning** before the `rsync --delete`: if the marketplace
   dir holds a manifest whose `.name != "derio-net"`, name the squatter and say
   whose plugins are about to stop resolving. Advisory — we still reclaim, or a
   squat would permanently break super-fr installs.
3. **Orphan report**: any `X@derio-net` in installed_plugins.json /
   enabledPlugins that our manifest does not list is named, with both remedies.
   Deliberately NOT deleted — that is another repo's install state.

Failing test written first: `tests/integration/test_install_marketplace_namespace.py`
(11 tests; 4 red before the fix, all green after). Full suite 1599 passed / 80
skipped. Version 3.12.0 -> 3.12.1 (install.sh is user-observable).
