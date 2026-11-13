"""Coherence rules over the effective settings (spec 2026-11-04-repo-feature-settings, R5).

The rules are DATA: a tuple of `(id, predicate, message)`. A predicate returns the
offending details (an empty tuple when the combination is coherent), and the message
carries a `{detail}` placeholder for them. Adding a rule is one tuple entry.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import yaml

from fr.artifacts.paths import KIND_DIRS, feature_roots, space_for
from fr.settings import SettingsError, load_settings
from fr.settings.load import read_at_default
from fr.settings.model import Settings

TRIAGE_PATH: Final = ".fr/triage.yaml"

Predicate = Callable[[Path, Settings], tuple[str, ...]]


@dataclass(frozen=True)
class Problem:
    id: str
    message: str


def _live_plans_with_ops(root: Path, settings: Settings) -> tuple[str, ...]:
    if settings.artifacts.gates != "off":
        return ()
    from fr.ops.load import plan_has_ops

    # Every feature's live plans: under quiet each feature has its own plans directory.
    found: set[str] = set()
    for froot in feature_roots(space_for(root)):
        plans = froot / KIND_DIRS["plan"]
        if plans.is_dir():
            found |= {d.name for d in plans.iterdir() if d.is_dir() and plan_has_ops(root, d)}
    return tuple(sorted(found))


DRIVEN_TRIAGE_KEYS: Final = ("post_merge", "export", "version", "post_merge_restart")
"""The definition of "driven triage scope": the `.fr/triage.yaml` keys the unattended
`fr triage batch drive` acts on. Any of them set (on the default ref) is driven scope."""


def _driven_triage(root: Path, settings: Settings) -> tuple[str, ...]:
    """The driven-scope keys `.fr/triage.yaml` sets, read from the default ref's commit."""
    if settings.git.push != "ask":
        return ()
    text = read_at_default(root, TRIAGE_PATH)
    if text is None:
        return ()
    from fr.triage.model import parse_triage_config

    try:
        config, _ = parse_triage_config(yaml.safe_load(text) or {})
    except (yaml.YAMLError, ValueError) as e:
        raise SettingsError(f"{TRIAGE_PATH}: cannot be parsed on the default branch: {e}") from e
    return tuple(
        key
        for key, on in (
            ("post_merge", bool(config.post_merge)),
            ("export", config.export is not None),
            ("version", config.version is not None),
            ("post_merge_restart", config.post_merge_restart != "none"),
        )
        if on
    )


def _report_without_comments(_root: Path, settings: Settings) -> tuple[str, ...]:
    forge = settings.forge
    if forge.report_comment == "on" and forge.comments == "off":
        return ("forge.report_comment",)
    return ()


def _report_comment_outside_repo(_root: Path, settings: Settings) -> tuple[str, ...]:
    """R22: a PR comment is a forge write the quiet and stealth placements do not make."""
    if settings.forge.report_comment == "on" and settings.placement in ("quiet", "stealth"):
        return ("forge.report_comment",)
    return ()


def _stealth_forge_explicit(root: Path, settings: Settings) -> tuple[str, ...]:
    """R5: under stealth, a forge key the tracking file sets explicitly to anything but
    stealth's own value. Stealth sets those keys itself; the contrary value is refused
    rather than ignored."""
    if settings.placement != "stealth":
        return ()
    return load_settings(root).contrary


RULES: Final[tuple[tuple[str, Predicate, str], ...]] = (
    (
        "gates-off-with-ops",
        _live_plans_with_ops,
        "artifacts.gates: off while a live plan carries manual operations ({detail}); "
        "nothing would hold them",
    ),
    (
        "push-ask-with-driven-triage",
        _driven_triage,
        "git.push: ask while .fr/triage.yaml (default branch) sets {detail}: driven triage "
        "scope is any of post_merge, export, version, post_merge_restart, and "
        "`fr triage batch drive` is unattended by design and cannot answer",
    ),
    (
        "report-comment-needs-comments",
        _report_without_comments,
        "{detail}: on needs forge.comments: on",
    ),
    (
        "report-comment-needs-repo-placement",
        _report_comment_outside_repo,
        "{detail}: on is refused under placement quiet and stealth (reports are local only)",
    ),
    (
        "stealth-forge-explicit",
        _stealth_forge_explicit,
        "{detail} is set explicitly in the tracking repo's settings file, to a value other "
        "than stealth's own (labels, comments and issues off, pr_body minimal): stealth sets "
        "those keys itself and refuses a contrary value rather than ignoring it",
    ),
)


def check_settings(root: Path) -> list[Problem]:
    """Every incoherent combination in *root*'s effective settings.

    An invalid file raises `SettingsError` (the loader's refusal), not a problem list.
    """
    settings = load_settings(root).settings
    return [
        Problem(rule_id, message.format(detail=", ".join(details)))
        for rule_id, predicate, message in RULES
        if (details := predicate(root, settings))
    ]
