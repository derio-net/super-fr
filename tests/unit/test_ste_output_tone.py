"""Spec 2026-09-14-ste-output-tone: the STE output style and its rule carrier."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
STYLE = REPO_ROOT / "plugins/super-fr/output-styles/simplified-technical-english.md"
START = "<!-- ste-shared:start -->"
END = "<!-- ste-shared:end -->"


def _frontmatter(text: str) -> dict:
    assert text.startswith("---\n"), "file must open with YAML frontmatter"
    _, fm, _ = text.split("---\n", 2)
    return yaml.safe_load(fm)


def _shared_block(path: Path) -> str:
    text = path.read_text()
    assert text.count(START) == 1 and text.count(END) == 1, (
        f"{path.name}: needs exactly one ste-shared marker pair"
    )
    return text.split(START, 1)[1].split(END, 1)[0].strip()


def test_style_is_forced_and_keeps_coding_instructions() -> None:
    fm = _frontmatter(STYLE.read_text())
    assert fm["name"] == "Simplified Technical English"
    assert fm["force-for-plugin"] is True
    assert fm["keep-coding-instructions"] is True
    assert _shared_block(STYLE)


SECTIONS = (
    "### Scope",
    "### Words",
    "### Sentences",
    "### Structure",
    "### Warnings",
    "### Insight blocks",
)
FILLER = ("just", "really", "basically", "actually", "simply", "i think", "it seems")


def test_shared_text_has_every_section() -> None:
    block = _shared_block(STYLE)
    missing = [s for s in SECTIONS if s not in block]
    assert not missing, f"shared STE text lacks sections: {missing}"


def test_insight_blocks_cannot_lengthen_replies() -> None:
    block = _shared_block(STYLE)
    insight = block.split("### Insight blocks", 1)[1]
    assert "maximum of three points" in insight
    assert "does not permit replies longer" in insight


def test_shared_text_uses_no_filler_outside_quoted_examples() -> None:
    unquoted = re.sub(r'"[^"]*"', "", _shared_block(STYLE)).lower()
    found = [w for w in FILLER if re.search(rf"\b{re.escape(w)}\b", unquoted)]
    assert not found, f"shared STE text uses its own filler words: {found}"
