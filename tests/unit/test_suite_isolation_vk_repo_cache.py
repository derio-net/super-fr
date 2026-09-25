"""The suite must not leak `fr_vk.config._cache` from one test into the next.

`fr_vk.config` keeps a process-global, single-slot `list_repos` snapshot that
production clears once per tick. A test that populates it (e.g. via `tick()`
against a fake registry) and a later test that calls `dispatch_phase` directly
— no tick, so no clear — used to share it: `test_bridge_e2e.py` followed by
`test_bridge_lifecycle.py::test_lifecycle_hook_not_invoked_when_env_unset`
failed with "VK has no repo registered ... (known short names: ['bar', 'foo'])".
Serial default order happened to hide it; `pytest -n auto` reshuffles order and
exposed it.

The observation has to cross a test boundary, and under xdist two tests in one
outer module may land on different workers. So the pair runs in its own inner
pytest session, in a subprocess, with a copy of the REAL `tests/conftest.py` —
its order is fixed whatever the outer scheduler does, and what is under test is
the conftest this suite actually uses.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

CONFTEST = Path(__file__).resolve().parents[1] / "conftest.py"

PAIR = """
from fr_vk import config


class _Registry:
    def list_repos(self):
        return {"repos": [{"id": "uuid-leaked", "name": "leaked"}]}


def test_a_populates_the_cache():
    assert config.known_repos(_Registry()) == {"leaked": "uuid-leaked"}


def test_b_starts_with_an_empty_cache():
    assert config._cache is None, f"leaked from the previous test: {config._cache!r}"
"""


def test_repo_cache_does_not_leak_between_tests(tmp_path: Path) -> None:
    # An ini here stops pytest walking up from tmp_path to some ancestor's
    # addopts (--rootdir alone does not stop ini discovery).
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    (tmp_path / "conftest.py").write_text(CONFTEST.read_text())
    (tmp_path / "test_pair.py").write_text(PAIR)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-p",
            "no:xdist",
            "-p",
            "no:cov",
            "--rootdir",
            str(tmp_path),
            str(tmp_path / "test_pair.py"),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 passed" in result.stdout, result.stdout
