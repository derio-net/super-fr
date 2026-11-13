"""Writing standards for the published docs (spec 2026-11-13-writing-standards-docs)."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]


def _page_globs() -> list[str]:
    return list(yaml.safe_load((REPO / ".fr/docs.yaml").read_text())["pages"])


def test_the_docs_config_names_the_three_page_groups() -> None:
    assert sorted(_page_globs()) == sorted(
        ["docs/explainers/*.md", "docs/*.md", "docs/reference/*.md"]
    )
