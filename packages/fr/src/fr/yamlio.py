"""Safe YAML loading backed by libyaml when it is installed.

Spec 2026-11-01-ci-speed §3.A: PyYAML's pure-Python loader dominates the
acceptance matrix's parse time; ``CSafeLoader`` is the same grammar in C. This
module is the one place that picks the loader. Standardizing every other
``yaml.safe_load`` call site on it is a tracked follow-up issue, not part of
this change.
"""

from __future__ import annotations

from typing import Any, NoReturn

import yaml

SafeLoader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def safe_load(text: str) -> object:
    """`yaml.safe_load`, through libyaml's loader when available."""
    return yaml.load(text, Loader=SafeLoader)  # noqa: S506 - a safe loader


class StrictLoader(yaml.SafeLoader):
    """`SafeLoader` that refuses a mapping with a repeated key.

    PyYAML keeps the LAST occurrence and says nothing, which makes a duplicate
    key a *silent drop*: the shape still validates, and everything the earlier
    block declared is simply gone. This repo shipped exactly that: a row of
    `docs/acceptance/matrix.yaml` carried `levels:` twice, so one of its two
    test refs disappeared from the matrix, from the generated reports and from
    `fr acceptance check`, with nothing anywhere reporting a problem.

    This is the one owner of the detector. A reader that words the refusal
    differently overrides `duplicate_key` only. It is still based on the
    pure-Python `yaml.SafeLoader`; moving it to libyaml is a separate change.
    """

    def construct_mapping(self, node: Any, deep: bool = False) -> dict[Any, Any]:
        seen: set[Any] = set()
        for key_node, _ in node.value:
            # PyYAML ships no stubs for its constructor API, hence the ignore.
            key: Any = self.construct_object(key_node, deep=deep)  # type: ignore[no-untyped-call]
            try:
                duplicate = key in seen
            except TypeError:  # pragma: no cover - an unhashable YAML key
                continue
            if duplicate:
                self.duplicate_key(node, key_node, key)
            seen.add(key)
        return super().construct_mapping(node, deep=deep)

    def duplicate_key(self, node: Any, key_node: Any, key: Any) -> NoReturn:
        """Refuse a repeated `key`; the default is PyYAML's own error type."""
        raise yaml.constructor.ConstructorError(
            "while constructing a mapping",
            node.start_mark,
            f"found duplicate key {key!r}",
            key_node.start_mark,
        )
