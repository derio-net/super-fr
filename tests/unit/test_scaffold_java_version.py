"""gh#574 — `detect_java_version`: the project's Java major from its version
files and root pom.xml (spec §3.A "Java version detection")."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.isolation.scaffold import detect_java_version

POM_NS = 'xmlns="http://maven.apache.org/POM/4.0.0"'


def _pom(root: Path, body: str, ns: str = POM_NS) -> None:
    (root / "pom.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<project {ns}>\n'
        f"<modelVersion>4.0.0</modelVersion>\n{body}\n</project>\n"
    )


def _props(**props: str) -> str:
    inner = "".join(f"<{k}>{v}</{k}>" for k, v in props.items())
    return f"<properties>{inner}</properties>"


def test_nothing_is_none(tmp_path: Path) -> None:
    assert detect_java_version(tmp_path) is None


def test_java_version_file(tmp_path: Path) -> None:
    (tmp_path / ".java-version").write_text("17.0.9\n")
    assert detect_java_version(tmp_path) == ("17", ".java-version")


def test_sdkmanrc(tmp_path: Path) -> None:
    (tmp_path / ".sdkmanrc").write_text("# sdkman\njava=21.0.1-tem\nmaven=3.9.6\n")
    assert detect_java_version(tmp_path) == ("21", ".sdkmanrc")


def test_tool_versions(tmp_path: Path) -> None:
    (tmp_path / ".tool-versions").write_text("nodejs 20.1.0\njava temurin-17.0.9+9\n")
    assert detect_java_version(tmp_path) == ("17", ".tool-versions")


def test_precedence_java_version_over_everything(tmp_path: Path) -> None:
    (tmp_path / ".java-version").write_text("11\n")
    (tmp_path / ".sdkmanrc").write_text("java=21.0.1-tem\n")
    (tmp_path / ".tool-versions").write_text("java temurin-17.0.9+9\n")
    _pom(tmp_path, _props(**{"maven.compiler.release": "8"}))
    assert detect_java_version(tmp_path) == ("11", ".java-version")


def test_precedence_sdkmanrc_over_tool_versions_and_pom(tmp_path: Path) -> None:
    (tmp_path / ".sdkmanrc").write_text("java=21.0.1-tem\n")
    (tmp_path / ".tool-versions").write_text("java temurin-17.0.9+9\n")
    _pom(tmp_path, _props(**{"maven.compiler.release": "8"}))
    assert detect_java_version(tmp_path) == ("21", ".sdkmanrc")


def test_precedence_tool_versions_over_pom(tmp_path: Path) -> None:
    (tmp_path / ".tool-versions").write_text("java temurin-17.0.9+9\n")
    _pom(tmp_path, _props(**{"maven.compiler.release": "8"}))
    assert detect_java_version(tmp_path) == ("17", ".tool-versions")


def test_pom_release_property_with_namespace(tmp_path: Path) -> None:
    _pom(tmp_path, _props(**{"maven.compiler.release": "17"}))
    assert detect_java_version(tmp_path) == ("17", "pom.xml maven.compiler.release")


def test_pom_without_namespace(tmp_path: Path) -> None:
    _pom(tmp_path, _props(**{"maven.compiler.release": "17"}), ns="")
    assert detect_java_version(tmp_path) == ("17", "pom.xml maven.compiler.release")


def test_pom_property_order_release_before_target_source_java_version(tmp_path: Path) -> None:
    _pom(
        tmp_path,
        _props(
            **{
                "java.version": "8",
                "maven.compiler.source": "11",
                "maven.compiler.target": "17",
                "maven.compiler.release": "21",
            }
        ),
    )
    assert detect_java_version(tmp_path) == ("21", "pom.xml maven.compiler.release")


def test_pom_source_1_8_normalises_to_8(tmp_path: Path) -> None:
    _pom(tmp_path, _props(**{"maven.compiler.source": "1.8"}))
    assert detect_java_version(tmp_path) == ("8", "pom.xml maven.compiler.source")


def test_pom_one_level_indirection(tmp_path: Path) -> None:
    _pom(
        tmp_path,
        _props(**{"java.version": "11", "maven.compiler.release": "${java.version}"}),
    )
    assert detect_java_version(tmp_path) == ("11", "pom.xml maven.compiler.release")


def test_pom_compiler_plugin_release(tmp_path: Path) -> None:
    _pom(
        tmp_path,
        "<build><plugins><plugin>"
        "<groupId>org.apache.maven.plugins</groupId>"
        "<artifactId>maven-compiler-plugin</artifactId>"
        "<configuration><release>21</release></configuration>"
        "</plugin></plugins></build>",
    )
    assert detect_java_version(tmp_path) == ("21", "pom.xml maven-compiler-plugin release")


def test_pom_compiler_plugin_target(tmp_path: Path) -> None:
    _pom(
        tmp_path,
        "<build><plugins><plugin>"
        "<artifactId>maven-compiler-plugin</artifactId>"
        "<configuration><target>1.8</target></configuration>"
        "</plugin></plugins></build>",
    )
    assert detect_java_version(tmp_path) == ("8", "pom.xml maven-compiler-plugin target")


def test_pom_unresolvable_placeholder_skips_to_next_source(tmp_path: Path) -> None:
    _pom(
        tmp_path,
        _props(**{"maven.compiler.release": "${nowhere}", "maven.compiler.target": "17"}),
    )
    assert detect_java_version(tmp_path) == ("17", "pom.xml maven.compiler.target")


def test_pom_only_unresolvable_placeholder_is_none(tmp_path: Path) -> None:
    _pom(tmp_path, _props(**{"maven.compiler.release": "${nowhere}"}))
    assert detect_java_version(tmp_path) is None


def test_pom_two_level_indirection_is_not_followed(tmp_path: Path) -> None:
    _pom(
        tmp_path,
        _props(**{"a": "17", "b": "${a}", "maven.compiler.release": "${b}"}),
    )
    assert detect_java_version(tmp_path) is None


@pytest.mark.parametrize("text", ["<project><properties>", "not xml at all", ""])
def test_malformed_pom_is_none_and_never_raises(tmp_path: Path, text: str) -> None:
    (tmp_path / "pom.xml").write_text(text)
    assert detect_java_version(tmp_path) is None


def test_unparseable_version_file_falls_through(tmp_path: Path) -> None:
    (tmp_path / ".java-version").write_text("temurin-latest\n")
    _pom(tmp_path, _props(**{"maven.compiler.release": "17"}))
    assert detect_java_version(tmp_path) == ("17", "pom.xml maven.compiler.release")


# --- phase-4 review (p4r-f1..f4) ---------------------------------------------


@pytest.mark.parametrize(
    ("raw", "major"),
    [
        # p4r-f1: vendor/arch digits and graalvm's own version used to win.
        ("openjdk64-11.0.2", "11"),
        ("oracle64-1.8.0.181", "8"),
        ("zulu64-17", "17"),
        ("adoptopenjdk-openj9-11.0.11+9", "11"),
        ("semeru-openj9-17", "17"),
        ("graalvm-22.3.0+java17", "17"),
        # regressions that must hold
        ("corretto-1.8.0.392", "8"),
        ("1.8", "8"),
        ("17", "17"),
        ("temurin-21", "21"),
        ("java=8.0.392-tem", "8"),
        ("java=11.0.21-amzn", "11"),
        ("adoptopenjdk-8.0.272+10", "8"),
        ("corretto-17.0.9.8.1", "17"),
        ("openjdk-21", "21"),
        ("zulu-8.74.0.17", "8"),
        ("temurin-17.0.9+9", "17"),
    ],
)
def test_java_major_ignores_vendor_digits(raw: str, major: str) -> None:
    from fr.isolation.scaffold import _java_major

    assert _java_major(raw) == major


@pytest.mark.parametrize("raw", ["1", "5", "41", "64", "temurin-latest"])
def test_java_major_outside_plausible_range_is_a_miss(raw: str) -> None:
    """p4r-f2: a bare `1` (or 64, or 5) is no Java major."""
    from fr.isolation.scaffold import _java_major

    assert _java_major(raw) is None


def test_implausible_version_file_falls_through_to_pom(tmp_path: Path) -> None:
    (tmp_path / ".java-version").write_text("1\n")
    _pom(tmp_path, _props(**{"maven.compiler.release": "17"}))
    assert detect_java_version(tmp_path) == ("17", "pom.xml maven.compiler.release")


_PLUGIN = (
    "<plugin><artifactId>maven-compiler-plugin</artifactId>"
    "<configuration><release>17</release></configuration></plugin>"
)


def test_pom_compiler_plugin_wins_over_properties(tmp_path: Path) -> None:
    """p4r-f3: Maven semantics — the plugin's explicit configuration beats the
    `maven.compiler.*` properties that only feed its defaults."""
    _pom(
        tmp_path,
        _props(**{"maven.compiler.source": "1.8"}) + f"<build><plugins>{_PLUGIN}</plugins></build>",
    )
    assert detect_java_version(tmp_path) == ("17", "pom.xml maven-compiler-plugin release")


def test_pom_plugin_management_is_read(tmp_path: Path) -> None:
    _pom(
        tmp_path,
        f"<build><pluginManagement><plugins>{_PLUGIN}</plugins></pluginManagement></build>",
    )
    assert detect_java_version(tmp_path) == ("17", "pom.xml maven-compiler-plugin release")


def test_pom_profile_properties_are_ignored(tmp_path: Path) -> None:
    _pom(
        tmp_path,
        "<profiles><profile><id>x</id>"
        + _props(**{"maven.compiler.release": "21"})
        + "</profile></profiles>",
    )
    assert detect_java_version(tmp_path) is None


def test_pom_xml_comment_is_ignored(tmp_path: Path) -> None:
    _pom(
        tmp_path,
        "<properties><!-- <maven.compiler.release>21</maven.compiler.release> -->"
        "<maven.compiler.release>17</maven.compiler.release></properties>",
    )
    assert detect_java_version(tmp_path) == ("17", "pom.xml maven.compiler.release")
