"""The fr-triage skill's judgements.yaml example must be YAML an agent can copy.

The skill says the file "is your whole interface", so its example IS the spec an
agent writes from. The post-merge OpenCode walk (Test Plan 12, 2026-09-22) hit
`fr triage check` exit 2 twice while writing judgements.yaml, both times by
following the example:

- the `cx` comment listed a bare `-`, and `cx: -` is not the string "-":
  a lone `-` is YAML's block-sequence marker, a parse error;
- tiers and patterns were inline `{...}` flow mappings, which break on the
  first `: ` in free text ("Friction: real cost").

The engine refused loudly with file and line, so nothing was misread, but an
example that walks every reader into an error is a defect in the example.
These tests make the example a reader of the real model, not a guess about it.
"""

from __future__ import annotations

import re
import typing
from pathlib import Path

import pytest
import yaml
from fr.triage.model import Cx, load_judgements

SKILL = Path(__file__).resolve().parents[2] / "plugins/super-fr/skills/fr-triage/SKILL.md"


def _example() -> str:
    match = re.search(r"^```yaml\n(.*?)^```$", SKILL.read_text(), re.S | re.M)
    assert match, "the fr-triage skill has no ```yaml example block"
    return match.group(1)


def test_the_example_loads_through_the_real_judgements_model(tmp_path: Path) -> None:
    path = tmp_path / "judgements.yaml"
    path.write_text(_example())

    judgements = load_judgements(path)

    assert judgements.issues, "the example should show at least one judged issue"


def test_every_documented_cx_value_parses_as_written() -> None:
    """Each value the `cx:` comment offers must load to that exact Cx literal."""
    line = next(ln for ln in _example().splitlines() if ln.strip().startswith("cx:"))
    comment = line.split("#", 1)[1]
    documented = re.findall(r'"[^"]*"|[^\s|,]+', comment.split("(")[0])
    documented = [d for d in documented if d not in {"or"}]

    assert {d.strip('"') for d in documented} == set(typing.get_args(Cx)), (
        f"the cx comment documents {documented}, the model accepts {typing.get_args(Cx)}"
    )
    for form in documented:
        loaded = yaml.safe_load(f"cx: {form}")
        assert loaded == {"cx": form.strip('"')}, (
            f"`cx: {form}` as the skill writes it loads as {loaded!r}, not the Cx literal"
        )


def test_the_example_uses_no_flow_mappings_for_free_text() -> None:
    """Inline {...} entries break on the first `: ` in a title or description."""
    flow = [ln for ln in _example().splitlines() if re.match(r"\s*-\s*\{", ln)]

    assert not flow, f"flow-mapping entries in the skill's example: {flow}"


@pytest.mark.parametrize("free_text", ["Friction: real cost", "- starts with a dash", "x, y: z"])
def test_the_tier_shape_the_example_teaches_survives_hostile_free_text(
    tmp_path: Path, free_text: str
) -> None:
    """Swap every tier description for text containing YAML syntax; it must still load."""
    lines = _example().splitlines()
    swapped = [
        re.sub(r'(description: )(".*"|.*)$', lambda m: f'{m.group(1)}"{free_text}"', ln)
        for ln in lines
    ]
    path = tmp_path / "judgements.yaml"
    path.write_text("\n".join(swapped) + "\n")

    judgements = load_judgements(path)

    assert all(t.description == free_text for t in judgements.tiers)
