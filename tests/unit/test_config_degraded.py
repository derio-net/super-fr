"""Executable and trust configuration DEGRADES under quiet and stealth when the
configuration branch is not enforced; it never locks a repo out (review finding p4-r3,
plan decision p4-degraded-not-lockout, spec 2026-11-19-event-driven-a-la-carte R7 as
amended).

- a repo workflow shape or verification strategy from the configuration branch is ignored
  and the SHIPPED one is used, with the reason said once;
- `profiles.yaml` is read, but its security-relevant keys (each profile's `secrets` and
  `ops`, the `forge`/`ci`/`tracking` service blocks, the version-1 `backend`/`host`, and
  any key fr does not know) are dropped with the reason; names, purposes and the default
  stay;
- a failed protection read still refuses an executor; the read-only `fr services` shows the
  degraded view and says "protection unknown".

The protection answer is a REAL one: a local origin is no forge repository (not enforced),
and an enforced answer is a fake forge client serving the captured approved-ruleset reply,
reached through `fr.config.protection.protection_of` (nothing mocks `read_checked`).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.config import protection, space

from tests.unit.settings_repo import git
from tests.unit.test_config_protection_executors import SLUG, _quiet_with_config, _Rules

REPO = Path(__file__).resolve().parents[2]
LIGHT = (REPO / "plugins/super-fr/workflows/fr-goal-light.yaml").read_text()
CANDIDATE = (REPO / "plugins/super-fr/verifications/candidate.yaml").read_text()
MINE_LIGHT = LIGHT.replace("description: TDD", "description: REPO-OVERRIDE TDD")
MINE_CANDIDATE = CANDIDATE.replace("description: Install", "description: REPO-OVERRIDE Install")
PROFILES = (
    "schema_version: 3\n"
    "profiles:\n"
    "  dev:\n    purpose: dev\n    secrets: [KUBE_TOKEN]\n    ops: true\n"
    "default: dev\n"
    "forge:\n  type: github\n  host: evil.example.com\n"
)


@pytest.fixture(autouse=True)
def _fresh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    protection.forget()
    protection._CACHE.clear()
    space._OLD_NOTICED.clear()
    from fr.config import degraded

    degraded._SAID.clear()


def _enforce(monkeypatch: pytest.MonkeyPatch) -> _Rules:
    client = _Rules()
    monkeypatch.setattr(protection, "_origin_slug", lambda _r: SLUG)
    monkeypatch.setattr(protection, "_default_client", lambda _s: client)
    return client


def _root(tmp_path: Path) -> Path:
    return _quiet_with_config(
        tmp_path,
        {
            ".fr/workflows/fr-goal-light.yaml": MINE_LIGHT,
            ".fr/verifications/candidate.yaml": MINE_CANDIDATE,
            ".fr/profiles.yaml": PROFILES,
        },
    )


def test_an_unprotected_repo_workflow_falls_back_to_the_shipped_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from fr.workflow.resolve import resolve_workflow

    root = _root(tmp_path)
    assert "REPO-OVERRIDE" not in resolve_workflow("fr-goal-light", root).description
    err = capsys.readouterr().err
    assert "ignoring" in err and "not a forge repository" in err and "shipped" in err
    resolve_workflow("fr-goal-light", root)
    assert "ignoring" not in capsys.readouterr().err  # said once


def test_a_protected_repo_workflow_is_used_from_the_fetched_tip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.workflow.resolve import resolve_workflow

    root = _root(tmp_path)
    client = _enforce(monkeypatch)
    assert "REPO-OVERRIDE" in resolve_workflow("fr-goal-light", root).description
    assert client.asked == [(SLUG, "fr-config")]


def test_an_unprotected_repo_strategy_falls_back_to_the_shipped_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from fr.verification.resolve import resolve_strategy

    root = _root(tmp_path)
    assert "REPO-OVERRIDE" not in resolve_strategy("candidate", root).description
    assert "ignoring" in capsys.readouterr().err
    protection._CACHE.clear()
    _enforce(monkeypatch)
    assert "REPO-OVERRIDE" in resolve_strategy("candidate", root).description


def test_unprotected_profiles_keep_names_and_drop_the_security_keys(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from fr.isolation.types import profiles_config

    root = _root(tmp_path)
    data = profiles_config(root)
    assert data == {"schema_version": 3, "profiles": {"dev": {"purpose": "dev"}}, "default": "dev"}
    err = capsys.readouterr().err
    for key in ("profiles.dev.secrets", "profiles.dev.ops", "forge"):
        assert key in err


def test_protected_profiles_are_read_whole(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fr.isolation.types import profiles_config

    root = _root(tmp_path)
    _enforce(monkeypatch)
    data = profiles_config(root)
    assert data["profiles"]["dev"]["secrets"] == ["KUBE_TOKEN"] and data["forge"]["host"]


def test_isolation_profile_selection_works_on_an_unprotected_repo(tmp_path: Path) -> None:
    from fr.isolation.types import resolve_profile

    root = _root(tmp_path)
    for name in ("dev", "admin"):
        (root / f".devcontainer/{name}").mkdir(parents=True)
        (root / f".devcontainer/{name}/devcontainer.json").write_text("{}\n")
    assert resolve_profile(root, None) == "dev"


def test_a_failed_protection_read_refuses_an_executor_but_not_fr_services(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from fr.isolation.types import profiles_config
    from fr.services.resolve import resolve_services

    root = _root(tmp_path)

    class _Down:
        def branch_rules(self, repo: str, branch: str) -> object:
            raise RuntimeError("connection reset")

    monkeypatch.setattr(protection, "_origin_slug", lambda _r: SLUG)
    monkeypatch.setattr(protection, "_default_client", lambda _s: _Down())
    with pytest.raises(protection.ProtectionReadError):
        profiles_config(root)
    services = resolve_services(root)
    assert services.forge.host != "evil.example.com"
    assert "protection unknown" in capsys.readouterr().err


def test_an_old_path_workflow_under_quiet_is_ignored_for_the_shipped_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """No configuration branch: the old directory is read, but its executable content is
    not on any protected configuration branch, so the shipped shape is used."""
    from fr.workflow.resolve import resolve_workflow

    from tests.unit.test_migration_config_kinds import _put, _quiet

    root = _quiet(tmp_path)
    _put(root, "docs/superpowers/workflows/fr-goal-light.yaml", MINE_LIGHT)
    git(root, "push", "-q", "origin", "HEAD:main")
    assert "REPO-OVERRIDE" not in resolve_workflow("fr-goal-light", root).description
    assert "old path" in capsys.readouterr().err


def test_run_advance_resolves_its_shape_through_the_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`fr run advance` resolves the run's shape with `_resolve_manifest_checked_schema`:
    under quiet the repo override counts only from a protected fr-config."""
    from types import SimpleNamespace

    from fr.commands import run_cmd

    root = _root(tmp_path)
    state: object = SimpleNamespace(workflow="fr-goal-light@1", run="r1")
    shape = run_cmd._resolve_manifest_checked_schema(root, state)  # type: ignore[arg-type]
    assert "REPO-OVERRIDE" not in shape.description
    protection._CACHE.clear()
    _enforce(monkeypatch)
    shape = run_cmd._resolve_manifest_checked_schema(root, state)  # type: ignore[arg-type]
    assert "REPO-OVERRIDE" in shape.description
