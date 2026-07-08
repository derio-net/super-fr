#!/usr/bin/env bash
# Install super-fr extras that the plugin system can't handle.
# Skills are delivered by the plugin system (enabledPlugins in settings.json).
# This script handles: marketplace + plugin registration, stale cache cleanup,
# rules, MCP config, vk CLI, stale skill cleanup, and PostToolUse hook hint.
set -euo pipefail

# Clean up any .tmp sidecar files on failure so a rerun starts clean.
cleanup_tmps() {
  local rc=$?
  if [ "$rc" -ne 0 ]; then
    rm -f "${SETTINGS:-}.tmp" "${MCP_CONFIG:-}.tmp" \
          "${KNOWN_MARKETPLACES:-}.tmp" "${INSTALLED_PLUGINS:-}.tmp" 2>/dev/null || true
    echo "install.sh failed (exit $rc). Rerun after fixing." >&2
  fi
  exit "$rc"
}
trap cleanup_tmps EXIT

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CLAUDE_DIR="$HOME/.claude"
RULES_DIR="$CLAUDE_DIR/rules"
SETTINGS="$CLAUDE_DIR/settings.json"
MCP_CONFIG="$CLAUDE_DIR/.mcp.json"
VK_MCP_BINARY="$HOME/bin/vibe-kanban-mcp"
MARKETPLACE_DIR="$CLAUDE_DIR/plugins/marketplaces/derio-net"
CACHE_BASE="$CLAUDE_DIR/plugins/cache/derio-net"
PLUGIN_NAMES=(super-fr super-fr-dispatch)
OPENCODE_SKILLS_DIR="$HOME/.config/opencode/skills"
PLUGINS_DIR="$CLAUDE_DIR/plugins"
KNOWN_MARKETPLACES="$PLUGINS_DIR/known_marketplaces.json"
INSTALLED_PLUGINS="$PLUGINS_DIR/installed_plugins.json"
# Legacy user-level copies from pre-plugin installs (old vk-* names).
SKILL_NAMES=(vk-plan vk-dispatch vk-execute vk-progress)

if [[ "${1:-}" == "--install-bridge" ]]; then
  # Write the cron wrapper that exec's `python -m fr_vk.bridge`. Hidden by
  # design — there is no `vk bridge` public CLI verb.
  # Default to a user-writable path so operators don't need sudo. The
  # legacy default was /opt/vk-bridge/run.sh — fine for root-owned pod
  # deployments, but painful for shared-pod setups where the bridge runs
  # as the same user as the operator (no write access to /opt). Override
  # with VK_BRIDGE_WRAPPER_PATH=/opt/vk-bridge/run.sh (run via sudo) for
  # the system-path layout.
  wrapper_path="${VK_BRIDGE_WRAPPER_PATH:-$HOME/.local/bin/vk-bridge}"
  mkdir -p "$(dirname "$wrapper_path")"
  # Prefer the active uv tool's interpreter so the wrapper can't pick
  # up a stale system Python that doesn't have vk installed.
  vk_python="$(uv tool dir 2>/dev/null)/fr/bin/python"
  if [ ! -x "$vk_python" ]; then
    # Fallback chain: any `uv run` env, then plain `python3`.
    vk_python="$(uv run --no-project which python 2>/dev/null || command -v python3 || echo /usr/bin/python3)"
  fi
  # The wrapper is only correct if its interpreter can actually import the
  # adapter — verify before writing (review finding, 2026-06-06).
  if ! "$vk_python" -c "import fr_vk.bridge" >/dev/null 2>&1; then
    echo "  ERROR: $vk_python cannot import fr_vk.bridge — bridge wrapper not installed" >&2
    echo "  (re-run after: uv tool install --force --with $PLUGIN_ROOT/packages/fr-vk $PLUGIN_ROOT/packages/fr)" >&2
    exit 1
  fi
  cat > "$wrapper_path" <<EOF
#!/bin/bash
exec "$vk_python" -m fr_vk.bridge "\$@"
EOF
  chmod +x "$wrapper_path"
  echo "Wrapper installed at $wrapper_path"
  echo ""
  echo "To schedule the bridge, add this line to your crontab:"
  echo "*/2 * * * * $wrapper_path"
  exit 0
fi

if [[ "${1:-}" == "--uninstall" ]]; then
  echo "Uninstalling super-fr extras..."
  rm -f "$RULES_DIR/fr-plan-override.md" "$RULES_DIR/vk-plan-override.md"
  echo "  Removed fr/vk plan-override rules"
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
  if [ -d "$OPENCODE_SKILLS_DIR" ]; then
    for skill_dir in "$PLUGIN_ROOT"/plugins/super-fr/skills/*/; do
      skill="$(basename "$skill_dir")"
      if [ -d "$OPENCODE_SKILLS_DIR/$skill" ]; then
        rm -rf "$OPENCODE_SKILLS_DIR/$skill"
        echo "  Removed $OPENCODE_SKILLS_DIR/$skill"
      fi
    done
  fi
  echo "Done. Note: Plugin and PostToolUse hook in settings.json were NOT removed (manual cleanup)."
  exit 0
fi

# Preflight: hard-require jq and uv. Both are used unconditionally downstream;
# continuing past a missing one yields a half-install that looks successful.
for cmd in jq uv rsync git; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "ERROR: '$cmd' not found in PATH. Install it first." >&2
    exit 1
  fi
done

# Preflight: PLUGIN_ROOT must be a clean checkout of main, in sync with origin.
# This script clobbers $MARKETPLACE_DIR with PLUGIN_ROOT's contents, so anything
# uncommitted, unpushed, or off-main gets baked into the cache. Past incidents
# (cache stuck with a transient "Status: Not Started" revert that broke every
# subsequent `git pull --ff-only`) trace back to running this from a dirty tree.
#
# Escape hatch: integration tests (and only integration tests) set
# VK_INSTALL_SKIP_PREFLIGHT=1 to bypass these checks. CI runs this script from
# a detached HEAD on a PR ref, which would always fail the branch/sync gates.
echo ""
if [ "${VK_INSTALL_SKIP_PREFLIGHT:-}" = "1" ]; then
  echo "Preflight: SKIPPED (VK_INSTALL_SKIP_PREFLIGHT=1 — testing only)"
else
echo "Preflight: validating source repo at $PLUGIN_ROOT..."

if [ ! -d "$PLUGIN_ROOT/.git" ]; then
  echo "ERROR: $PLUGIN_ROOT is not a git checkout." >&2
  echo "  install.sh must be run from a git clone of derio-net/super-fr." >&2
  exit 1
fi

PREFLIGHT_FAILED=0
report_preflight_failure() {
  PREFLIGHT_FAILED=1
  echo "  - $1" >&2
  if [ -n "${2:-}" ]; then
    echo "    Fix: $2" >&2
  fi
}

CURRENT_BRANCH="$(git -C "$PLUGIN_ROOT" symbolic-ref --short HEAD 2>/dev/null || echo "DETACHED")"
if [ "$CURRENT_BRANCH" != "main" ]; then
  report_preflight_failure \
    "Current branch is '$CURRENT_BRANCH', expected 'main'." \
    "git -C $PLUGIN_ROOT checkout main"
fi

if [ -n "$(git -C "$PLUGIN_ROOT" status --porcelain)" ]; then
  report_preflight_failure \
    "Working tree has uncommitted or untracked files." \
    "git -C $PLUGIN_ROOT status   # then commit, stash --include-untracked, or clean"
fi

if ! git -C "$PLUGIN_ROOT" fetch --quiet origin main 2>/dev/null; then
  report_preflight_failure \
    "Could not fetch origin/main." \
    "check network/SSH access to origin"
else
  LOCAL_SHA="$(git -C "$PLUGIN_ROOT" rev-parse HEAD)"
  ORIGIN_SHA="$(git -C "$PLUGIN_ROOT" rev-parse origin/main)"
  if [ "$LOCAL_SHA" != "$ORIGIN_SHA" ]; then
    BEHIND="$(git -C "$PLUGIN_ROOT" rev-list --count HEAD..origin/main)"
    AHEAD="$(git -C "$PLUGIN_ROOT" rev-list --count origin/main..HEAD)"
    if [ "$BEHIND" -gt 0 ] && [ "$AHEAD" -eq 0 ]; then
      report_preflight_failure \
        "Local main is behind origin/main by $BEHIND commit(s)." \
        "git -C $PLUGIN_ROOT pull --ff-only"
    elif [ "$AHEAD" -gt 0 ] && [ "$BEHIND" -eq 0 ]; then
      report_preflight_failure \
        "Local main is ahead of origin/main by $AHEAD commit(s) (unpushed work)." \
        "git -C $PLUGIN_ROOT push origin main"
    else
      report_preflight_failure \
        "Local main has diverged from origin/main (ahead $AHEAD, behind $BEHIND)." \
        "reconcile (rebase/merge/reset) before installing"
    fi
  fi
fi

if [ "$PREFLIGHT_FAILED" -ne 0 ]; then
  echo "" >&2
  echo "Preflight failed. install.sh refuses to run from a dirty / out-of-sync source" >&2
  echo "because it clobbers \$MARKETPLACE_DIR with PLUGIN_ROOT's contents — anything" >&2
  echo "uncommitted ends up baked into the cache." >&2
  exit 1
fi
echo "  OK: on main, clean, in sync with origin/main"
fi  # end VK_INSTALL_SKIP_PREFLIGHT guard

# VK MCP binary is optional — warn but continue if missing.
if [ ! -x "$VK_MCP_BINARY" ]; then
  echo "WARNING: VK MCP binary not found at $VK_MCP_BINARY" >&2
  echo "  MCP server configuration will be skipped." >&2
  echo "  Install it later: see https://github.com/derio-net/vibe-kanban" >&2
  SKIP_MCP=true
else
  SKIP_MCP=false
fi

echo ""
echo "Installing super-fr..."

# 2. Register derio-net marketplace so the plugin system knows where to find it
echo ""
echo "Registering marketplace..."
if command -v jq &>/dev/null; then
  # Add to extraKnownMarketplaces in settings.json
  if [ -f "$SETTINGS" ]; then
    if ! jq -e '.extraKnownMarketplaces["derio-net"]' "$SETTINGS" &>/dev/null; then
      jq '.extraKnownMarketplaces["derio-net"] = {"source":{"source":"github","repo":"derio-net/super-fr"}}' \
        "$SETTINGS" > "${SETTINGS}.tmp" && mv "${SETTINGS}.tmp" "$SETTINGS"
      echo "  Added derio-net to extraKnownMarketplaces"
    else
      echo "  derio-net already in extraKnownMarketplaces"
    fi
  fi

  # Add to known_marketplaces.json
  if [ -f "$KNOWN_MARKETPLACES" ]; then
    if ! jq -e '.["derio-net"]' "$KNOWN_MARKETPLACES" &>/dev/null; then
      jq '."derio-net" = {"source":{"source":"github","repo":"derio-net/super-fr"},"installLocation":"'"$MARKETPLACE_DIR"'"}' \
        "$KNOWN_MARKETPLACES" > "${KNOWN_MARKETPLACES}.tmp" && mv "${KNOWN_MARKETPLACES}.tmp" "$KNOWN_MARKETPLACES"
      echo "  Added derio-net to known_marketplaces.json"
    else
      echo "  derio-net already in known_marketplaces.json"
    fi
  fi

  # Enable both plugins in settings.json (v3: superpowers-for-vk is gone)
  if [ -f "$SETTINGS" ]; then
    for plugin_name in "${PLUGIN_NAMES[@]}"; do
      if ! jq -e ".enabledPlugins[\"$plugin_name@derio-net\"]" "$SETTINGS" &>/dev/null; then
        jq ".enabledPlugins[\"$plugin_name@derio-net\"] = true" \
          "$SETTINGS" > "${SETTINGS}.tmp" && mv "${SETTINGS}.tmp" "$SETTINGS"
        echo "  Enabled $plugin_name@derio-net in settings.json"
      else
        echo "  $plugin_name@derio-net already enabled"
      fi
    done
    # v3 clean break: drop the retired plugin entry if present.
    if jq -e '.enabledPlugins["superpowers-for-vk@derio-net"]' "$SETTINGS" &>/dev/null; then
      jq 'del(.enabledPlugins["superpowers-for-vk@derio-net"])' \
        "$SETTINGS" > "${SETTINGS}.tmp" && mv "${SETTINGS}.tmp" "$SETTINGS"
      echo "  Removed retired superpowers-for-vk@derio-net entry"
    fi
  fi
else
  echo "  WARNING: jq not found — cannot register marketplace automatically" >&2
fi

# 3. Copy plugin into marketplace directory (decoupled from source repo).
# The cache is treated as ephemeral — it holds nothing worth preserving across
# runs, so we wipe any stale .git from older installs and clobber the rest.
echo ""
echo "Setting up marketplace directory..."
mkdir -p "$MARKETPLACE_DIR"
# Remove stale symlinks from older installs
if [ -L "$MARKETPLACE_DIR" ]; then
  rm "$MARKETPLACE_DIR"
  mkdir -p "$MARKETPLACE_DIR"
  echo "  Replaced stale symlink with standalone copy"
fi
# Drop any leftover .git so the cache cannot accumulate locally-modified state
# that would make a future operation refuse to update it.
if [ -e "$MARKETPLACE_DIR/.git" ]; then
  rm -rf "$MARKETPLACE_DIR/.git"
  echo "  Removed stale .git from cache (cache is ephemeral)"
fi
rsync -a --delete --exclude='.git' --exclude='__pycache__' --exclude='.venv' \
  "$PLUGIN_ROOT/" "$MARKETPLACE_DIR/"
echo "  Copied plugin into $MARKETPLACE_DIR"

# 4. Register each plugin in installed_plugins.json + sync per-plugin cache
echo ""
echo "Registering plugins..."
if command -v jq &>/dev/null && [ -f "$INSTALLED_PLUGINS" ]; then
  for plugin_name in "${PLUGIN_NAMES[@]}"; do
    plugin_src="$PLUGIN_ROOT/plugins/$plugin_name"
    CURRENT_VERSION=$(jq -r '.version' "$plugin_src/.claude-plugin/plugin.json" 2>/dev/null || echo "unknown")
    PLUGIN_CACHE="$CACHE_BASE/$plugin_name"
    CACHE_VERSION_DIR="$PLUGIN_CACHE/$CURRENT_VERSION"
    CACHE_CURRENT_LINK="$PLUGIN_CACHE/current"
    mkdir -p "$CACHE_VERSION_DIR"
    rsync -a --delete --exclude='__pycache__' \
      "$plugin_src/" "$CACHE_VERSION_DIR/"
    echo "  Synced $plugin_name v$CURRENT_VERSION to cache"

    # Point a stable `current` symlink at the freshly-synced version, AFTER the
    # sync completes (atomic-ish via -fn). installPath records this symlink, not
    # the version dir — so a running Claude Code session, which keeps installPath
    # literal and resolves it at exec time, picks up new hook/command code on the
    # next fire without a restart. Relative target keeps the link path-independent.
    ln -sfn "$CURRENT_VERSION" "$CACHE_CURRENT_LINK"
    echo "  Pointed $plugin_name/current -> $CURRENT_VERSION"

    INSTALL_ENTRY='[{"scope":"user","installPath":"'"$CACHE_CURRENT_LINK"'","version":"'"$CURRENT_VERSION"'","installedAt":"'"$(date -u +%Y-%m-%dT%H:%M:%S.000Z)"'","lastUpdated":"'"$(date -u +%Y-%m-%dT%H:%M:%S.000Z)"'"}]'
    jq --argjson entry "$INSTALL_ENTRY" ".plugins[\"$plugin_name@derio-net\"] = \$entry" \
      "$INSTALLED_PLUGINS" > "${INSTALLED_PLUGINS}.tmp" && mv "${INSTALLED_PLUGINS}.tmp" "$INSTALLED_PLUGINS"
    echo "  Registered $plugin_name@derio-net v$CURRENT_VERSION in installed_plugins.json"

    # Prune to current + the most-recent previous version dir (N-1 buffer): a
    # session that somehow cached a realpath keeps working until restart. Never
    # touch the `current` symlink — the `*/` glob matches it, so skip symlinks.
    PREV_KEEP=""
    while IFS= read -r prev_dir; do
      [ -n "$prev_dir" ] || continue
      PREV_KEEP="$(basename "$prev_dir")"
      break
    done < <(ls -dt "$PLUGIN_CACHE"/*/ 2>/dev/null | while IFS= read -r p; do
               q="${p%/}"
               [ -L "$q" ] && continue
               [ "$(basename "$q")" = "$CURRENT_VERSION" ] && continue
               echo "$q"
             done)

    for version_dir in "$PLUGIN_CACHE"/*/; do
      vd="${version_dir%/}"
      [ -L "$vd" ] && continue   # leave the `current` symlink alone
      version_name="$(basename "$vd")"
      if [ "$version_name" = "$CURRENT_VERSION" ]; then
        echo "  keeping cache: $plugin_name/$version_name (current)"
      elif [ "$version_name" = "$PREV_KEEP" ]; then
        echo "  keeping cache: $plugin_name/$version_name (previous)"
      else
        rm -rf "$vd"
        echo "  cleared stale cache: $plugin_name/$version_name"
      fi
    done
  done
  # v3 clean break: retire the old single-plugin entry + cache wholesale.
  if jq -e '.plugins["superpowers-for-vk@derio-net"]' "$INSTALLED_PLUGINS" &>/dev/null; then
    jq 'del(.plugins["superpowers-for-vk@derio-net"])' \
      "$INSTALLED_PLUGINS" > "${INSTALLED_PLUGINS}.tmp" && mv "${INSTALLED_PLUGINS}.tmp" "$INSTALLED_PLUGINS"
    rm -rf "$CACHE_BASE/superpowers-for-vk"
    echo "  Retired superpowers-for-vk@derio-net (entry + cache removed)"
  fi
else
  echo "  WARNING: cannot register plugins — jq or installed_plugins.json missing" >&2
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
rm -f "$RULES_DIR/vk-plan-override.md" "$RULES_DIR/fr-plan-override.md"
cp "$PLUGIN_ROOT/plugins/super-fr/rules/fr-plan-override.md" "$RULES_DIR/fr-plan-override.md"
echo "  Installed $RULES_DIR/fr-plan-override.md (retired vk-plan-override.md)"
cp "$PLUGIN_ROOT/plugins/super-fr/rules/fr-isolation-required.md" "$RULES_DIR/fr-isolation-required.md"
echo "  Installed $RULES_DIR/fr-isolation-required.md (#328 isolation Edit/Write guard)"
cp "$PLUGIN_ROOT/plugins/super-fr/rules/no-claude-p-batch.md" "$RULES_DIR/no-claude-p-batch.md"
echo "  Installed $RULES_DIR/no-claude-p-batch.md (#328 batch-LLM convention)"

# 7b. OpenCode skill delivery — opt-in only (OpenCode has no plugin/marketplace
# concept; it discovers plain SKILL.md files from its own global skills dir).
# Gate on an explicit opt-in or evidence the operator already uses OpenCode,
# so installs on machines without it stay untouched.
if [ "${OPENCODE_SKILLS_INSTALL:-}" = "1" ] || [ -d "$HOME/.config/opencode" ]; then
  echo ""
  echo "Installing skills for OpenCode ($OPENCODE_SKILLS_DIR)..."
  mkdir -p "$OPENCODE_SKILLS_DIR"
  for skill_dir in "$PLUGIN_ROOT"/plugins/super-fr/skills/*/; do
    skill="$(basename "$skill_dir")"
    mkdir -p "$OPENCODE_SKILLS_DIR/$skill"
    cp "$skill_dir/SKILL.md" "$OPENCODE_SKILLS_DIR/$skill/SKILL.md"
    echo "  Installed $OPENCODE_SKILLS_DIR/$skill/SKILL.md"
  done
else
  echo ""
  echo "Skipping OpenCode skill delivery (no ~/.config/opencode found; set"
  echo "OPENCODE_SKILLS_INSTALL=1 to force)."
fi

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
  echo "Installing fr CLI globally (workspace member fr + the VK adapter)..."
  # `uv tool install --force` removes the tool env in place; on macOS that
  # rmdir intermittently fails with "Directory not empty" (ENOTEMPTY), and a
  # freshly built env can fail a one-shot `fr --version` before it quiesces.
  # Both self-heal on a retry (the operator hit fail→fail→succeed). Retry
  # rather than turn a momentary hiccup into a hard install abort; on a stuck
  # tool dir, an explicit uninstall clears the ENOTEMPTY before the next try.
  # See docs/superpowers/debugging/2026-07-05-install-uv-tool-flaky.md.
  fr_install_retry_sleep="${FR_INSTALL_RETRY_SLEEP:-2}"
  fr_installed=""
  for attempt in 1 2 3; do
    # Pipeline lives in the `if` condition so a `uv` failure (propagated by
    # `pipefail` through `sed`) is caught here instead of tripping `set -e`.
    if uv tool install --force \
      --with "$PLUGIN_ROOT/packages/fr-vk" \
      "$PLUGIN_ROOT/packages/fr" 2>&1 | sed 's/^/  /'; then
      fr_installed=1
      break
    fi
    if [ "$attempt" -lt 3 ]; then
      echo "  uv tool install attempt $attempt failed; clearing tool env and retrying..." >&2
      uv tool uninstall fr >/dev/null 2>&1 || true
      rm -rf "$(uv tool dir 2>/dev/null)/fr" 2>/dev/null || true
      sleep "$fr_install_retry_sleep"
    fi
  done
  if [ -z "$fr_installed" ]; then
    echo "  ERROR: uv tool install failed after 3 attempts" >&2
    exit 1
  fi
  # Smoke check — a tool env without a working entry point must fail loud,
  # but give a just-installed env a couple of beats to quiesce first.
  fr_bin="$(uv tool dir 2>/dev/null)/fr/bin/fr"
  if [ -x "$fr_bin" ]; then
    fr_runs=""
    for _ in 1 2 3; do
      if "$fr_bin" --version >/dev/null 2>&1; then
        fr_runs=1
        break
      fi
      sleep "$fr_install_retry_sleep"
    done
    if [ -z "$fr_runs" ]; then
      echo "  ERROR: fr CLI installed but does not run" >&2
      exit 1
    fi
  else
    echo "  WARNING: fr entry point not found at $fr_bin (uv stub or unusual layout?)" >&2
  fi
else
  echo ""
  echo "  WARNING: uv not found — install vk CLI manually:"
  echo "    uv tool install $PLUGIN_ROOT"
fi

# 11. devcontainer CLI (fr-isolation dependency)
# `fr isolation up` shells out to `devcontainer` unconditionally; without it,
# the failure mode is a bare "command not found" deep inside isolation code,
# not a clear preflight message. Best-effort only (not a hard preflight
# requirement above): plenty of installs never touch fr isolation, and
# forcing an npm-global install on every operator would be too heavy-handed.
if command -v devcontainer &>/dev/null; then
  echo ""
  echo "  OK: devcontainer CLI already installed ($(devcontainer --version 2>/dev/null || echo present))"
elif command -v npm &>/dev/null; then
  echo ""
  echo "Installing devcontainer CLI (npm -g @devcontainers/cli, needed by fr isolation up)..."
  if npm install -g @devcontainers/cli >/dev/null 2>&1; then
    echo "  Installed devcontainer CLI"
  else
    echo "  WARNING: npm install -g @devcontainers/cli failed — install manually if you plan to use fr isolation" >&2
  fi
else
  echo ""
  echo "  WARNING: devcontainer CLI not found and npm not available — 'fr isolation up' will fail until"
  echo "  you install it manually: npm install -g @devcontainers/cli"
fi

echo ""
echo "Installation complete. Restart Claude Code to pick up plugin changes."
echo ""
echo "Verify with:"
echo "  jq '.mcpServers.vibe_kanban' ~/.claude/.mcp.json"
echo "  cat ~/.claude/rules/fr-plan-override.md"
echo "  fr --version"
echo ""
echo "Per-repo step (only for repos that keep plans under docs/superpowers/plans/):"
echo "  The PostToolUse hook calls \$REPO_ROOT/scripts/validate-plans.sh — drop"
echo "  in a thin wrapper by running this from the repo root:"
echo "    bash ~/.claude/plugins/marketplaces/derio-net/scripts/install-validator-wrapper.sh"
