#!/bin/bash
# Deliver (or remove) fr-opencode-plugin into an OpenCode plugins directory.
#
# `fr harness parity` credits OpenCode's edit gate and idle adapter from the
# plugin's source, but install.sh used to copy only skills, commands and agents,
# so no consumer ever received the plugin (gh#563). This is the delivery step.
#
# OpenCode (verified live on 1.18.32) registers and imports only TOP-LEVEL
# *.ts / *.js files in its global plugins directory and does not scan
# subdirectories. So the delivered shape is:
#
#   <plugins>/fr-opencode-plugin.ts      the loader — the one file OpenCode loads
#   <plugins>/fr-opencode-plugin/*.ts    the sources, skipped by the scan
#
# The loader is the same default re-export this repo's own
# .opencode/plugins/fr-isolation-required.ts uses. OpenCode runs plugins on
# Bun, which runs TypeScript directly: no build step and no `bun` on the
# consumer's PATH.
#
# Usage: deliver-opencode-plugin.sh install|uninstall <plugins-dir>
#
# - install replaces the source directory wholesale, so a file removed
#   upstream does not linger; it is idempotent.
# - uninstall removes exactly the two paths install writes and nothing else;
#   with nothing installed it is a no-op.

set -eu

usage="usage: deliver-opencode-plugin.sh install|uninstall <plugins-dir>"
action="${1:?$usage}"
plugins="${2:?$usage}"

src="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/packages/fr-opencode-plugin/src"
name="fr-opencode-plugin"

case "$action" in
  install)
    [ -d "$src" ] || { echo "deliver-opencode-plugin: no plugin sources at $src" >&2; exit 1; }
    mkdir -p "$plugins"
    rm -rf "${plugins:?}/$name"
    mkdir -p "$plugins/$name"
    cp "$src"/*.ts "$plugins/$name/"
    cat > "$plugins/$name.ts" <<'EOF'
// Installed by super-fr's install.sh (scripts/deliver-opencode-plugin.sh).
// Re-running it overwrites this file and ./fr-opencode-plugin/; do not edit.
// OpenCode loads only top-level modules here, so this loader is the plugin
// and the sources beside it are its imports (gh#563).
export { FrIsolationRequired as default } from "./fr-opencode-plugin/index";
EOF
    ;;
  uninstall)
    rm -rf "${plugins:?}/$name" "${plugins:?}/$name.ts"
    ;;
  *)
    echo "$usage" >&2
    exit 2
    ;;
esac
