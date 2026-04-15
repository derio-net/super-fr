#!/usr/bin/env bash
# Drop a thin validate-plans.sh wrapper into the current repo.
# The wrapper exec's the canonical validator shipped with the
# superpowers-for-vk plugin at user level, so it tracks plugin updates
# automatically (no hardcoded version or absolute path).
#
# Run from the root of the repo that should get plan validation:
#   bash ~/.claude/plugins/marketplaces/derio-net/scripts/install-validator-wrapper.sh
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
TARGET="$REPO_ROOT/scripts/validate-plans.sh"

mkdir -p "$REPO_ROOT/scripts"

if [ -e "$TARGET" ] && ! grep -q "superpowers-for-vk" "$TARGET" 2>/dev/null; then
  echo "ERROR: $TARGET already exists and is not a superpowers-for-vk wrapper." >&2
  echo "  Refusing to overwrite. Remove or rename it first." >&2
  exit 1
fi

cat > "$TARGET" <<'EOF'
#!/usr/bin/env bash
# Thin wrapper — delegates to the canonical validator from the
# superpowers-for-vk plugin installed at the user level.
exec "$HOME/.claude/plugins/marketplaces/derio-net/scripts/validate-plans.sh" "$@"
EOF
chmod +x "$TARGET"

echo "Installed wrapper at $TARGET"
echo "Commit it so the PostToolUse hook can validate plans in this repo."
