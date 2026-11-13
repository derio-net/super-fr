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


SCRIPT = REPO / "scripts/check-writing-standards.sh"

# The page-group mapping the spec fixes (R1): standard -> the `.fr/docs.yaml` globs it covers.
GROUPS = {
    "ste": ["docs/*.md", "docs/reference/*.md"],
    "plain-language": ["docs/explainers/*.md"],
}

# The only pages whose front matter departs from their group's standard (R3).
EXCEPTIONS = {
    "docs/explainers/why-fr.md": "elements-of-style",
    "docs/explainers/index.md": "none",
    "docs/reference/cli.md": "none",
}


def _script_groups() -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for line in SCRIPT.read_text().splitlines():
        words = line.split()
        if words[:2] == ["run", "--default"]:
            groups[words[2]] = words[3:]
    return groups


def _front_matter(path: Path) -> dict[str, object]:
    text = path.read_text()
    assert text.startswith("---\n"), path
    return yaml.safe_load(text[4 : text.index("\n---\n", 4)]) or {}


def test_the_script_exists_and_is_executable() -> None:
    assert SCRIPT.is_file()
    assert SCRIPT.stat().st_mode & 0o111


def test_the_script_maps_each_group_to_its_standard() -> None:
    assert _script_groups() == GROUPS


def test_the_script_covers_exactly_the_docs_config_pages() -> None:
    covered = [glob for globs in _script_groups().values() for glob in globs]
    assert sorted(covered) == sorted(_page_globs())


def test_the_script_runs_from_the_toplevel_with_its_own_pyyaml() -> None:
    text = SCRIPT.read_text()
    assert 'cd "$(git rev-parse --show-toplevel)"' in text
    assert "uv run --isolated --no-project --with pyyaml python" in text
    assert "tools/validate_writing_standard.py" in text


def test_only_the_three_exceptions_carry_a_writing_standard_key() -> None:
    carried = {}
    for glob in _page_globs():
        for page in sorted(REPO.glob(glob)):
            meta = _front_matter(page)
            if "writing_standard" in meta:
                carried[page.relative_to(REPO).as_posix()] = meta["writing_standard"]
    assert carried == EXCEPTIONS
