#!/usr/bin/env bash
# Check every published page against its group's writing standard
# (spec 2026-11-13-writing-standards-docs, R1-R4).
#
#   scripts/check-writing-standards.sh <blog-craft-dir>
#
# The globs are .fr/docs.yaml's `pages:`. A page's own front matter
# (`writing_standard: <name>|none`) wins over its group's --default, and the
# checker reads .writing-standard-terms from the repo root. Every group runs;
# the script exits with the highest code any group returned (1 on a FAIL,
# 2 on a usage error; warnings alone exit 0).
set -uo pipefail

if [ $# -ne 1 ] || [ ! -d "$1" ]; then
  echo "usage: $0 <blog-craft-dir>" >&2
  exit 2
fi
checker="$(realpath "$1")/tools/validate_writing_standard.py"
# The repo this script belongs to, whatever the caller's directory.
top="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)" || exit 2
cd "$top" || exit 2

worst=0
run() {
  uv run --isolated --no-project --with pyyaml python "$checker" "$@"
  local code=$?
  if [ "$code" -gt "$worst" ]; then worst=$code; fi
}

# One line per page group: --default <standard> <globs>.
run --default ste docs/*.md docs/reference/*.md
run --default plain-language docs/explainers/*.md

exit "$worst"
