"""The S1 transition gate (spec 2026-11-28-s1-followups R1, R10).

Every test here forces its side of the gate (monkeypatching `fr.__version__` and
the environment), so a release into 9.2 turns none of them red."""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import fr
import pytest
from fr.config import transition

pytestmark = pytest.mark.own_artifacts


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("9.1.0rc10", False),
        ("9.1.0-rc.10", False),
        ("9.1.3", False),
        ("9.2.0rc1", True),
        ("9.2.0-rc.1", True),
        ("9.2.0", True),
        ("10.0.0", True),
        ("not-a-version", True),
    ],
)
def test_refusing_follows_the_release_line(
    monkeypatch: pytest.MonkeyPatch, version: str, expected: bool
) -> None:
    monkeypatch.delenv(transition.ENV, raising=False)
    monkeypatch.setattr(fr, "__version__", version)
    assert transition.refusing() is expected


@pytest.mark.parametrize(
    ("value", "expected"), [("refuse", True), ("open", False), ("", False), ("1", False)]
)
def test_only_refuse_in_the_environment_ends_it_early(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: bool
) -> None:
    monkeypatch.setattr(fr, "__version__", "9.1.0")
    monkeypatch.setenv(transition.ENV, value)
    assert transition.refusing() is expected


def test_the_environment_never_extends_the_transition(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fr, "__version__", "9.2.0")
    monkeypatch.setenv(transition.ENV, "open")
    assert transition.refusing() is True


def test_old_path_refusal_names_both_paths_and_the_migration() -> None:
    err = transition.old_path_refusal("docs/superpowers/plan-config.yaml", ".fr/plan-config.yaml")
    assert isinstance(err, transition.TransitionError)
    text = str(err)
    assert "docs/superpowers/plan-config.yaml" in text
    assert ".fr/plan-config.yaml" in text
    assert "fr migrate artifacts --yes" in text


def test_the_transition_errors_are_settings_errors() -> None:
    from fr.settings import SettingsError

    assert issubclass(transition.TransitionError, SettingsError)
    assert issubclass(transition.LegacyEnvRefused, transition.TransitionError)


# --- R9: one `9.2` per language, and it is the minor after S1's release -------------------

REPO = Path(__file__).resolve().parents[2]
SHELL_LIB = REPO / "plugins" / "super-fr" / "hooks" / "lib" / "fr-isolation-decision.sh"
MARKER_TS = REPO / "packages" / "fr-opencode-plugin" / "src" / "marker.ts"
S1_FRAGMENT = REPO / ".changes" / "feat-event-driven-a-la-carte.yaml"


def _shell_refuse_from() -> tuple[int, int]:
    found = re.findall(
        r"^FR_REFUSE_FROM=(\d+)\.(\d+) # fr-refuse-from$", SHELL_LIB.read_text(), re.M
    )
    assert len(found) == 1, "the shell library names FR_REFUSE_FROM exactly once"
    return int(found[0][0]), int(found[0][1])


def _ts_refuse_from() -> tuple[int, int]:
    found = re.findall(
        r"^export const REFUSE_FROM = \[(\d+), (\d+)\] as const; // fr-refuse-from$",
        MARKER_TS.read_text(),
        re.M,
    )
    assert len(found) == 1, "marker.ts names REFUSE_FROM exactly once"
    return int(found[0][0]), int(found[0][1])


def test_the_gate_literals_agree() -> None:
    assert _shell_refuse_from() == transition.REFUSE_FROM
    assert _ts_refuse_from() == transition.REFUSE_FROM


@pytest.mark.skipif(not S1_FRAGMENT.exists(), reason="S1's fragment was consumed by a release")
def test_the_gate_is_the_minor_after_s1s_release() -> None:
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        import changes
        from versions import Version
    finally:
        sys.path.remove(str(REPO / "scripts"))
    current = tomllib.loads((REPO / "packages" / "fr" / "pyproject.toml").read_text())
    pending = changes.aggregate(changes.load_pending(REPO))
    release = Version.parse(changes.bumped(current["project"]["version"], pending))
    major, minor = transition.REFUSE_FROM
    assert (release.major, release.minor + 1) == (major, minor), (str(release), (major, minor))
