"""`fr acceptance ...` CLI — the acceptance-matrix registry and gate.

Spec: docs/superpowers/specs/2026-07-04-acceptance-matrix-design.md §4.
"""

from __future__ import annotations

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
    out: Path = typer.Option(
        Path("docs/acceptance/report.html"), "--out", help="Output path (repo-relative)."
    ),
) -> None:
    """Render the HTML report."""
    import subprocess

    from fr.acceptance.check import resolve_identity
    from fr.acceptance.report import LinkBuilder, render

    if link_mode not in ("github", "local"):
        err_console.print(f"--link-mode must be github|local, got {link_mode!r}")
        raise typer.Exit(2)
    root = resolve_repo_root()
    matrix = _load(root)
    try:
        org, own_repo = resolve_identity(matrix, root)
    except AcceptanceError as e:
        err_console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(1) from e
    out_path = (root / out).resolve()
    links = LinkBuilder(
        mode=link_mode,
        ref=ref,
        root=root,
        out_dir=out_path.parent,
        sibling_root=sibling_root,
        org=org,
        own_repo=own_repo,
    )
    ts = subprocess.run(
        ["git", "log", "-1", "--format=%cs %h"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    stamp = f"matrix @ {ts} · links: {link_mode}" + (
        f" (ref {ref})" if link_mode == "github" else ""
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(matrix, links, stamp))
    typer.echo(f"wrote {out_path}")


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
        load_matrix(matrix_path)  # post-write invariant
    except AcceptanceError as e:
        matrix_path.write_text(original)
        err_console.print(f"[red]error:[/red] append produced an invalid matrix, rolled back: {e}")
        raise typer.Exit(2) from e
    typer.echo(f"added row {new_row.id} ({new_row.status})")


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
