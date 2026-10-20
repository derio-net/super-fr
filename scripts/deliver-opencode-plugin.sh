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

# The cli.json entry is the plugin directory's absolute path. It is derived
# from the plugins directory's PARENT, so uninstall can still name it after the
# plugins directory itself was removed by hand or by another tool.
entry_path() {
  printf '%s/%s/%s' "$(cd "$(dirname "$plugins")" && pwd)" "$(basename "$plugins")" "$name"
}

# Refuse BEFORE a byte moves: an existing cli.json that is not a JSON object
# with a `plugins` array (JSONC with comments, a typo) stops install here, with
# the file and the remedy named, and nothing on disk changed.
validate_cli_json() {
  [ -e "$cli_json" ] || return 0
  if ! jq -e 'type == "object" and ((.plugins // []) | type == "array")' "$cli_json" >/dev/null 2>&1; then
    echo "deliver-opencode-plugin: refusing to install: $cli_json is not a plain JSON object with a \`plugins\` array (comments/JSONC are not supported). Nothing was written. Fix that file by hand (or move it aside) and re-run install." >&2
    exit 1
  fi
}

# Write $1 (a jq filter, with --arg e "$entry") into cli.json without breaking
# it: a symlinked cli.json (dotfiles managers) stays a symlink and its TARGET
# is rewritten; the target's mode survives (a 0600 file stays 0600).
write_cli_json() {
  local filter="$1" entry="$2" real link mode tmp
  real="$cli_json"
  while [ -L "$real" ]; do
    link="$(readlink "$real")"
    case "$link" in
      /*) real="$link" ;;
      *) real="$(dirname "$real")/$link" ;;
    esac
  done
  mode="$(stat -f '%Lp' "$real" 2>/dev/null || stat -c '%a' "$real")"
  tmp="$real.fr-tmp.$$"
  if jq --arg e "$entry" "$filter" "$real" >"$tmp"; then
    chmod "$mode" "$tmp"
    mv "$tmp" "$real"
  else
    rm -f "$tmp"
    return 1
  fi
}

register() {
  [ -e "$cli_json" ] || printf '{}\n' >"$cli_json"
  # Drop every exact copy of our entry, then append one (spec §E); any other
  # entry — strings, objects, numbers, nulls — is kept as it was.
  write_cli_json '.plugins = (((.plugins // []) | map(select(. != $e))) + [$e])' "$(entry_path)"
}

unregister() {
  local entry
  [ -f "$cli_json" ] || return 0
  entry="$(entry_path)"
  if ! jq -e 'type == "object"' "$cli_json" >/dev/null 2>&1; then
    echo "deliver-opencode-plugin: leaving $cli_json alone: it is not a JSON object" >&2
    return 0
  fi
  jq -e --arg e "$entry" '(.plugins // []) | type == "array" and any(. == $e)' "$cli_json" >/dev/null 2>&1 || return 0
  write_cli_json '.plugins = (.plugins | map(select(. != $e)))' "$entry"
}

case "$action" in
  install)
    [ -d "$src" ] || { echo "deliver-opencode-plugin: no plugin sources at $src" >&2; exit 1; }
    [ -f "$segment" ] || { echo "deliver-opencode-plugin: no status-line segment at $segment" >&2; exit 1; }
    command -v jq >/dev/null 2>&1 || { echo "deliver-opencode-plugin: jq is required" >&2; exit 1; }
    validate_cli_json
    mkdir -p "$plugins"
    rm -rf "${plugins:?}/$name" "${plugins:?}/$name.ts"
    mkdir -p "$plugins/$name/tui"
    cp "$src"/*.ts "$plugins/$name/"
    cp "$src"/tui/*.ts "$src"/tui/*.tsx "$plugins/$name/tui/"
    cp "$segment" "$plugins/$name/tui/"
    register
    ;;
  uninstall)
    command -v jq >/dev/null 2>&1 && unregister
    rm -rf "${plugins:?}/$name" "${plugins:?}/$name.ts"
    ;;
  *)
    echo "$usage" >&2
    exit 2
    ;;
esac
