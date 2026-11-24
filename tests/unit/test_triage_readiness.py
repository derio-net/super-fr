"""`fr.triage.readiness` (spec 2026-11-24-batch-merge-readiness R1-R6, R12)."""

from __future__ import annotations


def test_the_module_names_its_spec() -> None:
    import fr.triage.readiness as readiness

    assert "2026-11-24-batch-merge-readiness" in (readiness.__doc__ or "")
