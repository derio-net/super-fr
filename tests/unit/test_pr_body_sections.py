"""`forge.pr_sections` turns three PR-body sections off (spec 2026-11-28-alacarte-settings
R4, R5): an off section is rendered nowhere, `deliver` does not require it on the live PR,
and `settle: off` drops only the section, never the deliver settle check."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fr.record.pr_body import (
    PR_SECTION_HEADINGS,
    REQUIRED_SECTIONS,
    render_pr_body,
    required_sections,
)
from fr.settings.model import parse_settings

from tests.unit.settings_repo import land_on_main, make_repo
from tests.unit.test_deliver_pr_body import live

pytestmark = pytest.mark.own_artifacts

__all__ = ["live"]

SPEC = "docs/superpowers/specs/2026-11-28-x-design.md"


def _settings(**sections: str):
    return parse_settings({"schema": 3, "forge": {"pr_sections": sections}}, source="t")


def test_the_three_keys_name_the_three_headings() -> None:
    assert PR_SECTION_HEADINGS == {
        "proportionality": "## Proportionality",
        "cost": "## Cost",
        "settle": "## PR settle",
    }


def test_cost_off_drops_only_the_cost_heading_and_keeps_the_order() -> None:
    required = required_sections(_settings(cost="off"))
    assert "## Cost" not in required
    assert list(required) == [h for h in REQUIRED_SECTIONS if h != "## Cost"]


def test_all_three_off_drops_the_three() -> None:
    required = required_sections(_settings(cost="off", proportionality="off", settle="off"))
    assert list(required) == [
        h for h in REQUIRED_SECTIONS if h not in set(PR_SECTION_HEADINGS.values())
    ]


def test_every_section_on_is_the_full_tuple() -> None:
    assert required_sections(parse_settings({}, source="t")) == REQUIRED_SECTIONS


@pytest.fixture
def root(tmp_path: Path) -> Path:
    repo = make_repo(tmp_path)
    (repo / SPEC).parent.mkdir(parents=True)
    (repo / SPEC).write_text("# X\n\n## Verification\n\nstrategy: candidate\n")
    return repo


def _state() -> SimpleNamespace:
    steps = {"brainstorm": SimpleNamespace(emitted={"spec": SPEC}, units=None)}
    return SimpleNamespace(run="r1", steps=steps, workflow="fr-goal@1")


def test_an_off_section_is_not_rendered_nor_computed(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fr.record.pr_body as pr_body

    land_on_main(
        root, "schema: 3\nforge:\n  pr_sections:\n    proportionality: off\n    cost: off\n"
    )

    def _boom(*_a: object, **_k: object) -> str:
        raise AssertionError("an off section's body is not computed")

    monkeypatch.setattr(pr_body, "_proportionality", _boom)
    monkeypatch.setattr(pr_body, "_cost", _boom)
    body = render_pr_body(root, _state())  # type: ignore[arg-type]
    assert "## Proportionality" not in body
    assert "## Cost" not in body
    assert "## PR settle" in body


def test_settle_off_drops_the_settle_section(root: Path) -> None:
    land_on_main(root, "schema: 3\nforge:\n  pr_sections:\n    settle: off\n")
    body = render_pr_body(root, _state())  # type: ignore[arg-type]
    assert "## PR settle" not in body
    assert "## Cost" in body and "## Proportionality" in body


# --- deliver ---------------------------------------------------------------------------


def _body_without(*headings: str) -> str:
    return "\n\n".join(f"{h}\n\nNone." for h in REQUIRED_SECTIONS if h not in headings)


def test_deliver_does_not_require_an_off_section_on_the_live_pr(
    tmp_path: Path, live: dict[str, str]
) -> None:
    from fr.run.model import load_run_state

    from tests.unit.test_deliver_pr_body import RUN, _at_deliver, _deliver
    from tests.unit.test_forge_quiet_pr_body import _land_policy

    root = _at_deliver(tmp_path)
    _land_policy(root, "schema: 3\nforge:\n  pr_sections:\n    cost: off\n")
    live["body"] = _body_without("## Cost")

    _rec, out = _deliver(root)

    assert out.exit_code == 0, out.output
    assert load_run_state(root, RUN).steps["deliver"].state == "done"


def test_the_durable_render_lacks_an_off_section(tmp_path: Path, live: dict[str, str]) -> None:
    from tests.unit.test_deliver_pr_body import _at_deliver, _deliver
    from tests.unit.test_forge_quiet_pr_body import PLAIN, _durable, _land_policy

    root = _at_deliver(tmp_path)
    _land_policy(
        root,
        "schema: 3\nforge:\n  pr_body: minimal\n  pr_sections:\n"
        "    cost: off\n    proportionality: off\n",
    )
    live["body"] = PLAIN

    _rec, out = _deliver(root)

    assert out.exit_code == 0, out.output
    durable = _durable(root).read_text()
    assert "## Cost" not in durable and "## Proportionality" not in durable
    assert "## Findings" in durable


def test_deliver_still_requires_an_on_section(tmp_path: Path, live: dict[str, str]) -> None:
    from tests.unit.test_deliver_pr_body import _at_deliver, _deliver

    root = _at_deliver(tmp_path)
    live["body"] = _body_without("## Cost")

    _rec, out = _deliver(root)

    assert out.exit_code == 2, out.output
    assert "## Cost" in out.output


def test_settle_off_still_runs_the_deliver_settle_check(
    tmp_path: Path, live: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit.test_deliver_pr_body import _at_deliver, _deliver
    from tests.unit.test_forge_quiet_pr_body import _land_policy
    from tests.unit.test_run_settle_witness import REPO, Forge

    root = _at_deliver(tmp_path)
    monkeypatch.setattr("fr.settle.witness.origin_slug", lambda _root: REPO)
    monkeypatch.setattr("fr.settle.target.ci_none", lambda _root: False)
    forge = Forge(mergeable="CONFLICTING", merge_state="DIRTY")
    monkeypatch.setattr("fr.settle.witness.client_for", lambda _root: forge)
    _land_policy(root, "schema: 3\nforge:\n  pr_sections:\n    settle: off\n")
    live["body"] = _body_without("## PR settle")

    _rec, out = _deliver(root)

    assert out.exit_code == 2, out.output
    assert "settle" in out.output and "conflicting" in out.output
