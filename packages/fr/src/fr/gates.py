"""The gate vocabulary — spec 2026-10-14 exit-gates R2.

A run's exit names who must act on it. Gates are a closed set; only the
post-merge gates (`tester`, `devops`) hold a merge's close-out. `devops` also holds
the merge itself (spec 2026-10-22-fr-ops R14, `PRE_MERGE_HOLD_GATES`): the DevOps
stage owns that merge. The other four are recorded but never hold anything. A
workflow step's `gate: operator` is a different thing (a step gate) and is not in
this vocabulary.
"""

from __future__ import annotations

from typing import Literal, get_args

Gate = Literal["developer", "reviewer", "tester", "devops", "owner", "security"]

GATES: frozenset[str] = frozenset(get_args(Gate))
POST_MERGE_GATES: frozenset[str] = frozenset({"tester", "devops"})
"""Gates that hold a merge's close-out; their labels and pass rules (`fr gate pass`)."""
PRE_MERGE_HOLD_GATES: frozenset[str] = frozenset({"devops"})
"""Gates that also hold the merge: the triage merge path refuses a PR carrying
`gate:<g>` without `gate:<g>-passed` (R14). A forge-UI merge is not blocked."""
