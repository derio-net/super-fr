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

# Preflight: the deps install.sh needs unconditionally. Fail loud and early.
for cmd in git uv jq; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: '$cmd' not found in PATH. Install it first, then re-run." >&2
    exit 1
  fi
done

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
