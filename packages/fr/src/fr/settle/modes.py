"""The effective settle modes (spec 2026-11-23-pr-readiness-wait R1, R6).

Today: the repo setting `git.settle`, read from the default branch like every key of
`.fr/settings.yaml`. Phase 2 of the plan applies the per-feature overrides on top.
"""

from __future__ import annotations

from pathlib import Path

from fr.settle.model import Modes


def effective_modes(repo_root: Path) -> Modes:
    """Each key's mode and where it came from; `SettingsError` when unreadable."""
    from fr.settings.load import load_settings

    eff = load_settings(repo_root)
    settle = eff.settings.git.settle
    return Modes.model_validate(
        {
            "conflicts": {
                "mode": settle.conflicts,
                "source": eff.sources.get("git.settle.conflicts", "default"),
            },
            "ci": {"mode": settle.ci, "source": eff.sources.get("git.settle.ci", "default")},
        }
    )
