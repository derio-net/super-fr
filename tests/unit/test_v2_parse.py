from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


def test_planmeta_loads_minimal_fixture():
    import yaml
    from fr.types import PlanMeta

    meta = PlanMeta.model_validate(yaml.safe_load((FIXTURE_DIR / "_meta.yaml").read_text()))
    assert meta.plan == "2026-05-09-fixture-minimal"
    assert meta.target_repo == "derio-net/superpowers-for-vk"
    assert meta.vk_version == ">=1.0.0,<3.0.0"
    assert meta.parent_plan is None
    assert meta.origin_items == []


def test_planmeta_rejects_missing_required():
    from fr.types import PlanMeta
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        PlanMeta.model_validate({"schema_version": 2, "plan": "x"})


def test_parse_minimal_fixture():
    from fr import parse

    plan = parse(FIXTURE_DIR)
    assert plan.meta.plan == "2026-05-09-fixture-minimal"
    assert len(plan.phases) == 1
    assert plan.phases[0].phase.number == 1
    assert plan.dir == FIXTURE_DIR


def test_parse_roundtrip(tmp_path):
    import shutil

    import yaml
    from fr import parse

    shutil.copytree(FIXTURE_DIR, tmp_path / "copy")
    plan = parse(tmp_path / "copy")
    (tmp_path / "copy" / "_meta.yaml").write_text(yaml.safe_dump(plan.meta.model_dump()))
    (tmp_path / "copy" / "01.yaml").write_text(yaml.safe_dump(plan.phases[0].model_dump()))
    reparsed = parse(tmp_path / "copy")
    assert reparsed.meta == plan.meta
    assert reparsed.phases == plan.phases


def test_parse_rejects_v1_plan(tmp_path):
    from fr import PlanSchemaError, parse

    v1 = tmp_path / "v1-plan"
    v1.mkdir()
    (v1 / "looks-like-a-plan.md").write_text("# old")
    with pytest.raises(PlanSchemaError, match="not a v2 plan"):
        parse(v1)


def test_parse_rejects_phase_zero(tmp_path):
    """Phase numbering starts at 1. A `00.yaml` with `phase.number: 0` must
    fail parse loud, naming the offending file."""
    import re
    import shutil

    from fr import PlanSchemaError, parse

    shutil.copytree(FIXTURE_DIR, tmp_path / "copy")
    phase0 = (
        (tmp_path / "copy" / "01.yaml")
        .read_text()
        .replace("number: 1", "number: 0")
        .replace("P1.T1.S1", "P0.T1.S1")
    )
    (tmp_path / "copy" / "01.yaml").unlink()
    (tmp_path / "copy" / "00.yaml").write_text(phase0)
    with pytest.raises(PlanSchemaError, match=re.escape("00.yaml")):
        parse(tmp_path / "copy")


def test_parse_accepts_phase_one():
    """Control: 1-based plans (the minimal fixture) keep parsing."""
    from fr import parse

    assert parse(FIXTURE_DIR).phases[0].phase.number == 1


def test_parse_enforces_fr_version(monkeypatch, tmp_path):
    """`fr_version` (when present) gates parsing; the legacy `vk_version`
    field is INERT — it constrains a tool that no longer exists (v3)."""
    import shutil

    from fr import PlanSchemaError, parse

    plan_dir = tmp_path / "plan"
    shutil.copytree(FIXTURE_DIR, plan_dir)
    meta = (plan_dir / "_meta.yaml").read_text()
    (plan_dir / "_meta.yaml").write_text(meta + 'fr_version: ">=9.0.0,<10.0.0"\n')

    monkeypatch.setattr("fr.parser.INSTALLED_FR_VERSION", "3.0.0")
    with pytest.raises(PlanSchemaError, match="requires fr_version"):
        parse(plan_dir)


def test_parse_enforce_fr_version_false_admits_a_plan_the_default_would_reject(
    monkeypatch, tmp_path
):
    """Phase 8 (spec §3.E.1): `enforce_fr_version=False` is the one escape
    from the gate, for read-only historical status — not a general
    loosening. The default (True, unspecified) must still reject the exact
    same plan: the fixture's ceiling genuinely excludes the installed
    version, so admitting it under the flag proves the flag actually did
    something (an already-admitted plan would prove nothing)."""
    import shutil

    from fr import PlanSchemaError, parse

    plan_dir = tmp_path / "plan"
    shutil.copytree(FIXTURE_DIR, plan_dir)
    meta = (plan_dir / "_meta.yaml").read_text()
    (plan_dir / "_meta.yaml").write_text(meta + 'fr_version: ">=9.0.0,<10.0.0"\n')

    monkeypatch.setattr("fr.parser.INSTALLED_FR_VERSION", "3.0.0")

    with pytest.raises(PlanSchemaError, match="requires fr_version"):
        parse(plan_dir)
    with pytest.raises(PlanSchemaError, match="requires fr_version"):
        parse(plan_dir, enforce_fr_version=True)

    plan = parse(plan_dir, enforce_fr_version=False)
    assert plan.meta.plan == "2026-05-09-fixture-minimal"
    assert plan.meta.fr_version == ">=9.0.0,<10.0.0"  # retained, just unenforced


def test_parse_legacy_vk_version_is_inert(monkeypatch, tmp_path):
    """A wild plan pinned to vk <3.0.0 parses fine under fr 3.x —
    the v3 landmine the split design defused (labels-are-data doctrine
    applied to plan files)."""
    import shutil

    from fr import parse

    plan_dir = tmp_path / "plan"
    shutil.copytree(FIXTURE_DIR, plan_dir)
    # fixture carries vk_version ">=1.0.0,<3.0.0"
    monkeypatch.setattr("fr.parser.INSTALLED_FR_VERSION", "99.0.0")
    plan = parse(plan_dir)
    assert plan.meta.vk_version is not None  # parsed, retained, unenforced


def test_parse_rejects_invalid_fr_version_specifier(tmp_path):
    """Malformed fr_version surfaces as PlanSchemaError, not
    InvalidSpecifier. (A malformed legacy vk_version is inert — ignored.)"""
    import shutil

    from fr import PlanSchemaError, parse

    shutil.copytree(FIXTURE_DIR, tmp_path / "copy")
    (tmp_path / "copy" / "_meta.yaml").write_text(
        "schema_version: 2\nplan: x\ntarget_repo: o/r\n"
        'vk_version: "totally not a spec"\n'
        'fr_version: "also not a spec"\ncreated: "2026-05-09"\n'
    )
    with pytest.raises(PlanSchemaError, match="invalid fr_version"):
        parse(tmp_path / "copy")


def test_parse_multi_phase_sorts_numerically(tmp_path):
    """01.yaml, 02.yaml, 10.yaml must order [1, 2, 10] (numeric, not lex)."""
    from fr import parse

    multi = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"
    plan = parse(multi)
    assert [p.phase.number for p in plan.phases] == [1, 2, 10]


def test_parse_corrupt_yaml_raises_planschemaerror():
    """Syntactically broken phase yaml surfaces as PlanSchemaError naming the file."""
    from fr import PlanSchemaError, parse

    bad = Path(__file__).parent / "fixtures" / "v2_plan_corrupt_yaml"
    with pytest.raises(PlanSchemaError, match="01.yaml"):
        parse(bad)


def test_parse_schema_failure_in_phase_raises_planschemaerror():
    """Phase yaml that parses but fails pydantic validation → PlanSchemaError."""
    from fr import PlanSchemaError, parse

    bad = Path(__file__).parent / "fixtures" / "v2_plan_bad_tag"
    with pytest.raises(PlanSchemaError, match="01.yaml"):
        parse(bad)


def test_parse_state_key_mismatch_raises_planschemaerror_via_parse():
    """state.steps key mismatch in fixture → PlanSchemaError (not naked ValidationError)."""
    from fr import PlanSchemaError, parse

    bad = Path(__file__).parent / "fixtures" / "v2_plan_state_mismatch"
    with pytest.raises(PlanSchemaError, match="01.yaml"):
        parse(bad)


def test_parse_rework_loads_origin_items_and_parent_links():
    """Rework fixture round-trips parent_plan, prior_rework, origin_items."""
    from fr import parse

    rework = Path(__file__).parent / "fixtures" / "v2_plan_rework"
    plan = parse(rework)
    assert plan.meta.parent_plan is not None
    assert "fixture-parent" in plan.meta.parent_plan
    assert plan.meta.prior_rework is not None
    assert "rework-0" in plan.meta.prior_rework
    assert len(plan.meta.origin_items) == 3
    assert plan.meta.origin_items[0].id == 1
    assert plan.meta.origin_items[0].track == "development"
    assert plan.meta.origin_items[2].track == "decision"


def test_plan_prose_path_resolves_under_dir():
    """Plan.prose_path is dir / _prose.md."""
    from fr import parse

    plan = parse(FIXTURE_DIR)
    assert plan.prose_path == FIXTURE_DIR / "_prose.md"
    assert plan.prose_path.exists()


def test_plan_repo_root_discovered_when_in_git_repo():
    """parse() walks up from plan_dir to find .git."""
    from fr import parse

    plan = parse(FIXTURE_DIR)
    # We're running from the superpowers-for-vk repo, so repo_root should resolve
    assert plan.repo_root is not None
    assert (plan.repo_root / ".git").exists()
    assert FIXTURE_DIR.is_relative_to(plan.repo_root)


def test_plan_repo_relative_dir_strips_repo_prefix():
    """Plan.repo_relative_dir is dir relative to repo_root."""
    from fr import parse

    plan = parse(FIXTURE_DIR)
    rel = plan.repo_relative_dir
    assert not rel.is_absolute()
    assert str(rel).startswith("tests/unit/fixtures/")


def test_plan_repo_relative_dir_falls_back_when_no_git(tmp_path):
    """Outside a git repo, repo_relative_dir falls back to absolute dir."""
    import shutil

    from fr import parse

    # Copy fixture to a tmp dir that is NOT inside a git repo
    dest = tmp_path / "v2_plan_minimal"
    shutil.copytree(FIXTURE_DIR, dest)
    plan = parse(dest)
    assert plan.repo_root is None
    assert plan.repo_relative_dir == plan.dir


def test_parse_populates_prose_and_phase_texts():
    """parse() carries _prose.md and raw NN.yaml texts onto the Plan."""
    from fr import parse

    multi = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"
    plan = parse(multi)
    assert plan.prose == (multi / "_prose.md").read_text()
    assert set(plan.phase_texts) == {1, 2, 10}
    for n, fname in ((1, "01.yaml"), (2, "02.yaml"), (10, "10.yaml")):
        assert plan.phase_texts[n] == (multi / fname).read_text()


def test_parse_missing_prose_is_none(tmp_path):
    """A plan folder without _prose.md parses fine; prose is None."""
    import shutil

    from fr import parse

    dest = tmp_path / "no_prose"
    shutil.copytree(FIXTURE_DIR, dest)
    (dest / "_prose.md").unlink()
    plan = parse(dest)
    assert plan.prose is None
    assert set(plan.phase_texts) == {1}


def test_phasedoc_loads_minimal_fixture():
    import yaml
    from fr.types import PhaseDoc

    doc = PhaseDoc.model_validate(yaml.safe_load((FIXTURE_DIR / "01.yaml").read_text()))
    assert doc.phase.number == 1
    assert doc.phase.tag == "agentic"
    assert doc.phase.depends_on == ()
    assert doc.tasks[0].steps[0].id == "P1.T1.S1"
    assert doc.state.steps["P1.T1.S1"].state == " "


def test_phasedoc_rejects_state_key_mismatch():
    from fr.types import PhaseDoc
    from pydantic import ValidationError

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
    from fr.types import PlanMeta
    from pydantic import ValidationError

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


# ── the fr_version floor must be reachable by the fr it is aimed at ────


def test_the_version_floor_is_reported_before_an_unknown_key_kills_the_parse(tmp_path):
    """Review r5-b4, the whole point of a floor.

    `PlanMeta` is `extra="forbid"`, so a plan carrying a key this fr does not
    know is a hard parse failure. Validating the schema BEFORE the version
    gate meant the upgrade message — the plan's way of telling an older fr
    not to try — was never printed: fr 3.x meeting 4.0.0's `workflow:` key
    died on pydantic's `extra_forbidden` instead. Simulated here with a key
    no fr knows, plus a floor no installed fr satisfies.
    """
    import pytest
    from fr.parser import PlanSchemaError, parse

    plan_dir = tmp_path / "p"
    plan_dir.mkdir()
    (plan_dir / "_meta.yaml").write_text(
        "schema_version: 2\n"
        "plan: 2026-08-31-from-the-future\n"
        "target_repo: acme/demo\n"
        "created: 2026-08-31\n"
        'fr_version: ">=99.0.0,<100.0.0"\n'
        "a_key_from_a_later_fr: yes\n"
    )

    with pytest.raises(PlanSchemaError) as e:
        parse(plan_dir)

    assert "requires fr_version >=99.0.0,<100.0.0" in str(e.value)
    assert "To upgrade" in str(e.value)
    assert "extra_forbidden" not in str(e.value)


def test_an_unknown_key_still_fails_when_the_version_gate_passes(tmp_path):
    """The gate moved earlier; it did not become a substitute for schema
    validation."""
    import pytest
    from fr.parser import PlanSchemaError, parse

    plan_dir = tmp_path / "p"
    plan_dir.mkdir()
    (plan_dir / "_meta.yaml").write_text(
        "schema_version: 2\n"
        "plan: 2026-08-31-ok\n"
        "target_repo: acme/demo\n"
        "created: 2026-08-31\n"
        'fr_version: ">=4.0.0,<5.0.0"\n'
        "a_key_from_a_later_fr: yes\n"
    )

    with pytest.raises(PlanSchemaError, match="_meta.yaml"):
        parse(plan_dir)


def test_enforce_fr_version_false_still_skips_the_gate_entirely(tmp_path):
    """`fr.spec.compute_status` reads archived plans with the gate off; that
    must stay true now that the gate runs earlier."""
    import pytest
    from fr.parser import PlanSchemaError, parse

    plan_dir = tmp_path / "p"
    plan_dir.mkdir()
    (plan_dir / "_meta.yaml").write_text(
        "schema_version: 2\n"
        "plan: 2026-08-31-archived\n"
        "target_repo: acme/demo\n"
        "created: 2026-08-31\n"
        'fr_version: ">=99.0.0,<100.0.0"\n'
    )

    plan = parse(plan_dir, enforce_fr_version=False)
    assert plan.meta.plan == "2026-08-31-archived"
    with pytest.raises(PlanSchemaError):
        parse(plan_dir)
