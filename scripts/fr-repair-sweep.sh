#!/usr/bin/env bash
set -euo pipefail

# fr-repair-sweep — personal cross-repo maintenance tool, not part of the
# plugin's install surface (install.sh/bootstrap.sh don't ship or invoke
# this). Scans one or more given root directories for fr-enabled repos
# (each root's immediate subdirectories), runs `fr repair` on each one
# that's cleanly on a synced `main`, commits the result, and asks before
# pushing. Grew out of the 2026-07-06 spec-table-header-guard fix (#364):
# that PR taught `fr repair` to normalize a mislabeled `## Implementation
# Plans` header, and this script is how that repair actually gets applied
# across every repo it might have drifted in, instead of one-off by hand.
#
# Requires `fr` >= 3.8.4 (the version that added the header-normalization
# rewrite) on PATH — `fr --version` is printed at startup so a stale
# install is obvious rather than silently doing nothing.
#
# Usage: scripts/fr-repair-sweep.sh <all|one-by-one> <root>...
#   all|one-by-one   see push behavior below
#   root...          one or more directories whose immediate subdirectories
#                     are candidate repos (at least one required)
#
#   one-by-one   confirm push after each repo individually
#   all          process every eligible repo first (no push), then one
#                final prompt to push everything that got committed
#
# Per repo:
#   a. fr-enabled check (docs/superpowers/plans/ or .devcontainer/*/) — skip
#      silently if not, this is just noise otherwise.
#   b. must be on `main`. If `main` != `origin/main`: fast-forward it when
#      that's safe (local is a strict ancestor of origin/main and the tree
#      is clean); otherwise skip and report (ahead/diverged needs a human).
#   c. `fr repair` (dry run, for visibility) then `fr repair --yes`.
#   d. commit whatever changed under docs/superpowers/ — nothing else.
# Then: print a summary, ask before pushing.

MODE="${1:-}"
case "$MODE" in
  all|one-by-one) ;;
  *)
    echo "usage: $(basename "$0") <all|one-by-one> <root>..." >&2
    exit 2
    ;;
esac
shift

if [[ "$#" -eq 0 ]]; then
  echo "usage: $(basename "$0") <all|one-by-one> <root>..." >&2
  echo "  at least one root directory is required." >&2
  exit 2
fi
ROOTS=("$@")

if ! command -v fr >/dev/null 2>&1; then
  echo "fr not found on PATH — install it first." >&2
  exit 2
fi
echo "using: $(command -v fr) ($(fr --version))"

REPORT=()       # summary lines, printed once at the end
PUSH_QUEUE=()   # repo paths with a local commit ready to push

is_fr_enabled() {
  local repo="$1"
  [[ -d "$repo/docs/superpowers/plans" ]] && return 0
  compgen -G "$repo/.devcontainer/*/" >/dev/null 2>&1 && return 0
  return 1
}

# Fast-forwards local `main` to `origin/main` when that's a safe, lossless
# move (local strictly behind, clean tree). Ahead/diverged is left alone —
# resolving that is a judgment call, not something to automate here.
sync_main() {
  local repo="$1" local_sha remote_sha
  local_sha="$(git -C "$repo" rev-parse main)"
  remote_sha="$(git -C "$repo" rev-parse origin/main)"
  [[ "$local_sha" == "$remote_sha" ]] && return 0

  if ! git -C "$repo" merge-base --is-ancestor main origin/main; then
    REPORT+=("$(basename "$repo"): skipped — main has diverged from / is ahead of origin/main")
    return 1
  fi
  if [[ -n "$(git -C "$repo" status --porcelain)" ]]; then
    REPORT+=("$(basename "$repo"): skipped — main is behind origin/main but the tree is dirty")
    return 1
  fi
  if ! git -C "$repo" merge --ff-only -q origin/main; then
    REPORT+=("$(basename "$repo"): skipped — fast-forward sync failed")
    return 1
  fi
  echo "  synced main -> origin/main (fast-forward)"
  return 0
}

process_repo() {
  local repo="$1" name branch
  name="$(basename "$repo")"

  is_fr_enabled "$repo" || return 0   # not fr-enabled: skip silently

  echo "=== $name ==="

  if ! git -C "$repo" fetch --quiet origin main 2>/dev/null; then
    REPORT+=("$name: skipped — could not fetch origin/main")
    return 0
  fi

  branch="$(git -C "$repo" symbolic-ref --short -q HEAD || true)"
  if [[ "$branch" != "main" ]]; then
    REPORT+=("$name: skipped — on branch '${branch:-detached HEAD}', not main")
    return 0
  fi

  sync_main "$repo" || return 0

  ( cd "$repo" && fr repair ) || true
  if ! ( cd "$repo" && fr repair --yes ); then
    REPORT+=("$name: skipped — fr repair --yes failed (see output above)")
    return 0
  fi

  if git -C "$repo" diff --quiet -- docs/superpowers \
     && git -C "$repo" diff --cached --quiet -- docs/superpowers; then
    REPORT+=("$name: nothing to repair")
    return 0
  fi

  git -C "$repo" add docs/superpowers
  git -C "$repo" commit -q -m "$(cat <<'EOF'
fix: normalize Implementation Plans table refs via fr repair

Ran `fr repair --yes` as part of a cross-repo sweep.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
  local sha
  sha="$(git -C "$repo" rev-parse --short HEAD)"
  REPORT+=("$name: committed $sha — ready to push")
  PUSH_QUEUE+=("$repo")

  if [[ "$MODE" == "one-by-one" ]]; then
    read -r -p "Push $name now? [y/N] " ans
    if [[ "$ans" =~ ^[Yy]$ ]]; then
      git -C "$repo" push
      REPORT+=("$name: pushed")
    else
      REPORT+=("$name: push declined — left committed locally")
    fi
  fi
}

for root in "${ROOTS[@]}"; do
  [[ -d "$root" ]] || continue
  for repo in "$root"/*/; do
    [[ -d "${repo}.git" ]] || continue
    process_repo "${repo%/}"
  done
done

echo
echo "=== Summary ==="
printf '%s\n' "${REPORT[@]}"

if [[ "$MODE" == "all" && ${#PUSH_QUEUE[@]} -gt 0 ]]; then
  echo
  echo "Repos with a local commit ready to push:"
  printf '  - %s\n' "${PUSH_QUEUE[@]}"
  read -r -p "Push all of the above now? [y/N] " ans
  if [[ "$ans" =~ ^[Yy]$ ]]; then
    for repo in "${PUSH_QUEUE[@]}"; do
      git -C "$repo" push && echo "pushed: $(basename "$repo")"
    done
  else
    echo "Push declined — commits left local."
  fi
fi
