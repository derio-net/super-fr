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
from fr.config.space import config_space, rel
from fr.settings import SettingsError, load_settings
from fr.settings.model import Settings

TRIAGE_PATH: Final = rel("triage")

Predicate = Callable[[Path, Settings], tuple[str, ...]]
Message = str | Callable[[Settings], str]
"""A rule's message: a template with `{detail}`, or one chosen from the settings."""


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
    """The driven-scope keys `.fr/triage.yaml` sets, read from the default ref's commit
    (under stealth, from the tracking space, where `git.push` is always `ask`)."""
    if settings.git.push != "ask":
        return ()
    space = config_space(root)
    if settings.placement == "stealth":
        from fr.config.space import branch_fetched

        # Stealth forces `ask` on every run (alacarte R7), so a run whose tracking space
        # was never created must still start. fr cannot tell "not created" from "not
        # fetched here", so it says which it read as none (l-errors-r1), never silently.
        if not branch_fetched(space):
            import sys

            branch = (space.ref or "").removeprefix("origin/")
            print(
                f"fr: the stealth configuration branch {branch} is not fetched here, so fr "
                f"reads no driven triage scope from it; if it exists, fetch it: "
                f"git fetch origin {branch}",
                file=sys.stderr,
            )
            return ()
    text = space.at_default(TRIAGE_PATH)
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


def _unknown_disabled(root: Path, settings: Settings) -> tuple[str, ...]:
    """alacarte R3: a `workflows.disabled` entry no shipped or repo shape carries."""
    if not settings.workflows.disabled:
        return ()
    from fr.workflow.resolve import discover_names

    known = set(discover_names(root))
    return tuple(n for n in settings.workflows.disabled if n not in known)


def _every_shape_disabled(root: Path, settings: Settings) -> tuple[str, ...]:
    """alacarte R3: a list that leaves no shape to start a run on."""
    if not settings.workflows.disabled:
        return ()
    from fr.workflow.resolve import discover_names

    names = discover_names(root)
    left = [n for n in names if n not in settings.workflows.disabled]
    return () if left else tuple(names)


def _driven_triage_message(settings: Settings) -> str:
    """Under stealth `git.push: ask` is forced (epic D7), so the fix is the triage keys."""
    if settings.placement == "stealth":
        return (
            "placement stealth forces git.push: ask (epic D7), and .fr/triage.yaml in the "
            "tracking space sets {detail}: `fr triage batch drive` is unattended by design "
            "and cannot answer. git.push is not yours to change under stealth: remove the "
            "driven keys (post_merge, export, version, post_merge_restart) from .fr/triage.yaml"
        )
    return (
        "git.push: ask while .fr/triage.yaml (default branch) sets {detail}: driven triage "
        "scope is any of post_merge, export, version, post_merge_restart, and "
        "`fr triage batch drive` is unattended by design and cannot answer"
    )


RULES: Final[tuple[tuple[str, Predicate, Message], ...]] = (
    (
        "gates-off-with-ops",
        _live_plans_with_ops,
        "artifacts.gates: off while a live plan carries manual operations ({detail}); "
        "nothing would hold them",
    ),
    ("push-ask-with-driven-triage", _driven_triage, _driven_triage_message),
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
        "than stealth's own (forge labels, comments and issues off, pr_body minimal; git "
        "push and pr ask): stealth sets those keys itself and refuses a contrary value "
        "rather than ignoring it; remove the key from the tracking repo's settings file",
    ),
    (
        "unknown-disabled-shape",
        _unknown_disabled,
        "workflows.disabled names {detail}, which no shipped or repo workflow shape carries "
        "(`fr workflow check --all` lists them)",
    ),
    (
        "every-shape-disabled",
        _every_shape_disabled,
        "workflows.disabled disables every workflow shape ({detail}): no run could start",
    ),
)


def check_settings(root: Path) -> list[Problem]:
    """Every incoherent combination in *root*'s effective settings.

    An invalid file raises `SettingsError` (the loader's refusal), not a problem list.
    """
    settings = load_settings(root).settings
    return [
        Problem(
            rule_id,
            (message if isinstance(message, str) else message(settings)).format(
                detail=", ".join(details)
            ),
        )
        for rule_id, predicate, message in RULES
        if (details := predicate(root, settings))
    ]
