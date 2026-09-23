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
