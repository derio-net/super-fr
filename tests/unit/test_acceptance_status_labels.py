"""Every acceptance status has a report label (spec 2026-11-16 R10)."""

from __future__ import annotations

from typing import get_args

from fr.acceptance.model import Status
from fr.acceptance.report import STATUS_LABEL


def test_every_status_has_a_label_and_no_label_is_orphaned() -> None:
    assert set(STATUS_LABEL) == set(get_args(Status))
