"""R9 (spec 2026-11-04-repo-feature-settings): one predicate, `fr.settings.forge_allows`,
decides every forge write of a kind, and `tracking: {type: none}` keeps meaning all three
kinds are off. The inventory test keeps the old tracking-none checks from coming back."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fr.settings import FORGE_KINDS, ForgeQuietError, forge_allows, forge_block, require_forge

from tests.unit.settings_repo import git, land_on_main, make_repo

SRC = Path(__file__).resolve().parents[2] / "packages" / "fr" / "src" / "fr"
NONE = "schema_version: 2\ntracking: {type: none}\n"


def _declare_tracking_none(root: Path) -> None:
    (root / ".devcontainer").mkdir(exist_ok=True)
    (root / ".devcontainer" / "fr-profiles.yaml").write_text(NONE)
    git(root, "add", "-A")
    git(root, "commit", "-qm", "tracking none")
    git(root, "push", "-q", "origin", "main")


@pytest.mark.parametrize("kind", FORGE_KINDS)
def test_every_kind_is_allowed_by_default(tmp_path: Path, kind: str) -> None:
    root = make_repo(tmp_path)
    assert forge_allows(root, kind) is True
    assert forge_block(root, kind) is None
    require_forge(root, kind)  # no raise


@pytest.mark.parametrize("kind", FORGE_KINDS)
def test_the_setting_off_forbids_only_its_own_kind(tmp_path: Path, kind: str) -> None:
    root = make_repo(tmp_path)
    land_on_main(root, f"forge:\n  {kind}: 'off'\n")
    assert forge_allows(root, kind) is False
    why = forge_block(root, kind)
    assert why is not None and f"forge.{kind}: off" in why
    with pytest.raises(ForgeQuietError, match=f"forge.{kind}: off"):
        require_forge(root, kind)
    for other in set(FORGE_KINDS) - {kind}:
        assert forge_allows(root, other) is True


@pytest.mark.parametrize("kind", FORGE_KINDS)
def test_tracking_none_forbids_every_kind_with_the_settings_on(tmp_path: Path, kind: str) -> None:
    root = make_repo(tmp_path)
    land_on_main(root, "forge:\n  labels: 'on'\n  comments: 'on'\n  issues: 'on'\n")
    _declare_tracking_none(root)
    assert forge_allows(root, kind) is False
    why = forge_block(root, kind)
    assert why is not None and "tracking: none" in why


def test_the_setting_off_wins_over_a_tracker(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    land_on_main(root, "forge:\n  issues: 'off'\n")
    assert "forge.issues: off" in (forge_block(root, "issues") or "")


def test_an_unknown_kind_is_a_programming_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        forge_allows(make_repo(tmp_path), "pr_body")


def test_an_unreadable_policy_refuses_rather_than_allowing(tmp_path: Path) -> None:
    from fr.settings import SettingsError

    root = make_repo(tmp_path)
    land_on_main(root, "forge:\n  issues: sometimes\n")
    with pytest.raises(SettingsError):
        forge_allows(root, "issues")


def test_a_malformed_tracking_declaration_refuses_strictly_and_allows_leniently(
    tmp_path: Path,
) -> None:
    from fr.services import ServicesError

    root = make_repo(tmp_path)
    (root / ".devcontainer").mkdir()
    (root / ".devcontainer" / "fr-profiles.yaml").write_text(": : not yaml [\n")
    with pytest.raises(ServicesError):
        forge_allows(root, "issues")
    assert forge_allows(root, "issues", lenient=True) is True


# The old checks: a tracking lookup, the strict gate, or a `tracking ... "none"` comparison.
_OLD = re.compile(
    r"resolve_tracking\(|require_tracker\(|TrackerRequiredError\b"
    r"|tracking[\w.]*\s*(?:==|!=)\s*\"none\""
)


def test_no_module_outside_services_and_settings_checks_tracking_none_itself() -> None:
    hits = []
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        if rel.startswith(("services/", "settings/")):
            continue
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if _OLD.search(line):
                hits.append(f"{rel}:{n}: {line.strip()}")
    assert not hits, "move these to fr.settings.forge_allows:\n" + "\n".join(hits)
