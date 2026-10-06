"""A scripted prober for the run-integration tests of model bindings (spec
2026-10-06-model-binding-churn §C), and the user-layer files it acts on.

Installed over `fr.bindings.prober_for` — the one factory every caller reaches
a prober through — exactly as `tests/conftest.py`'s always-live stub is.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.bindings.catalogue import CatalogueEntry
from fr.bindings.probe import ProbeResult

P = "prov"
NOT_FOUND = "ProviderModelNotFoundError: Model not found"


def ent(name: str, family: str, date: str, price: float | None = 10.0) -> CatalogueEntry:
    return CatalogueEntry(f"{P}/{name}", P, family, date, price, True)


class ScriptedProber:
    """``dead`` maps a model to the provider's hint (or None); ``unknown``
    lists models whose probe is inconclusive; every other model is live."""

    def __init__(
        self,
        entries: list[CatalogueEntry],
        dead: dict[str, str | None] | None = None,
        unknown: tuple[str, ...] = (),
    ) -> None:
        self.entries = entries
        self.dead = dead or {}
        self.unknown = unknown
        self.probed: list[str] = []

    def probe(self, model: str) -> ProbeResult:
        self.probed.append(model)
        if model in self.dead:
            return ProbeResult("dead", f"{NOT_FOUND}: {model}", self.dead[model], 0.0)
        if model in self.unknown:
            return ProbeResult("unknown", "timed out", None, 0.0)
        return ProbeResult("live", "", None, 0.0)

    def catalogue(self, provider: str) -> list[CatalogueEntry]:
        return [e for e in self.entries if e.provider == provider]


def install(monkeypatch: pytest.MonkeyPatch, prober: ScriptedProber, *, any_harness=False) -> None:
    """Route `fr.bindings.prober_for` to ``prober`` (for opencode only, as the
    real factory does, unless ``any_harness`` — a test proving the caller never
    asks for another harness)."""
    import fr.bindings

    monkeypatch.setattr(
        fr.bindings,
        "prober_for",
        lambda harness: prober if (any_harness or harness == "opencode") else None,
    )


def user_models(tmp_path: Path, text: str) -> Path:
    """Write the user-layer models.yaml under the test's XDG_CONFIG_HOME."""
    path = tmp_path / ".config" / "fr" / "models.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def agent_file(tmp_path: Path, tier: str, model: str) -> Path:
    """An installed OpenCode tier agent file, as `materialize_agents` finds it."""
    path = tmp_path / ".config" / "opencode" / "agent" / f"fr-phase-executor-{tier}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\ndescription: executor\nmode: subagent\nmodel: {model}\n---\nbody\n")
    return path
