"""`fr init scaffold --tool` resolution (gh#574, spec §3.A).

`resolve_tools` is pure and runs before any file is written: an unknown tool is
refused rather than silently recorded, `--feature` is the escape hatch, `maven`
implies the java feature, and `<tool>@<version>` pins the feature's version.
"""

from __future__ import annotations

import pytest
from fr.isolation.scaffold import KNOWN_TOOLS, parse_tool, resolve_tools
from fr.isolation.types import IsolationError

JAVA = "ghcr.io/devcontainers/features/java:1"


@pytest.mark.parametrize("name", sorted(KNOWN_TOOLS))
def test_every_known_tool_reaches_its_feature(name: str) -> None:
    spec = KNOWN_TOOLS[name]
    resolved = resolve_tools([name], [])
    assert list(resolved) == [spec.feature]
    assert resolved[spec.feature] == dict(spec.options)


def test_the_existing_refs_are_unchanged() -> None:
    assert KNOWN_TOOLS["uv"].feature == "ghcr.io/jsburckhardt/devcontainer-features/uv:1"
    assert KNOWN_TOOLS["docker-in-docker"].feature == (
        "ghcr.io/devcontainers/features/docker-in-docker:2"
    )
    assert KNOWN_TOOLS["java"].feature == JAVA
    assert KNOWN_TOOLS["maven"].feature == JAVA


def test_java_and_maven_merge_into_one_java_feature_with_maven() -> None:
    resolved = resolve_tools(["java", "maven"], [])
    assert resolved == {JAVA: {"installMaven": True}}
    assert resolved[JAVA]["installMaven"] is True  # a JSON bool, not "true"


def test_maven_alone_implies_java() -> None:
    assert resolve_tools(["maven"], []) == {JAVA: {"installMaven": True}}


@pytest.mark.parametrize(
    ("tool", "expected"),
    [
        ("java@17", {JAVA: {"version": "17"}}),
        ("maven@3.9.6", {JAVA: {"installMaven": True, "mavenVersion": "3.9.6"}}),
        ("node@20", {"ghcr.io/devcontainers/features/node:1": {"version": "20"}}),
    ],
)
def test_at_version_sets_the_tools_version_option(tool: str, expected: dict) -> None:
    assert resolve_tools([tool], []) == expected


def test_java_version_and_maven_version_merge() -> None:
    assert resolve_tools(["java@17", "maven@3.9.6"], []) == {
        JAVA: {"version": "17", "installMaven": True, "mavenVersion": "3.9.6"}
    }


def test_the_same_tool_twice_is_idempotent() -> None:
    assert resolve_tools(["java@17", "java@17"], []) == {JAVA: {"version": "17"}}


def test_conflicting_versions_are_refused_naming_both() -> None:
    with pytest.raises(IsolationError) as exc:
        resolve_tools(["java@17", "java@21"], [])
    assert "17" in str(exc.value) and "21" in str(exc.value)


def test_an_unknown_tool_is_refused_naming_the_known_set_and_feature() -> None:
    with pytest.raises(IsolationError) as exc:
        resolve_tools(["uv", "nosuchtool"], [])
    msg = str(exc.value)
    assert "nosuchtool" in msg
    assert ", ".join(sorted(KNOWN_TOOLS)) in msg
    assert "--feature" in msg


def test_a_raw_feature_passes_through_with_no_options() -> None:
    assert resolve_tools([], ["ghcr.io/acme/x:1"]) == {"ghcr.io/acme/x:1": {}}


def test_a_raw_feature_equal_to_a_tools_ref_keeps_the_tools_options() -> None:
    assert resolve_tools(["maven"], [JAVA]) == {JAVA: {"installMaven": True}}


@pytest.mark.parametrize("bad", ["", "   ", "ghcr.io/acme/x:1 extra", "a\tb"])
def test_a_feature_that_is_empty_or_has_whitespace_is_refused(bad: str) -> None:
    with pytest.raises(IsolationError):
        resolve_tools([], [bad])


@pytest.mark.parametrize(
    "bad", ["java@", "@17", "", "java@ 17", "java@17 ", "java@1\t7", "java@17@x", "java@@17"]
)
def test_a_malformed_tool_arg_is_refused_naming_it(bad: str) -> None:
    """Empty name/version, whitespace in the version, or a second `@` (p3r-f1/f5)."""
    with pytest.raises(IsolationError) as exc:
        resolve_tools([bad], [])
    assert repr(bad) in str(exc.value)


def test_parse_tool() -> None:
    assert parse_tool("java") == ("java", None)
    assert parse_tool("maven@3.9.6") == ("maven", "3.9.6")
    for bad in ("java@ 17", "java@17 ", "java@17@x", "java@@17"):
        with pytest.raises(IsolationError, match="malformed"):
            parse_tool(bad)


def test_an_unknown_tool_differing_only_in_case_gets_a_hint() -> None:
    with pytest.raises(IsolationError) as exc:
        resolve_tools(["Java"], [])
    assert "did you mean 'java'?" in str(exc.value)


def test_a_truly_unknown_tool_gets_no_hint() -> None:
    with pytest.raises(IsolationError) as exc:
        resolve_tools(["nosuchtool"], [])
    assert "did you mean" not in str(exc.value)


@pytest.mark.parametrize(
    ("tools", "feature"),
    [
        (["java"], "ghcr.io/devcontainers/features/java:2"),
        ([], "ghcr.io/devcontainers/features/java:2"),
        (["java"], "ghcr.io/devcontainers/features/java"),
        ([], "ghcr.io/devcontainers/features/node:2"),
    ],
)
def test_a_feature_shadowing_a_known_tool_at_another_tag_is_refused(
    tools: list[str], feature: str
) -> None:
    """p3r-f2: a known tool's ref at another tag would yield a SECOND copy of the
    same feature; point at --tool instead."""
    with pytest.raises(IsolationError) as exc:
        resolve_tools(tools, [feature])
    msg = str(exc.value)
    assert feature in msg and "--tool" in msg
