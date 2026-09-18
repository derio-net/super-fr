"""`fr acceptance ...` CLI — the acceptance-matrix registry and gate.

Spec: docs/superpowers/specs/2026-07-04-acceptance-matrix-design.md §4.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from fr.acceptance.model import AcceptanceError, Matrix, Row, load_matrix
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


def _parse_levels(level: list[str]) -> dict[str, list[str]]:
    """`['unit=own:tests/x.py', …]` → `{'unit': ['own:tests/x.py']}`."""
    levels: dict[str, list[str]] = {}
    for item in level:
        lv, sep, ref = item.partition("=")
        if not sep:
            err_console.print(f"--level must be '<level>=<ref>', got {item!r}")
            raise typer.Exit(2)
        levels.setdefault(lv, []).append(ref)
    return levels


def _validate_refs(row: Row) -> None:
    """Ref grammar checked BEFORE the file is touched — a shell-mangled ref
    (zsh's `$VAR:t` modifier eating "…:tests/…") must not land and surface
    only at the next `check`."""
    from fr.acceptance.model import split_ref

    for ref in row.refs():
        try:
            split_ref(ref)
        except AcceptanceError as e:
            err_console.print(f"[red]error:[/red] {e}")
            raise typer.Exit(2) from e


def _commit_matrix(matrix_path: Path, new_text: str, original: str) -> Matrix:
    """Write, re-validate, and roll back on a shape violation.

    Both mutating verbs land here, so neither can leave an unparseable matrix
    behind — the post-write invariant `add` has always carried, now shared.
    """
    matrix_path.write_text(new_text)
    try:
        return load_matrix(matrix_path)
    except AcceptanceError as e:
        matrix_path.write_text(original)
        err_console.print(f"[red]error:[/red] write produced an invalid matrix, rolled back: {e}")
        raise typer.Exit(2) from e


def _regenerate_reports(matrix: Matrix, root: Path) -> None:
    """Keep the three committed renderings in lockstep with `matrix.yaml`.

    The matrix on disk is already valid — a render failure NEVER rolls the
    change back (that would discard valid work); it warns, and `fr acceptance
    check`'s drift gate is the backstop.
    """
    from fr.acceptance.report import prune_stale_reports, render_committed_set

    try:
        for rel, html in render_committed_set(matrix, root).items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(html)
        prune_stale_reports(root)
    except Exception as e:  # noqa: BLE001 — never fail a valid write on a render hiccup
        err_console.print(
            f"[yellow]warning:[/yellow] matrix updated but the HTML reports were not "
            f"regenerated ({e}); run `fr acceptance report --deterministic` and commit them."
        )


@acceptance_app.command("set-status")
def set_status_cmd(
    row_id: str = typer.Option(..., "--id", help="Existing row id (never created here)."),
    status: str = typer.Option(
        ..., "--status", help="ci | scheduled | skipped | not-implemented | failing."
    ),
    notes: str = typer.Option(
        ...,
        "--notes",
        help="Why the status moved (required — a status that moved for no recorded "
        "reason is the silent change the acceptance-matrix rule forbids).",
    ),
    level: list[str] = typer.Option(
        [],
        "--level",
        help="'<level>=<repo>:<path>[#Lline]' evidence to ADD (repeatable) — the other "
        "half of the documented transition.",
    ),
) -> None:
    """Move an existing row's status, in place, with a reason (spec §3.G.2).

    The matrix is a registry of CURRENT state, not a log: `check` and the three
    committed reports read today's status, so this rewrites the row and
    regenerates the report set. Provenance lives in git history, which for a
    registry is the right place — the asymmetry with `fr journal resolve`
    (append-only) is deliberate.

    Refuses an unknown id rather than creating a row: that is `add`'s job, and
    silently creating one on a typo'd id is how a row gets orphaned.
    """
    from typing import get_args

    from fr.acceptance.edit import merge_levels, replace_row
    from fr.acceptance.model import Status

    root = resolve_repo_root()
    matrix_path = root / MATRIX_REL
    matrix = _load(root)

    valid = list(get_args(Status))
    if status not in valid:
        err_console.print(
            f"[red]error:[/red] unknown status {status!r} (valid: {' | '.join(valid)})"
        )
        raise typer.Exit(2)
    target = next((r for r in matrix.rows if r.id == row_id), None)
    if target is None:
        known = ", ".join(r.id for r in matrix.rows) or "none"
        err_console.print(
            f"[red]error:[/red] no row with id {row_id!r} — nothing changed "
            f"(`fr acceptance add` creates rows; existing ids: {known})"
        )
        raise typer.Exit(2)

    try:
        merged = merge_levels(target.levels, _parse_levels(level))
    except AcceptanceError as e:
        err_console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(2) from e
    try:
        new_row = Row(
            id=target.id,
            capability=target.capability,
            acceptance=target.acceptance,
            origin=target.origin,
            levels=merged,
            status=status,  # type: ignore[arg-type]  # pydantic validates the literal
            notes=notes,
        )
    except Exception as e:  # pydantic ValidationError → operator-readable
        err_console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(2) from e
    _validate_refs(new_row)

    original = matrix_path.read_text()
    try:
        new_text = replace_row(original, row_id, new_row)
    except AcceptanceError as e:
        err_console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(2) from e
    reloaded = _commit_matrix(matrix_path, new_text, original)
    typer.echo(f"{row_id}: {target.status} → {new_row.status}")
    _regenerate_reports(reloaded, root)


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
    """Append a schema-validated row (agents never hand-edit YAML shapes).

    `add` CREATES rows; moving an existing row's status is
    `fr acceptance set-status` (re-adding an id is refused below, by design).
    """
    from fr.acceptance.edit import append_row

    root = resolve_repo_root()
    matrix_path = root / MATRIX_REL
    matrix = _load(root)

    levels = _parse_levels(level)
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
        err_console.print(
            f"[red]error:[/red] duplicate row id: {new_row.id} "
            "(move an existing row with `fr acceptance set-status`)"
        )
        raise typer.Exit(2)
    _validate_refs(new_row)

    # Textual append: a load→dump cycle would destroy the header comments.
    original = matrix_path.read_text()
    reloaded = _commit_matrix(matrix_path, append_row(original, new_row), original)
    typer.echo(f"added row {new_row.id} ({new_row.status})")
    _regenerate_reports(reloaded, root)


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
