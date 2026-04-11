#!/usr/bin/env bash
# Validate SKILL.md files start with clean YAML frontmatter.
#
# Catches the "outer code fence leaked into skill content" class of bug
# (2026-04-11 incident, fixed in dd965e6). A SKILL.md must begin with
# '---' as its first non-empty line — anything else (notably a code fence
# like '```markdown' or '````markdown') indicates the plan's outer wrapper
# was copied into the target file during a full file rewrite.
#
# Usage:
#   validate-skills.sh                          # validate all skills/*/SKILL.md
#   validate-skills.sh path/to/SKILL.md ...     # validate specific files
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
ERRORS=()

if [ $# -eq 0 ]; then
  mapfile -t FILES < <(find "$REPO_ROOT/skills" -maxdepth 3 -name SKILL.md 2>/dev/null)
else
  FILES=("$@")
fi

for f in "${FILES[@]}"; do
  [ -f "$f" ] || continue
  first=$(awk 'NF {print; exit}' "$f")
  rel="${f#$REPO_ROOT/}"
  if [[ "$first" != "---" ]]; then
    ERRORS+=("$rel: first non-empty line is not '---' (got: '$first'). Possible fence-leak from plan source.")
  fi
done

if [ ${#ERRORS[@]} -gt 0 ]; then
  echo "Skill validation failed:" >&2
  for e in "${ERRORS[@]}"; do echo "  - $e" >&2; done
  exit 1
fi

echo "Validated ${#FILES[@]} skill file(s) — all clean."
