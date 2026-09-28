"""`validate_profiles` — the `profiles` kind's structure validator (spec
2026-09-28-fr-profiles-services §3.D.4, R3), reached by `fr validate artifacts`."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.artifacts.validate import validate_repo

HEAD = "schema_version: 2\nprofiles:\n  dev:\n    purpose: x\ndefault: dev\n"


def _problems(tmp_path: Path, text: str) -> list[str]:
    path = tmp_path / ".devcontainer" / "fr-profiles.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    report = validate_repo(tmp_path, kind_name="profiles")
    assert report.checked == 1
    return [issue.message for issue in report.issues]


def test_a_valid_v2_file_passes(tmp_path: Path) -> None:
    text = HEAD + "forge:\n  type: gitlab\n  host: g.example.com\nci:\n  type: none\n"
    text += "tracking:\n  type: gitlab\n"
    assert _problems(tmp_path, text) == []


def test_a_v2_file_with_only_a_forge_passes(tmp_path: Path) -> None:
    assert _problems(tmp_path, HEAD + "forge:\n  type: github\n") == []


def test_type_specific_keys_are_allowed(tmp_path: Path) -> None:
    text = HEAD + "forge:\n  type: gitlab\nci:\n  type: gitlab-ci\n  job: build\n"
    assert _problems(tmp_path, text) == []


@pytest.mark.parametrize(
    ("block", "needle"),
    [
        ("forge:\n  type: bitbucket\n", "bitbucket"),
        ("forge:\n  type: github\nci:\n  type: travis\n", "travis"),
        ("forge:\n  type: github\nci:\n  type: jenkins\n  host: j.example.com\n", "#795"),
        ("forge:\n  type: github\ntracking:\n  type: jira\n  host: j.example.com\n", "#795"),
        ("forge:\n  type: github\ntracking:\n  type: gitlab\n", "#795"),
        ("forge:\n  type: github\nci:\n  type: gitlab-ci\n", "host"),
        ("forge:\n  host: x.example.com\n", "type"),
        ("forge: github\n", "forge"),
    ],
    ids=[
        "unknown-forge",
        "unknown-ci",
        "jenkins",
        "jira",
        "cross-forge-tracker",
        "missing-required-host",
        "missing-type",
        "not-a-mapping",
    ],
)
def test_a_bad_service_fails(tmp_path: Path, block: str, needle: str) -> None:
    problems = _problems(tmp_path, HEAD + block)
    assert problems, "expected a problem"
    assert any(needle in p for p in problems), problems


@pytest.mark.parametrize("key", ["backend: github\n", "host: g.example.com\n"])
def test_a_leftover_top_level_key_at_version_two_fails(tmp_path: Path, key: str) -> None:
    problems = _problems(tmp_path, HEAD + key + "forge:\n  type: github\n")
    assert any(key.split(":")[0] in p and "version 2" in p for p in problems), problems


def test_a_duplicate_key_fails(tmp_path: Path) -> None:
    text = HEAD + "forge:\n  type: github\nforge:\n  type: gitlab\n"
    assert any("duplicate key" in p for p in _problems(tmp_path, text))


def _v1(tmp_path: Path, text: str) -> list[str]:
    """A version-1 file is STALE, so `validate_repo` reports that and stops;
    its structure is checked by calling the validator directly."""
    from fr.artifacts.structure import validate_profiles

    path = tmp_path / "fr-profiles.yaml"
    path.write_text(text)
    return validate_profiles(path)


def test_a_valid_v1_file_passes_structure(tmp_path: Path) -> None:
    """Version 1 is still a shape fr reads (through `ProfilesV1`)."""
    assert _v1(tmp_path, "backend: gitlab\nhost: g.example.com\nprofiles: {}\n") == []


@pytest.mark.parametrize("text", ["backend: bitbucket\n", "forge_type: gitlab\n"])
def test_an_invalid_v1_file_fails(tmp_path: Path, text: str) -> None:
    problems = _v1(tmp_path, text)
    assert any(text.split(":")[0] in p for p in problems), problems


# --- phase-2 review --------------------------------------------------------


@pytest.mark.parametrize(
    "block",
    ["tracking:\n  type: gitlab\n", "ci:\n  type: gitlab-ci\n"],
    ids=["cross-forge-tracker", "hostless-foreign-ci"],
)
def test_an_undeclared_forge_is_derived_for_the_cross_service_rules(
    tmp_path: Path, block: str
) -> None:
    """r2: with no `forge:` the forge is derived offline (no origin here, so
    github) and the rules still run — fail closed, as `resolve_services` does."""
    assert _problems(tmp_path, HEAD + block)


def test_an_unknown_top_level_key_fails(tmp_path: Path) -> None:
    """r3: a typo would silently fall back to the forge's own tracker."""
    problems = _problems(tmp_path, HEAD + "forge:\n  type: github\ntrackng:\n  type: none\n")
    assert any("trackng" in p for p in problems), problems
