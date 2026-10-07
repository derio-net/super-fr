#!/usr/bin/env bash
# Waves 11-12, proposed by the 2026-10-07 triage (judgements in
# derio-net--super-fr/judgements.yaml). Not yet created: `batch create` needs
# fresh facts, and `fr triage collect` could not run from the session that wrote
# this (no GraphQL there). Run from a host that can collect:
#
#   fr triage state import --from docs/triage --repo derio-net/super-fr
#   fr triage collect --repo derio-net/super-fr --pr-limit 1000
#   fr triage check --repo derio-net/super-fr     # expect no unranked, no unplaced besides these
#   bash docs/triage/waves-2026-10-07.sh          # add --yes to each line to write the owed claims
#   fr triage render --repo derio-net/super-fr --open
set -euo pipefail
R=(--repo derio-net/super-fr)

# ---- Wave 11: who acts next (operator priority: #1086 and similar) ----------
fr triage batch create needs-you "${R[@]}" --wave 11 --bump minor --skill goal \
  --title "Board and driver say who acts next: Needs-you columns, mergeable-aware merge ready, red-CI hand-back" \
  --issue super-fr#1086 --issue super-fr#1082 --issue super-fr#1065 --issue super-fr#1066 \
  --rationale "Operator priority 2026-10-07. #1086 D and #1082 are one hand-back mechanism; #1065/#1066 touch the same cards and column list. Starts with a brainstorm: column model and run-cursor signals."

fr triage batch create adopt-hold "${R[@]}" --wave 11 --bump minor --skill goal \
  --title "batch adopt --hold: adopted agents wait for the operator" \
  --issue super-fr#1081 \
  --rationale "Small and urgent while sweeps run: 3 of 9 adopted agents started work unasked."

fr triage batch create claims-followups "${R[@]}" --wave 11 --bump patch --skill goal \
  --title "Claims follow-ups: drop fr:in-progress on finish, warn on single-user trust, merge skips held batches" \
  --issue super-fr#1085 --issue super-fr#1075 --issue super-fr#1076 \
  --rationale "Triage-claims follow-ups; the forge label and trust set are the shared coordination channel."

# ---- Wave 12 -----------------------------------------------------------------
fr triage batch create merge-queue "${R[@]}" --wave 12 --after needs-you --bump minor --skill goal \
  --title "Merge race: required checks or merge queue on main, release-bot bypass, driver enqueues where required" \
  --issue super-fr#1062 \
  --rationale "Changes the merge train after needs-you does. Pieces 1-2 are operator infra; starts with a brainstorm."

fr triage batch create adopt-sweep "${R[@]}" --wave 12 --after adopt-hold --bump minor --skill goal \
  --title "batch adopt from a real sweep: richer --list, default-branch sessions, issue from transcript" \
  --issue super-fr#1071 --issue super-fr#1069 --issue super-fr#1072 \
  --rationale "The rest of the 2026-10-07 sweep findings; same command module as adopt-hold."

fr triage batch create model-binding-fixes "${R[@]}" --wave 12 --bump patch --skill goal \
  --title "fr models: clean dead-binding reason, clean refusal on a corrupt models.yaml" \
  --issue super-fr#1057 --issue super-fr#1055 \
  --rationale "Two small model-binding defects, one subsystem."
