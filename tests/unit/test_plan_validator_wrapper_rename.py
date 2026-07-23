"""The validator wrapper's writer and recognizer are versioned differently.

`scripts/validate-plans.sh` is a thin wrapper that every fr-enabled repo
**commits**, and it hardcodes the marketplace directory it delegates to.  When
the marketplace was renamed `derio-net` -> `derio-net--super-fr` (see
docs/superpowers/journals/debug/2026-07-23-marketplace-config-clobber.md) every
one of those committed wrappers still carried the old path.

`ensure_validator_wrapper` refuses to overwrite a file it doesn't recognize as
ours — that guard exists so we never clobber a repo's own hand-written
validator.  So a recognizer that only knew the new path would classify every
existing wrapper as foreign and refuse to upgrade exactly the repos that need
upgrading.  Write the new form only; recognize both.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.plan_validator_wrapper import (
    WRAPPER_TEXT,
    ValidatorWrapperError,
    ensure_validator_wrapper,
    is_super_fr_validator_wrapper,
)

LEGACY_WRAPPER = """#!/usr/bin/env bash
# Thin wrapper — delegates to the canonical validator from the
# super-fr plugin installed at the user level.
exec "$HOME/.claude/plugins/marketplaces/derio-net/scripts/validate-plans.sh" "$@"
"""

PRE_SWEEP_WRAPPER = """#!/usr/bin/env bash
# Thin wrapper — superpowers-for-vk plugin at user level.
exec "$HOME/.claude/plugins/marketplaces/derio-net/scripts/validate-plans.sh" "$@"
"""


def _wrapper(repo: Path, text: str) -> Path:
    target = repo / "scripts" / "validate-plans.sh"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    target.chmod(0o755)
    return target


def test_writes_the_new_marketplace_path() -> None:
    assert "marketplaces/derio-net--super-fr/scripts/validate-plans.sh" in WRAPPER_TEXT
    assert "marketplaces/derio-net/scripts" not in WRAPPER_TEXT


def test_recognizes_the_current_wrapper(tmp_path: Path) -> None:
    assert is_super_fr_validator_wrapper(_wrapper(tmp_path, WRAPPER_TEXT))


@pytest.mark.parametrize("text", [LEGACY_WRAPPER, PRE_SWEEP_WRAPPER])
def test_recognizes_a_committed_legacy_wrapper(tmp_path: Path, text: str) -> None:
    """The deployed fleet's wrappers all point at the retired bare-org name."""
    assert is_super_fr_validator_wrapper(_wrapper(tmp_path, text))


def test_still_rejects_a_foreign_validator(tmp_path: Path) -> None:
    """The recognizer got looser, not blind — a repo's own validator must still
    be protected from being overwritten."""
    target = _wrapper(tmp_path, "#!/usr/bin/env bash\n# our own house validator\nexit 0\n")
    assert not is_super_fr_validator_wrapper(target)
    with pytest.raises(ValidatorWrapperError):
        ensure_validator_wrapper(tmp_path)


def test_upgrades_a_legacy_wrapper_in_place(tmp_path: Path) -> None:
    target = _wrapper(tmp_path, LEGACY_WRAPPER)

    changed = ensure_validator_wrapper(tmp_path)

    assert changed is True
    assert target.read_text() == WRAPPER_TEXT
    assert target.stat().st_mode & 0o111


def test_upgrade_is_idempotent(tmp_path: Path) -> None:
    _wrapper(tmp_path, LEGACY_WRAPPER)

    ensure_validator_wrapper(tmp_path)
    assert ensure_validator_wrapper(tmp_path) is False
