"""The closed settings model (spec 2026-11-04-repo-feature-settings, R4)."""

from __future__ import annotations

from typing import Any

import pytest
from fr.settings import SettingsError
from fr.settings.model import parse_settings


def test_empty_settings_are_every_documented_default() -> None:
    s = parse_settings({}, source="x")
    assert s.schema_ == 1
    assert s.placement == "repo"
    assert (s.artifacts.acceptance, s.artifacts.test_plan, s.artifacts.gates) == ("on",) * 3
    assert (s.forge.labels, s.forge.comments, s.forge.issues) == ("on",) * 3
    assert s.forge.pr_body == "full"
    assert s.forge.report_comment == "off"
    assert (s.git.push, s.git.pr, s.git.history) == ("auto", "auto", "keep")
    assert s.git.commit.with_issue == "{type}({scope}): {summary} (#{issue})"
    assert s.git.commit.without_issue == "{type}({scope}): {summary}"


def test_yaml_booleans_read_as_on_off() -> None:
    """PyYAML reads a bare `on`/`off` as a bool; the documented values are the words."""
    s = parse_settings({"artifacts": {"gates": False}, "forge": {"labels": True}}, source="x")
    assert s.artifacts.gates == "off"
    assert s.forge.labels == "on"


@pytest.mark.parametrize(
    ("data", "key"),
    [
        ({"bogus": 1}, "bogus"),
        ({"forge": {"bogus": "on"}}, "forge.bogus"),
        ({"git": {"commit": {"bogus": "x"}}}, "git.commit.bogus"),
        ({"placement": "cloud"}, "placement"),
        ({"forge": {"pr_body": "tiny"}}, "forge.pr_body"),
        ({"git": {"push": "never"}}, "git.push"),
        ({"artifacts": {"gates": "maybe"}}, "artifacts.gates"),
        ({"schema": 2}, "schema"),
        ({"artifacts": {"spec": "off"}}, "artifacts.spec"),
        ({"artifacts": {"plan": "off"}}, "artifacts.plan"),
        ({"artifacts": {"journals": "off"}}, "artifacts.journals"),
        ({"artifacts": {"runs": "off"}}, "artifacts.runs"),
        ({"git": {"commit": {"with_issue": "{type}: {nope}"}}}, "git.commit.with_issue"),
        ({"git": {"commit": {"without_issue": "{type}: {issue}"}}}, "git.commit.without_issue"),
    ],
)
def test_a_bad_file_is_refused_naming_file_and_dotted_key(data: dict[str, Any], key: str) -> None:
    with pytest.raises(SettingsError) as e:
        parse_settings(data, source=".fr/settings.yaml")
    assert ".fr/settings.yaml" in str(e.value)
    assert key in str(e.value)


def test_a_non_mapping_file_is_refused() -> None:
    with pytest.raises(SettingsError, match="mapping"):
        parse_settings(["x"], source=".fr/settings.yaml")


def test_the_vocabularies_are_stated_once() -> None:
    from fr.settings import model

    assert model.PLACEMENTS == frozenset({"repo", "quiet", "stealth"})
    assert model.ON_OFF == frozenset({"on", "off"})
    assert model.PLACEHOLDERS == frozenset({"type", "scope", "summary", "issue"})
