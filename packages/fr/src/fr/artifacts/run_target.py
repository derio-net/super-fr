"""Run 11 -> 12: optional explicit merge target; never guess one for an old run."""

from __future__ import annotations

from pathlib import Path

import yaml

from fr.artifacts.run_cursor import UnreadableRunCursorError
from fr.artifacts.runner import MIGRATIONS, SchemaMigration


def refuse_unreadable_v11_cursor(path: Path) -> None:
    from fr.artifacts.run_usage_split import _already_v11

    try:
        text = path.read_text()
        readable = _already_v11(text, yaml.safe_load(text))
    except (OSError, yaml.YAMLError):
        readable = False
    if not readable:
        raise UnreadableRunCursorError(
            f"{path}: not a readable version-11 run cursor; "
            "left unchanged, not stamped as version 12"
        )


MIGRATIONS.register(
    SchemaMigration(
        kind="run",
        from_version=11,
        to_version=12,
        fn=refuse_unreadable_v11_cursor,
        description="run cursor: optional explicit merge target (base_branch); stamp only",
    )
)
