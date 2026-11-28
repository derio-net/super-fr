"""The generated CLI tree does not change when fr's version crosses S1's transition gate
(spec 2026-11-28-s1-followups R5, R10): `fr settings sync` stays listed, with a help line
that is the same on both sides, so a release into 9.2 leaves `docs/reference/cli.md` and
the README in step."""

from __future__ import annotations

import fr
import pytest

from tests.unit.test_tripwire_readme_sync import REPO_ROOT, sync_readme

pytestmark = pytest.mark.own_artifacts


@pytest.mark.parametrize("version", ["9.1.0", "9.2.0"])
def test_the_generated_cli_tree_is_the_same_on_both_sides_of_the_gate(
    monkeypatch: pytest.MonkeyPatch, version: str
) -> None:
    from fr.config import transition

    monkeypatch.delenv(transition.ENV, raising=False)
    monkeypatch.setattr(fr, "__version__", version)
    assert sync_readme.find_drift(REPO_ROOT) == []
