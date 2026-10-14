#!/usr/bin/env bash
# super-fr remote one-liner installer.
#
#   curl -fsSL https://raw.githubusercontent.com/derio-net/super-fr/main/scripts/bootstrap.sh | bash
#   curl -fsSL .../scripts/bootstrap.sh | bash -s -- --uninstall   # forward flags
#   curl -fsSL .../scripts/bootstrap.sh | bash -s -- --version RC  # pick a channel
#
# --version (spec 2026-10-14-exit-gates R22; every other flag goes to install.sh):
#   (none)      newest installable vX.Y.Z; with none yet, origin/main, saying so
#   RC          newest installable vX.Y.Z-rc.N (numeric order)
#   X.Y.Z       that release          X.Y.Z-RC   newest vX.Y.Z-rc.*
#   X.Y.Z-rc.N  exactly that RC       main       origin/main (development)
# A tag is installable only if its scripts/install.sh carries the comment
# "# fr-install-channels: 1"; an unknown or uninstallable version lists the
# installable ones and installs nothing.
#
# This is a thin source-manager: it clones (or updates) super-fr into a managed
# cache dir, then exec's the canonical scripts/install.sh — which stays the
# single source of truth for what "install" actually does. Re-running self-heals
# (fetch, then check out the chosen channel: the newest release by default, or
# what --version names; main is `checkout -B main origin/main`), so the
# one-liner doubles as an updater and the operator never manually clones.
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

VERSION=""
HAVE_VERSION=0
ARGS=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --version)
      if [ "$#" -lt 2 ] || [ -z "$2" ]; then
        echo "ERROR: --version needs a value (RC, X.Y.Z, X.Y.Z-RC, X.Y.Z-rc.N or main)." >&2
        exit 1
      fi
      VERSION="$2"; HAVE_VERSION=1; shift 2 ;;
    --version=*) VERSION="${1#--version=}"; HAVE_VERSION=1; shift ;;
    *) ARGS+=("$1"); shift ;;
  esac
done

if [ -d "$SRC/.git" ]; then
  echo "Updating super-fr source at $SRC ..."
  git -C "$SRC" fetch --quiet --tags --force origin main </dev/null
else
  echo "Cloning super-fr into $SRC ..."
  mkdir -p "$(dirname "$SRC")"
  # Clone main explicitly so a fork/mirror with a different default branch fails
  # here, not opaquely later; the channel (a tag or main) is checked out below.
  git clone --quiet --branch main "$REMOTE" "$SRC" </dev/null
fi

# Release and RC tags, one per line, versions only (no leading v). The per-branch
# pre-merge tags rc/<branch>/<sha> never match and are not channels.
channel_tags() {
  git -C "$SRC" ls-remote --tags origin </dev/null | sed -n 's|.*refs/tags/\(v[0-9][0-9.]*\(-rc\.[0-9]*\)\{0,1\}\)$|\1|p' |
    grep -E '^v[0-9]+\.[0-9]+\.[0-9]+(-rc\.[0-9]+)?$' | sort -u
}
# Installable = the tag's install.sh carries the channel marker.
installable_tags() {
  local t content
  while IFS= read -r t; do
    content="$(git -C "$SRC" show "refs/tags/$t:scripts/install.sh" 2>/dev/null </dev/null)" || continue
    if printf '%s\n' "$content" | grep -qx '# fr-install-channels: 1'; then
      echo "$t"
    fi
  done < <(channel_tags)
  return 0
}
# Numeric version order (rc.10 > rc.9, and vX.Y.Z above its own RCs): sort on
# X.Y.Z[.N] fields, never lexically; a final's N is a large sentinel.
sort_versions() {
  sed -e 's/^v//' -e 's/-rc\./ /' | awk '{ n = split($1, v, "."); printf "%d %d %d %d %s\n", v[1], v[2], v[3], ($2 == "" ? 999999999 : $2), $0 }' |
    sort -k1,1n -k2,2n -k3,3n -k4,4n | cut -d' ' -f5- | sed -e 's/^\([0-9][0-9.]*\) \(.*\)$/v\1-rc.\2/' -e 't' -e 's/^\([0-9][0-9.]*\)$/v\1/'
}

refuse() {
  local all
  echo "ERROR: $1" >&2
  all="$(installable_tags | sort_versions)"
  if [ -n "$all" ]; then
    echo "Installable versions:" >&2
    printf '  %s\n' "$all" >&2
  else
    echo "No installable versions exist yet; use --version main." >&2
  fi
  exit 1
}

TAG=""
WANT="$(printf '%s' "$VERSION" | sed -e 's/^v//' | tr '[:upper:]' '[:lower:]')"
if [ "$HAVE_VERSION" = 1 ] && [ "$WANT" = main ]; then
  TAG=main
elif [ "$HAVE_VERSION" = 0 ]; then
  TAG="$(installable_tags | grep -v -- '-rc\.' | sort_versions | tail -n 1 || true)"
  [ -n "$TAG" ] || TAG=main_fallback
else
  AVAILABLE="$(installable_tags)"
  case "$WANT" in
    rc) CAND="$(printf '%s\n' "$AVAILABLE" | grep -- '-rc\.' | sort_versions | tail -n 1 || true)" ;;
    *-rc) CAND="$(printf '%s\n' "$AVAILABLE" | grep -F "v${WANT%-rc}-rc." | sort_versions | tail -n 1 || true)" ;;
    *) CAND="$(printf '%s\n' "$AVAILABLE" | grep -Fx "v$WANT" || true)" ;;
  esac
  [ -n "$CAND" ] || refuse "version '$VERSION' is not installable (unknown, missing, or its tag predates install channels)."
  TAG="$CAND"
fi

case "$TAG" in
  main | main_fallback)
    if [ "$TAG" = main_fallback ]; then
      echo "No installable release yet; installing origin/main."
    fi
    git -C "$SRC" checkout -q -f -B main origin/main </dev/null
    echo "Channel: main" ;;
  *)
    git -C "$SRC" checkout -q -f --detach "refs/tags/$TAG" </dev/null
    echo "Channel: $TAG" ;;
esac

echo "Running installer ..."
exec "$SRC/scripts/install.sh" "${ARGS[@]+"${ARGS[@]}"}"
