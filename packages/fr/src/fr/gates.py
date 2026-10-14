"""The gate vocabulary — spec 2026-10-14 exit-gates R2.

A run's exit names who must act on it. Gates are a closed set; only the
post-merge gates (`tester`, `devops`) hold a merge's close-out. The other four
are recorded but never hold anything. A workflow step's `gate: operator` is a
different thing (a step gate) and is not in this vocabulary.
"""

from __future__ import annotations

from typing import Literal, get_args

Gate = Literal["developer", "reviewer", "tester", "devops", "owner", "security"]

GATES: frozenset[str] = frozenset(get_args(Gate))
POST_MERGE_GATES: frozenset[str] = frozenset({"tester", "devops"})
