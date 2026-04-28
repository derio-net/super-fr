"""Configuration loader — reads plan-config.yaml and builds a Profile.

The dispatch gate is fail-closed: missing file, missing key, ``false``, ``null``,
or a non-map scalar all mean dispatch is disabled.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from vk.plan.format import PlanFormat


@dataclass(frozen=True)
class PlanConfig:
    """Plan file naming and storage settings."""

    filename: str = "YYYY-MM-DD-{name}.md"
    save_to: str = "docs/superpowers/plans/"
    archive_to: str = "docs/superpowers/archived-plans/"


@dataclass(frozen=True)
class HeaderConfig:
    """Required header fields and allowed status values."""

    required: tuple[str, ...] = ("Spec", "Status")
    status_values: tuple[str, ...] = ("Not Started", "In Progress", "Complete")


_DEFAULT_DISPATCH_LABELS: dict[str, str] = {
    "agentic": "vk-ready",
    "manual": "manual",
    "in_progress": "in-progress",
    "pr_ready": "pr-ready",
}


@dataclass(frozen=True)
class DispatchConfig:
    """GitHub Issues dispatch settings.  Present = dispatch enabled."""

    owner: str = "derio-net"
    project_board: str = "Derio Ops"
    default_repo: str = ""
    target: str = "github-issues"
    labels: dict[str, str] = field(default_factory=lambda: dict(_DEFAULT_DISPATCH_LABELS))


@dataclass(frozen=True)
class Profile:
    """Loaded plan-config profile.  Single source of truth for repo behaviour."""

    plan: PlanConfig = field(default_factory=PlanConfig)
    header: HeaderConfig = field(default_factory=HeaderConfig)
    dispatch: DispatchConfig | None = None

    @property
    def dispatch_enabled(self) -> bool:
        """Fail-closed: only True when an explicit dispatch map was loaded."""
        return self.dispatch is not None

    @property
    def format(self) -> PlanFormat:
        """Format is derived from dispatch presence (Decision D3)."""
        from vk.plan.format import PlanFormat

        return PlanFormat.PHASED if self.dispatch_enabled else PlanFormat.FLAT


def _parse_dispatch(raw: object) -> DispatchConfig | None:
    """Parse the raw dispatch value from YAML.  Returns None for disabled."""
    if raw is None:
        return None
    if raw is False:
        return None
    if raw is True:
        warnings.warn(
            "`dispatch: true` is invalid — dispatch must be a map, not a scalar. "
            "Treating as disabled.",
            UserWarning,
            stacklevel=3,
        )
        return None
    if not isinstance(raw, dict):
        return None
    raw_labels = raw.get("labels")
    user_labels: dict[str, str] = raw_labels if isinstance(raw_labels, dict) else {}
    return DispatchConfig(
        owner=raw.get("owner", "derio-net"),
        project_board=raw.get("project_board", "Derio Ops"),
        default_repo=raw.get("default_repo", ""),
        target=raw.get("target", "github-issues"),
        labels={**_DEFAULT_DISPATCH_LABELS, **user_labels},
    )


def _parse_plan(raw: dict[str, object] | None) -> PlanConfig:
    """Parse plan section with defaults."""
    if not raw or not isinstance(raw, dict):
        return PlanConfig()
    return PlanConfig(
        filename=str(raw.get("filename", PlanConfig.filename)),
        save_to=str(raw.get("save_to", PlanConfig.save_to)),
        archive_to=str(raw.get("archive_to", PlanConfig.archive_to)),
    )


def _parse_header(raw: dict[str, object] | None) -> HeaderConfig:
    """Parse header section with defaults."""
    if not raw or not isinstance(raw, dict):
        return HeaderConfig()
    required = raw.get("required", list(HeaderConfig.required))
    status_values = raw.get("status_values", list(HeaderConfig.status_values))
    return HeaderConfig(
        required=tuple(required) if isinstance(required, list) else HeaderConfig.required,
        status_values=tuple(status_values)
        if isinstance(status_values, list)
        else HeaderConfig.status_values,
    )


def load_profile(config_path: Path) -> Profile:
    """Load a Profile from a plan-config.yaml file.

    Returns an all-defaults Profile if the file is missing or empty.
    """
    if not config_path.exists():
        return Profile()

    text = config_path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        return Profile()

    return Profile(
        plan=_parse_plan(data.get("plan")),
        header=_parse_header(data.get("header")),
        dispatch=_parse_dispatch(data.get("dispatch")),
    )
