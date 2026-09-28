"""fr.services.model — the three services' vocabulary and cross-checks
(spec 2026-09-28-fr-profiles-services §3.A, R1/R2)."""

from __future__ import annotations

import pytest
from fr.services.model import (
    FOLLOW_UP,
    CiService,
    ForgeService,
    ServicesError,
    TrackingService,
    validate_services,
)
from pydantic import ValidationError


def test_the_follow_up_is_the_step_two_issue() -> None:
    assert FOLLOW_UP == "derio-net/super-fr#795"


@pytest.mark.parametrize("kind", ["github", "gitlab", "gitea"])
def test_forge_types(kind: str) -> None:
    assert ForgeService(type=kind).type == kind


@pytest.mark.parametrize("kind", ["none", "github-actions", "gitlab-ci", "gitea-actions"])
def test_ci_types(kind: str) -> None:
    assert CiService(type=kind).type == kind


@pytest.mark.parametrize("kind", ["none", "github", "gitlab", "gitea"])
def test_tracking_types(kind: str) -> None:
    assert TrackingService(type=kind).type == kind


def test_type_specific_keys_round_trip() -> None:
    ci = CiService.model_validate({"type": "gitlab-ci", "job": "acceptance"})
    assert ci.model_dump(exclude_none=True) == {"type": "gitlab-ci", "job": "acceptance"}
    tracking = TrackingService.model_validate({"type": "gitlab", "project": "g/p"})
    assert tracking.model_dump(exclude_none=True) == {"type": "gitlab", "project": "g/p"}


@pytest.mark.parametrize(
    ("model", "kind"),
    [(CiService, "jenkins"), (TrackingService, "jira"), (ForgeService, "jenkins")],
)
def test_deferred_types_are_refused_naming_the_follow_up(model: type, kind: str) -> None:
    with pytest.raises(ValidationError, match="derio-net/super-fr#795"):
        model(type=kind)


def test_an_unknown_type_is_refused_naming_the_valid_ones() -> None:
    with pytest.raises(ValidationError, match="gitlab-ci"):
        CiService(type="circleci")


def test_a_cross_forge_tracker_is_refused_naming_the_follow_up() -> None:
    with pytest.raises(ServicesError, match="derio-net/super-fr#795"):
        validate_services(
            ForgeService(type="github"), CiService(type="none"), TrackingService(type="gitlab")
        )


def test_the_forges_own_tracker_or_none_is_accepted() -> None:
    forge = ForgeService(type="gitlab", host="gitlab.example.com")
    validate_services(forge, CiService(type="gitlab-ci"), TrackingService(type="gitlab"))
    validate_services(forge, CiService(type="none"), TrackingService(type="none"))


def test_a_non_native_type_with_no_host_is_refused() -> None:
    with pytest.raises(ServicesError, match="host is required"):
        validate_services(
            ForgeService(type="github"), CiService(type="gitlab-ci"), TrackingService(type="none")
        )


def test_a_non_native_type_with_a_host_is_accepted() -> None:
    validate_services(
        ForgeService(type="github"),
        CiService(type="gitlab-ci", host="gitlab.example.com"),
        TrackingService(type="github"),
    )
