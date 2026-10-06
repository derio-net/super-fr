"""`fr verification check` — semantic validation of a strategy (spec §A, R2).

Structural validity (unknown key, bad `when` / `driver`, unknown placeholder,
the reserved name) is `parse_strategy`'s: a manifest failing those never
becomes a `StrategyManifest`. What only a valid manifest can get wrong is
checked here.
"""

from __future__ import annotations

from fr.verification.model import StrategyManifest

__all__ = ["check_strategy"]


def check_strategy(manifest: StrategyManifest) -> list[str]:
    """Every problem with `manifest`, as human-readable strings. Empty = clean."""
    errors: list[str] = []
    if manifest.when == "post-merge" and manifest.install is not None:
        errors.append("a post-merge strategy installs nothing: the released build is what runs")
    if manifest.driver == "agent" and manifest.when == "pre-merge" and manifest.scenario is None:
        errors.append("an agent-driven pre-merge strategy needs a `scenario` template")
    if "source" in manifest.used_placeholders() and manifest.source == "none":
        errors.append("a template uses {source} but `source:` is none")
    return errors
