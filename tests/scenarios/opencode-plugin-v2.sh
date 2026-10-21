#!/usr/bin/env bash
# Rows opencode-2-push-guard / -claim / -pin / -nag / -sentinel / -bind-unbind
# (spec 2026-10-20-opencode-2-support §E): the DELIVERY contract those rows ride
# on, and — when a real binary is present — that OpenCode 2 loads the delivered
# directory exactly once.
#
# What this scenario proves, always:
#   * install writes ONE plugin directory, nothing at the top level
#   * a second install is idempotent (the cli.json entry appears once)
#   * cli.json lists the plugin DIRECTORY (a file path is silently ignored by 2.x)
#   * an unparsable cli.json refuses the install, names the file, and writes nothing
#   * uninstall removes the directory and its entry and leaves a foreign entry alone
#
# What it proves only where the binary is installed (the walk container, CI's
# live job): `opencode plugin list` logs exactly one `loading plugin` line for
# this directory. Where the binary is absent it says so and continues — the
# enforcement of each hook is the bun test each row names, and the model-driven
# proof is the post-merge live rows, not this script.
#
# The delivered copy is the repo's own `scripts/deliver-opencode-plugin.sh`, so
# this scenario and install.sh cannot drift apart unnoticed.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

repo="$(cd "$here/../.." && pwd)"
deliver="$repo/scripts/deliver-opencode-plugin.sh"
[ -f "$deliver" ] || fail "no delivery script at $deliver"

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
export HOME="$world/home"
mkdir -p "$HOME"
plugins="$world/config/opencode/plugins"
cli="$world/config/opencode/cli.json"
mkdir -p "$(dirname "$plugins")"
unset FR_HARNESS_FR OPENCODE_SESSION_ID FR_OPENCODE_SESSION_ID CLAUDE_CODE_SESSION_ID

# --- install: one directory, cli.json names the directory ---------------------
run_bash() { local __var="$1"; shift; local __out; __out="$(bash "$@" 2>&1)"; RC=$?; printf -v "$__var" '%s' "$__out"; }

run_bash out "$deliver" install "$plugins"
require_exit 0 "$out"
[ -f "$plugins/fr-opencode-plugin/index.ts" ] || fail "no server entrypoint delivered"
[ -f "$plugins/fr-opencode-plugin/tui/index.tsx" ] || fail "no tui entrypoint delivered"
if compgen -G "$plugins/*.ts" >/dev/null; then
  fail "a top-level .ts was delivered: $(printf '%s ' "$plugins"/*.ts)"
fi
[ -f "$cli" ] || fail "install did not create cli.json"
entry="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); p=d.get("plugins") or []; print("\n".join(x for x in p if isinstance(x,str)))' "$cli")" \
  || fail "cli.json is not readable JSON after install"
[ "$entry" = "$plugins/fr-opencode-plugin" ] || fail "cli.json entry is '$entry', not the plugin directory"
refuse_grep '\.ts$' "$entry" "cli.json must list the directory, never a file"

# --- reinstall is idempotent --------------------------------------------------
run_bash out "$deliver" install "$plugins"
require_exit 0 "$out"
count="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(sum(1 for x in (d.get("plugins") or []) if x == sys.argv[2]))' "$cli" "$plugins/fr-opencode-plugin")"
[ "$count" = "1" ] || fail "the cli.json entry appears $count times after two installs"

# --- a foreign entry survives -------------------------------------------------
python3 - "$cli" <<'PY'
import json, sys
path = sys.argv[1]
data = json.load(open(path))
data["plugins"].append("some-other-plugin")
data["theme"] = "kept"
json.dump(data, open(path, "w"), indent=2)
PY
run_bash out "$deliver" install "$plugins"
require_exit 0 "$out"
python3 - "$cli" "$plugins/fr-opencode-plugin" <<'PY' || fail "a foreign cli.json entry or key was lost"
import json, sys
data = json.load(open(sys.argv[1]))
assert "some-other-plugin" in data["plugins"], data
assert data.get("theme") == "kept", data
assert data["plugins"].count(sys.argv[2]) == 1, data
PY

# --- uninstall removes its own, keeps the other -------------------------------
run_bash out "$deliver" uninstall "$plugins"
require_exit 0 "$out"
[ ! -e "$plugins/fr-opencode-plugin" ] || fail "uninstall left the plugin directory"
python3 - "$cli" "$plugins/fr-opencode-plugin" <<'PY' || fail "uninstall did not remove exactly its own entry"
import json, sys
data = json.load(open(sys.argv[1]))
assert data["plugins"] == ["some-other-plugin"], data
assert data.get("theme") == "kept", data
PY

# --- an unparsable cli.json refuses, names the file, writes nothing -----------
printf '// jsonc: comments are not JSON\n{"plugins": []}\n' > "$cli"
before="$(cksum < "$cli")"
run_bash out "$deliver" install "$plugins"
[ "$RC" -ne 0 ] || fail "install accepted an unparsable cli.json"
expect_grep 'cli\.json' "$out" "the refusal names the file to fix"
refuse_grep 'Traceback' "$out" "the refusal is a message, not a traceback"
[ ! -e "$plugins/fr-opencode-plugin" ] || fail "a refused install still wrote the plugin directory"
[ "$(cksum < "$cli")" = "$before" ] || fail "a refused install rewrote cli.json"

# --- the real binary, where it exists ----------------------------------------
if command -v opencode >/dev/null 2>&1; then
  rm -f "$cli"
  run_bash out "$deliver" install "$plugins"
  require_exit 0 "$out"
  export XDG_CONFIG_HOME="$world/config" XDG_DATA_HOME="$world/data" \
    XDG_STATE_HOME="$world/state" XDG_CACHE_HOME="$world/cache"
  mkdir -p "$XDG_DATA_HOME" "$XDG_STATE_HOME" "$XDG_CACHE_HOME"
  project="$world/project"
  mkdir -p "$project"
  ( cd "$project" && git init -q )
  port="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
  ( cd "$project" && opencode service set port "$port" >/dev/null 2>&1 )
  listed="$world/plugin-list.txt"
  ( cd "$project" && timeout 120 opencode plugin list ) >"$listed" 2>&1 \
    || fail "opencode plugin list failed: $(tail -3 "$listed")"
  log="$XDG_DATA_HOME/opencode/log/opencode.log"
  # The daemon logs `loading plugin` a beat AFTER the CLI has printed its list
  # (measured: ~150ms), so a straight grep races the load and reads 0. Wait for
  # it, bounded, and stop the daemon either way — a survivor inherits this
  # script's stdio and holds the runner's pipe for minutes.
  ours=""
  for _ in $(seq 1 120); do
    ours="$(grep -c 'msg="loading plugin".*fr-opencode-plugin' "$log" 2>/dev/null || true)"
    [ "${ours:-0}" -ge 1 ] && break
    sleep 0.25
  done
  state="$XDG_STATE_HOME/opencode/service.json"
  pid=""
  [ -f "$state" ] && pid="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("pid") or "")' "$state" 2>/dev/null || true)"
  ( cd "$project" && timeout 60 opencode service stop ) >/dev/null 2>&1 || true
  if [ -n "${pid:-}" ]; then
    for _ in $(seq 1 20); do kill -0 "$pid" 2>/dev/null || break; sleep 0.1; done
    kill -TERM "$pid" 2>/dev/null || true
    for _ in $(seq 1 20); do kill -0 "$pid" 2>/dev/null || break; sleep 0.05; done
    kill -KILL "$pid" 2>/dev/null || true
  fi
  [ "${ours:-0}" = "1" ] || fail "OpenCode loaded the delivered plugin ${ours:-0} times, expected exactly 1"
  if grep -q 'failed to load plugin' "$log"; then
    fail "OpenCode logged a failed plugin load: $(grep 'failed to load plugin' "$log" | tail -2)"
  fi
  echo "probed: opencode $(opencode --version 2>/dev/null | head -1) loaded the delivered directory once"
else
  echo "note: no opencode binary on PATH — the load probe is the post-merge live rows' job"
fi

echo "ok: opencode-plugin-v2"
