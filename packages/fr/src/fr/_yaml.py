"""Shared YAML serialisation for plan files.

PyYAML's default `safe_dump` emits multi-line strings as double-quoted
scalars with `\\n` escapes (e.g. `text: "line one\\n\\nline two\\n```bash\\n..."`).
That's borderline unreadable for v2 step bodies, which routinely contain
fenced code blocks, multiple paragraphs, and unicode arrows.

`dump_plan_yaml` swaps in a custom representer that emits any string
containing a newline as a YAML literal block scalar (`text: |`), which
preserves the source text verbatim:

    text: |
      Write a failing test pinning the default-None behaviour

      ```python
      def test_phase_track_label_defaults_to_none() -> None:
          ...
      ```

Single-line strings still use the default plain / quoted style — only
multi-line content gets the block-scalar treatment. `allow_unicode=True`
keeps `→`, em-dashes, and other operator-friendly punctuation as-is
instead of `\\u2192`-escaping them.

For fields that should always use the literal block style regardless of
line count (e.g. step `text:` values), wrap the value in `LiteralStr`.
The representer dispatches on type, so `LiteralStr` always gets `|-`.

Both `vk.migrate` and `vk.plan_ops` route through this so migrated and
hand-edited yaml files stay visually consistent.
"""

from __future__ import annotations

from typing import Any

import yaml


class LiteralStr(str):
    """A str subclass that always serialises as a YAML literal block scalar.

    Use for step `text:` fields so single-line step titles get `|-` instead
    of plain or single-quoted scalars, keeping all phase YAML consistent.
    """


def _represent_str(dumper: yaml.SafeDumper, data: str) -> yaml.ScalarNode:
    """Use literal block scalar for any string that contains a newline."""
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


def _represent_literal_str(dumper: yaml.SafeDumper, data: LiteralStr) -> yaml.ScalarNode:
    """Always use literal block scalar, even for single-line strings."""
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


class _PlanYamlDumper(yaml.SafeDumper):
    """SafeDumper variant with literal-block-scalar representer for multi-line strings."""


_PlanYamlDumper.add_representer(str, _represent_str)
_PlanYamlDumper.add_representer(LiteralStr, _represent_literal_str)


def dump_plan_yaml(data: dict[str, Any]) -> str:
    """Canonical plan-yaml serialisation.

    - `sort_keys=False` — preserve declared key order (`schema_version`
      first, `phase` before `tasks`, etc.).
    - `allow_unicode=True` — keep `→`, em-dashes, etc. as-is.
    - Multi-line strings → literal block scalars (`|`).
    """
    return yaml.dump(
        data,
        Dumper=_PlanYamlDumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
