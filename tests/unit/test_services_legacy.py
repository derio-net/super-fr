"""fr.services.legacy — the frozen reader of a version-1 fr-profiles.yaml
(flat `backend:` / `host:`), per .claude/rules/artifact-versioning.md."""

from __future__ import annotations

import hashlib
import inspect

import pytest
from fr.services import legacy
from pydantic import ValidationError

FROZEN_CLASSES = ("ProfilesV1",)


def test_profiles_v1_accepts_the_version_one_keys() -> None:
    v1 = legacy.ProfilesV1.model_validate(
        {
            "profiles": {"dev": {"purpose": "x", "secrets": []}},
            "default": "dev",
            "backend": "gitlab",
            "host": "gitlab.example.com",
        }
    )
    assert (v1.backend, v1.host, v1.default) == ("gitlab", "gitlab.example.com", "dev")


def test_profiles_v1_keys_are_all_optional() -> None:
    v1 = legacy.ProfilesV1.model_validate({})
    assert (v1.backend, v1.host, v1.default, v1.profiles) == (None, None, None, {})


def test_profiles_v1_accepts_an_explicit_schema_version_one() -> None:
    assert legacy.ProfilesV1.model_validate({"schema_version": 1}).schema_version == 1
    with pytest.raises(ValidationError):
        legacy.ProfilesV1.model_validate({"schema_version": 2})


def test_profiles_v1_refuses_an_unknown_top_level_key() -> None:
    with pytest.raises(ValidationError):
        legacy.ProfilesV1.model_validate({"profiles": {}, "forge": {"type": "gitlab"}})


def test_profiles_v1_refuses_an_unknown_backend() -> None:
    with pytest.raises(ValidationError):
        legacy.ProfilesV1.model_validate({"backend": "bitbucket"})


def test_the_frozen_classes_are_exactly_these() -> None:
    declared = tuple(
        name for name, obj in vars(legacy).items() if inspect.isclass(obj) and name.endswith("V1")
    )
    assert sorted(declared) == sorted(FROZEN_CLASSES)


def test_the_frozen_v1_reader_has_not_been_edited() -> None:
    drifted = {
        name: hashlib.sha256(inspect.getsource(getattr(legacy, name)).encode()).hexdigest()
        for name in FROZEN_CLASSES
        if hashlib.sha256(inspect.getsource(getattr(legacy, name)).encode()).hexdigest()
        != legacy.FROZEN_CLASS_SHA256[name]
    }
    assert not drifted, (
        f"{sorted(drifted)} changed. `fr.services.legacy` is FROZEN — it is how fr reads "
        "a version-1 fr-profiles.yaml that is already written. Freeze a `…V2` beside it "
        "instead of editing it."
    )
