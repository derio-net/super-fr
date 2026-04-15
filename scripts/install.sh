#!/usr/bin/env bash
# Install superpowers-for-vk extras that the plugin system can't handle.
# Skills are delivered by the plugin system (enabledPlugins in settings.json).
# This script handles: marketplace + plugin registration, stale cache cleanup,
# rules, MCP config, vk CLI, stale skill cleanup, and PostToolUse hook hint.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CLAUDE_DIR="$HOME/.claude"
RULES_DIR="$CLAUDE_DIR/rules"
SETTINGS="$CLAUDE_DIR/settings.json"
MCP_CONFIG="$CLAUDE_DIR/.mcp.json"
VK_MCP_BINARY="$HOME/bin/vibe-kanban-mcp"
MARKETPLACE_DIR="$CLAUDE_DIR/plugins/marketplaces/derio-net"
CACHE_DIR="$CLAUDE_DIR/plugins/cache/derio-net/superpowers-for-vk"
PLUGINS_DIR="$CLAUDE_DIR/plugins"
KNOWN_MARKETPLACES="$PLUGINS_DIR/known_marketplaces.json"
INSTALLED_PLUGINS="$PLUGINS_DIR/installed_plugins.json"
SKILL_NAMES=(vk-plan vk-dispatch vk-execute vk-progress)

if [[ "${1:-}" == "--uninstall" ]]; then
  echo "Uninstalling superpowers-for-vk extras..."
  rm -f "$RULES_DIR/vk-plan-override.md"
  echo "  Removed $RULES_DIR/vk-plan-override.md"
  if [ -f "$MCP_CONFIG" ] && command -v jq &>/dev/null; then
    if jq -e '.mcpServers.vibe_kanban' "$MCP_CONFIG" &>/dev/null; then
      jq 'del(.mcpServers.vibe_kanban)' "$MCP_CONFIG" > "${MCP_CONFIG}.tmp" && mv "${MCP_CONFIG}.tmp" "$MCP_CONFIG"
      echo "  Removed vibe_kanban from $MCP_CONFIG"
    fi
  fi
  for skill in "${SKILL_NAMES[@]}"; do
    if [ -d "$CLAUDE_DIR/skills/$skill" ] || [ -L "$CLAUDE_DIR/skills/$skill" ]; then
      rm -rf "$CLAUDE_DIR/skills/$skill"
      echo "  Removed stale $CLAUDE_DIR/skills/$skill"
    fi
  done
  echo "Done. Note: Plugin and PostToolUse hook in settings.json were NOT removed (manual cleanup)."
  exit 0
fi

# VK MCP binary is optional — warn but continue if missing
if [ ! -x "$VK_MCP_BINARY" ]; then
  echo "WARNING: VK MCP binary not found at $VK_MCP_BINARY" >&2
  echo "  MCP server configuration will be skipped." >&2
  echo "  Install it later: see https://github.com/derio-net/vibe-kanban" >&2
  SKIP_MCP=true
else
  SKIP_MCP=false
fi

echo "Installing superpowers-for-vk..."

# 1. If marketplace is a real git clone (not a symlink), pull latest first
if [ ! -L "$MARKETPLACE_DIR" ] && [ -d "$MARKETPLACE_DIR/.git" ]; then
  echo ""
  echo "Pulling marketplace clone..."
  git -C "$MARKETPLACE_DIR" pull --ff-only origin main 2>&1 | sed 's/^/  /' || echo "  WARNING: marketplace pull failed"
fi

# 2. Register derio-net marketplace so the plugin system knows where to find it
echo ""
echo "Registering marketplace..."
if command -v jq &>/dev/null; then
  # Add to extraKnownMarketplaces in settings.json
  if [ -f "$SETTINGS" ]; then
    if ! jq -e '.extraKnownMarketplaces["derio-net"]' "$SETTINGS" &>/dev/null; then
      jq '.extraKnownMarketplaces["derio-net"] = {"source":{"source":"github","repo":"derio-net/superpowers-for-vk"}}' \
        "$SETTINGS" > "${SETTINGS}.tmp" && mv "${SETTINGS}.tmp" "$SETTINGS"
      echo "  Added derio-net to extraKnownMarketplaces"
    else
      echo "  derio-net already in extraKnownMarketplaces"
    fi
  fi

  # Add to known_marketplaces.json
  if [ -f "$KNOWN_MARKETPLACES" ]; then
    if ! jq -e '.["derio-net"]' "$KNOWN_MARKETPLACES" &>/dev/null; then
      jq '."derio-net" = {"source":{"source":"github","repo":"derio-net/superpowers-for-vk"},"installLocation":"'"$MARKETPLACE_DIR"'"}' \
        "$KNOWN_MARKETPLACES" > "${KNOWN_MARKETPLACES}.tmp" && mv "${KNOWN_MARKETPLACES}.tmp" "$KNOWN_MARKETPLACES"
      echo "  Added derio-net to known_marketplaces.json"
    else
      echo "  derio-net already in known_marketplaces.json"
    fi
  fi

  # Enable the plugin in settings.json
  if [ -f "$SETTINGS" ]; then
    if ! jq -e '.enabledPlugins["superpowers-for-vk@derio-net"]' "$SETTINGS" &>/dev/null; then
      jq '.enabledPlugins["superpowers-for-vk@derio-net"] = true' \
        "$SETTINGS" > "${SETTINGS}.tmp" && mv "${SETTINGS}.tmp" "$SETTINGS"
      echo "  Enabled superpowers-for-vk@derio-net in settings.json"
    else
      echo "  superpowers-for-vk@derio-net already enabled"
    fi
  fi
else
  echo "  WARNING: jq not found — cannot register marketplace automatically" >&2
fi

# 3. Copy plugin into marketplace directory (decoupled from source repo)
echo ""
echo "Setting up marketplace directory..."
mkdir -p "$MARKETPLACE_DIR"
# Remove stale symlinks from older installs
if [ -L "$MARKETPLACE_DIR" ]; then
  rm "$MARKETPLACE_DIR"
  mkdir -p "$MARKETPLACE_DIR"
  echo "  Replaced stale symlink with standalone copy"
fi
rsync -a --delete --exclude='.git' --exclude='__pycache__' --exclude='.venv' \
  "$PLUGIN_ROOT/" "$MARKETPLACE_DIR/"
echo "  Copied plugin into $MARKETPLACE_DIR"

# 4. Register in installed_plugins.json so Claude Code loads the cached plugin
echo ""
echo "Registering plugin..."
CURRENT_VERSION=$(jq -r '.version' "$PLUGIN_ROOT/.claude-plugin/plugin.json" 2>/dev/null || echo "unknown")
if command -v jq &>/dev/null && [ -f "$INSTALLED_PLUGINS" ]; then
  CACHE_VERSION_DIR="$CACHE_DIR/$CURRENT_VERSION"
  mkdir -p "$CACHE_VERSION_DIR"
  # Sync plugin files into cache
  rsync -a --delete --exclude='.git' --exclude='__pycache__' --exclude='.venv' \
    "$PLUGIN_ROOT/" "$CACHE_VERSION_DIR/"
  echo "  Synced plugin v$CURRENT_VERSION to cache"

  INSTALL_ENTRY='[{"scope":"user","installPath":"'"$CACHE_VERSION_DIR"'","version":"'"$CURRENT_VERSION"'","installedAt":"'"$(date -u +%Y-%m-%dT%H:%M:%S.000Z)"'","lastUpdated":"'"$(date -u +%Y-%m-%dT%H:%M:%S.000Z)"'"}]'
  jq --argjson entry "$INSTALL_ENTRY" '.plugins["superpowers-for-vk@derio-net"] = $entry' \
    "$INSTALLED_PLUGINS" > "${INSTALLED_PLUGINS}.tmp" && mv "${INSTALLED_PLUGINS}.tmp" "$INSTALLED_PLUGINS"
  echo "  Registered superpowers-for-vk@derio-net v$CURRENT_VERSION in installed_plugins.json"
else
  echo "  WARNING: cannot register plugin — jq or installed_plugins.json missing" >&2
fi

# 5. Clear stale cache versions (keep only the current version)
if [ -d "$CACHE_DIR" ]; then
  echo ""
  echo "Checking plugin cache..."
  CURRENT_VERSION=$(jq -r '.plugins[] | select(.name == "superpowers-for-vk") | .version' "$MARKETPLACE_DIR/.claude-plugin/marketplace.json" 2>/dev/null || echo "")
  for version_dir in "$CACHE_DIR"/*/; do
    [ -d "$version_dir" ] || continue
    version_name=$(basename "$version_dir")
    if [ -n "$CURRENT_VERSION" ] && [ "$version_name" = "$CURRENT_VERSION" ]; then
      echo "  keeping cache: $version_name (current)"
    else
      rm -rf "$version_dir"
      echo "  cleared stale cache: $version_name"
    fi
  done
fi

# 6. Clean stale user-level skill copies (from older installs)
for skill in "${SKILL_NAMES[@]}"; do
  if [ -d "$CLAUDE_DIR/skills/$skill" ] || [ -L "$CLAUDE_DIR/skills/$skill" ]; then
    rm -rf "$CLAUDE_DIR/skills/$skill"
    echo "  Removed stale $CLAUDE_DIR/skills/$skill (now delivered by plugin)"
  fi
done

# 7. Rules
echo ""
echo "Installing rules..."
mkdir -p "$RULES_DIR"
rm -f "$RULES_DIR/vk-plan-override.md"
cp "$PLUGIN_ROOT/rules/vk-plan-override.md" "$RULES_DIR/vk-plan-override.md"
echo "  Installed $RULES_DIR/vk-plan-override.md"

# 8. VK MCP server at user level
if [ "$SKIP_MCP" = true ]; then
  echo ""
  echo "Skipping MCP configuration (binary not found)."
else
  echo ""
  echo "Configuring MCP..."
  VK_MCP_ENTRY='{"command":"'"$VK_MCP_BINARY"'","args":["--mode","global"],"env":{"VIBE_BACKEND_URL":"http://localhost:8081"}}'
  if [ -f "$MCP_CONFIG" ] && command -v jq &>/dev/null; then
    jq --argjson entry "$VK_MCP_ENTRY" '.mcpServers.vibe_kanban = $entry' "$MCP_CONFIG" > "${MCP_CONFIG}.tmp" && mv "${MCP_CONFIG}.tmp" "$MCP_CONFIG"
    echo "  Updated vibe_kanban in $MCP_CONFIG"
  elif command -v jq &>/dev/null; then
    echo '{"mcpServers":{}}' | jq --argjson entry "$VK_MCP_ENTRY" '.mcpServers.vibe_kanban = $entry' > "$MCP_CONFIG"
    echo "  Created $MCP_CONFIG with vibe_kanban"
  else
    echo "  WARNING: jq not found — cannot configure MCP server automatically" >&2
    echo "  Add vibe_kanban manually to $MCP_CONFIG" >&2
  fi
fi

# 9. PostToolUse hook hint
if [ ! -f "$SETTINGS" ]; then
  echo "  WARNING: $SETTINGS not found — skipping hook check"
else
  if grep -q "validate-plans" "$SETTINGS"; then
    echo "  PostToolUse hook already present — skipping"
  else
    echo ""
    echo "  NOTE: Manual settings.json edit required. Add this PostToolUse hook:"
    cat << 'HOOK'
    {
      "matcher": "Edit|Write",
      "hooks": [
        {
          "type": "command",
          "command": "bash -c 'FILE=$(cat | jq -r \".tool_input.file_path // .tool_response.filePath // empty\"); case \"$FILE\" in */docs/superpowers/plans/*.md) REPO_ROOT=$(git -C \"$(dirname \"$FILE\")\" rev-parse --show-toplevel 2>/dev/null); [ -x \"$REPO_ROOT/scripts/validate-plans.sh\" ] && \"$REPO_ROOT/scripts/validate-plans.sh\" \"$FILE\" 2>&1 || true;; esac'",
          "statusMessage": "Validating plan..."
        }
      ]
    }
HOOK
  fi
fi

# 10. vk CLI
if command -v uv &>/dev/null; then
  echo ""
  echo "Installing vk CLI globally..."
  uv tool install "$PLUGIN_ROOT" 2>&1 | sed 's/^/  /'
else
  echo ""
  echo "  WARNING: uv not found — install vk CLI manually:"
  echo "    uv tool install $PLUGIN_ROOT"
fi

echo ""
echo "Installation complete. Restart Claude Code to pick up plugin changes."
echo ""
echo "Verify with:"
echo "  jq '.mcpServers.vibe_kanban' ~/.claude/.mcp.json"
echo "  cat ~/.claude/rules/vk-plan-override.md"
echo "  vk --version"
echo ""
echo "Per-repo step (only for repos that keep plans under docs/superpowers/plans/):"
echo "  The PostToolUse hook calls \$REPO_ROOT/scripts/validate-plans.sh — drop"
echo "  in a thin wrapper by running this from the repo root:"
echo "    bash ~/.claude/plugins/marketplaces/derio-net/scripts/install-validator-wrapper.sh"
