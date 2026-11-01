"""`scripts/split_check.py` — CI's proof that the shards ran exactly the collected set.

Spec 2026-11-01-ci-speed §3.B (R5): the multiset of node ids across the shards'
duration files must equal what the leg collects; any missing, extra or
duplicated id is named.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "split_check.py"

spec = importlib.util.spec_from_file_location("split_check", SCRIPT)
assert spec and spec.loader
split_check = importlib.util.module_from_spec(spec)
sys.modules["split_check"] = split_check
spec.loader.exec_module(split_check)

COLLECTED = (
    "tests/a.py::test_1\ntests/a.py::test_2\ntests/b.py::TestX::test_3\n\n"
    "3 tests collected in 0.5s\n"
)


def test_parse_collected_keeps_only_node_ids() -> None:
    assert split_check.parse_collected(COLLECTED) == [
        "tests/a.py::test_1",
        "tests/a.py::test_2",
        "tests/b.py::TestX::test_3",
    ]


def test_check_is_empty_when_shards_equal_the_collected_set() -> None:
    shards = {
        "s1": {"tests/a.py::test_1": 1.0, "tests/a.py::test_2": 2.0},
        "s2": {"tests/b.py::TestX::test_3": 0.1},
    }
    assert split_check.check(split_check.parse_collected(COLLECTED), shards) == []


def test_check_names_missing_extra_and_duplicated_ids() -> None:
    shards = {
        "s1": {"tests/a.py::test_1": 1.0, "tests/a.py::test_2": 1.0, "tests/x.py::test_extra": 1.0},
        "s2": {"tests/a.py::test_2": 1.0},
    }
    problems = "\n".join(split_check.check(split_check.parse_collected(COLLECTED), shards))
    assert "tests/b.py::TestX::test_3" in problems and "missing" in problems
    assert "tests/x.py::test_extra" in problems and "extra" in problems
    assert "tests/a.py::test_2" in problems and "s1" in problems and "s2" in problems


def test_merge_unions_with_sorted_keys() -> None:
    merged = split_check.merge({"s1": {"b": 1.0}, "s2": {"a": 2.0}})
    assert list(merged) == ["a", "b"]
    assert merged == {"a": 2.0, "b": 1.0}


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), *args], capture_output=True, text=True, check=False
    )


def test_cli_check_and_merge(tmp_path: Path) -> None:
    (tmp_path / "c.txt").write_text(COLLECTED)
    (tmp_path / "s1.json").write_text(
        json.dumps({"tests/a.py::test_1": 1, "tests/a.py::test_2": 1})
    )
    (tmp_path / "s2.json").write_text(json.dumps({"tests/b.py::TestX::test_3": 1}))
    ok = _cli(
        "check",
        "--collected",
        str(tmp_path / "c.txt"),
        str(tmp_path / "s1.json"),
        str(tmp_path / "s2.json"),
    )
    assert ok.returncode == 0, ok.stderr
    assert "split-check: 3 tests, 2 shards, complete" in ok.stdout
    bad = _cli("check", "--collected", str(tmp_path / "c.txt"), str(tmp_path / "s1.json"))
    assert bad.returncode == 1
    assert "tests/b.py::TestX::test_3" in bad.stdout
    out = tmp_path / "not-yet" / "m.json"
    m = _cli("merge", "-o", str(out), str(tmp_path / "s1.json"), str(tmp_path / "s2.json"))
    assert m.returncode == 0, m.stderr
    assert sorted(json.loads(out.read_text())) == sorted(
        ["tests/a.py::test_1", "tests/a.py::test_2", "tests/b.py::TestX::test_3"]
    )
