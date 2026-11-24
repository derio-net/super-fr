"""The configuration space resolver (spec 2026-11-19-event-driven-a-la-carte §A, R1-R4)."""

from __future__ import annotations

import fr.config.space as space_mod


def test_the_resolver_names_its_spec() -> None:
    assert "2026-11-19-event-driven-a-la-carte" in (space_mod.__doc__ or "")
