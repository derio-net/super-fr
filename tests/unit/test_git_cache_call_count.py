"""The git answer cache's effect, pinned (spec 2026-11-19-local-suite-cost R1, §3.A).

The profiled scenario is spec §2's test,
`tests/unit/test_record_review_fixes.py::test_a_crash_at_the_commit_restores_everything_and_a_retry_converges`:
two `record_support.started_run` walks to `implement`, a clean resolve, a crashed
resolve and its retry — 19 in-process `fr` calls. Before the cache it started
**926** git processes (measured 2026-11-18 with a profile of that test alone; this
test's counter read 924 on the same tree without the cache). With the cache it
reads 611: `remote_name` and `remote_default_ref` now cost one answer per `fr`
call (`config --system` once per scope, `config --get checkout.defaultRemote`,
`remote`, `symbolic-ref`, `rev-parse --verify`: 19 each) instead of about seven.
The remaining starts are call sites R1 does not cover (`rev-parse --verify
<ref>^{commit}` in settings and the acceptance fold, `rev-parse --git-dir`,
`for-each-ref`, ...); see plan journal finding `p1-call-count-target`.

Measure it: `uv run pytest tests/unit/test_git_cache_call_count.py -p no:xdist --no-cov -s`
(it prints the count).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

BASELINE = 926
CEILING = 615
"""The measured 611 with a small margin; spec §3.A's 500 is out of R1's reach."""


def test_the_profiled_scenario_starts_far_fewer_git_processes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit.test_record_review_fixes import (
        test_a_crash_at_the_commit_restores_everything_and_a_retry_converges as scenario,
    )

    starts: list[list[str]] = []
    real = subprocess.Popen

    class Counted(real):  # type: ignore[misc,valid-type]
        def __init__(self, args, *a, **kw):  # type: ignore[no-untyped-def]
            argv = [str(x) for x in args] if isinstance(args, (list, tuple)) else [str(args)]
            if argv and Path(argv[0]).name == "git":
                starts.append(argv)
            super().__init__(args, *a, **kw)

    monkeypatch.setattr(subprocess, "Popen", Counted)
    scenario(tmp_path, monkeypatch)
    print(f"\ngit starts: {len(starts)} (baseline {BASELINE}, ceiling {CEILING})")
    assert len(starts) <= CEILING, f"{len(starts)} git starts, more than {CEILING}"
