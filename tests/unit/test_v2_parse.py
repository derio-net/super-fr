from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


def test_planmeta_loads_minimal_fixture():
    import yaml

    from vk.v2.types import PlanMeta

    meta = PlanMeta.model_validate(yaml.safe_load((FIXTURE_DIR / "_meta.yaml").read_text()))
    assert meta.plan == "2026-05-09-fixture-minimal"
    assert meta.target_repo == "derio-net/superpowers-for-vk"
    assert meta.vk_version == ">=1.0.0,<3.0.0"
    assert meta.parent_plan is None
    assert meta.origin_items == []


def test_planmeta_rejects_missing_required():
    from pydantic import ValidationError

    from vk.v2.types import PlanMeta

    with pytest.raises(ValidationError):
        PlanMeta.model_validate({"schema_version": 2, "plan": "x"})


def test_parse_minimal_fixture():
    from vk.v2 import parse

    plan = parse(FIXTURE_DIR)
    assert plan.meta.plan == "2026-05-09-fixture-minimal"
    assert len(plan.phases) == 1
    assert plan.phases[0].phase.number == 1
    assert plan.dir == FIXTURE_DIR


def test_parse_roundtrip(tmp_path):
    import shutil

    import yaml

    from vk.v2 import parse

    shutil.copytree(FIXTURE_DIR, tmp_path / "copy")
    plan = parse(tmp_path / "copy")
    (tmp_path / "copy" / "_meta.yaml").write_text(yaml.safe_dump(plan.meta.model_dump()))
    (tmp_path / "copy" / "01.yaml").write_text(yaml.safe_dump(plan.phases[0].model_dump()))
    reparsed = parse(tmp_path / "copy")
    assert reparsed.meta == plan.meta
    assert reparsed.phases == plan.phases


def test_parse_rejects_v1_plan(tmp_path):
    from vk.v2 import PlanSchemaError, parse

    v1 = tmp_path / "v1-plan"
    v1.mkdir()
    (v1 / "looks-like-a-plan.md").write_text("# old")
    with pytest.raises(PlanSchemaError, match="not a v2 plan"):
        parse(v1)


def test_parse_enforces_vk_version(monkeypatch):
    from vk.v2 import PlanSchemaError, parse

    monkeypatch.setattr("vk.v2.parser.INSTALLED_VK_VERSION", "1.4.5")
    future = Path(__file__).parent / "fixtures" / "v2_plan_future"
    with pytest.raises(PlanSchemaError, match="vk_version"):
        parse(future)


def test_phasedoc_loads_minimal_fixture():
    import yaml

    from vk.v2.types import PhaseDoc

    doc = PhaseDoc.model_validate(yaml.safe_load((FIXTURE_DIR / "01.yaml").read_text()))
    assert doc.phase.number == 1
    assert doc.phase.tag == "agentic"
    assert doc.phase.depends_on == ()
    assert doc.tasks[0].steps[0].id == "P1.T1.S1"
    assert doc.state.steps["P1.T1.S1"].state == " "


def test_phasedoc_rejects_state_key_mismatch():
    from pydantic import ValidationError

    from vk.v2.types import PhaseDoc

    with pytest.raises(ValidationError):
        PhaseDoc.model_validate(
            {
                "schema_version": 2,
                "phase": {"number": 1, "title": "x", "tag": "agentic"},
                "tasks": [{"number": 1, "title": "t", "steps": [{"id": "P1.T1.S1", "text": "s"}]}],
                "state": {
                    "steps": {"P1.T1.S99": {"state": " "}},
                    "completion": {"observed_prs": []},
                },
            }
        )


def test_planmeta_rejects_extra_field():
    from pydantic import ValidationError

    from vk.v2.types import PlanMeta

    with pytest.raises(ValidationError):
        PlanMeta.model_validate(
            {
                "schema_version": 2,
                "plan": "x",
                "target_repo": "o/r",
                "vk_version": ">=2",
                "created": "2026-05-09",
                "extra_field": "boom",
            }
        )
