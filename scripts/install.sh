#!/usr/bin/env bash
# Install superpowers-for-vk skills, rules, and hooks at user level.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CLAUDE_DIR="$HOME/.claude"
SKILLS_DIR="$CLAUDE_DIR/skills"
RULES_DIR="$CLAUDE_DIR/rules"
SETTINGS="$CLAUDE_DIR/settings.json"

SKILL_NAMES=(vk-plan vk-dispatch vk-execute vk-progress)

if [[ "${1:-}" == "--uninstall" ]]; then
  echo "Uninstalling superpowers-for-vk..."
  for skill in "${SKILL_NAMES[@]}"; do
    rm -rf "$SKILLS_DIR/$skill"
    echo "  Removed $SKILLS_DIR/$skill"
  done
  rm -f "$RULES_DIR/vk-plan-override.md"
  echo "  Removed $RULES_DIR/vk-plan-override.md"
  echo "Done. Note: PostToolUse hook in settings.json was NOT removed (manual cleanup)."
  exit 0
fi

echo "Installing superpowers-for-vk..."

for skill in "${SKILL_NAMES[@]}"; do
  mkdir -p "$SKILLS_DIR/$skill"
  cp "$PLUGIN_ROOT/skills/$skill/SKILL.md" "$SKILLS_DIR/$skill/SKILL.md"
  echo "  Installed $SKILLS_DIR/$skill/SKILL.md"
done

mkdir -p "$RULES_DIR"
cp "$PLUGIN_ROOT/rules/vk-plan-override.md" "$RULES_DIR/vk-plan-override.md"
echo "  Installed $RULES_DIR/vk-plan-override.md"

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

echo ""
echo "Installation complete. Verify with:"
echo "  ls ~/.claude/skills/vk-*/"
echo "  cat ~/.claude/rules/vk-plan-override.md"
