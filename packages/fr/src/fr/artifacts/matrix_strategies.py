"""The `matrix` kind's 3 -> 4 migration (spec
`2026-10-06-verification-strategies-design.md` §B, R7).

`Row.verify` widens from `Literal["post-merge"]` to a strategy name or `none`,
and the row gains `scenario`, `issues`, `harnesses` and `walks`. The old
`verify: post-merge` becomes `verify: live` — the shipped post-merge,
operator-driven strategy that is exactly what it meant. That is a BODY
rewrite, so every rule of `.claude/rules/artifact-versioning.md` applies:

1. **Frozen reader.** The old body is read with `fr.acceptance.legacy.MatrixV3`
   (versions 1 to 3), never the live model — and so is every earlier hop
   (`fr.artifacts.matrix_verify.guard_matrix`).
2. **Line surgery, built in memory, written once.** Only the `verify:` lines
   change — header comments, key order and every other byte survive — and the
   result must read as the live v4 `Matrix` with exactly the expected `verify`
   values before `write_text_atomic` runs. A body no line rewrite can convert
   safely (a flow-style row) is left byte-identical and reported as that one
   artifact's failure.
3. **The crash window.** A body that already reads as v4 under a v3 stamp (the
   rewrite landed, the stamp did not) is left alone and the runner stamps it —
   the one legitimate use of the live model here.

The reports do not render `verify`, so no companion is regenerated.
"""

from __future__ import annotations

import re
from pathlib import Path

from fr.artifacts.atomic import write_text_atomic
from fr.artifacts.matrix_verify import UnreadableMatrixError
from fr.artifacts.runner import MIGRATIONS, SchemaMigration

MIGRATION_NAME = "matrix-strategies"
NEW_SPELLING = "live"

__all__ = [
    "MATRIX_STRATEGIES_MIGRATION",
    "MIGRATION_NAME",
    "UnconvertibleMatrixError",
    "rewrite_post_merge",
]

# A block-style `verify: post-merge` line, quoted or not, keeping its
# indentation, any list-item dash and any trailing comment.
_VERIFY_LINE = re.compile(
    r"^(?P<lead>[ \t]*(?:-[ \t]+)?verify:[ \t]*)(?P<q>['\"]?)post-merge(?P=q)"
    r"(?P<tail>[ \t]*(?:#.*)?)$",
    re.MULTILINE,
)


class UnconvertibleMatrixError(UnreadableMatrixError):
    """A v3 matrix fr READ fine and still will not rewrite."""


def _is_v4(text: str) -> bool:
    from fr.acceptance.model import AcceptanceError, parse_matrix

    try:
        parse_matrix(text)
    except AcceptanceError:
        return False
    return True


def rewrite_post_merge(path: Path) -> None:
    """Rewrite `path` from v3 to v4 in place, or raise leaving it untouched."""
    from fr.acceptance.legacy import MatrixV3Error, parse_matrix_v3
    from fr.acceptance.model import AcceptanceError, parse_matrix

    try:
        text = path.read_text()
    except OSError as e:
        raise UnreadableMatrixError(f"{path}: cannot read: {e}") from e
    if _is_v4(text):
        return  # already v4 in body (crash window): the runner only stamps it
    try:
        old = parse_matrix_v3(text)
    except MatrixV3Error as e:
        raise UnreadableMatrixError(
            f"{path}: not a readable matrix, so fr will not stamp it ({e}). "
            "Fix the file by hand — it is left on its current version and will be retried."
        ) from e
    owed = sorted(r.id for r in old.rows if r.verify == "post-merge")
    new_text, n = _VERIFY_LINE.subn(rf"\g<lead>{NEW_SPELLING}\g<tail>", text)
    expected = {r.id: (NEW_SPELLING if r.verify else None) for r in old.rows}
    try:
        got = {r.id: r.verify for r in parse_matrix(new_text).rows}
    except AcceptanceError as e:
        got = {"<unreadable>": str(e)}
    if n != len(owed) or got != expected:
        raise UnconvertibleMatrixError(
            f"{path}: {len(owed)} row(s) carry `verify: post-merge` ({', '.join(owed)}) but "
            f"a line rewrite could not convert them to `verify: {NEW_SPELLING}` safely — "
            "rewrite them by hand, then re-run `fr migrate artifacts --yes`. "
            "Left on version 3, byte-identical."
        )
    if new_text != text:
        write_text_atomic(path, new_text)


MATRIX_STRATEGIES_MIGRATION = SchemaMigration(
    kind="matrix",
    from_version=3,
    to_version=4,
    fn=rewrite_post_merge,
    description="matrix: `verify` names a strategy — `post-merge` becomes `live`",
)

MIGRATIONS.register(MATRIX_STRATEGIES_MIGRATION)
