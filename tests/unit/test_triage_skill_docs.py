"""Triage skills document pages, fragments, data fields and verbs (phase 5, R14)."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TRIAGE_SKILL = REPO / "plugins" / "super-fr" / "skills" / "fr-triage" / "SKILL.md"
ORIGINS_SKILL = REPO / "plugins" / "super-fr" / "skills" / "fr-origins" / "SKILL.md"
AUDIT_SKILL = REPO / "plugins" / "super-fr" / "skills" / "fr-audit" / "SKILL.md"


def test_fr_triage_skill_documents_pages_and_history() -> None:
    """fr-triage SKILL.md names the four page goals and history verb."""
    text = TRIAGE_SKILL.read_text()
    assert "fr triage history render" in text, "SKILL.md must document fr triage history render"


def test_fr_triage_skill_documents_state_export() -> None:
    """fr-triage SKILL.md names the state export verb."""
    text = TRIAGE_SKILL.read_text()
    assert "fr triage state export" in text or "state export" in text, (
        "SKILL.md must document state export verb"
    )


def test_fr_triage_skill_documents_severity() -> None:
    """fr-triage SKILL.md names severity field."""
    text = TRIAGE_SKILL.read_text()
    assert "severity" in text, "SKILL.md must document severity field"


def test_fr_triage_skill_documents_duplicate_of() -> None:
    """fr-triage SKILL.md names duplicate_of field."""
    text = TRIAGE_SKILL.read_text()
    assert "duplicate_of" in text or "duplicate of" in text, (
        "SKILL.md must document duplicate_of field"
    )


def test_fr_triage_skill_documents_export_config() -> None:
    """fr-triage SKILL.md names the export config key."""
    text = TRIAGE_SKILL.read_text()
    assert "export:" in text, "SKILL.md must document export: config key"


def test_fr_triage_skill_documents_board_manifest() -> None:
    """fr-triage SKILL.md names board/manifest.yaml (fragment manifests)."""
    text = TRIAGE_SKILL.read_text()
    assert "board/manifest.yaml" in text or "manifest.yaml" in text, (
        "SKILL.md must document fragment manifests"
    )


def test_fr_origins_skill_documents_duplicate_of() -> None:
    """fr-origins SKILL.md names duplicate_of field."""
    text = ORIGINS_SKILL.read_text()
    assert "duplicate_of" in text or "duplicate of" in text, (
        "SKILL.md must document duplicate_of field"
    )


def test_fr_origins_skill_documents_fixed_by() -> None:
    """fr-origins SKILL.md names fixed_by field."""
    text = ORIGINS_SKILL.read_text()
    assert "fixed_by" in text or "fixed by" in text, "SKILL.md must document fixed_by field"


def test_fr_origins_skill_documents_introduced_in() -> None:
    """fr-origins SKILL.md names introduced_in field."""
    text = ORIGINS_SKILL.read_text()
    assert "introduced_in" in text or "introduced in" in text, (
        "SKILL.md must document introduced_in field"
    )


def test_fr_origins_skill_documents_schema_2() -> None:
    """fr-origins SKILL.md names schema 2."""
    text = ORIGINS_SKILL.read_text()
    assert "schema: 2" in text or "schema 2" in text, "SKILL.md must document schema 2"


def test_fr_origins_skill_documents_origins_manifest() -> None:
    """fr-origins SKILL.md names origins/manifest.yaml (fragment manifests)."""
    text = ORIGINS_SKILL.read_text()
    assert "origins/manifest.yaml" in text or "manifest.yaml" in text, (
        "SKILL.md must document fragment manifests"
    )


def test_fr_audit_skill_documents_four_page_goals() -> None:
    """fr-audit SKILL.md documents the four page goals."""
    text = AUDIT_SKILL.read_text()
    # The board page goal: "What do I do next?"
    assert "What do I do next" in text or "what to do next" in text, (
        "SKILL.md must document the board page goal"
    )
    # The origins page goal: "Where do defects come from?"
    assert "Where do defects come from" in text or "where defects come from" in text, (
        "SKILL.md must document the origins page goal"
    )
    # The architecture page goal: "What is the system?"
    assert "What is the system" in text or "what is the system" in text, (
        "SKILL.md must document the architecture page goal"
    )
    # The history page goal: "How did we get here?"
    assert "How did we get here" in text or "how did we get here" in text or "history" in text, (
        "SKILL.md must document the history page goal"
    )


def test_fr_audit_skill_documents_hand_written_analysis_in_fragments() -> None:
    """fr-audit SKILL.md says hand-written analysis lives in fragments."""
    text = AUDIT_SKILL.read_text()
    assert "fragment" in text and ("hand" in text or "author" in text or "you author" in text), (
        "SKILL.md must document that hand-written analysis lives in fragments"
    )


def test_fr_triage_skill_documents_claims_scope_config_and_publishing_in_every_copy() -> None:
    """R16: the canonical skill and both generated mirrors carry the Claims paragraph."""
    needles = (
        "**Claims:**",
        "fr:claimed",
        "FR_HOST_ID",
        "fr triage claim take",
        "claim_expiry_hours",
        "scope.yaml",
        "publish",
        "{scope_id}",
        "Held elsewhere",
    )
    for path in (
        TRIAGE_SKILL,
        REPO / ".opencode" / "skills" / "fr-triage" / "SKILL.md",
        REPO / ".hermes" / "skills" / "fr" / "fr-triage" / "SKILL.md",
    ):
        text = path.read_text()
        missing = [n for n in needles if n not in text]
        assert not missing, f"{path.relative_to(REPO)} lacks {missing}"


# --- the cloud driver (2026-10-07 cloud-triage R20, R21, R23) -----------------------


def _skill_text() -> str:
    return TRIAGE_SKILL.read_text()


def test_fr_triage_skill_documents_the_cloud_driver() -> None:
    text = _skill_text()
    for needle in (
        "fr triage drive pass",
        "fr triage drive record",
        "wake",
        "outbox",
        "host-id",
    ):
        assert needle in text, f"SKILL.md must name {needle!r} (R21)"


def test_fr_triage_skill_documents_forge_api_state_ref_repo_and_privacy() -> None:
    text = _skill_text()
    for needle in (
        "forge.api",
        "refs/fr/triage/",
        "state_repo",
        "privacy guard",
        "merge_method",
        "fr cloud doctor",
        "docs/cloud-setup.md",
    ):
        assert needle in text, f"SKILL.md must name {needle!r} (R21, R23, p1-r5)"


def test_fr_triage_skill_says_the_cloud_driver_runs_no_post_merge() -> None:
    """R20: post_merge is the host driver's; the cloud driver runs nothing."""
    text = _skill_text()
    assert "cloud driver runs no `post_merge`" in text


def test_fr_triage_skill_stays_within_its_line_budget() -> None:
    assert len(_skill_text().strip().split("\n")) <= 120
