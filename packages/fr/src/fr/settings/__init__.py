"""Per-repo feature settings (spec 2026-11-04-repo-feature-settings, R2-R5)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from fr.services.require import TrackerRequiredError

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
        if section.row_gates and disabled(repo_root, "acceptance"):
            problems.append(
                disabled_because(
                    "acceptance", "the spec's `## Verification` has a row-level `gate: <row>=` line"
                )
            )
    return problems


TRACKING_NONE: Final = (
    "tracking: none (.devcontainer/fr-profiles.yaml declares `tracking: {type: none}`)"
)
"""Why a forge write is off when the services declaration, not a setting, turns it off."""


LEDGER_KINDS: Final = ("labels", "comments")
"""The kinds of the PR gate ledger: the `gate:*` / `gate:*-passed` labels and the
gate-pass comments a pull request carries (R9)."""


def setting_block(forge: object, kind: str) -> str | None:
    """`forge.<kind>: off (...)` when the `forge` settings section turns *kind* off."""
    if kind not in FORGE_KINDS:
        raise ValueError(f"{kind!r} is not a forge write kind; kinds are {FORGE_KINDS}")
    if getattr(forge, kind) != "on":
        return f"forge.{kind}: off ({DISABLED})"
    return None


def forge_block(repo_root: Path, kind: str, *, lenient: bool = False) -> str | None:
    """None when fr may make a TRACKER write of *kind* (`labels`, `comments`, `issues`)
    to the forge; else the setting that forbids it: `forge.<kind>: off`, or
    `tracking: none`, which keeps meaning all three are off for tracker work (R9).

    The settings are read strictly (`SettingsError` propagates: an unreadable policy
    refuses, it never reads as the defaults). The tracking declaration is strict too
    (`ServicesError`), unless *lenient*: then an unreadable one counts as a tracker,
    the posture of the sites that must never raise. The PR gate ledger is not a tracker
    write: it asks `ledger_block`."""
    why = setting_block(load_settings(repo_root).settings.forge, kind)
    if why is not None:
        return why
    return TRACKING_NONE if tracking_none(repo_root, lenient=lenient) else None


def tracking_none(repo_root: Path, *, lenient: bool = False) -> bool:
    """Whether *repo_root* declares `tracking: {type: none}` (lenient: unreadable is no)."""
    from fr.services.model import ServicesError
    from fr.services.resolve import resolve_tracking

    try:
        return resolve_tracking(repo_root, lenient=lenient).type == "none"
    except ServicesError:
        if not lenient:
            raise
        return False


def forge_allows(repo_root: Path, kind: str, *, lenient: bool = False) -> bool:
    """Whether fr may make a tracker write of *kind* (`labels`, `comments`, `issues`)."""
    return forge_block(repo_root, kind, lenient=lenient) is None


def ledger_block(repo_root: Path, kind: str) -> str | None:
    """The one rule of the PR gate ledger (R9): None when fr may write a PR's `gate:*`
    labels (*kind* `labels`) or its gate-pass comment (`comments`); else the setting
    that forbids it. Only `forge.labels` / `forge.comments` decide: `tracking: none`
    never governed the ledger, which the release gate and the DevOps stage read.
    `deliver`'s label sync, `fr gate pass`, `fr gate backfill` and the driver's pass all
    ask this."""
    if kind not in LEDGER_KINDS:
        raise ValueError(f"{kind!r} is not a gate-ledger kind; kinds are {LEDGER_KINDS}")
    return setting_block(load_settings(repo_root).settings.forge, kind)


def ledger_allows(repo_root: Path, kind: str) -> bool:
    """Whether fr may write the PR gate ledger's *kind* (`labels`, `comments`)."""
    return ledger_block(repo_root, kind) is None


class ForgeQuietError(TrackerRequiredError):
    """A forge write of a kind the repo turned off; a `TrackerRequiredError`, so every
    caller that refused `tracking: none` refuses this the same way."""


def require_forge(repo_root: Path, *kinds: str) -> None:
    """Raise `ForgeQuietError` naming the setting when fr may not write each of *kinds*
    (a filed issue carries labels, so filing asks for both)."""
    for kind in kinds:
        why = forge_block(repo_root, kind)
        if why is not None:
            raise ForgeQuietError(f"no forge {kind} are written here — {why}.")


__all__ = [
    "DISABLED",
    "LEDGER_KINDS",
    "TRACKING_NONE",
    "ForgeQuietError",
    "SettingsError",
    "disabled",
    "disabled_because",
    "forge_allows",
    "forge_block",
    "ledger_allows",
    "ledger_block",
    "load_settings",
    "require_forge",
    "setting_block",
    "spec_policy_problems",
    "tracking_none",
]
