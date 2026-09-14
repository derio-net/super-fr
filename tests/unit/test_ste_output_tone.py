"""Spec 2026-09-14-ste-output-tone: the STE output style and its rule carrier."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
STYLE = REPO_ROOT / "plugins/super-fr/output-styles/simplified-technical-english.md"
START = "<!-- ste-shared:start -->"
END = "<!-- ste-shared:end -->"
MAX_SENTENCE_WORDS = 25


def _frontmatter(text: str) -> dict:
    assert text.startswith("---\n"), "file must open with YAML frontmatter"
    _, fm, _ = text.split("---\n", 2)
    return yaml.safe_load(fm)


def _shared_block(path: Path) -> str:
    text = path.read_text()
    assert text.count(START) == 1 and text.count(END) == 1, (
        f"{path.name}: needs exactly one ste-shared marker pair"
    )
    assert text.index(START) < text.index(END), f"{path.name}: ste-shared markers out of order"
    return text.split(START, 1)[1].split(END, 1)[0].strip()


def _section(block: str, heading: str) -> str:
    """Text under `heading`, up to the next `### ` heading, whitespace-normalized."""
    section = block.split(heading + "\n", 1)[1].split("\n### ", 1)[0]
    return re.sub(r"\s+", " ", section)


def _sentences(block: str) -> list[str]:
    """Sentences of prose and bullets; headings, code spans and quoted examples dropped."""
    sentences: list[str] = []
    for item in re.split(r"\n\s*\n|\n(?=- )", block):
        prose = " ".join(line for line in item.splitlines() if not line.startswith("#"))
        prose = re.sub(r'`[^`]*`|"[^"]*"', "", prose.removeprefix("- "))
        sentences += [s for s in re.split(r"(?<=[.!?])\s+", prose.strip()) if s]
    return sentences


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


def test_shared_text_has_every_section() -> None:
    block = _shared_block(STYLE)
    missing = [s for s in SECTIONS if not re.search(rf"^{re.escape(s)}$", block, re.M)]
    assert not missing, f"shared STE text lacks sections: {missing}"


def test_scope_excludes_edited_files_and_defers_to_prescribed_formats() -> None:
    scope = _section(_shared_block(STYLE), "### Scope")
    assert "Do not apply them to files that you edit" in scope
    assert "gives a format or exact words, use them" in scope


def test_insight_blocks_cannot_lengthen_replies() -> None:
    insight = _section(_shared_block(STYLE), "### Insight blocks")
    assert "maximum of three points" in insight
    assert "Insight blocks do not make a reply longer" in insight
    assert "exceed typical length constraints" in insight
    assert "take precedence" in insight


def test_shared_text_uses_no_filler_outside_quoted_examples() -> None:
    block = re.sub(r"\s+", " ", _shared_block(STYLE))
    assert block.count('"') % 2 == 0, "unbalanced double quote hides text from this check"
    bullet = block.split("Do not use filler", 1)[1].split(" - ", 1)[0]
    filler = [w.lower() for w in re.findall(r'"([^"]+)"', bullet)]
    assert {"just", "really", "i think"} <= set(filler), f"filler list not parsed: {filler}"
    unquoted = re.sub(r'"[^"]*"', "", block).lower()
    found = [w for w in filler if re.search(rf"\b{re.escape(w)}\b", unquoted)]
    assert not found, f"shared STE text uses its own filler words: {found}"


def test_no_shared_sentence_exceeds_the_description_limit() -> None:
    long = [
        (len(re.findall(r"[\w'-]+", s)), s)
        for s in _sentences(_shared_block(STYLE))
        if len(re.findall(r"[\w'-]+", s)) > MAX_SENTENCE_WORDS
    ]
    assert not long, f"sentences over {MAX_SENTENCE_WORDS} words: {long}"


def test_sentence_splitter_finds_a_long_sentence() -> None:
    """The length guard must be able to fail: a fake over-long sentence is caught."""
    fake = "### Scope\n\n- " + " ".join(["word"] * 30) + ".\n- Short one."
    counts = [len(re.findall(r"[\w'-]+", s)) for s in _sentences(fake)]
    assert counts == [30, 2]
