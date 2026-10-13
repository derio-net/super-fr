"""The `matrix` kind's 4 -> 5 migration (spec `2026-10-11-debt-engine-design.md`
§D, R6).

The status `skipped` ("verification exists, not in CI") hid four situations,
so it splits into `unwired`, `walk-owed`, `walked` and `manual`. Every
`skipped` row moves into exactly one of the first three by a fixed rule, read
from the row itself:

- a passing walk → `walked`;
- otherwise its own `verify` names a post-merge strategy → `walk-owed`;
- otherwise → `unwired`.

`manual` is never assigned mechanically: it is an operator's reclassification
(`fr acceptance set-status`). Rows in other statuses are untouched.

A status REMOVAL, so every rule of `.claude/rules/artifact-versioning.md`
applies:

1. **Frozen reader.** The old body is read with `fr.acceptance.legacy.MatrixV4`
   (versions 1 to 4), never the live model — and so is every earlier hop.
2. **Map by the row's own `verify`.** `is_post_merge(row.verify, repo_root)`
   decides; no spec or shape default is consulted. A name that does not
   resolve refuses the whole matrix, byte-identical.
3. **Line surgery, built in memory, written once.** Only the `status:` lines of
   `skipped` rows change. The result must read as the live v5 `Matrix` with
   exactly the expected statuses, and the committed reports are rendered from
   it, all before `write_text_atomic` runs. A body no line rewrite can convert
   safely (a flow-style row) is left byte-identical and reported as that one
   artifact's failure.
4. **The crash window.** A body that already reads as v5 under a v4 stamp (the
   rewrite landed, the stamp did not) is not rewritten — the one legitimate use
   of the live model here — but its reports are still brought in line.
"""

from __future__ import annotations

import re
from pathlib import Path

from fr.artifacts.atomic import write_text_atomic
from fr.artifacts.matrix_strategies import UnconvertibleMatrixError
from fr.artifacts.matrix_verify import UnreadableMatrixError
from fr.artifacts.runner import MIGRATIONS, SchemaMigration

MIGRATION_NAME = "matrix-status-split"

__all__ = [
    "MATRIX_STATUS_SPLIT_MIGRATION",
    "MIGRATION_NAME",
    "split_status",
    "split_skipped",
]

_ITEM = re.compile(r"^(?P<ind>[ \t]*)-[ \t]+(?P<key>[\w-]+)[ \t]*:")
_ROWS_KEY = re.compile(r"^rows[ \t]*:", re.MULTILINE)
_SKIPPED_TAIL = re.compile(r"""^(?P<q>['"]?)skipped(?P=q)(?P<tail>[ \t]*(?:#.*)?)$""")


# The status comment `fr acceptance init` wrote into a matrix's header before
# the split, verbatim. The 4 -> 5 rewrite swaps it for the current scaffold's
# when it matches EXACTLY; a header anyone edited is theirs and left alone.
_V4_STATUS_COMMENT = """\
#   status:     ci | scheduled | skipped | not-implemented | failing
#     ci               automated on every PR — cannot drift silently
#     scheduled        automated on cron/path triggers
#     skipped          verification exists but does not run in CI (proven
#                      live once / manual walk) → CI warning, backfill owed
#     not-implemented  no test or surface exists yet → CI warning
#     failing          known red → `fr acceptance check` exits 2, CI FAILS
"""


def current_status_comment() -> str:
    """The status comment of the current matrix scaffold (`MATRIX_TEMPLATE`):
    its lines from `#   status:` up to `#   notes:`."""
    from fr.acceptance.scaffold import MATRIX_TEMPLATE

    start = MATRIX_TEMPLATE.index("#   status:")
    return MATRIX_TEMPLATE[start : MATRIX_TEMPLATE.index("#   notes:", start)]


def replace_status_comment(text: str) -> str:
    """`text` with its header's v4 scaffold status comment replaced by the
    current one, when the header carries it exactly once; else `text`."""
    rows_at = _ROWS_KEY.search(text)
    head = text[: rows_at.start()] if rows_at else text
    if head.count(_V4_STATUS_COMMENT) != 1:
        return text
    return text.replace(_V4_STATUS_COMMENT, current_status_comment(), 1)


def _root(path: Path) -> Path:
    """`<root>/docs/acceptance/matrix.yaml` → `<root>` (the kind's locator)."""
    return path.parents[2]


def _report_paths(path: Path) -> list[Path]:
    from fr.acceptance.report import REPORT_SET

    return [_root(path) / rel for rel in REPORT_SET]


def split_status(walked: bool, verify: str | None, repo_root: Path | None) -> str:
    """R6's fixed rule for one `skipped` row (or step-record entry), given
    whether it has a passing walk and its own `verify`: `walked`, `walk-owed`
    or `unwired`. Raises `StrategyError` for a `verify` that does not resolve —
    the caller refuses rather than guess."""
    from fr.verification.effective import is_post_merge

    if walked:
        return "walked"
    if is_post_merge(verify, repo_root):
        return "walk-owed"
    return "unwired"


def _rewrite_lines(text: str, targets: dict[str, str]) -> tuple[str, set[str]]:
    """Rewrite the block-style `status: skipped` line of each row in `targets`
    (id → new status). Returns the new text and the ids actually rewritten."""
    lines = text.splitlines(keepends=True)
    in_rows = False
    item_ind: str | None = None
    key_col: int | None = None
    current: list[int] = []  # indexes of the current item's lines
    done: set[str] = set()

    def flush() -> None:
        if key_col is None or not current:
            return
        rid: str | None = None
        status_at: int | None = None
        for idx in current:
            line = lines[idx].rstrip("\r\n")
            body = line[key_col:] if len(line) > key_col else ""
            head = line[:key_col]
            if head.strip() not in ("", "-"):
                continue  # deeper or shallower than this item's keys
            if body.startswith("id:"):
                rid = body[3:].split("#", 1)[0].strip().strip("'\"")
            elif body.startswith("status:"):
                status_at = idx
        if rid in targets and status_at is not None and rid not in done:
            line = lines[status_at]
            eol = line[len(line.rstrip("\r\n")) :]
            stripped = line.rstrip("\r\n")
            prefix_len = key_col + len("status:")
            value = stripped[prefix_len:]
            lead = len(value) - len(value.lstrip(" \t"))
            m = _SKIPPED_TAIL.match(value.lstrip(" \t"))
            if m:
                lines[status_at] = (
                    stripped[: prefix_len + lead] + targets[rid] + m.group("tail") + eol
                )
                done.add(rid)

    for i, raw in enumerate(lines):
        line = raw.rstrip("\r\n")
        if not in_rows:
            in_rows = bool(_ROWS_KEY.match(line))
            continue
        if line and not line[0].isspace() and not line.startswith("-") and not line.startswith("#"):
            break  # a later top-level key: the rows are over
        m = _ITEM.match(line)
        if m and (item_ind is None or m.group("ind") == item_ind):
            flush()
            item_ind = m.group("ind")
            key_col = m.start("key")
            current = [i]
            continue
        if item_ind is not None:
            current.append(i)
    flush()
    return "".join(lines), done


def split_skipped(path: Path) -> list[Path]:
    """Rewrite `path` from v4 to v5 in place (and its committed reports), or
    raise leaving every file untouched. Returns the reports it wrote."""
    from fr.acceptance.legacy import MatrixV4Error, parse_matrix_v4
    from fr.acceptance.model import AcceptanceError, parse_matrix
    from fr.acceptance.report import render_committed_set
    from fr.verification.model import StrategyError

    root = _root(path)
    try:
        text = path.read_text()
    except OSError as e:
        raise UnreadableMatrixError(f"{path}: cannot read: {e}") from e
    try:
        parse_matrix(text)
        new_text = text  # already v5 in body (crash window): only the stamp is owed
    except AcceptanceError:
        try:
            old = parse_matrix_v4(text)
        except MatrixV4Error as e:
            raise UnreadableMatrixError(
                f"{path}: not a readable matrix, so fr will not stamp it ({e}). "
                "Fix the file by hand — it is left on its current version and will be retried."
            ) from e
        targets: dict[str, str] = {}
        for row in old.rows:
            if row.status != "skipped":
                continue
            try:
                passed = any(w.outcome == "pass" for w in row.walks)
                targets[row.id] = split_status(passed, row.verify, root)
            except StrategyError as e:
                raise UnconvertibleMatrixError(
                    f"{path}: row {row.id} is `skipped` and its verify {row.verify!r} does not "
                    f"resolve ({e}), so fr cannot tell `walk-owed` from `unwired` — fix the "
                    "row's verify, then re-run `fr migrate artifacts --yes`. "
                    "Left on version 4, byte-identical."
                ) from e
        new_text, done = _rewrite_lines(text, targets)
        expected = {r.id: targets.get(r.id, r.status) for r in old.rows}
        try:
            got: dict[str, str] = {r.id: r.status for r in parse_matrix(new_text).rows}
        except AcceptanceError as e:
            got = {"<unreadable>": str(e)}
        if done != set(targets) or got != expected:
            raise UnconvertibleMatrixError(
                f"{path}: {len(targets)} row(s) are `skipped` ({', '.join(sorted(targets))}) "
                "but a line rewrite could not move them to unwired / walk-owed / walked "
                "safely — rewrite them by hand, then re-run `fr migrate artifacts --yes`. "
                "Left on version 4, byte-identical."
            )
    new_text = replace_status_comment(new_text)
    # Everything is rendered before a byte moves: a render that fails leaves
    # the matrix untouched, and the hop retries next run.
    reports: dict[Path, str] = {}
    if any(p.exists() for p in _report_paths(path)):
        try:
            rendered = render_committed_set(parse_matrix(new_text), root)
        except AcceptanceError as e:
            raise UnconvertibleMatrixError(
                f"{path}: the committed reports could not be rendered ({e}). "
                "Left on version 4, byte-identical."
            ) from e
        reports = {root / rel: body for rel, body in rendered.items()}
    if new_text != text:
        write_text_atomic(path, new_text)
    wrote: list[Path] = []
    for target, body in reports.items():
        if not target.exists() or target.read_text() != body:
            write_text_atomic(target, body)
            wrote.append(target)
    return wrote


MATRIX_STATUS_SPLIT_MIGRATION = SchemaMigration(
    kind="matrix",
    from_version=4,
    to_version=5,
    fn=split_skipped,
    description="matrix: `skipped` splits into unwired / walk-owed / walked (manual by hand)",
    companions=_report_paths,
)

MIGRATIONS.register(MATRIX_STATUS_SPLIT_MIGRATION)
