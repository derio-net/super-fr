"""Per-repo feature settings (spec 2026-11-04-repo-feature-settings, R2-R5)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from pathlib import Path

    from fr.settings.load import EffectiveSettings

POLICY_FEATURES: Final = ("acceptance", "test_plan", "gates")
"""The `artifacts.*` keys: policy kinds only. spec, plan, journals and runs have no key."""
FORGE_KINDS: Final = ("labels", "comments", "issues")


DISABLED: Final = "disabled by repo setting"
"""The one wording every surface uses when a repo setting turned a feature off."""


class SettingsError(Exception):
    """The settings file (or the fr reading it) cannot be served; names file and key."""


def load_settings(repo_root: Path) -> EffectiveSettings:
    """The effective settings of *repo_root* (see `fr.settings.load`)."""
    from fr.settings.load import load_settings as _load

    return _load(repo_root)


def disabled(repo_root: Path, feature: str) -> bool:
    """Whether the repo turned *feature* (`acceptance`, `test_plan`, `gates`) off."""
    if feature not in POLICY_FEATURES:
        raise ValueError(f"{feature!r} has no setting; policy features are {POLICY_FEATURES}")
    return bool(getattr(load_settings(repo_root).settings.artifacts, feature) == "off")


def disabled_because(feature: str, what: str) -> str:
    """`<what>: disabled by repo setting (artifacts.<feature>: off)` — the refusal line."""
    return f"{what}: {DISABLED} (artifacts.{feature}: off)"


def spec_policy_problems(repo_root: Path, spec_path: Path) -> list[str]:
    """What the repo's policy forbids in the spec at *spec_path* (R6-R8).

    A `## Test Plan` under `test_plan: off`; any `gate:` line in `## Verification` under
    `gates: off`; a row-level `gate: <row>=<gate>` line under `acceptance: off` (a
    run-level line stays valid). A section that does not parse is not this check's to report.
    """
    from fr.spec import find_test_plan_heading
    from fr.verification.spec_section import SectionError, parse_section

    try:
        text = spec_path.read_text()
    except (OSError, UnicodeDecodeError):
        return []  # an unreadable spec is the other validators' to report
    problems: list[str] = []
    if find_test_plan_heading(text) is not None and disabled(repo_root, "test_plan"):
        problems.append(disabled_because("test_plan", "the spec carries a `## Test Plan`"))
    try:
        section = parse_section(text)
    except SectionError:
        section = None
    if section is not None:
        if (section.gate is not None or section.row_gates) and disabled(repo_root, "gates"):
            problems.append(
                disabled_because("gates", "the spec's `## Verification` has a `gate:` line")
            )
        elif section.row_gates and disabled(repo_root, "acceptance"):
            problems.append(
                disabled_because(
                    "acceptance", "the spec's `## Verification` has a row-level `gate: <row>=` line"
                )
            )
    return problems


def forge_allows(repo_root: Path, kind: str) -> bool:
    """Whether fr may write *kind* (`labels`, `comments`, `issues`) to the forge."""
    if kind not in FORGE_KINDS:
        raise ValueError(f"{kind!r} is not a forge write kind; kinds are {FORGE_KINDS}")
    return bool(getattr(load_settings(repo_root).settings.forge, kind) == "on")


__all__ = [
    "DISABLED",
    "SettingsError",
    "disabled",
    "disabled_because",
    "forge_allows",
    "load_settings",
    "spec_policy_problems",
]
