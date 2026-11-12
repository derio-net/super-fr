"""`fr lenses check` problems (spec 2026-11-12-review-lenses R3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.lenses.check import check_config


def _write(root: Path, text: str) -> None:
    (root / ".fr").mkdir(exist_ok=True)
    (root / ".fr" / "lenses.yaml").write_text(text)


def test_no_file_is_no_problem(tmp_path: Path) -> None:
    assert check_config(tmp_path) == []


def test_a_valid_file_is_no_problem(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "disable: [errors]\nlenses:\n  a11y:\n    title: T\n    brief: b\n"
        "require:\n  - paths: ['src/**']\n    lenses: [security, a11y]\n",
    )

    assert check_config(tmp_path) == []


@pytest.mark.parametrize(
    ("text", "needle"),
    [
        ("lenses: [\n", "invalid YAML"),
        ("bogus: 1\n", "bogus"),
        ("lenses:\n  Bad_Id:\n    title: T\n    brief: b\n", "Bad_Id"),
        ("lenses:\n  ok:\n    title: T\n    brief: ''\n", "brief"),
        ("disable: [nope]\n", "nope"),
        ("require:\n  - paths: ['x']\n    lenses: [nope]\n", "nope"),
        (
            "disable: [security]\nrequire:\n  - paths: ['x']\n    lenses: [security]\n",
            "disables",
        ),
    ],
)
def test_one_named_problem_each(tmp_path: Path, text: str, needle: str) -> None:
    _write(tmp_path, text)

    problems = check_config(tmp_path)

    assert len(problems) == 1, problems
    assert needle in problems[0]
