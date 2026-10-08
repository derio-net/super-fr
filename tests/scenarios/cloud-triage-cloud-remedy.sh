#!/usr/bin/env bash
# Row cloud-triage-cloud-remedy: in a Claude Code cloud session an fr failure caused by the
# environment names what is missing and how to fix the environment once; `fr cloud doctor`
# lists it (spec 2026-10-07-cloud-triage R23, §H). In a fresh HOME with
# CLAUDE_CODE_REMOTE=true, doctor exits 1 naming forge.api and the plugin; the script
# `fr cloud setup-script` prints is then run with its network steps stubbed (apt-get, curl
# and gh are shims; super-fr's "clone" is a local repo whose install.sh registers the
# plugin), and doctor exits 0. A forced GraphQL 403 prints the remedy block in the cloud
# session and none without CLAUDE_CODE_REMOTE.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
export HOME="$world/home" CLAUDE_CODE_REMOTE=true
unset FR_FORGE_API
mkdir -p "$HOME" "$world/bin"
export PATH="$world/bin:$PATH"

# --- the network, stubbed ----------------------------------------------------------
cat > "$world/bin/gh" <<'SH'
#!/usr/bin/env bash
echo "gh: HTTP 403: Forbidden (https://api.github.com/graphql)" >&2
exit 1
SH
cat > "$world/bin/apt-get" <<SH
#!/usr/bin/env bash
for tool in rsync jq; do
  command -v "\$tool" >/dev/null 2>&1 || printf '#!/bin/sh\nexit 0\n' > "$world/bin/\$tool"
  chmod +x "$world/bin/\$tool" 2>/dev/null || true
done
SH
printf '#!/bin/sh\necho "exit 0"\n' > "$world/bin/curl"
chmod +x "$world/bin/"*
# super-fr's source: a local origin whose install.sh registers the plugin as the real one does.
git init -q --bare -b main "$world/origin.git" || fail "bare origin"
src="$world/seed"
git init -q -b main "$src" || fail "seed repo"
mkdir -p "$src/scripts"
cat > "$src/scripts/install.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
f="$HOME/.claude/plugins/installed_plugins.json"
[ -f "$f" ] && [ -f "$HOME/.claude/settings.json" ] || { echo "missing registration files" >&2; exit 1; }
printf '{"version":2,"plugins":{"super-fr@derio-net--super-fr":[{"version":"stub"}]}}\n' > "$f"
SH
git -C "$src" add -A && git -C "$src" commit -qm seed || fail "seed commit"
git -C "$src" push -q "$world/origin.git" main || fail "seed push"
mkdir -p "$HOME/.cache/fr/src"
git clone -q "$world/origin.git" "$HOME/.cache/fr/src/super-fr" || fail "pre-clone"

# --- before: the environment is missing its prerequisites ---------------------------
run_fr out cloud doctor
require_exit 1 "$out"
expect_grep 'FAIL forge\.api' "$out" "doctor names forge.api"
expect_grep 'FAIL plugin' "$out" "doctor names the plugin"
expect_grep 'This is a Claude Code cloud session' "$out" "doctor ends with the remedy"

# --- the setup script, run ----------------------------------------------------------
run_fr script cloud setup-script
require_exit 0 "$script"
printf '%s\n' "$script" > "$world/setup.sh"
bash "$world/setup.sh" > "$world/setup.log" 2>&1 || { cat "$world/setup.log" >&2; fail "the setup script failed"; }
grep -qx 'api: rest' "$HOME/.config/fr/forge.yaml" || fail "the script did not write api: rest"

run_fr out init agents
require_exit 0 "$out"
run_fr out cloud doctor
require_exit 0 "$out"
expect_grep 'every cloud prerequisite holds' "$out" "doctor passes after the setup script"

# --- a GraphQL 403: the block in the cloud, none on a host --------------------------
export FR_FORGE_API=graphql
run_fr out triage collect --repo derio-net/super-fr --dir "$world/state"
[ "$RC" -ne 0 ] || fail "collect passed over a 403: $out"
[ "$(printf '%s\n' "$out" | grep -c 'This is a Claude Code cloud session')" -eq 1 ] \
  || { printf '%s\n' "$out" >&2; fail "the cloud 403 does not end with the remedy block once"; }
expect_grep 'forge\.api: rest' "$out" "the block names forge.api"

unset CLAUDE_CODE_REMOTE
run_fr out triage collect --repo derio-net/super-fr --dir "$world/state"
[ "$RC" -ne 0 ] || fail "collect passed over a 403 on the host: $out"
refuse_grep 'cloud session' "$out" "a host never prints the remedy block"

echo "ok: cloud-triage-cloud-remedy"
