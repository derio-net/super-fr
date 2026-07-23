"""Phase 4: the harness-neutral `tier` field on PhaseHeader.

Spec §B.2: fr-plan annotates each phase with a tier (mechanical|standard|hard);
the plan never names a concrete model. Optional + defaulting None keeps
pre-tier plans byte-stable.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestPhaseTier:
    def test_accepts_valid_tiers(self) -> None:
        from fr.types import PhaseHeader

        for tier in ("mechanical", "standard", "hard"):
            h = PhaseHeader(number=1, title="t", tag="agentic", tier=tier)
            assert h.tier == tier

    def test_defaults_none(self) -> None:
        from fr.types import PhaseHeader

        assert PhaseHeader(number=1, title="t", tag="agentic").tier is None

    def test_rejects_unknown_tier(self) -> None:
        from fr.types import PhaseHeader

        with pytest.raises(ValidationError):
            PhaseHeader(number=1, title="t", tag="agentic", tier="huge")

    def test_tier_round_trips_through_phase_yaml(self, tmp_path) -> None:
        """A phase carrying `tier: hard` parses back with the tier intact."""
        import yaml
        from fr.types import PhaseDoc

        doc = {
            "schema_version": 2,
            "phase": {"number": 1, "title": "t", "tag": "agentic", "tier": "hard"},
            "tasks": [{"number": 1, "title": "task", "steps": [{"id": "P1.T1.S1", "text": "s"}]}],
            "state": {
                "steps": {"P1.T1.S1": {"state": " "}},
                "completion": {},
            },
        }
        text = yaml.safe_dump(doc)
        parsed = PhaseDoc.model_validate(yaml.safe_load(text))
        assert parsed.phase.tier == "hard"
