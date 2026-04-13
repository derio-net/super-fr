#!/usr/bin/env bash
# Install superpowers-for-vk skills, rules, and hooks at user level.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CLAUDE_DIR="$HOME/.claude"
SKILLS_DIR="$CLAUDE_DIR/skills"
RULES_DIR="$CLAUDE_DIR/rules"
SETTINGS="$CLAUDE_DIR/settings.json"
MCP_CONFIG="$CLAUDE_DIR/.mcp.json"
VK_MCP_BINARY="$HOME/bin/vibe-kanban-mcp"

SKILL_NAMES=(vk-plan vk-dispatch vk-execute vk-progress)

if [[ "${1:-}" == "--uninstall" ]]; then
  echo "Uninstalling superpowers-for-vk..."
  for skill in "${SKILL_NAMES[@]}"; do
    rm -rf "$SKILLS_DIR/$skill"
    echo "  Removed $SKILLS_DIR/$skill"
  done
  rm -f "$RULES_DIR/vk-plan-override.md"
  echo "  Removed $RULES_DIR/vk-plan-override.md"
  # Remove vibe_kanban from user-level MCP config
  if [ -f "$MCP_CONFIG" ] && command -v jq &>/dev/null; then
    if jq -e '.mcpServers.vibe_kanban' "$MCP_CONFIG" &>/dev/null; then
      jq 'del(.mcpServers.vibe_kanban)' "$MCP_CONFIG" > "${MCP_CONFIG}.tmp" && mv "${MCP_CONFIG}.tmp" "$MCP_CONFIG"
      echo "  Removed vibe_kanban from $MCP_CONFIG"
    fi
  fi
  echo "Done. Note: PostToolUse hook in settings.json was NOT removed (manual cleanup)."
  exit 0
fi

# Fail fast: VK MCP binary must exist
if [ ! -x "$VK_MCP_BINARY" ]; then
  echo "ERROR: VK MCP binary not found at $VK_MCP_BINARY" >&2
  echo "Install it first: see https://github.com/derio-net/vibe-kanban" >&2
  exit 1
fi

echo "Installing superpowers-for-vk..."

for skill in "${SKILL_NAMES[@]}"; do
  mkdir -p "$SKILLS_DIR/$skill"
  cp "$PLUGIN_ROOT/skills/$skill/SKILL.md" "$SKILLS_DIR/$skill/SKILL.md"
  echo "  Installed $SKILLS_DIR/$skill/SKILL.md"
done

mkdir -p "$RULES_DIR"
rm -f "$RULES_DIR/vk-plan-override.md"
cp "$PLUGIN_ROOT/rules/vk-plan-override.md" "$RULES_DIR/vk-plan-override.md"
echo "  Installed $RULES_DIR/vk-plan-override.md"

# Install vibe_kanban MCP server at user level
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

if [ ! -f "$SETTINGS" ]; then
  echo "  WARNING: $SETTINGS not found — skipping hook installation"
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

# Install vk CLI globally via uv tool
if command -v uv &>/dev/null; then
  echo ""
  echo "Installing vk CLI globally..."
  uv tool install "$PLUGIN_ROOT" 2>&1 | sed 's/^/  /'
else
  echo ""
  echo "  WARNING: uv not found — install vk CLI manually:"
  echo "    uv tool install $PLUGIN_ROOT"
fi

# Clean marketplace duplicates (if plugin was previously installed via marketplace)
MARKETPLACE_DIR="$CLAUDE_DIR/plugins/marketplaces/derio-net/skills"
if [ -d "$MARKETPLACE_DIR" ]; then
  for skill in "${SKILL_NAMES[@]}"; do
    if [ -d "$MARKETPLACE_DIR/$skill" ]; then
      rm -rf "$MARKETPLACE_DIR/$skill"
      echo "  Removed marketplace duplicate: $MARKETPLACE_DIR/$skill"
    fi
  done
fi

echo ""
echo "Installation complete. Verify with:"
echo "  ls ~/.claude/skills/vk-*/"
echo "  cat ~/.claude/rules/vk-plan-override.md"
echo "  jq '.mcpServers.vibe_kanban' ~/.claude/.mcp.json"
echo "  vk --version"
