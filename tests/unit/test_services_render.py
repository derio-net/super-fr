"""fr.services.render — the one text renderer of the three service blocks,
shared by the 1 -> 2 migration and `fr init scaffold` (spec
2026-09-28-fr-profiles-services §3.A/§3.D)."""

from __future__ import annotations

import pytest
import yaml
from fr.services.render import render_services


def test_blocks_are_written_in_service_order_type_first() -> None:
    text = render_services(
        {
            "tracking": {"type": "none"},
            "forge": {"host": "gitlab.example.com", "type": "gitlab"},
            "ci": {"type": "gitlab-ci"},
        }
    )
    assert text == (
        "forge:\n  type: gitlab\n  host: gitlab.example.com\n"
        "ci:\n  type: gitlab-ci\n"
        "tracking:\n  type: none\n"
    )


def test_newline_style_is_the_callers() -> None:
    assert render_services({"ci": {"type": "none"}}, newline="\r\n") == "ci:\r\n  type: none\r\n"


@pytest.mark.parametrize(
    "host", ["gitlab.example.com:8443", "a # b", "yes", "123", " padded", "x: y", ""]
)
def test_awkward_scalars_round_trip(host: str) -> None:
    text = render_services({"forge": {"type": "gitlab", "host": host}})
    assert yaml.safe_load(text) == {"forge": {"type": "gitlab", "host": host}}


def test_an_unknown_service_is_refused() -> None:
    with pytest.raises(ValueError, match="jenkins"):
        render_services({"jenkins": {"type": "x"}})
