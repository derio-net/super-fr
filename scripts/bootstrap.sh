#!/usr/bin/env bash
# super-fr remote one-liner installer.
#
#   curl -fsSL https://raw.githubusercontent.com/derio-net/super-fr/main/scripts/bootstrap.sh | bash
#   curl -fsSL .../scripts/bootstrap.sh | bash -s -- --uninstall   # forward flags
#
# This is a thin source-manager: it clones (or updates) super-fr into a managed
# cache dir, then exec's the canonical scripts/install.sh — which stays the
# single source of truth for what "install" actually does. Re-running self-heals
# (fetch + reset --hard origin/main), so the one-liner doubles as an updater and
# the operator never manually clones.
#
# Prefer-not-to-pipe-curl-into-bash alternative:
#   curl -fsSL .../scripts/bootstrap.sh -o bootstrap.sh
#   less bootstrap.sh        # inspect
#   bash bootstrap.sh
#
# Overrides (mainly for tests / non-default layouts):
#   FR_SRC_DIR     where to keep the managed checkout (default ~/.cache/fr/src/super-fr)
#   FR_SRC_REMOTE  git remote to clone/fetch  (default https://github.com/derio-net/super-fr)
set -euo pipefail

REMOTE="${FR_SRC_REMOTE:-https://github.com/derio-net/super-fr}"
SRC="${FR_SRC_DIR:-$HOME/.cache/fr/src/super-fr}"

# >>> prereq preflight (keep identical in scripts/install.sh and scripts/bootstrap.sh)
# Name EVERY missing prerequisite and the command that installs it on this host,
# then exit 1 (gh#1087). Stopping at the first one with "install it first" cost a
# round trip per tool and left the reader to work out the package manager.
require_prereqs() {
  local cmd missing=() pkgs=() os sudo=""
  for cmd in "$@"; do
    command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
  done
  [ "${#missing[@]}" -eq 0 ] && return 0
  for cmd in "${missing[@]}"; do
    echo "ERROR: '$cmd' not found in PATH." >&2
    [ "$cmd" = uv ] || pkgs+=("$cmd")
  done
  echo "Install the missing prerequisites, then re-run:" >&2
  if [ "${#pkgs[@]}" -gt 0 ]; then
    os="$(uname -s 2>/dev/null || echo unknown)"
    [ "$(id -u 2>/dev/null || echo 0)" = 0 ] || sudo="sudo "
    case "$os" in
      Darwin)
        command -v brew >/dev/null 2>&1 || echo "  (Homebrew first: https://brew.sh)" >&2
        echo "  brew install ${pkgs[*]}" >&2 ;;
      *)
        if command -v apt-get >/dev/null 2>&1; then
          echo "  ${sudo}apt-get update && ${sudo}apt-get install -y ${pkgs[*]}" >&2
        elif command -v dnf >/dev/null 2>&1; then
          echo "  ${sudo}dnf install -y ${pkgs[*]}" >&2
        elif command -v yum >/dev/null 2>&1; then
          echo "  ${sudo}yum install -y ${pkgs[*]}" >&2
        elif command -v apk >/dev/null 2>&1; then
          echo "  ${sudo}apk add ${pkgs[*]}" >&2
        elif command -v pacman >/dev/null 2>&1; then
          echo "  ${sudo}pacman -S --needed ${pkgs[*]}" >&2
        elif command -v zypper >/dev/null 2>&1; then
          echo "  ${sudo}zypper install -y ${pkgs[*]}" >&2
        else
          echo "  install with your system's package manager: ${pkgs[*]}" >&2
        fi ;;
    esac
  fi
  case " ${missing[*]} " in
    *" uv "*)
      echo "  curl -LsSf https://astral.sh/uv/install.sh | sh   # uv; then put ~/.local/bin on PATH" >&2 ;;
  esac
  exit 1
}
# <<< prereq preflight
# Preflight: the deps install.sh needs unconditionally (its own list), checked
# here too so a missing one fails before the clone, not after it.
require_prereqs git uv jq rsync

if [ -d "$SRC/.git" ]; then
  echo "Updating super-fr source at $SRC ..."
  git -C "$SRC" fetch --quiet origin main
  git -C "$SRC" reset --hard origin/main
else
  echo "Cloning super-fr into $SRC ..."
  mkdir -p "$(dirname "$SRC")"
  # install.sh's preflight requires HEAD == main; clone main explicitly so a
  # fork/mirror with a different default branch fails here, not opaquely later.
  git clone --branch main "$REMOTE" "$SRC"
fi

echo "Running installer ..."
exec "$SRC/scripts/install.sh" "$@"
