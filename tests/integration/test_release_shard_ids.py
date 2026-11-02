"""A release shard's node ids are the ids `collect` lists, under real pytest.

Found on the first release cut by the ci-speed job graph (run 41389896526):
every shard was green and `split-check` reported every test both missing and
extra, because the shard passed `--durations-path <runner.temp path>` as two
argv tokens. pytest resolves its rootdir before pytest-split registers that
option, so the path read as a test argument; with no positional path the rootdir
became the common ancestor of the checkout and `runner.temp`, every nodeid
gained a `<org>/<repo>/` prefix, and the project's pytest config did not load.
The unit tests fake `run`, so only real pytest argv reaches this.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_ids", REPO / "scripts" / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"{name}_ids"] = mod
    spec.loader.exec_module(mod)
    return mod


release = _load("release")
split_check = _load("split_check")


def _project(root: Path) -> None:
    root.mkdir()
    # A marker only the project's own config registers: under `--strict-markers`
    # a run that lost the config fails to collect instead of passing quietly.
    (root / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\nmarkers = ["slow: a registered marker"]\n'
    )
    (root / "test_a.py").write_text(
        "import pytest\n\n"
        "@pytest.mark.slow\n"
        "@pytest.mark.parametrize('n', range(3))\n"
        "def test_x(n):\n    assert True\n"
    )


def _pytest(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_shard_with_its_durations_file_outside_the_checkout_reports_collects_ids(
    tmp_path: Path,
) -> None:
    proj = tmp_path / "work" / "org" / "repo"
    proj.parent.mkdir(parents=True)
    _project(proj)
    # Like `runner.temp`: a sibling of the checkout, never inside it.
    temp = tmp_path / "work" / "_temp"
    temp.mkdir()
    out = temp / "shard-durations.json"
    out.write_text("{}")

    collected = _pytest(proj, [*release._collect_pytest_args(proj), "--collect-only"])
    assert collected.returncode == 0, collected.stdout + collected.stderr
    ids = split_check.parse_collected(collected.stdout)
    assert ids and all(i.startswith("test_a.py::") for i in ids)

    shard = _pytest(proj, release._shard_pytest_args(proj, group=1, splits=1, out=out))
    assert shard.returncode == 0, shard.stdout + shard.stderr

    ran = json.loads(out.read_text())
    assert split_check.check(ids, {"1": ran}) == []
