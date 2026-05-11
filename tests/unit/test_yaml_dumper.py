"""Tests for vk._yaml.dump_plan_yaml — readable yaml for plan files.

The whole reason this module exists: PyYAML's default `safe_dump` emits
multi-line strings as double-quoted scalars with `\\n` escapes, which is
unreadable for v2 step bodies (multi-paragraph prose + fenced code).
The custom dumper here uses literal block scalars (`|`) instead.
"""

from __future__ import annotations

import yaml

from vk._yaml import LiteralStr, dump_plan_yaml


def test_multiline_string_uses_literal_block_scalar():
    """Any string with a newline → `|` block scalar."""
    out = dump_plan_yaml({"text": "first line\nsecond line\nthird line"})
    # Literal block scalar opens with `|`
    assert "text: |" in out
    # No quoted-string `\n` escapes
    assert "\\n" not in out
    # Round-trips losslessly
    assert yaml.safe_load(out) == {"text": "first line\nsecond line\nthird line"}


def test_singleline_string_stays_plain():
    """Single-line strings should NOT get the block-scalar treatment."""
    out = dump_plan_yaml({"title": "Phase 1"})
    assert "title: Phase 1\n" == out


def test_unicode_arrows_preserved_as_is():
    """allow_unicode=True keeps `→`, em-dash, etc. as-is (not `\\u2192`)."""
    out = dump_plan_yaml({"track": "decision → development"})
    assert "→" in out
    assert "\\u" not in out


def test_key_order_preserved():
    """sort_keys=False — declared order is the canonical order."""
    out = dump_plan_yaml({"schema_version": 2, "phase": "x", "tasks": []})
    # `schema_version` line index < `phase` line index
    lines = out.splitlines()
    assert next(i for i, line in enumerate(lines) if line.startswith("schema_version")) < next(
        i for i, line in enumerate(lines) if line.startswith("phase")
    )


def test_multiline_with_code_fence_is_human_readable():
    """The motivating use case: step text containing a fenced code block."""
    text = (
        "Write a failing test pinning the default behaviour\n\n"
        "```python\n"
        "def test_foo() -> None:\n"
        "    assert True\n"
        "```\n\n"
        "Run: `pytest -x -q` — expect green."
    )
    out = dump_plan_yaml({"text": text})
    assert "text: |" in out
    # The code fence appears verbatim in the output
    assert "```python" in out
    assert "def test_foo() -> None:" in out
    # Round-trips losslessly
    assert yaml.safe_load(out) == {"text": text}


def test_nested_dict_with_multiline_values():
    """Multi-line strings nested inside lists/dicts also get block scalars."""
    data = {
        "tasks": [{"number": 1, "title": "T", "steps": [{"id": "P1.T1.S1", "text": "a\nb\nc"}]}]
    }
    out = dump_plan_yaml(data)
    assert "text: |" in out
    assert "\\n" not in out
    assert yaml.safe_load(out) == data


def test_empty_dict():
    """No regression on empty input."""
    out = dump_plan_yaml({})
    assert out == "{}\n"


def test_literal_str_single_line_uses_block_scalar():
    """LiteralStr forces literal block even for single-line strings."""
    out = dump_plan_yaml({"text": LiteralStr("Run the tests")})
    assert "text: |-\n" in out
    assert yaml.safe_load(out) == {"text": "Run the tests"}


def test_literal_str_with_special_chars_no_quoting():
    """LiteralStr avoids single-quoting for strings with backticks or colons."""
    out = dump_plan_yaml({"text": LiteralStr("Install `foo`: run the script")})
    assert "'" not in out
    assert "text: |-\n" in out
    assert yaml.safe_load(out) == {"text": "Install `foo`: run the script"}


def test_literal_str_multiline_same_as_plain_str():
    """LiteralStr and plain str both use block scalar for multi-line content."""
    text = "line one\nline two"
    out_plain = dump_plan_yaml({"text": text})
    out_literal = dump_plan_yaml({"text": LiteralStr(text)})
    assert yaml.safe_load(out_plain) == yaml.safe_load(out_literal)
