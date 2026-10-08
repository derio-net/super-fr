#!/usr/bin/env bash
# Canonical super-fr installer, normally invoked by scripts/bootstrap.sh.
# Handles Claude Code marketplace/plugin registration, OpenCode skill/command
# delivery, rules, MCP config, the fr CLI, stale cache cleanup, and the
# PostToolUse hook hint.
set -euo pipefail

# One install per machine at a time (gh#938). Every release is followed by a
# reinstall — by hand, by a watcher, by `fr triage batch drive`'s post_merge —
# and two of them overlapping share the fixed `<file>.tmp` sidecars below and
# rebuild the same fr env and plugin cache at once. A mkdir lock, because
# flock(1) is not on a stock macOS. A lock whose holder is gone is reclaimed;
# a live one is waited on for FR_INSTALL_LOCK_TIMEOUT seconds, then refused.
INSTALL_LOCK="$HOME/.cache/fr/install.lock"
INSTALL_LOCK_HELD=""
acquire_install_lock() {
  local timeout="${FR_INSTALL_LOCK_TIMEOUT:-900}" waited=0 holder announced=""
  case "$timeout" in ''|*[!0-9]*) timeout=900 ;; esac
  mkdir -p "$(dirname "$INSTALL_LOCK")"
  while ! mkdir "$INSTALL_LOCK" 2>/dev/null; do
    holder="$(cat "$INSTALL_LOCK/pid" 2>/dev/null || true)"
    # Stale: the holder is gone, or it died between mkdir and writing its pid
    # (no pid a minute on). Reclaim by renaming the lock aside first, so two
    # waiters that both saw it stale cannot remove each other's fresh lock:
    # only one rename of that directory can succeed.
    if { [ -n "$holder" ] && ! kill -0 "$holder" 2>/dev/null; } \
       || { [ -z "$holder" ] && [ -n "$(find "$INSTALL_LOCK" -maxdepth 0 -mmin +1 2>/dev/null)" ]; }; then
      if mv "$INSTALL_LOCK" "$INSTALL_LOCK.stale.$$" 2>/dev/null; then
        echo "Reclaiming stale install lock $INSTALL_LOCK (holder pid ${holder:-unknown} is gone)" >&2
        rm -rf "$INSTALL_LOCK.stale.$$"
      fi
      continue
    fi
    if [ -z "$announced" ]; then
      echo "Another super-fr install is running (pid ${holder:-unknown}); waiting up to ${timeout}s for $INSTALL_LOCK" >&2
      announced=1
    fi
    if [ "$waited" -ge "$timeout" ]; then
      echo "ERROR: install lock $INSTALL_LOCK still held by pid ${holder:-unknown} after ${timeout}s." >&2
      echo "  Wait for that install to finish, or remove the lock if no install is running." >&2
      exit 1
    fi
    sleep 1
    waited=$((waited + 1))
  done
  echo "$$" > "$INSTALL_LOCK/pid"
  INSTALL_LOCK_HELD=1
}
release_install_lock() {
  [ -n "$INSTALL_LOCK_HELD" ] || return 0
  if [ "$(cat "$INSTALL_LOCK/pid" 2>/dev/null)" = "$$" ]; then
    rm -rf "$INSTALL_LOCK"
  fi
  INSTALL_LOCK_HELD=""
}

# Repoint a live symlink to a FILE with rename(2), never `ln -sf` — that
# unlinks, then creates, and a call resolving the path in between finds nothing
# (gh#938). Files only: `mv` onto a link to a directory would move into it, and
# the flags that stop that (GNU -T, BSD -h) are not portable (busybox has
# neither).
atomic_symlink() {
  local target="$1" link="$2" tmp="$2.tmp.$$"
  rm -f "$tmp"
  ln -s "$target" "$tmp"
  mv -f "$tmp" "$link"
}

# Clean up any .tmp sidecar files on failure so a rerun starts clean.
cleanup_tmps() {
  local rc=$?
  if [ "$rc" -ne 0 ]; then
    # Only sidecars of files this run named: an exit before they are set (a
    # timed-out lock wait) must not remove a stray `.tmp` from the cwd.
    for f in "${SETTINGS:-}" "${MCP_CONFIG:-}" "${KNOWN_MARKETPLACES:-}" "${INSTALLED_PLUGINS:-}"; do
      [ -z "$f" ] || rm -f "$f.tmp" 2>/dev/null || true
    done
    echo "install.sh failed (exit $rc). Rerun after fixing." >&2
  fi
  release_install_lock
  exit "$rc"
}
trap cleanup_tmps EXIT
acquire_install_lock

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# `--with` for every workspace package that registers an `fr.runners` entry
# point, derived rather than listed: a hand-kept list silently missed fr-cncd
# and fr-herdr, and `uv run fr` (what the tests use) sees the whole workspace,
# so nothing noticed the installed `fr` could not load them (#650). The
# scaffold's POST_CREATE keeps the same set as a literal, pinned by
# tests/integration/test_runner_package_lists.py.
FR_RUNNER_WITH=()
for pyproject in "$PLUGIN_ROOT"/packages/*/pyproject.toml; do
  if grep -q '^\[project\.entry-points\."fr\.runners"\]' "$pyproject"; then
    FR_RUNNER_WITH+=(--with "$(dirname "$pyproject")")
  fi
done
# `uv tool install --with` exposes only the main package's scripts, so the one
# console script a workspace package ships for the operator (`fr-herdr
# restart-idle`, spec 2026-10-06-driver-sessions §A) is asked for by name. It
# rides the same `--with` set above, so it resolves to the workspace package.
# An older uv has no such flag and refuses the whole install over it, so it is only
# passed when `uv tool install --help` lists it. Without it the `--with` package's
# script still lands in the tool env's bin, and `relink_herdr` links it from there.
FR_EXECUTABLES_FROM=()
fr_uv_install_help="$(uv tool install --help 2>&1 || true)"
case "$fr_uv_install_help" in
  *--with-executables-from*) FR_EXECUTABLES_FROM=(--with-executables-from fr-herdr) ;;
esac
CLAUDE_DIR="$HOME/.claude"
RULES_DIR="$CLAUDE_DIR/rules"
SETTINGS="$CLAUDE_DIR/settings.json"
MCP_CONFIG="$CLAUDE_DIR/.mcp.json"
VK_MCP_BINARY="$HOME/bin/vibe-kanban-mcp"
# A Claude Code marketplace name is a 1:1 namespace over ONE source repo: its
# manifest (marketplaces/<name>/.claude-plugin/marketplace.json) is a single
# file listing every plugin of that marketplace, and the rsync that populates
# it is `--delete` — replace, never merge. So the name encodes org AND repo.
#
# It used to be the bare org name `derio-net`, which the sibling blog-craft
# repo also claimed; both installers rsync'd their own repo root into the same
# directory and evicted each other. The bare name is now RETIRED — no repo owns
# an org-level namespace — and both installers purge it on sight. See
# docs/superpowers/implemented/journals/debug/2026-07-23-marketplace-config-clobber.md.
MARKETPLACE_NAME="derio-net--super-fr"
MARKETPLACE_DIR="$CLAUDE_DIR/plugins/marketplaces/$MARKETPLACE_NAME"
CACHE_BASE="$CLAUDE_DIR/plugins/cache/$MARKETPLACE_NAME"
PLUGIN_NAMES=(super-fr super-fr-dispatch)
# The retired shared namespace. Purged wholesale: with no owner left, every
# `*@derio-net` registration is dangling by definition.
LEGACY_MARKETPLACE_NAME="derio-net"
LEGACY_MARKETPLACE_DIR="$CLAUDE_DIR/plugins/marketplaces/$LEGACY_MARKETPLACE_NAME"
LEGACY_CACHE_BASE="$CLAUDE_DIR/plugins/cache/$LEGACY_MARKETPLACE_NAME"
OPENCODE_SKILLS_DIR="$HOME/.config/opencode/skills"
OPENCODE_COMMANDS_DIR="$HOME/.config/opencode/commands"
OPENCODE_AGENTS_DIR="$HOME/.config/opencode/agent"
OPENCODE_PLUGINS_DIR="$HOME/.config/opencode/plugins"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
PLUGINS_DIR="$CLAUDE_DIR/plugins"
KNOWN_MARKETPLACES="$PLUGINS_DIR/known_marketplaces.json"
INSTALLED_PLUGINS="$PLUGINS_DIR/installed_plugins.json"
# fr's WorktreeCreate/WorktreeRemove hooks are ALSO registered in settings.json.
# Live on 2026-09-24 (Claude Code 2.1.281), `claude --worktree <name>` never
# invoked the plugin-registered WorktreeCreate, and the session landed in
# Claude's native worktree outside fr. The same scripts registered in
# settings.json do fire. The command points at the cache's `current` link, so
# upgrades need no rewrite. WT_HOOKS_STRIP removes every entry naming fr's
# scripts (current or stale path) and drops an event left empty, leaving a
# group without a `hooks` array (not ours to judge) untouched; install strips,
# then appends, so it converges. The path is quoted inside the command because
# Claude Code runs it through a shell, and a HOME may contain a space.
WT_HOOKS_DIR="$CACHE_BASE/super-fr/current/hooks"
WT_HOOKS_STRIP='
  def strip(ev; s):
    if .hooks[ev] == null then .
    else .hooks[ev] |= [ .[]
           | if (.hooks | type) != "array" then .
             else (.hooks |= map(select((.command // "") | contains(s) | not)))
                  | select((.hooks | length) > 0)
             end ]
         | if (.hooks[ev] | length) == 0 then del(.hooks[ev]) else . end
    end;
  strip("WorktreeCreate"; "fr-worktree-create.sh")
  | strip("WorktreeRemove"; "fr-worktree-remove.sh")'
# Authoritative list of Claude rules to install to ~/.claude/rules/.
# Used for both install copy operations and --uninstall removal.
CLAUDE_RULES=(
  fr-plan-override.md
  fr-isolation-required.md
  no-claude-p-batch.md
  fr-worktree-override.md
)
# Retired rule name, no longer installed but must be removed on --uninstall.
RETIRED_CLAUDE_RULES=(vk-plan-override.md)
# Retired OpenCode agents: fr-phase-reviewer (4.29–4.40) was removed in 5.0.0
# (spec 2026-09-29-spec-is-the-contract). Its copies told the agent to fetch the
# operator input first, so install and uninstall both purge them.
RETIRED_OPENCODE_AGENTS=(
  fr-phase-reviewer.md
  fr-phase-reviewer-mechanical.md
  fr-phase-reviewer-standard.md
  fr-phase-reviewer-hard.md
)
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
    echo "  (re-run after: uv tool install --force ${FR_RUNNER_WITH[*]} ${FR_EXECUTABLES_FROM[*]-} $PLUGIN_ROOT/packages/fr)" >&2
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
  # Remove all currently installed rules
  for rule in "${CLAUDE_RULES[@]}"; do
    rm -f "$RULES_DIR/$rule"
  done
  # Remove retired rules that may be left over from older installations
  for rule in "${RETIRED_CLAUDE_RULES[@]}"; do
    rm -f "$RULES_DIR/$rule"
  done
  echo "  Removed Claude rules (including retired vk-plan-override.md)"
  if [ -f "$SETTINGS" ] && command -v jq &>/dev/null; then
    jq "$WT_HOOKS_STRIP" "$SETTINGS" > "${SETTINGS}.tmp" && mv "${SETTINGS}.tmp" "$SETTINGS"
    echo "  Removed fr's WorktreeCreate/WorktreeRemove hooks from $SETTINGS"
  fi
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
  if [ -d "$OPENCODE_COMMANDS_DIR" ]; then
    for skill_dir in "$PLUGIN_ROOT"/plugins/super-fr/skills/*/; do
      skill="$(basename "$skill_dir")"
      if [ -f "$OPENCODE_COMMANDS_DIR/$skill.md" ]; then
        rm -f "$OPENCODE_COMMANDS_DIR/$skill.md"
        echo "  Removed $OPENCODE_COMMANDS_DIR/$skill.md"
      fi
    done
  fi
  if [ -d "$OPENCODE_AGENTS_DIR" ]; then
    for agent_file in "$PLUGIN_ROOT"/.opencode/agent/*.md; do
      agent="$(basename "$agent_file")"
      if [ -f "$OPENCODE_AGENTS_DIR/$agent" ]; then
        rm -f "$OPENCODE_AGENTS_DIR/$agent"
        echo "  Removed $OPENCODE_AGENTS_DIR/$agent"
      fi
    done
    for agent in "${RETIRED_OPENCODE_AGENTS[@]}"; do
      if [ -f "$OPENCODE_AGENTS_DIR/$agent" ]; then
        rm -f "$OPENCODE_AGENTS_DIR/$agent"
        echo "  Removed retired $OPENCODE_AGENTS_DIR/$agent"
      fi
    done
  fi
  if [ -e "$OPENCODE_PLUGINS_DIR/fr-opencode-plugin.ts" ] || [ -d "$OPENCODE_PLUGINS_DIR/fr-opencode-plugin" ]; then
    bash "$PLUGIN_ROOT/scripts/deliver-opencode-plugin.sh" uninstall "$OPENCODE_PLUGINS_DIR"
    echo "  Removed fr-opencode-plugin from $OPENCODE_PLUGINS_DIR"
  fi
  # Hermes: run the uninstall from THIS checkout, not whichever `fr` happens
  # to be installed globally. Upgrade removals may rename shipped inputs; a
  # stale binary then cannot parse the new tree and used to fail silently,
  # leaving active hooks behind while deleting only the skills.
  if [ -d "$HERMES_HOME" ]; then
    if ! command -v uv &>/dev/null; then
      echo "  ERROR: uv is required to remove Hermes hooks with this checkout's fr code" >&2
      exit 1
    fi
    if uv run --project "$PLUGIN_ROOT/packages/fr" fr hermes uninstall --source "$PLUGIN_ROOT" --home "$HERMES_HOME"; then
      echo "  Removed Hermes hooks/rules ($HERMES_HOME)"
    else
      echo "  ERROR: failed to remove Hermes hooks/rules; Hermes skills left intact" >&2
      exit 1
    fi
  fi
  if [ -d "$HERMES_HOME/skills/fr" ]; then
    rm -rf "$HERMES_HOME/skills/fr"
    echo "  Removed $HERMES_HOME/skills/fr"
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

# The two files Claude Code registers a plugin in. Without them steps 2 and 4
# used to skip with a warning and exit 0, so a cloud environment's setup script
# reported success over a session with no plugin (spec 2026-10-07-cloud-triage
# R19). A fresh container has neither; seed them rather than guess their shape.
missing_registration=0
for f in "$INSTALLED_PLUGINS" "$SETTINGS"; do
  if [ ! -f "$f" ]; then
    echo "ERROR: $f not found — install.sh cannot register the super-fr plugin without it." >&2
    missing_registration=1
  fi
done
if [ "$missing_registration" -ne 0 ]; then
  echo "  Seed them (a fresh Claude Code home has neither), then re-run install.sh:" >&2
  echo "    mkdir -p \"$PLUGINS_DIR\"" >&2
  echo "    [ -f \"$INSTALLED_PLUGINS\" ] || echo '{\"version\":2,\"plugins\":{}}' > \"$INSTALLED_PLUGINS\"" >&2
  echo "    [ -f \"$SETTINGS\" ] || echo '{}' > \"$SETTINGS\"" >&2
  echo "  In a Claude Code cloud environment, use the setup script \`fr cloud setup-script\` prints." >&2
  exit 1
fi

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

# 2. Register the marketplace so the plugin system knows where to find it.
#
# These writes are UNCONDITIONAL, not skip-if-present. `if ! jq -e '."<key>"'`
# reads as idempotence but means first-writer-wins: a wrong `source.repo` left
# by anyone else survives every reinstall, and a later
# `/plugin marketplace update` then re-fetches the wrong repo. Idempotence for
# a key we own means converging on our value, not deferring to whatever is
# already there.
echo ""
echo "Registering marketplace..."
if command -v jq &>/dev/null; then
  MARKETPLACE_SOURCE='{"source":"github","repo":"derio-net/super-fr"}'

  # Add to extraKnownMarketplaces in settings.json
  if [ -f "$SETTINGS" ]; then
    jq --arg name "$MARKETPLACE_NAME" --argjson src "$MARKETPLACE_SOURCE" \
      '.extraKnownMarketplaces[$name] = {"source":$src}' \
      "$SETTINGS" > "${SETTINGS}.tmp" && mv "${SETTINGS}.tmp" "$SETTINGS"
    echo "  Registered $MARKETPLACE_NAME in extraKnownMarketplaces"
  fi

  # Add to known_marketplaces.json. `lastUpdated` is required: Claude Code's
  # `/plugin` rejects the WHOLE file ("Marketplace configuration file is
  # corrupted: <name>.lastUpdated: Invalid input") when one entry lacks it,
  # and this line replaces the entry wholesale, so it must write every field.
  # This same install re-syncs the marketplace dir below, so "now" is true.
  if [ -f "$KNOWN_MARKETPLACES" ]; then
    jq --arg name "$MARKETPLACE_NAME" --argjson src "$MARKETPLACE_SOURCE" \
      --arg loc "$MARKETPLACE_DIR" --arg now "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)" \
      '.[$name] = {"source":$src,"installLocation":$loc,"lastUpdated":$now}' \
      "$KNOWN_MARKETPLACES" > "${KNOWN_MARKETPLACES}.tmp" && mv "${KNOWN_MARKETPLACES}.tmp" "$KNOWN_MARKETPLACES"
    echo "  Registered $MARKETPLACE_NAME in known_marketplaces.json"
  fi

  # Enable both plugins in settings.json (v3: superpowers-for-vk is gone)
  if [ -f "$SETTINGS" ]; then
    for plugin_name in "${PLUGIN_NAMES[@]}"; do
      jq --arg id "$plugin_name@$MARKETPLACE_NAME" '.enabledPlugins[$id] = true' \
        "$SETTINGS" > "${SETTINGS}.tmp" && mv "${SETTINGS}.tmp" "$SETTINGS"
      echo "  Enabled $plugin_name@$MARKETPLACE_NAME in settings.json"
    done
  fi

  # Worktree hooks in settings.json too; see WT_HOOKS_STRIP above for why.
  if [ -f "$SETTINGS" ]; then
    jq --arg c "bash \"$WT_HOOKS_DIR/fr-worktree-create.sh\"" \
      --arg r "bash \"$WT_HOOKS_DIR/fr-worktree-remove.sh\"" \
      "$WT_HOOKS_STRIP"' | .hooks.WorktreeCreate += [{"hooks":[{"type":"command","command":$c}]}]
        | .hooks.WorktreeRemove += [{"hooks":[{"type":"command","command":$r}]}]' \
      "$SETTINGS" > "${SETTINGS}.tmp" && mv "${SETTINGS}.tmp" "$SETTINGS"
    echo "  Registered fr's WorktreeCreate/WorktreeRemove hooks in settings.json"
  fi

  # Purge the retired bare-org marketplace. Two repos claimed `derio-net` and
  # rsync --delete'd each other out of it; the name is retired rather than
  # awarded to either, so no repo owns an org-level namespace. With no owner
  # left, EVERY `*@derio-net` registration is dangling by definition — including
  # blog-craft's, which its own installer re-registers under
  # `derio-net--blog-craft`. Removing the whole key is therefore safe by
  # construction, not us reaching into another repo's state.
  purged_ids=""
  for state_file in "$INSTALLED_PLUGINS" "$SETTINGS"; do
    [ -f "$state_file" ] || continue
    if [ "$state_file" = "$INSTALLED_PLUGINS" ]; then
      key_path='.plugins'
    else
      key_path='.enabledPlugins'
    fi
    while IFS= read -r plugin_id; do
      [ -n "$plugin_id" ] || continue
      case " $purged_ids " in *" $plugin_id "*) ;; *) purged_ids="$purged_ids $plugin_id" ;; esac
    done < <(jq -r "($key_path // {}) | keys[] | select(endswith(\"@$LEGACY_MARKETPLACE_NAME\"))" \
               "$state_file" 2>/dev/null || true)
    jq --arg suffix "@$LEGACY_MARKETPLACE_NAME" \
      "$key_path |= with_entries(select(.key | endswith(\$suffix) | not))" \
      "$state_file" > "${state_file}.tmp" && mv "${state_file}.tmp" "$state_file"
  done
  if [ -f "$KNOWN_MARKETPLACES" ]; then
    jq --arg name "$LEGACY_MARKETPLACE_NAME" 'del(.[$name])' \
      "$KNOWN_MARKETPLACES" > "${KNOWN_MARKETPLACES}.tmp" && mv "${KNOWN_MARKETPLACES}.tmp" "$KNOWN_MARKETPLACES"
  fi
  if [ -f "$SETTINGS" ]; then
    jq --arg name "$LEGACY_MARKETPLACE_NAME" 'del(.extraKnownMarketplaces[$name])' \
      "$SETTINGS" > "${SETTINGS}.tmp" && mv "${SETTINGS}.tmp" "$SETTINGS"
  fi
  if [ -n "$purged_ids" ] || [ -d "$LEGACY_MARKETPLACE_DIR" ] || [ -d "$LEGACY_CACHE_BASE" ]; then
    rm -rf "$LEGACY_MARKETPLACE_DIR" "$LEGACY_CACHE_BASE"
    echo "  Retired the '$LEGACY_MARKETPLACE_NAME' marketplace (registry, cache, directory)"
    for plugin_id in $purged_ids; do
      echo "    - dropped $plugin_id"
    done
    case " $purged_ids " in
      *"@$LEGACY_MARKETPLACE_NAME"*)
        if [ -n "$(echo "$purged_ids" | tr ' ' '\n' | grep -v "^super-fr@\|^super-fr-dispatch@\|^superpowers-for-vk@\|^$" || true)" ]; then
          echo "  NOTE: some of those belong to sibling repos. Re-run their installers" >&2
          echo "  to re-register them under their own 'derio-net--<repo>' marketplace." >&2
        fi
        ;;
    esac
  fi
else
  echo "  WARNING: jq not found — cannot register marketplace automatically" >&2
fi

# 3. Copy plugin into marketplace directory (decoupled from source repo).
# The cache is treated as ephemeral — it holds nothing worth preserving across
# runs, so we wipe any stale .git from older installs and clobber the rest.
echo ""
echo "Setting up marketplace directory..."
# The rsync below is `--delete`: it replaces the whole tree, it does not merge
# manifests. `derio-net--super-fr` names exactly one repo so nothing else should
# ever be here — but a name collision is silent and total, so check rather than
# assume. If a foreign manifest is squatting, we still reclaim (refusing would
# let a squat permanently break super-fr installs) and name whose plugins just
# went dark.
OCCUPANT_MANIFEST="$MARKETPLACE_DIR/.claude-plugin/marketplace.json"
if [ -f "$OCCUPANT_MANIFEST" ] && command -v jq &>/dev/null; then
  occupant_name="$(jq -r '.name // empty' "$OCCUPANT_MANIFEST" 2>/dev/null || true)"
  if [ -n "$occupant_name" ] && [ "$occupant_name" != "$MARKETPLACE_NAME" ]; then
    echo "  WARNING: foreign marketplace '$occupant_name' occupies $MARKETPLACE_DIR." >&2
    echo "  super-fr owns '$MARKETPLACE_NAME' and is reclaiming this directory;" >&2
    echo "  '$occupant_name' plugins installed from here will stop resolving." >&2
    echo "  Fix on that repo's side: a marketplace name is a 1:1 namespace over one" >&2
    echo "  source repo — use 'derio-net--<its own repo>', matching its own" >&2
    echo "  .claude-plugin/marketplace.json 'name'." >&2
  fi
fi
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
# Local state never ships (gh#630): coverage data, which a parallel test run
# creates and deletes mid-copy (rsync exit 23), and the devcontainer's venv.
rsync -a --delete --exclude='.git' --exclude='__pycache__' --exclude='.venv' \
  --exclude='.venv-container' --exclude='.coverage*' \
  "$PLUGIN_ROOT/" "$MARKETPLACE_DIR/"
echo "  Copied plugin into $MARKETPLACE_DIR"
# Shipped workflow manifests (plugins/super-fr/workflows/*.yaml, spec §4.A)
# ride this same wholesale rsync — no separate cp line, unlike rules/ or the
# OpenCode skill mirror below, both of which target a destination OUTSIDE
# this tree. fr.workflow.resolve.default_shipped_workflows_dir()'s fallback
# ($HOME/.claude/plugins/marketplaces/derio-net--super-fr/plugins/super-fr/
# workflows) is exactly $MARKETPLACE_DIR/plugins/super-fr/workflows —
# pinned by tests/integration/test_install_sh.py's TestInstallWorkflows so a
# future --exclude here can't silently unship a manifest.

# 4. Register each plugin in installed_plugins.json + sync per-plugin cache
echo ""
echo "Registering plugins..."
if command -v jq &>/dev/null && [ -f "$INSTALLED_PLUGINS" ]; then
  for plugin_name in "${PLUGIN_NAMES[@]}"; do
    plugin_src="$PLUGIN_ROOT/plugins/$plugin_name"
    CURRENT_VERSION=$(jq -r '.version' "$plugin_src/.claude-plugin/plugin.json" 2>/dev/null || echo "unknown")
    PLUGIN_CACHE="$CACHE_BASE/$plugin_name"
    CACHE_CURRENT="$PLUGIN_CACHE/current"
    mkdir -p "$PLUGIN_CACHE"

    # installPath is ONE real directory, `current`, synced in place — never a
    # symlink to a version dir (gh#938). Claude Code resolves installPath when it
    # loads the plugin and runs every hook of that session from the resolved
    # path, so with `current -> <version>` a session held <version>, and the
    # prune that kept only current + one previous deleted it under the session
    # two releases later: "Plugin directory does not exist", on every Stop,
    # PreToolUse and PostToolUse hook, the guards failing open. A path nothing
    # ever deletes cannot go missing. --delay-updates moves the changed files
    # into place together at the end, each by rename, and --delete-after drops
    # removed ones only then. --checksum, because the quick check (size and
    # mtime) skips a same-length edit made within the same second, and in
    # place a skipped file stays stale for good.
    if [ -L "$CACHE_CURRENT" ]; then
      # One-time move off the versioned layout. A session started before it
      # holds some version dir, and a dir's mtime is the SOURCE's (rsync -a),
      # not when it was installed — so restart every one's 7-day clock (below).
      for legacy in "$PLUGIN_CACHE"/*/; do
        [ -L "${legacy%/}" ] || touch "${legacy%/}"
      done
      cache_stage="$PLUGIN_CACHE/.current.new.$$"
      rm -rf "$cache_stage"
      mkdir -p "$cache_stage"
      rsync -a --exclude='__pycache__' "$plugin_src/" "$cache_stage/"
      rm "$CACHE_CURRENT"
      mv "$cache_stage" "$CACHE_CURRENT"
      echo "  Moved $plugin_name/current from a version symlink to a directory"
    else
      mkdir -p "$CACHE_CURRENT"
      rsync -a --checksum --delete-after --delay-updates --exclude='__pycache__' \
        "$plugin_src/" "$CACHE_CURRENT/"
    fi
    echo "  Synced $plugin_name v$CURRENT_VERSION to $CACHE_CURRENT"

    INSTALL_ENTRY='[{"scope":"user","installPath":"'"$CACHE_CURRENT"'","version":"'"$CURRENT_VERSION"'","installedAt":"'"$(date -u +%Y-%m-%dT%H:%M:%S.000Z)"'","lastUpdated":"'"$(date -u +%Y-%m-%dT%H:%M:%S.000Z)"'"}]'
    jq --argjson entry "$INSTALL_ENTRY" --arg id "$plugin_name@$MARKETPLACE_NAME" \
      '.plugins[$id] = $entry' \
      "$INSTALLED_PLUGINS" > "${INSTALLED_PLUGINS}.tmp" && mv "${INSTALLED_PLUGINS}.tmp" "$INSTALLED_PLUGINS"
    echo "  Registered $plugin_name@$MARKETPLACE_NAME v$CURRENT_VERSION in installed_plugins.json"

    # Version dirs are legacy: only sessions started before the move above can
    # hold one. Remove each once it is 7 days old — no session lives that long —
    # and never sooner, whatever number of releases landed meanwhile.
    for version_dir in "$PLUGIN_CACHE"/*/; do
      vd="${version_dir%/}"
      [ "$vd" = "$CACHE_CURRENT" ] && continue
      [ -L "$vd" ] && continue
      if [ -n "$(find "$vd" -maxdepth 0 -mtime +7 2>/dev/null)" ]; then
        rm -rf "$vd"
        echo "  cleared legacy cache: $plugin_name/$(basename "$vd")"
      fi
    done
  done
  # (The retired superpowers-for-vk@derio-net entry needs no special case any
  # more — the bare-org purge above drops every `*@derio-net` id wholesale.)

  # Report — never delete — `X@derio-net--super-fr` registrations our own
  # manifest doesn't list. Ours is the only repo that can legitimately write
  # this namespace, so an unknown id here means a stale plugin name from an
  # older super-fr, or a genuine collision. Name it rather than guess: silently
  # deleting a registration is how the original bug hid for two months.
  OWNED_IDS=""
  for plugin_name in "${PLUGIN_NAMES[@]}"; do
    OWNED_IDS="$OWNED_IDS $plugin_name@$MARKETPLACE_NAME"
  done
  orphans=""
  for source_file in "$INSTALLED_PLUGINS" "$SETTINGS"; do
    [ -f "$source_file" ] || continue
    if [ "$source_file" = "$INSTALLED_PLUGINS" ]; then
      jq_path='.plugins // {}'
    else
      jq_path='.enabledPlugins // {}'
    fi
    while IFS= read -r plugin_id; do
      [ -n "$plugin_id" ] || continue
      case " $OWNED_IDS " in *" $plugin_id "*) continue ;; esac
      case " $orphans " in *" $plugin_id "*) continue ;; esac
      orphans="$orphans $plugin_id"
    done < <(jq -r "$jq_path | keys[] | select(endswith(\"@$MARKETPLACE_NAME\"))" \
               "$source_file" 2>/dev/null || true)
  done
  if [ -n "$orphans" ]; then
    echo "" >&2
    echo "  WARNING: orphaned plugin registration(s) in the $MARKETPLACE_NAME marketplace:" >&2
    for plugin_id in $orphans; do
      echo "    - $plugin_id  (not listed in super-fr's marketplace.json)" >&2
    done
    echo "  These stay enabled but can no longer resolve. Left in place rather than" >&2
    echo "  silently deleted. Remove them with:" >&2
    echo "    jq 'del(.plugins[\"<id>\"])' ~/.claude/plugins/installed_plugins.json" >&2
    echo "    jq 'del(.enabledPlugins[\"<id>\"])' ~/.claude/settings.json" >&2
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
# Remove stale vk-plan-override.md from older installations
rm -f "$RULES_DIR/vk-plan-override.md"
# Remove any stale versions of current rules (including symlinks) before installing fresh
for rule in "${CLAUDE_RULES[@]}"; do
  rm -f "$RULES_DIR/$rule"
  cp "$PLUGIN_ROOT/plugins/super-fr/rules/$rule" "$RULES_DIR/$rule"
  echo "  Installed $RULES_DIR/$rule"
done

# 7a. Allowlist the fr-phase-executor subagent in the org agent-worktree hook.
# fr-goal dispatches each plan phase to this narrow, serial, already-isolated
# subagent (2026-07-22 fr-goal-subagent-execution spec §B.1). Idempotent; a
# no-op when the org hook is absent (fr-goal then falls back to inline).
# The script already exits 0 when the hook is simply absent, so a non-zero exit
# here is a REAL failure (anchor drift / unwritable hook) — surface it as a
# warning instead of the misleading "not managed here", which used to mask it
# and leave every fr-goal run mysteriously degraded to inline execution.
if ! bash "$PLUGIN_ROOT/scripts/ensure-phase-executor-allowlist.sh" \
     "$CLAUDE_DIR/hooks/agent-worktree-required.sh"; then
  echo "  WARNING: could not allowlist fr-phase-executor in the agent-worktree hook" >&2
  echo "  (see the error above) — fr-goal will fall back to INLINE phase execution." >&2
fi
# The read-only fr-spec-reviewer too (2026-09-24 spec §E, gh#593): the hook
# decides by name, not by tools, and a worktree cut from `main` cannot see the
# feature branch's spec the reviewer is dispatched to read.
if ! bash "$PLUGIN_ROOT/scripts/ensure-phase-executor-allowlist.sh" \
     "$CLAUDE_DIR/hooks/agent-worktree-required.sh" super-fr:fr-spec-reviewer; then
  echo "  WARNING: could not allowlist fr-spec-reviewer in the agent-worktree hook" >&2
  echo "  (see the error above) — fr-goal's spec-review dispatch will be blocked." >&2
fi

# 7b. OpenCode skill + command + agent delivery — moved to after step 10 (fr CLI install)
# because it now shells out to `fr models apply`.

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

# 10. fr CLI
if command -v uv &>/dev/null; then
  echo ""
  echo "Installing fr CLI globally (workspace member fr + every runner adapter)..."
  # `uv tool install --force` removes the tool env in place; on macOS that
  # rmdir intermittently fails with "Directory not empty" (ENOTEMPTY), and a
  # freshly built env can fail a one-shot `fr --version` before it quiesces.
  # Both self-heal on a retry (the operator hit fail→fail→succeed). Retry
  # rather than turn a momentary hiccup into a hard install abort; on a stuck
  # tool dir, an explicit uninstall clears the ENOTEMPTY before the next try.
  # See docs/superpowers/debugging/2026-07-05-install-uv-tool-flaky.md.
  fr_install_retry_sleep="${FR_INSTALL_RETRY_SLEEP:-2}"
  # That in-place rebuild must not take the `fr` on PATH with it: every
  # session's hooks and commands call it (gh#938). uv's --force deletes the
  # entry point its receipt names before it rebuilds — whatever that path
  # points at by then — and relinks it only at the end. So uv's entry point
  # lives in a private bin dir, and the PATH entry is ours: a symlink this
  # script repoints by rename, onto a copy staged aside for the rebuild and
  # back onto uv's env after it. A call sees the old, the staged or the new fr,
  # never none. (A receipt written before this change still names the PATH
  # entry, so the first install after it loses fr once, for the rebuild.)
  # Only a PATH entry that is absent or a symlink is ours to manage.
  fr_path_dir="$(uv tool dir --bin 2>/dev/null || true)"
  fr_path_link="$fr_path_dir/fr"
  # `fr-herdr` gets a second PATH entry, managed exactly like fr's (same swap through
  # the staged rebuild), and only once an env that carries it exists.
  fr_herdr_link="$fr_path_dir/fr-herdr"
  relink_herdr() {  # $1 = a tool env's bin dir
    [ -n "$fr_manage_path" ] && [ -x "$1/fr-herdr" ] || return 0
    if [ -L "$fr_herdr_link" ] || [ ! -e "$fr_herdr_link" ]; then
      atomic_symlink "$1/fr-herdr" "$fr_herdr_link"
    fi
  }
  fr_uv_bin="$HOME/.local/share/fr/uv-bin"
  fr_stage_root="$HOME/.cache/fr/install-stage"
  fr_stage=""
  fr_manage_path=""
  if [ -n "$fr_path_dir" ] && { [ -L "$fr_path_link" ] || [ ! -e "$fr_path_link" ]; }; then
    fr_manage_path=1
    mkdir -p "$fr_uv_bin"
  fi
  if [ -n "$fr_manage_path" ] && [ -e "$fr_path_link" ]; then
    fr_stage="$fr_stage_root/$$.$(date +%s)"
    rm -rf "$fr_stage"
    mkdir -p "$fr_stage"
    if UV_TOOL_DIR="$fr_stage/tools" UV_TOOL_BIN_DIR="$fr_stage/bin" \
         uv tool install --force "${FR_RUNNER_WITH[@]}" ${FR_EXECUTABLES_FROM[@]+"${FR_EXECUTABLES_FROM[@]}"} \
         "$PLUGIN_ROOT/packages/fr" >/dev/null 2>&1 \
       && { "$fr_stage/tools/fr/bin/fr" --version >/dev/null 2>&1 \
            || { sleep "$fr_install_retry_sleep"; "$fr_stage/tools/fr/bin/fr" --version >/dev/null 2>&1; }; }; then
      atomic_symlink "$fr_stage/tools/fr/bin/fr" "$fr_path_link"
      relink_herdr "$fr_stage/tools/fr/bin"
      echo "  fr on PATH points at a staged copy while the tool env is rebuilt"
      # Let an fr that started on the old env just before the swap finish
      # loading it before that env is deleted.
      sleep "${FR_INSTALL_DRAIN_SECONDS:-2}"
    else
      echo "  WARNING: could not stage fr aside; rebuilding it in place" >&2
      rm -rf "$fr_stage"
      fr_stage=""
    fi
  fi
  fr_install_bin="$fr_path_dir"
  [ -z "$fr_manage_path" ] || fr_install_bin="$fr_uv_bin"
  fr_installed=""
  for attempt in 1 2 3; do
    # Pipeline lives in the `if` condition so a `uv` failure (propagated by
    # `pipefail` through `sed`) is caught here instead of tripping `set -e`.
    if UV_TOOL_BIN_DIR="$fr_install_bin" uv tool install --force \
      "${FR_RUNNER_WITH[@]}" ${FR_EXECUTABLES_FROM[@]+"${FR_EXECUTABLES_FROM[@]}"} \
      "$PLUGIN_ROOT/packages/fr" 2>&1 | sed 's/^/  /'; then
      fr_installed=1
      break
    fi
    if [ "$attempt" -lt 3 ]; then
      echo "  uv tool install attempt $attempt failed; clearing tool env and retrying..." >&2
      uv tool uninstall fr >/dev/null 2>&1 || true
      rm -rf "$(uv tool dir 2>/dev/null)/fr" 2>/dev/null || true
      # An old receipt's uninstall takes the PATH entry with it; keep fr
      # runnable meanwhile.
      if [ -n "$fr_stage" ]; then
        atomic_symlink "$fr_stage/tools/fr/bin/fr" "$fr_path_link"
        relink_herdr "$fr_stage/tools/fr/bin"
      fi
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
    # Back onto uv's own env. This install's stage is NOT removed now: an fr
    # started on it moments ago is still loading from it. It goes at the end of
    # the next install, as older stages go now — never one the PATH entry still
    # names (an install that failed above leaves fr on its stage).
    if [ -n "$fr_manage_path" ] && { [ -L "$fr_path_link" ] || [ ! -e "$fr_path_link" ]; }; then
      mkdir -p "$(dirname "$fr_path_link")"
      atomic_symlink "$fr_bin" "$fr_path_link"
      relink_herdr "$(dirname "$fr_bin")"
      for old_stage in "$fr_stage_root"/*/; do
        old_stage="${old_stage%/}"
        [ -d "$old_stage" ] && [ "$old_stage" != "$fr_stage" ] || continue
        case "$(readlink "$fr_path_link")" in "$old_stage"/*) continue ;; esac
        case "$(readlink "$fr_herdr_link" 2>/dev/null)" in "$old_stage"/*) continue ;; esac
        rm -rf "$old_stage"
      done
    fi
  else
    echo "  WARNING: fr entry point not found at $fr_bin (uv stub or unusual layout?)" >&2
  fi
else
  echo ""
  echo "  WARNING: uv not found — install fr CLI manually:"
  echo "    uv tool install $PLUGIN_ROOT/packages/fr"
fi

# 7b. OpenCode skill + command + agent delivery — opt-in only (OpenCode has no
# plugin/marketplace concept; it discovers plain SKILL.md files and
# commands/<name>.md files from its own global dirs, and agents from .opencode/agent/).
# Gate on an explicit opt-in or evidence the operator already uses OpenCode,
# so installs on machines without it stay untouched.
# Runs AFTER the fr CLI install above so `fr models apply` is on PATH.
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
  echo ""
  echo "Installing OpenCode slash commands ($OPENCODE_COMMANDS_DIR)..."
  mkdir -p "$OPENCODE_COMMANDS_DIR"
  for skill_dir in "$PLUGIN_ROOT"/plugins/super-fr/skills/*/; do
    skill="$(basename "$skill_dir")"
    # Copies from the repo's own already-synced, CI-guarded .opencode/commands/
    # mirror (scripts/sync-opencode.py) rather than regenerating — install.sh
    # stays bash+jq only, no Python/yaml dependency added here.
    cp "$PLUGIN_ROOT/.opencode/commands/$skill.md" "$OPENCODE_COMMANDS_DIR/$skill.md"
    echo "  Installed $OPENCODE_COMMANDS_DIR/$skill.md"
  done
  echo ""
  echo "Installing OpenCode agents ($OPENCODE_AGENTS_DIR)..."
  mkdir -p "$OPENCODE_AGENTS_DIR"
  for agent in "${RETIRED_OPENCODE_AGENTS[@]}"; do
    if [ -f "$OPENCODE_AGENTS_DIR/$agent" ]; then
      rm -f "$OPENCODE_AGENTS_DIR/$agent"
      echo "  Removed retired $OPENCODE_AGENTS_DIR/$agent"
    fi
  done
  for agent_file in "$PLUGIN_ROOT"/.opencode/agent/*.md; do
    agent="$(basename "$agent_file")"
    cp "$agent_file" "$OPENCODE_AGENTS_DIR/$agent"
    echo "  Installed $OPENCODE_AGENTS_DIR/$agent"
  done
  # Resolve tier bindings into the files just copied — the single materialiser
  # `fr.opencode_agents.materialize_agents` also used by `fr models set`
  # (spec 2026-09-20-opencode-tier-binding-reaches-dispatch §3.A), reached
  # through the one shell-callable entry point install.sh (bash, no Python
  # import) can use. Tolerate any failure exactly like the old rewrite's
  # `|| true` did — an unbound tier, a missing `fr`, or a hand-edited agent
  # file must never fail the install.
  fr models apply --harness opencode || true
  # The plugin behind OpenCode's edit gate and idle adapter (gh#563). Without
  # this step `fr harness parity` credits both to OpenCode users who never
  # received them. A failure here fails the install: an OpenCode user
  # without the gate is exactly the silent state this step exists to end.
  echo ""
  echo "Installing fr-opencode-plugin ($OPENCODE_PLUGINS_DIR)..."
  bash "$PLUGIN_ROOT/scripts/deliver-opencode-plugin.sh" install "$OPENCODE_PLUGINS_DIR"
  echo "  Installed $OPENCODE_PLUGINS_DIR/fr-opencode-plugin.ts (+ fr-opencode-plugin/)"
else
  echo ""
  echo "Skipping OpenCode skill/command/agent delivery (no ~/.config/opencode found; set"
  echo "OPENCODE_SKILLS_INSTALL=1 to force)."
fi

# 10b. Hermes Agent delivery — opt-in only (Hermes discovers skills from
# ~/.hermes/skills/ and loads its own config.yaml + SOUL.md). Gated like
# OpenCode. The invasive, reversible mutations (config.yaml hooks merge,
# shell-hooks allowlist, SOUL.md managed block, hook-tree copy) are delegated to
# the tested `fr hermes install` subcommand, so install.sh stays bash+jq only.
# Runs AFTER the fr CLI install above so `fr` is on PATH.
if [ "${HERMES_SKILLS_INSTALL:-}" = "1" ] || [ -d "$HERMES_HOME" ]; then
  echo ""
  echo "Installing skills for Hermes Agent ($HERMES_HOME/skills/fr)..."
  mkdir -p "$HERMES_HOME/skills/fr"
  for skill_dir in "$PLUGIN_ROOT"/.hermes/skills/fr/*/; do
    skill="$(basename "$skill_dir")"
    mkdir -p "$HERMES_HOME/skills/fr/$skill"
    cp "$skill_dir/SKILL.md" "$HERMES_HOME/skills/fr/$skill/SKILL.md"
    echo "  Installed $HERMES_HOME/skills/fr/$skill/SKILL.md"
  done
  if command -v fr &>/dev/null; then
    echo "Wiring Hermes hooks + rules (fr hermes install)..."
    if fr hermes install --source "$PLUGIN_ROOT" --home "$HERMES_HOME"; then
      echo "  Wired Hermes hooks + SOUL.md rules block"
    else
      echo "  WARNING: fr hermes install failed — hooks/rules not wired" >&2
    fi
  else
    echo "  WARNING: fr not on PATH — skipping fr hermes install (hooks/rules not wired)" >&2
  fi
else
  echo ""
  echo "Skipping Hermes Agent delivery (no ~/.hermes found; set"
  echo "HERMES_SKILLS_INSTALL=1 to force)."
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
