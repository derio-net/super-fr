"""fr.checkstate: the one check-verdict rule (spec 2026-11-24-ci-economy R3)."""

from __future__ import annotations

import fr.checkstate as checkstate


def test_the_module_names_its_spec() -> None:
    assert "2026-11-24-ci-economy" in (checkstate.__doc__ or "")
