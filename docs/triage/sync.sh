#!/usr/bin/env bash
# Mirror a triage scope's durable state between the working state directory
# (~/.cache/fr/triage/<scope>, where fr reads and writes it) and this repo
# (docs/triage/<scope>, where it is kept in history).
#
#   docs/triage/sync.sh export [scope]          cache -> repo   (then commit, via a PR)
#   docs/triage/sync.sh import [scope] [--force] repo -> cache   (a new machine, or a lost cache)
#
# Only inputs and history travel: the judgement files, subsystems.yaml, the
# architecture manifest, the stored snapshots and the authored-fragment sources.
# Everything fr can rebuild stays out: facts.json, origins-facts.json, the
# rendered pages and the built fragments (authored-src/build.py writes them).
# import never overwrites a newer cache file unless --force is given.
set -euo pipefail

cmd="${1:-}"; scope="${2:-derio-net--super-fr}"; force="${3:-}"
here="$(cd "$(dirname "$0")" && pwd)"
repo_dir="$here/$scope"
cache_dir="${FR_TRIAGE_CACHE:-$HOME/.cache/fr/triage}/$scope"

files=(judgements.yaml origins.yaml subsystems.yaml architecture/manifest.yaml)
dirs=(snapshots authored-src)

copy() { # src_root dst_root rsync-flags...
  local src="$1" dst="$2"; shift 2
  mkdir -p "$dst/architecture"
  for f in "${files[@]}"; do
    [ -f "$src/$f" ] && rsync -a "$@" "$src/$f" "$dst/$f"
  done
  for d in "${dirs[@]}"; do
    [ -d "$src/$d" ] && rsync -a "$@" --exclude '__pycache__' "$src/$d/" "$dst/$d/"
  done
  return 0
}

case "$cmd" in
  export)
    [ -d "$cache_dir" ] || { echo "no state at $cache_dir" >&2; exit 2; }
    copy "$cache_dir" "$repo_dir"
    echo "exported $cache_dir -> $repo_dir"
    ;;
  import)
    [ -d "$repo_dir" ] || { echo "no state at $repo_dir" >&2; exit 2; }
    if [ "$force" = "--force" ]; then copy "$repo_dir" "$cache_dir"
    else copy "$repo_dir" "$cache_dir" --update; fi
    echo "imported $repo_dir -> $cache_dir"
    echo "next: fr triage collect --repo <owner/repo> --pr-limit 1000, then build.py and the three renders (see README.md)"
    ;;
  *)
    sed -n '2,13p' "$0" >&2; exit 2
    ;;
esac
