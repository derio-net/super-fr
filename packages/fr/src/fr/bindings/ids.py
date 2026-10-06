"""Model-id validators — a leaf module (no fr imports) so the prober, the
config command and anything else that puts a binding on an argv share one rule.

A binding value can arrive from the tracked repo-layer ``models.yaml``, so a
value that could be read as an option (``--auto``, ``--dir=/x``) must never reach
a subprocess. The shape is OpenCode's: ``provider/model``, where the model part
may itself be nested (``openrouter/anthropic/claude-3.5``) or versioned
(``vertex/claude@20240620``). Every ``/``-separated segment starts alphanumeric,
and nothing allows whitespace or ``=``.
"""

from __future__ import annotations

import re

_PROVIDER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@+-]*")


def valid_provider(provider: str) -> bool:
    """A provider is the id's first segment only."""
    return _PROVIDER.fullmatch(provider) is not None


def valid_model_name(model: str) -> bool:
    """``provider/model[/more]`` or a bare name; no segment may start with ``-``
    or hold whitespace or ``=``."""
    head, sep, tail = model.partition("/")
    if not sep:
        return _SEGMENT.fullmatch(model) is not None
    return valid_provider(head) and all(_SEGMENT.fullmatch(s) for s in tail.split("/"))


def valid_model_id(model: str) -> bool:
    """`valid_model_name`, with a provider required: the shape OpenCode takes."""
    return "/" in model and valid_model_name(model)
