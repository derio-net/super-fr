"""A git commit date one test sets never reaches the next test (gh#1428's CI run).

`tests/unit/test_placement_merged.py`'s `tick()` writes `GIT_COMMITTER_DATE` and
`GIT_AUTHOR_DATE` into `os.environ` directly; its own autouse `_home` fixture
monkeypatches them first, so they were restored there. A module that imports
`Product` without `_home` (test_acceptance_amend_origin.py) left them set for the
rest of the worker, and every later commit in that process was dated 2026-11-05:
`test_run_ci_evidence` then read a fresh head as ten days old ("14404 minutes
after it was committed"). Longest-first shard order put the two on one worker.

The two tests below run in file order; the second fails if the first one's dates
survive it.
"""

from __future__ import annotations

import os

from tests.conftest import GIT_DATE_KEYS, SESSION_GIT_DATES


def test_a_test_sets_git_dates_directly() -> None:
    for key in GIT_DATE_KEYS:
        os.environ[key] = "1762300800 +0000"


def test_the_next_test_does_not_inherit_them() -> None:
    assert {k: os.environ.get(k) for k in GIT_DATE_KEYS} == SESSION_GIT_DATES
