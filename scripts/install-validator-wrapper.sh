#!/usr/bin/env bash
# Drop a thin validate-plans.sh wrapper into the current repo.
# The wrapper exec's the canonical validator shipped with the
# super-fr plugin at user level, so it tracks plugin updates
# automatically (no hardcoded version or absolute path).
#
# Run from the root of the repo that should get plan validation:
#   bash ~/.claude/plugins/marketplaces/derio-net--super-fr/scripts/install-validator-wrapper.sh
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
TARGET="$REPO_ROOT/scripts/validate-plans.sh"

mkdir -p "$REPO_ROOT/scripts"

# Recognize wrappers by the canonical delegate path plus either marker:
# pre-sweep deployments say "superpowers-for-vk", post-sweep ones say "super-fr".
# Accept BOTH marketplace names: `derio-net--super-fr` (current) and the retired
# bare `derio-net`, which every already-deployed wrapper still carries. We only
# ever write the new form — but a recognizer that rejected the old one would
# refuse to upgrade the very repos that need upgrading.
if [ -e "$TARGET" ] && ! (grep -qE "\.claude/plugins/marketplaces/derio-net(--super-fr)?/scripts/validate-plans\.sh" "$TARGET" 2>/dev/null && grep -qE "superpowers-for-vk|super-fr" "$TARGET" 2>/dev/null); then
  echo "ERROR: $TARGET already exists and is not a super-fr wrapper." >&2
  echo "  Refusing to overwrite. Remove or rename it first." >&2
  exit 1
fi

cat > "$TARGET" <<'EOF'
#!/usr/bin/env bash
# Thin wrapper — delegates to the canonical validator from the
# super-fr plugin installed at the user level.
exec "$HOME/.claude/plugins/marketplaces/derio-net--super-fr/scripts/validate-plans.sh" "$@"
EOF
chmod +x "$TARGET"

echo "Installed wrapper at $TARGET"
echo "Commit it so the PostToolUse hook can validate plans in this repo."
