#!/usr/bin/env bash
# Install superpowers-for-vk extras that the plugin system can't handle.
# Skills are delivered by the plugin system (enabledPlugins in settings.json).
# This script handles: marketplace pull, stale cache cleanup, rules, MCP config,
# vk CLI, stale skill cleanup, and PostToolUse hook hint.
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

# Fail fast: VK MCP binary must exist
if [ ! -x "$VK_MCP_BINARY" ]; then
  echo "ERROR: VK MCP binary not found at $VK_MCP_BINARY" >&2
  echo "Install it first: see https://github.com/derio-net/vibe-kanban" >&2
  exit 1
fi

echo "Installing superpowers-for-vk..."

# 1. Pull the marketplace clone so the plugin system sees the latest version
if [ -d "$MARKETPLACE_DIR/.git" ]; then
  echo ""
  echo "Pulling marketplace clone..."
  if git -C "$MARKETPLACE_DIR" pull --ff-only origin main 2>&1 | sed 's/^/  /'; then
    CURRENT_VERSION=$(jq -r '.plugins[] | select(.name == "superpowers-for-vk") | .version' "$MARKETPLACE_DIR/.claude-plugin/marketplace.json" 2>/dev/null || echo "unknown")
    echo "  marketplace version: $CURRENT_VERSION"
  else
    echo "  WARNING: marketplace pull failed"
  fi
else
  echo "  marketplace clone not found at $MARKETPLACE_DIR — skipping pull"
fi

# 2. Clear stale cache versions (keep only the current version)
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

# 3. Clean stale user-level skill copies (from older installs)
for skill in "${SKILL_NAMES[@]}"; do
  if [ -d "$CLAUDE_DIR/skills/$skill" ] || [ -L "$CLAUDE_DIR/skills/$skill" ]; then
    rm -rf "$CLAUDE_DIR/skills/$skill"
    echo "  Removed stale $CLAUDE_DIR/skills/$skill (now delivered by plugin)"
  fi
done

# 4. Rules
echo ""
echo "Installing rules..."
mkdir -p "$RULES_DIR"
rm -f "$RULES_DIR/vk-plan-override.md"
cp "$PLUGIN_ROOT/rules/vk-plan-override.md" "$RULES_DIR/vk-plan-override.md"
echo "  Installed $RULES_DIR/vk-plan-override.md"

# 5. VK MCP server at user level
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

# 6. PostToolUse hook hint
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

# 7. vk CLI
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
