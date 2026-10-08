#!/usr/bin/env bash
# fr's Claude Code cloud environment setup{for_repo}, printed by `fr cloud setup-script`.
# Paste it into the cloud environment's setup script (the environment menu in a
# session's title bar -> Edit -> Setup script). Every NEW session runs it before its
# first turn; a running session does not. Spec 2026-10-07-cloud-triage §H, R19, R23.
set -euo pipefail

# 1. rsync and jq (install.sh copies the plugin with them), and uv (it installs fr).
missing=""
for cmd in rsync jq; do
  command -v "$cmd" >/dev/null 2>&1 || missing="$missing $cmd"
done
if [ -n "$missing" ]; then
  apt-get update -qq
  # shellcheck disable=SC2086  # one word per package
  apt-get install -y -qq $missing
fi
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

# 2. The two files Claude Code registers a plugin in: a fresh container has neither,
#    and install.sh refuses to run without them.
mkdir -p "$HOME/.claude/plugins"
[ -f "$HOME/.claude/plugins/installed_plugins.json" ] \
  || echo '{"version":2,"plugins":{}}' > "$HOME/.claude/plugins/installed_plugins.json"
[ -f "$HOME/.claude/settings.json" ] || echo '{}' > "$HOME/.claude/settings.json"

# 3. super-fr from source, then its installer: the fr CLI, the derio-net--super-fr
#    plugin and its rules. The clone lives outside the marketplace directory, which
#    install.sh replaces.
src="$HOME/.cache/fr/src/super-fr"
if [ -d "$src/.git" ]; then
  git -C "$src" fetch --quiet origin main
  git -C "$src" checkout --quiet --force -B main origin/main
else
  rm -rf "$src"
  mkdir -p "$(dirname "$src")"
  git clone --quiet --branch main {source} "$src"
fi
bash "$src/scripts/install.sh"

# 4. The cloud proxy refuses GitHub's GraphQL API (HTTP 403): fr talks REST.
forge="$HOME/.config/fr/forge.yaml"
mkdir -p "$(dirname "$forge")"
if [ -f "$forge" ] && grep -q '^api:' "$forge"; then
  sed -i.bak 's/^api:.*/api: rest/' "$forge" && rm -f "$forge.bak"
else
  echo 'api: rest' >> "$forge"
fi

echo "fr cloud setup: done ($(command -v fr || echo 'fr not on PATH: add ~/.local/bin'))"
