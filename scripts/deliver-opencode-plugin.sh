#!/bin/bash
# Deliver (or remove) fr-opencode-plugin into an OpenCode 2 plugins directory.
#
# `fr harness parity` credits OpenCode's edit gate and idle adapter from the
# plugin's source, but install.sh used to copy only skills, commands and agents,
# so no consumer ever received the plugin (gh#563). This is the delivery step.
#
# OpenCode 2 (measured on 2.1.0) treats every DIRECTORY in its plugins
# directory as one plugin and resolves its entrypoints by name: the server
# loads `<dir>/server` or else `<dir>/index`, the TUI loads `<dir>/tui`. So the
# delivered shape is ONE directory and nothing at the top level:
#
#   <plugins>/fr-opencode-plugin/index.ts      the server plugin (+ its modules)
#   <plugins>/fr-opencode-plugin/tui/index.tsx the status line (TUI only)
#
# The 1.x shape also wrote a top-level loader, `<plugins>/fr-opencode-plugin.ts`,
# beside the directory. On 2.x that loads the plugin TWICE (plan finding
# p1-v2-loads-sources-dir-as-plugin), so install deletes a stale one.
#
# install also lists the directory in `<config>/cli.json`'s `plugins` (the
# config beside <plugins>), the TUI's own enablement directive (spec R12). The
# TUI already discovers the directory; the entry is what `fr harness parity`'s
# status-line probe reads, and OpenCode de-duplicates the two (measured).
# A file path there is silently ignored by 2.1.0 — it must be the directory.
#
# Usage: deliver-opencode-plugin.sh install|uninstall <plugins-dir>
#
# - install replaces the plugin directory wholesale, so a file removed upstream
#   does not linger; it is idempotent, and so is the cli.json entry (by exact
#   path). An unparsable cli.json is refused with the file named, never
#   overwritten.
# - uninstall removes exactly what install writes (and the 1.x loader) and only
#   its own cli.json entry; with nothing installed it is a no-op.

set -eu

usage="usage: deliver-opencode-plugin.sh install|uninstall <plugins-dir>"
action="${1:?$usage}"
plugins="${2:?$usage}"

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
src="$root/packages/fr-opencode-plugin/src"
segment="$root/plugins/super-fr/scripts/fr-statusline-segment.sh"
name="fr-opencode-plugin"
cli_json="$(dirname "$plugins")/cli.json"

# The cli.json entry is the plugin directory's absolute path.
entry_path() {
  printf '%s/%s' "$(cd "$plugins" && pwd)" "$name"
}

register() {
  local entry tmp
  entry="$(entry_path)"
  if [ -e "$cli_json" ]; then
    if ! jq -e 'type == "object" and ((.plugins // []) | type == "array")' "$cli_json" >/dev/null 2>&1; then
      echo "deliver-opencode-plugin: refusing to edit $cli_json: it is not a JSON object with a \`plugins\` array; fix it by hand and re-run" >&2
      exit 1
    fi
  else
    printf '{}\n' >"$cli_json"
  fi
  tmp="$cli_json.fr-tmp.$$"
  jq --arg e "$entry" '.plugins = ((.plugins // []) | if index($e) then . else . + [$e] end)' \
    "$cli_json" >"$tmp" && mv "$tmp" "$cli_json"
}

unregister() {
  local entry tmp
  [ -f "$cli_json" ] || return 0
  [ -d "$plugins" ] || return 0
  entry="$(entry_path)"
  if ! jq -e 'type == "object"' "$cli_json" >/dev/null 2>&1; then
    echo "deliver-opencode-plugin: leaving $cli_json alone: it is not a JSON object" >&2
    return 0
  fi
  jq -e --arg e "$entry" '(.plugins // []) | index($e)' "$cli_json" >/dev/null 2>&1 || return 0
  tmp="$cli_json.fr-tmp.$$"
  jq --arg e "$entry" '.plugins = (.plugins | map(select(. != $e)))' "$cli_json" >"$tmp" \
    && mv "$tmp" "$cli_json"
}

case "$action" in
  install)
    [ -d "$src" ] || { echo "deliver-opencode-plugin: no plugin sources at $src" >&2; exit 1; }
    [ -f "$segment" ] || { echo "deliver-opencode-plugin: no status-line segment at $segment" >&2; exit 1; }
    command -v jq >/dev/null 2>&1 || { echo "deliver-opencode-plugin: jq is required" >&2; exit 1; }
    mkdir -p "$plugins"
    rm -rf "${plugins:?}/$name" "${plugins:?}/$name.ts"
    mkdir -p "$plugins/$name/tui"
    cp "$src"/*.ts "$plugins/$name/"
    cp "$src"/tui/*.ts "$src"/tui/*.tsx "$plugins/$name/tui/"
    cp "$segment" "$plugins/$name/tui/"
    register
    ;;
  uninstall)
    unregister
    rm -rf "${plugins:?}/$name" "${plugins:?}/$name.ts"
    ;;
  *)
    echo "$usage" >&2
    exit 2
    ;;
esac
