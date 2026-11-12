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
        (
            "disable: [security]\nlenses:\n  security:\n    title: T\n    brief: b\n",
            "disables and also defines security",
        ),
    ],
)
def test_one_named_problem_each(tmp_path: Path, text: str, needle: str) -> None:
    _write(tmp_path, text)

    problems = check_config(tmp_path)

    assert len(problems) == 1, problems
    assert needle in problems[0]


def test_an_undecodable_file_is_one_problem(tmp_path: Path) -> None:
    (tmp_path / ".fr").mkdir()
    (tmp_path / ".fr" / "lenses.yaml").write_bytes(b"\xff\xfe\x00bad")

    problems = check_config(tmp_path)

    assert len(problems) == 1, problems
    assert ".fr/lenses.yaml" in problems[0]


def test_a_malformed_shipped_manifest_is_a_problem_not_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shipped = tmp_path / "shipped"
    shipped.mkdir()
    (shipped / "security.yaml").write_text("lens: [\n")
    monkeypatch.setenv("FR_SHIPPED_LENSES_DIR", str(shipped))
    _write(tmp_path, "disable: []\n")

    problems = check_config(tmp_path)

    assert len(problems) == 1, problems
    assert "invalid YAML" in problems[0]


def test_a_head_config_disabling_a_lens_a_base_only_rule_requires_is_a_problem(
    tmp_path: Path,
) -> None:
    from tests.unit.lens_repo import lens_repo

    root = lens_repo(
        tmp_path, base_config="require:\n  - paths: ['src/auth/**']\n    lenses: [security]\n"
    )
    _write(root, "disable: [security]\n")

    problems = check_config(root)

    assert any("disables security" in p and "src/auth/**" in p for p in problems), problems
