"""pytest-split's `--store-durations --clean-durations` file under xdist.

Spec 2026-11-01-ci-speed §3.B: the shard job runs with `-n auto` and uploads
the file at `--durations-path`. Workers register the writer too
(pytest_split/plugin.py), so this pins that the file left behind is the
controller's: each group's file holds exactly that group's tests, and the two
groups are disjoint and together complete.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _make_package(root: Path) -> None:
    for name in ("test_a.py", "test_b.py"):
        (root / name).write_text(
            "import pytest\n\n"
            "@pytest.mark.parametrize('n', range(3))\n"
            "def test_x(n):\n    assert True\n"
        )


def _run_group(root: Path, group: int) -> dict[str, float]:
    out = root / f"durations-{group}.json"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-o",
            "addopts=",
            "-n",
            "2",
            "--splits",
            "2",
            "--group",
            str(group),
            "--splitting-algorithm",
            "least_duration",
            "--durations-path",
            str(out),
            "--store-durations",
            "--clean-durations",
            str(root),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return json.loads(out.read_text())


def test_each_groups_file_is_the_controllers_and_the_groups_partition(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    _make_package(pkg)
    one = set(_run_group(pkg, 1))
    two = set(_run_group(pkg, 2))
    everything = {f"{f}::test_x[{n}]" for f in ("test_a.py", "test_b.py") for n in range(3)}
    assert len(everything) == 6
    assert one and two
    assert not one & two, "a test ran in both groups"
    assert one | two == everything
