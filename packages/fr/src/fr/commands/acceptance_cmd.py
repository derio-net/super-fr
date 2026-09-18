"""`fr acceptance ...` CLI — the acceptance-matrix registry and gate.

Spec: docs/superpowers/specs/2026-07-04-acceptance-matrix-design.md §4.
"""

from __future__ import annotations

import re
from pathlib import Path

import typer
from rich.console import Console

from fr.acceptance.model import AcceptanceError, Matrix, load_matrix
from fr.commands.common import resolve_repo_root

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)

MATRIX_REL = Path("docs/acceptance/matrix.yaml")

acceptance_app = typer.Typer(
    help="Acceptance matrix: business-level acceptance tests × verification levels.",
    no_args_is_help=True,
)


def _load(root: Path) -> Matrix:
    matrix_path = root / MATRIX_REL
    if not matrix_path.exists():
        err_console.print(f"no {MATRIX_REL} (run `fr acceptance init` to scaffold one)")
        raise typer.Exit(1)
    try:
        return load_matrix(matrix_path)
    except AcceptanceError as e:
        err_console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(1) from e


def _replace_row(root: Path, matrix: Matrix, old_id: str, replacement: object) -> Matrix:
    """Patch changed values in one YAML row without rewriting its comments."""
    import yaml

    from fr.acceptance.model import Row

    if not isinstance(replacement, Row):
        raise TypeError("replacement must be an acceptance row")
    matrix_path = root / MATRIX_REL
    original = matrix_path.read_text()
    source = original
    document = yaml.compose(source)
    if not isinstance(document, yaml.MappingNode):
        raise AcceptanceError("matrix top level must be a mapping")
    rows_node = next(
        (
            value
            for key, value in document.value
            if isinstance(key, yaml.ScalarNode) and key.value == "rows"
        ),
        None,
    )
    if not isinstance(rows_node, yaml.SequenceNode):
        raise AcceptanceError("matrix rows must be a sequence")
    target = next(
        (
            node
            for node in rows_node.value
            if isinstance(node, yaml.MappingNode)
            and any(
                isinstance(key, yaml.ScalarNode) and key.value == "id" and value.value == old_id
                for key, value in node.value
            )
        ),
        None,
    )
    if target is None:
        raise AcceptanceError(f"unknown row id: {old_id}")
    old = next(row for row in matrix.rows if row.id == old_id)
    fields = {
        key.value: (key, value)
        for key, value in target.value
        if isinstance(key, yaml.ScalarNode) and isinstance(value, yaml.Node)
    }

    def mutable_field(name: str) -> tuple[yaml.ScalarNode, yaml.Node] | None:
        pair = fields.get(name)
        if pair is None:
            return None
        key, value = pair
        line_end = source.find("\n", key.end_mark.index)
        raw = source[key.end_mark.index : len(source) if line_end == -1 else line_end]
        if re.search(r"(?:^|\s)[&*][A-Za-z0-9_-]+", raw.split("#", 1)[0]):
            raise AcceptanceError(
                f"row {old_id} {name!r} uses a YAML alias or anchor and cannot be updated"
            )
        return key, value

    def reject_alias_or_anchor(key: yaml.ScalarNode, name: str) -> None:
        line_end = source.find("\n", key.end_mark.index)
        raw = source[key.end_mark.index : len(source) if line_end == -1 else line_end]
        if re.search(r"(?:^|\s)[&*][A-Za-z0-9_-]+", raw.split("#", 1)[0]):
            raise AcceptanceError(
                f"row {old_id} {name!r} uses a YAML alias or anchor and cannot be updated"
            )

    edits: list[tuple[int, int, str]] = []
    for name, value in (("status", replacement.status), ("notes", replacement.notes)):
        if getattr(old, name) != value:
            field = mutable_field(name)
            if field is None:
                if name != "notes":
                    raise AcceptanceError(f"row {old_id} has no scalar {name!r}")
                status = mutable_field("status")
                if status is None:
                    raise AcceptanceError(f"row {old_id} has no scalar 'status'")
                status_key, status_node = status
                line_end = source.find("\n", status_node.end_mark.index)
                if line_end == -1:
                    line_end = len(source)
                indent = " " * status_key.start_mark.column
                rendered = yaml.safe_dump(value, default_style='"', allow_unicode=True).strip()
                edits.append((line_end, line_end, f"\n{indent}notes: {rendered}"))
                continue
            _, node = field
            if not isinstance(node, yaml.ScalarNode):
                raise AcceptanceError(f"row {old_id} has no scalar {name!r}")
            rendered = yaml.safe_dump(value, default_style='"', allow_unicode=True).strip()
            edits.append((node.start_mark.index, node.end_mark.index, rendered))

    for level, refs in replacement.levels.items():
        added = [ref for ref in refs if ref not in old.levels[level]]
        if not added:
            continue
        field = mutable_field("levels")
        if field is None:
            status = mutable_field("status")
            if status is None:
                raise AcceptanceError(f"row {old_id} has no scalar 'status'")
            status_key, _ = status
            indent = " " * status_key.start_mark.column
            rendered_refs = [
                yaml.safe_dump(ref, default_style='"', allow_unicode=True).strip() for ref in added
            ]
            refs_text = "".join(f"{indent}    - {ref}\n" for ref in rendered_refs)
            edits.append(
                (
                    status_key.start_mark.index - status_key.start_mark.column,
                    status_key.start_mark.index - status_key.start_mark.column,
                    f"{indent}levels:\n{indent}  {level}:\n{refs_text}",
                )
            )
            continue
        levels_key, levels = field
        if isinstance(levels, yaml.MappingNode) and not levels.value and levels.flow_style:
            indent = " " * levels_key.start_mark.column
            rendered_refs = [
                yaml.safe_dump(ref, default_style='"', allow_unicode=True).strip() for ref in added
            ]
            refs_text = "".join(f"{indent}    - {ref}\n" for ref in rendered_refs)
            edits.append(
                (
                    levels.start_mark.index,
                    levels.end_mark.index,
                    f"\n{indent}  {level}:\n{refs_text}".rstrip("\n"),
                )
            )
            continue
        if not isinstance(levels, yaml.MappingNode):
            raise AcceptanceError("row levels must be a mapping to add evidence")
        level_pair = next(
            (
                (key, value)
                for key, value in levels.value
                if isinstance(key, yaml.ScalarNode) and key.value == level
            ),
            None,
        )
        if level_pair is not None:
            level_key, evidence = level_pair
            reject_alias_or_anchor(level_key, f"levels.{level}")
            if not isinstance(evidence, yaml.SequenceNode):
                raise AcceptanceError(f"row {old_id} levels.{level!r} must be a sequence")
            rendered_refs = [
                yaml.safe_dump(ref, default_style='"', allow_unicode=True).strip() for ref in added
            ]
            if evidence.flow_style:
                refs_text = ", ".join(rendered_refs)
                prefix = ", " if evidence.value else ""
                edits.append(
                    (
                        evidence.end_mark.index - 1,
                        evidence.end_mark.index - 1,
                        f"{prefix}{refs_text}",
                    )
                )
            else:
                last_item = evidence.value[-1]
                line_end = source.find("\n", last_item.end_mark.index)
                if line_end == -1:
                    line_end = len(source)
                indent = " " * (last_item.start_mark.column - 2)
                refs_text = "".join(f"{indent}- {ref}\n" for ref in rendered_refs)
                edits.append((line_end, line_end, f"\n{refs_text}".rstrip("\n")))
            continue
        if levels.flow_style:
            refs_text = ", ".join(
                yaml.safe_dump(ref, default_style='"', allow_unicode=True).strip() for ref in added
            )
            prefix = ", " if levels.value else ""
            edits.append(
                (
                    levels.end_mark.index - 1,
                    levels.end_mark.index - 1,
                    f"{prefix}{level}: [{refs_text}]",
                )
            )
            continue
        last_key, last_value = levels.value[-1]
        last_end = last_value.end_mark.index
        line_end = source.find("\n", last_end)
        if line_end == -1:
            line_end = len(source)
        indent = " " * last_key.start_mark.column
        rendered_refs = [
            yaml.safe_dump(ref, default_style='"', allow_unicode=True).strip() for ref in added
        ]
        refs_text = "".join(f"{indent}  - {ref}\n" for ref in rendered_refs)
        edits.append((line_end, line_end, f"\n{indent}{level}:\n{refs_text}".rstrip("\n")))

    for start, end, text in sorted(edits, reverse=True):
        source = source[:start] + text + source[end:]
    matrix_path.write_text(source)
    try:
        reloaded = load_matrix(matrix_path)
        actual = next((row for row in reloaded.rows if row.id == old_id), None)
        if actual != replacement:
            raise AcceptanceError(f"update did not preserve intended row {old_id}, rolled back")
        return reloaded
    except AcceptanceError as e:
        matrix_path.write_text(original)
        raise AcceptanceError(f"update produced an invalid matrix, rolled back: {e}") from e


def _regenerate_reports(matrix: Matrix, root: Path, action: str) -> None:
    """Warn on rendering failures; a valid matrix mutation is never rolled back."""
    from fr.acceptance.report import prune_stale_reports, render_committed_set

    try:
        for rel, html in render_committed_set(matrix, root).items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(html)
        prune_stale_reports(root)
    except Exception as e:  # noqa: BLE001 — report drift is recoverable
        err_console.print(
            f"[yellow]warning:[/yellow] row {action} but reports were not regenerated ({e}); "
            "run `fr acceptance report --deterministic` and commit them."
        )


def _added_since(root: Path, ref: str, matrix: Matrix) -> list[str]:
    """Row ids present now but absent from `<ref>`'s matrix (spec decision 6:
    mid-flight additions are defended at PR time, and this diff feeds the
    PR-body section). A base without a matrix means every row is new."""
    import subprocess

    import yaml

    out = subprocess.run(
        ["git", "show", f"{ref}:{MATRIX_REL}"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        stderr = out.stderr.strip()
        if "does not exist" in stderr or "exists on disk, but not in" in stderr:
            old_ids: set[str] = set()
        else:
            raise AcceptanceError(f"--added-since {ref}: {stderr}")
    else:
        try:
            old = yaml.safe_load(out.stdout) or {}
        except yaml.YAMLError as e:
            raise AcceptanceError(f"--added-since {ref}: base matrix unparseable: {e}") from e
        old_ids = {str(r["id"]) for r in old.get("rows") or [] if isinstance(r, dict) and "id" in r}
    return [r.id for r in matrix.rows if r.id not in old_ids]


@acceptance_app.command("check")
def check_cmd(
    sibling_root: str = typer.Option(
        "..",
        "--sibling-root",
        help="Where sister repos live, relative to the repo root ('..' = repos as siblings).",
    ),
    added_since: str | None = typer.Option(
        None,
        "--added-since",
        help="Also list rows added since this git ref (feeds the PR-body section).",
    ),
) -> None:
    """The gate: refs resolve, staleness, exit 2 on failing rows."""
    from fr.acceptance.check import check

    root = resolve_repo_root()
    matrix = _load(root)
    try:
        result = check(matrix, root, sibling_root)
        added = _added_since(root, added_since, matrix) if added_since else []
    except AcceptanceError as e:
        err_console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(1) from e
    if added_since is not None:
        typer.echo(f"added since {added_since}:")
        by_id = {r.id: r for r in matrix.rows}
        for rid in added:
            typer.echo(f"  {rid} — {by_id[rid].acceptance}")
        if not added:
            typer.echo("  (none)")

    # Plain echo, never rich: `::warning::` annotations are parsed by GitHub
    # line-by-line — rich's soft-wrap would split them and they'd vanish.
    for r in result.warning_rows:
        typer.echo(
            f"::warning title=acceptance-matrix::{r.id} is {r.status}: "
            f"{r.acceptance} — backfill owed ({r.notes[:120]})"
        )
    for w in result.warnings:
        typer.echo(f"::warning title=acceptance-matrix::{w}")
    for e_line in result.errors:
        typer.echo(f"ERROR: {e_line}", err=True)
    if result.failing_ids:
        typer.echo(f"ERROR: failing acceptance rows: {result.failing_ids}", err=True)
    if result.exit_code == 0:
        typer.echo(result.summary)
    raise typer.Exit(result.exit_code)


@acceptance_app.command("report")
def report_cmd(
    link_mode: str = typer.Option(
        "local", "--link-mode", help="github (CI) | local (sibling checkouts)."
    ),
    ref: str = typer.Option("main", "--ref", help="Own-repo ref for github links."),
    sibling_root: str = typer.Option(
        "..", "--sibling-root", help="Where sister repos live, relative to the repo root."
    ),
    out: Path | None = typer.Option(
        None,
        "--out",
        help="Single explicit output/check target (repo-relative). Omit to operate on the "
        "whole committed set (report_local.html + report_linked.html + report_linked.md).",
    ),
    deterministic: bool = typer.Option(
        False,
        "--deterministic",
        help="Render as a pure function of matrix.yaml (matrix-derived stamp, no git "
        "date/hash, no filesystem twin-probing) — the committed-report / drift-check path.",
    ),
    check: bool = typer.Option(
        False,
        "--check",
        help="Verify the on-disk report matches a fresh deterministic render; write "
        "nothing, exit non-zero on drift. Implies --deterministic.",
    ),
) -> None:
    """Render the report set (or, with --check, verify it is in sync).

    Default subject is the committed SET — report_local.html (local HTML),
    report_linked.html (github HTML) and report_linked.md (github Markdown).
    With no flags, renders the ad-hoc, uncommitted `report.html` (git-stamped,
    honoring --link-mode). `--out` narrows to a single explicit file."""
    from fr.acceptance.report import (
        prune_stale_reports,
        render_committed_set,
        render_deterministic,
        render_report,
    )

    if link_mode not in ("github", "local"):
        err_console.print(f"--link-mode must be github|local, got {link_mode!r}")
        raise typer.Exit(2)
    root = resolve_repo_root()
    matrix = _load(root)
    # No `--out` → operate on the whole committed set; an explicit `--out`
    # (even one equal to the default path) narrows to that single file.

    if check:
        try:
            if out is not None:
                expected = {
                    out.as_posix(): render_deterministic(
                        matrix, root, (root / out).resolve().parent, sibling_root, link_mode
                    )
                }
            else:
                expected = render_committed_set(matrix, root)
        except AcceptanceError as e:
            err_console.print(f"[red]error:[/red] {e}")
            raise typer.Exit(1) from e
        stale = []
        for rel, want in expected.items():
            path = root / rel
            got = path.read_text() if path.exists() else None
            if got != want:
                stale.append(rel)
        if not stale:
            typer.echo(f"{', '.join(expected)} in sync with matrix.yaml")
            return
        typer.echo(
            f"ERROR: stale (drifted from docs/acceptance/matrix.yaml): {', '.join(stale)} — "
            "run `fr acceptance report --deterministic` and commit the result.",
            err=True,
        )
        raise typer.Exit(3)

    try:
        if out is not None:
            out_path = (root / out).resolve()
            html = (
                render_deterministic(matrix, root, out_path.parent, sibling_root, link_mode)
                if deterministic
                else render_report(matrix, root, out_path.parent, sibling_root, link_mode, ref)
            )
            files = {str(out_path): html}
        elif deterministic:
            files = {
                str(root / rel): html for rel, html in render_committed_set(matrix, root).items()
            }
            prune_stale_reports(root)
        else:
            # Ad-hoc default render → a single git-stamped report.html honoring
            # --link-mode (back-compat: the CI artifact step still uses this).
            out_path = (root / "docs" / "acceptance" / "report.html").resolve()
            files = {
                str(out_path): render_report(
                    matrix, root, out_path.parent, sibling_root, link_mode, ref
                )
            }
    except AcceptanceError as e:
        err_console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(1) from e
    for path_str, html in files.items():
        p = Path(path_str)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(html)
    typer.echo(f"wrote {', '.join(files)}")


@acceptance_app.command("status")
def status_cmd(
    brief: bool = typer.Option(
        False, "--brief", help="Counts + the 3 oldest open rows (session-start injection)."
    ),
) -> None:
    """Terminal nag: counts by status + open skipped/not-implemented rows.

    Read-only and exit-0 always — allowlist-safe like `fr status`.
    """
    from collections import Counter

    from fr.acceptance.check import open_rows

    root = resolve_repo_root()
    matrix = _load(root)
    counts = Counter(r.status for r in matrix.rows)
    summary = ", ".join(f"{s}: {n}" for s, n in sorted(counts.items())) or "empty matrix"
    typer.echo(f"acceptance: {summary}")
    opens = open_rows(matrix)
    if not opens:
        typer.echo("no acceptance debt.")
        return
    shown = opens[:3] if brief else opens
    for r in shown:  # matrix order = append order = oldest first
        typer.echo(f"  {r.id} [{r.status}] {r.acceptance} — {r.notes}")
    if brief and len(opens) > len(shown):
        typer.echo(f"  … +{len(opens) - len(shown)} more (fr acceptance status)")


@acceptance_app.command("summary")
def summary_cmd() -> None:
    """GitHub Actions-friendly Markdown summary: compact counts + collapsible debt."""
    from collections import Counter
    from html import escape

    from fr.acceptance.check import open_rows

    root = resolve_repo_root()
    matrix = _load(root)
    counts = Counter(r.status for r in matrix.rows)
    lines = [
        "## Acceptance matrix",
        "",
        "| status | count |",
        "|---|---:|",
        f"| ci | {counts.get('ci', 0)} |",
        f"| scheduled | {counts.get('scheduled', 0)} |",
        f"| skipped | {counts.get('skipped', 0)} |",
        f"| not-implemented | {counts.get('not-implemented', 0)} |",
        f"| failing | {counts.get('failing', 0)} |",
        "",
    ]
    opens = open_rows(matrix)
    if not opens:
        lines.append("No open acceptance debt.")
    else:
        lines += [f"### Open acceptance debt ({len(opens)})", ""]
        for r in opens:
            lines += [
                f"<details><summary><code>{escape(r.id)}</code> [{escape(r.status)}]</summary>",
                "",
                escape(r.acceptance),
                "",
                f"**Notes:** {escape(r.notes)}",
                "",
                "</details>",
                "",
            ]
    lines += ["", "Full HTML report remains attached as the `acceptance-report` artifact."]
    typer.echo("\n".join(lines))


@acceptance_app.command("add")
def add_cmd(
    row_id: str = typer.Option(..., "--id", help="Stable kebab-case row id."),
    capability: str = typer.Option(..., "--capability", help="Grouping heading."),
    acceptance: str = typer.Option(..., "--acceptance", help="The business-level statement."),
    origin: list[str] = typer.Option(
        [], "--origin", help="'<repo>:<path>[#anchor]' ref (repeatable)."
    ),
    level: list[str] = typer.Option(
        [], "--level", help="'<level>=<repo>:<path>[#Lline]' test ref (repeatable)."
    ),
    status: str = typer.Option(
        ..., "--status", help="ci | scheduled | skipped | not-implemented | failing."
    ),
    notes: str = typer.Option("", "--notes", help="Evidence detail / backfill owed."),
) -> None:
    """Append a schema-validated row (agents never hand-edit YAML shapes)."""
    import yaml

    from fr.acceptance.model import Row

    root = resolve_repo_root()
    matrix_path = root / MATRIX_REL
    matrix = _load(root)

    levels: dict[str, list[str]] = {}
    for item in level:
        lv, sep, ref = item.partition("=")
        if not sep:
            err_console.print(f"--level must be '<level>=<ref>', got {item!r}")
            raise typer.Exit(2)
        levels.setdefault(lv, []).append(ref)
    try:
        new_row = Row(
            id=row_id,
            capability=capability,
            acceptance=acceptance,
            origin=tuple(origin),
            levels={k: tuple(v) for k, v in levels.items()},
            status=status,  # type: ignore[arg-type]  # pydantic validates the literal
            notes=notes,
        )
    except Exception as e:  # pydantic ValidationError → operator-readable
        err_console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(2) from e
    if any(r.id == new_row.id for r in matrix.rows):
        err_console.print(f"[red]error:[/red] duplicate row id: {new_row.id}")
        raise typer.Exit(2)
    # Ref grammar validated NOW, not at the next check — a shell-mangled ref
    # (e.g. zsh's `$VAR:t` modifier eating "…:tests/…") must not land.
    from fr.acceptance.model import split_ref

    for ref in new_row.refs():
        try:
            split_ref(ref)
        except AcceptanceError as e:
            err_console.print(f"[red]error:[/red] {e}")
            raise typer.Exit(2) from e

    # Textual append: a load→dump cycle would destroy the header comments.
    block_data = {
        "id": new_row.id,
        "capability": new_row.capability,
        "acceptance": new_row.acceptance,
        "origin": list(new_row.origin),
        "levels": {lv: list(refs) for lv, refs in new_row.levels.items() if refs},
        "status": new_row.status,
        "notes": new_row.notes,
    }
    block = yaml.dump([block_data], default_flow_style=False, sort_keys=False, allow_unicode=True)
    original = matrix_path.read_text()
    text = original if original.endswith("\n") else original + "\n"
    indented = "".join(
        ("  " + line if line.strip() else line) + "\n" for line in block.rstrip("\n").split("\n")
    )
    matrix_path.write_text(text + indented)
    try:
        reloaded = load_matrix(matrix_path)  # post-write invariant
    except AcceptanceError as e:
        matrix_path.write_text(original)
        err_console.print(f"[red]error:[/red] append produced an invalid matrix, rolled back: {e}")
        raise typer.Exit(2) from e
    typer.echo(f"added row {new_row.id} ({new_row.status})")

    _regenerate_reports(reloaded, root, "added")


@acceptance_app.command("set-status")
def set_status_cmd(
    row_id: str = typer.Argument(..., help="ID of the existing row to update."),
    status: str = typer.Option(
        ..., "--status", help="ci | scheduled | skipped | not-implemented | failing."
    ),
    note: str | None = typer.Option(None, "--note", help="Evidence note to append."),
) -> None:
    """Set an existing row's status, preserving its other evidence."""
    from fr.acceptance.model import Row

    root = resolve_repo_root()
    matrix = _load(root)
    old = next((row for row in matrix.rows if row.id == row_id), None)
    if old is None:
        err_console.print(f"[red]error:[/red] unknown row id: {row_id}")
        raise typer.Exit(2)
    try:
        replacement = Row(
            id=old.id,
            capability=old.capability,
            acceptance=old.acceptance,
            origin=old.origin,
            levels=old.levels,
            status=status,  # type: ignore[arg-type]  # pydantic validates the literal
            notes=f"{old.notes}\n{note}" if old.notes and note else (note or old.notes),
        )
        reloaded = _replace_row(root, matrix, row_id, replacement)
    except Exception as e:
        err_console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(2) from e
    typer.echo(f"set row {row_id} status to {replacement.status}")
    _regenerate_reports(reloaded, root, "updated")


@acceptance_app.command("add-level")
def add_level_cmd(
    row_id: str = typer.Argument(..., help="ID of the existing row to update."),
    level: str = typer.Option(..., "--level", help="'<level>=<repo>:<path>[#Lline]' test ref."),
) -> None:
    """Add one verification reference to an existing row, idempotently."""
    from fr.acceptance.model import LEVELS, Row, split_ref

    root = resolve_repo_root()
    matrix = _load(root)
    old = next((row for row in matrix.rows if row.id == row_id), None)
    if old is None:
        err_console.print(f"[red]error:[/red] unknown row id: {row_id}")
        raise typer.Exit(2)
    level_name, separator, ref = level.partition("=")
    if not separator:
        err_console.print(f"[red]error:[/red] --level must be '<level>=<ref>', got {level!r}")
        raise typer.Exit(2)
    try:
        if level_name not in LEVELS:
            raise AcceptanceError(f"unknown level key {level_name!r} (allowed: {list(LEVELS)})")
        split_ref(ref)
        levels = dict(old.levels)
        if ref in levels[level_name]:
            typer.echo(f"{level_name} evidence already present on row {row_id}")
            return
        levels[level_name] = (*levels[level_name], ref)
        replacement = Row(
            id=old.id,
            capability=old.capability,
            acceptance=old.acceptance,
            origin=old.origin,
            levels=levels,
            status=old.status,
            notes=old.notes,
        )
        reloaded = _replace_row(root, matrix, row_id, replacement)
    except Exception as e:
        err_console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(2) from e
    typer.echo(f"added {level_name} evidence to row {row_id}")
    _regenerate_reports(reloaded, root, "updated")


@acceptance_app.command("init")
def init_cmd() -> None:
    """Scaffold matrix + CI workflow + backfill rule + gitignore (idempotent)."""
    from fr._hosts import detect_backend
    from fr.acceptance.check import resolve_identity
    from fr.acceptance.scaffold import init

    root = resolve_repo_root()
    try:
        org, repo = resolve_identity(Matrix(), root)
    except AcceptanceError as e:
        err_console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(1) from e
    backend = detect_backend(root)
    outcome = init(root, org, repo, backend=backend)
    for rel in outcome.created:
        typer.echo(f"created {rel}")
    for rel in outcome.skipped:
        typer.echo(f"exists  {rel} (left untouched)")


BACKFILL_PROTOCOL = """\
## Backfill work-protocol (agent-driven — see the fr-acceptance skill)

1. Inventory: the uncited Test Plan specs and unlinked plans above, plus any
   design/study docs with acceptance-like tables, and the test tree(s).
2. DRAFT rows — one row per business acceptance, not per test — with real
   refs and HONEST statuses: per-PR-automated evidence ⇒ `ci`; anything
   proven only by hand or once-live ⇒ `skipped`; absent ⇒ `not-implemented`.
   The drift channel is precisely the hand-tracked claims — when in doubt
   between `ci` and `skipped`, choose skipped.
3. Add rows via `fr acceptance add` (never hand-edit YAML shapes), run
   `fr acceptance check`, fix, and open a review PR — the operator audits
   statuses; do not inflate coverage.
"""


@acceptance_app.command("backfill")
def backfill_cmd() -> None:
    """Emit the agent backfill protocol + deterministic inventory (markdown)."""
    import yaml

    from fr.acceptance.check import SPEC_DIRS, TEST_PLAN_MARKER
    from fr.acceptance.model import archive_twin, split_ref

    root = resolve_repo_root()
    matrix = _load(root)

    referenced: set[str] = set()
    for r in matrix.rows:
        for ref in r.origin:
            try:
                _, path, _ = split_ref(ref)
            except AcceptanceError:
                continue
            referenced.add(path)
            twin = archive_twin(path)
            if twin:
                referenced.add(twin)
    uncited = [
        str(spec.relative_to(root))
        for spec_dir in SPEC_DIRS
        for spec in sorted((root / spec_dir).glob("*.md"))
        if TEST_PLAN_MARKER in spec.read_text() and str(spec.relative_to(root)) not in referenced
    ]

    unlinked_plans: list[str] = []
    plans_dir = root / "docs" / "superpowers" / "plans"
    if plans_dir.is_dir():
        for plan_dir in sorted(p for p in plans_dir.iterdir() if p.is_dir()):
            linked = False
            for phase_file in sorted(plan_dir.glob("[0-9][0-9].yaml")):
                try:
                    doc = yaml.safe_load(phase_file.read_text()) or {}
                except yaml.YAMLError:
                    continue  # unparseable plans are skipped gracefully
                if (doc.get("phase") or {}).get("acceptance"):
                    linked = True
                    break
            if not linked:
                unlinked_plans.append(plan_dir.name)

    lines = ["# Acceptance backfill — inventory + protocol", ""]
    lines.append("## Specs with a Test Plan not yet cited by any row")
    lines += [f"- {p}" for p in uncited] or ["- (none — every Test Plan spec is cited)"]
    lines += ["", "## Live plans with no `acceptance:` links"]
    lines += [f"- {p}" for p in unlinked_plans] or ["- (none)"]
    lines += ["", "## Test-tree hints"]
    tests_dir = root / "tests"
    if tests_dir.is_dir():
        lines += [f"- tests/{d.name}/" for d in sorted(tests_dir.iterdir()) if d.is_dir()] or [
            "- tests/ (flat)"
        ]
    else:
        lines.append("- (no tests/ directory found)")
    lines += ["", BACKFILL_PROTOCOL]
    typer.echo("\n".join(lines))


DIGEST_MARKER = "<!-- fr-acceptance-digest -->"


@acceptance_app.command("digest")
def digest_cmd() -> None:
    """Markdown for the upserted "Acceptance debt" issue (idempotence marker
    included; zero debt prints a closable body)."""
    from fr.acceptance.check import open_rows

    root = resolve_repo_root()
    matrix = _load(root)
    opens = open_rows(matrix)
    lines = ["## Acceptance debt", ""]
    if not opens:
        lines.append("No open acceptance debt.")
    else:
        lines += [
            "| id | status | acceptance | notes |",
            "|---|---|---|---|",
            *(
                f"| {r.id} | {r.status} | {r.acceptance} | {r.notes} |".replace("\n", " ")
                for r in opens
            ),
        ]
    lines += ["", DIGEST_MARKER, "", "_generated by `fr acceptance digest`_"]
    typer.echo("\n".join(lines))
