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
from fr.triage.model import JUDGEMENTS_SCHEMA, Cx, load_judgements

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


def test_the_skill_teaches_current_schema_and_batches(tmp_path: Path) -> None:
    """Review r2p-f14: agents copy the skill, so it must never say `schema: 1`,
    and its example must show a batch that loads through the real model."""
    text = SKILL.read_text()
    assert "schema: 1" not in text
    assert re.search(rf"^schema: {JUDGEMENTS_SCHEMA}$", _example(), re.M)
    assert f"**Schema {JUDGEMENTS_SCHEMA}:**" in text
    path = tmp_path / "judgements.yaml"
    path.write_text(_example())
    judgements = load_judgements(path)
    assert judgements.schema_ == JUDGEMENTS_SCHEMA
    assert judgements.batches, "the example should show a batch"
    assert all(not b.events for b in judgements.batches), "events are engine-written"


def test_historical_schema_3_example_still_loads_unchanged_batches(tmp_path: Path) -> None:
    """Current documentation does not retire already-authored schema-3 state."""
    path = tmp_path / "judgements.yaml"
    path.write_text(_example())
    current = load_judgements(path)
    historical = yaml.safe_load(_example())
    historical["schema"] = 3
    path.write_text(yaml.safe_dump(historical))
    loaded = load_judgements(path)
    assert loaded.schema_ == 3
    assert loaded.batches == current.batches and loaded.issues == current.issues


def test_the_skill_names_the_batch_verbs_and_the_yes_rule() -> None:
    text = SKILL.read_text()
    for verb in (
        "batch suggest",
        "batch create",
        "batch dispatch",
        "batch merge",
        "batch cancel",
        "batch drive",
    ):
        assert verb in text, verb
    assert "--yes" in text


def test_the_example_shows_both_duplicate_fields_and_loads_them(tmp_path: Path) -> None:
    path = tmp_path / "judgements.yaml"
    path.write_text(_example())

    judged = load_judgements(path).issues["super-fr#470"]

    assert judged.duplicate_of == "super-fr#435"
    assert judged.distinct_from == ["super-fr#469"]


def test_the_skill_teaches_judging_candidates_and_leaves_the_close_to_the_operator() -> None:
    text = SKILL.read_text()

    assert "**duplicate candidates**" in text and "**duplicates**" in text
    assert "`duplicate_of: <original>`" in text and "`distinct_from: [<other>]`" in text
    assert "gh issue close N --duplicate-of <url>" in text
    assert "link duplicates in `note`" not in text
    assert "`dedupe` line" in text
