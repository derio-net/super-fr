# Journal: 2026-07-24-hermes-uninstall-stale-cli

<!-- fr:journal kind=repro scope=debug id=p8-uninstall-stale-cli-repro created=2026-07-24T20:33:42 -->
### p8-uninstall-stale-cli-repro · repro · install.sh --uninstall left live Hermes hooks behind

On the live Hermes home, scripts/install.sh --uninstall removed skills/fr but printed no Hermes hooks/rules removal. hermes hooks list still showed all four active hooks. Direct fr hermes uninstall failed because the installed 3.15.1 binary read the old .hermes/cli-config.snippet.yaml path while the source checkout ships .hermes/config.snippet.yaml.

<!-- fr:journal kind=hypothesis scope=debug id=p8-uninstall-stale-cli-hypothesis created=2026-07-24T20:33:42 -->
### p8-uninstall-stale-cli-hypothesis · hypothesis · The uninstall path executes stale globally installed fr code

Confirmed: scripts/install.sh invoked command -v fr, and the traceback resolved fr/hermes.py from the base checkout's installed uv tool. The source worktree's corrected CLI was never loaded.

<!-- fr:journal kind=root-cause scope=debug id=p8-uninstall-stale-cli-root-cause created=2026-07-24T20:33:43 -->
### p8-uninstall-stale-cli-root-cause · root-cause · Uninstall was coupled to the previous installed package version

Upgrade removals may rename or change shipped inputs, so invoking the previous global fr binary against the new checkout is unsafe. Suppressing stderr made the failure appear successful and allowed skill deletion to continue.

<!-- fr:journal kind=finding scope=debug id=p8-uninstall-stale-cli-fixed created=2026-07-24T20:33:54 state=fixed -->
### p8-uninstall-stale-cli-fixed · finding [fixed] · Source-tree uninstall is fail-fast and regression-tested

Added a failing drift test, changed install.sh --uninstall to run uv run --project "$PLUGIN_ROOT/packages/fr" fr hermes uninstall, and made hook/rule removal failure fatal before deleting Hermes skills. RED reproduced the stale-binary coupling; GREEN passed. Live rerun removed all four hooks, four approvals, hook tree, rules block, and skills; unrelated config/allowlist content remained intact; corrected reinstall restored exactly four 30s hooks and four approvals.
