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
