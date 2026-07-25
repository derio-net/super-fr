"""HTML acceptance report — ported from cnc-fr's build_report.py.

Every YAML-sourced string passes through esc() before landing in HTML
(spec trap 5); summary tiles are computed from the same rows as the tables
so the two cannot disagree.
"""

from __future__ import annotations

import html
import os
from pathlib import Path

from fr.acceptance.model import LEVELS, Matrix, Row, archive_twin, split_ref

STATUS_LABEL = {
    "ci": ("CI · per-PR", "ci"),
    "scheduled": ("CI · scheduled", "sched"),
    "skipped": ("skipped", "live"),
    "not-implemented": ("not implemented", "none"),
    "failing": ("FAILING", "fail"),
}
LEVEL_LABEL = {"unit": "UNIT", "api": "API", "int": "INT", "ui": "UI"}


class LinkBuilder:
    """Resolves `<repo>:<path>[#frag]` refs to URLs in two modes.

    github: own repo pinned to `ref`, sibling repos pinned to main.
    local:  paths relative to the emitted HTML, siblings via sibling_root
            (default `..` — repos as siblings; trap 2).

    `probe` (default True) follows archived-spec twins by touching the
    filesystem. A committed, drift-checked report must be a pure function of
    matrix.yaml, so the deterministic path passes probe=False: no filesystem
    lookup, the raw ref path is emitted (see report_cmd's --deterministic).
    """

    def __init__(
        self,
        *,
        mode: str,
        ref: str,
        root: Path,
        out_dir: Path,
        sibling_root: str,
        org: str,
        own_repo: str,
        probe: bool = True,
    ) -> None:
        self.mode, self.ref, self.root, self.out_dir = mode, ref, root, out_dir
        self.sibling = (root / sibling_root).resolve()
        self.org, self.own_repo = org, own_repo
        self.probe = probe

    def _base(self, repo: str) -> Path:
        return self.root if repo == self.own_repo else self.sibling / repo

    def _actual_path(self, repo: str, path: str) -> str:
        """Follow an archived spec to its twin when the checkout can tell
        (trap 1). Sibling probing requires a real checkout (trap 4); the own
        repo root is authoritative. Skipped entirely when probe=False so the
        render stays a pure function of matrix.yaml (deterministic path)."""
        if not self.probe:
            return path
        base = self._base(repo)
        checkout = repo == self.own_repo or (base / ".git").exists()
        if checkout and not (base / path).exists():
            twin = archive_twin(path)
            if twin and (base / twin).exists():
                return twin
        return path

    def url(self, ref: str) -> str:
        repo, path, frag = split_ref(ref)
        path = self._actual_path(repo, path)
        if self.mode == "github":
            # v1 shortcut: sibling repos are pinned to literal `main` (a
            # master-defaulted sibling gets stale links). Recorded in the
            # plan's _prose.md; a per-repo override can come with demand.
            branch = self.ref if repo == self.own_repo else "main"
            anchor = f"#{frag}" if frag else ""
            return f"https://github.com/{self.org}/{repo}/blob/{branch}/{path}{anchor}"
        base = self._base(repo)
        try:
            return os.path.relpath(base / path, self.out_dir)
        except ValueError:
            return str(base / path)


CSS = """
  :root {
    --bg:#0e1116; --panel:#151a21; --panel-2:#1a2029; --line:#262d38;
    --ink:#dfe5ec; --ink-2:#9aa5b1; --ink-3:#67717e;
    --accent:#56b6c2; --ok:#7cc08a; --ok-bg:#17351f; --warn:#d8a656; --warn-bg:#3a2c12;
    --bad:#d4767c; --bad-bg:#3a1a1e; --sched:#6ea8d8; --sched-bg:#16283a;
    --chip-on:#223243; --chip-on-ink:#a8d4dd; --chip-off:#1a1f27; --chip-off-ink:#4a5460;
    --mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,monospace;
    --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  }
  @media (prefers-color-scheme: light) { :root {
    --bg:#f4f5f4; --panel:#fff; --panel-2:#eef0f1; --line:#d8dcdf;
    --ink:#22282e; --ink-2:#59636d; --ink-3:#8b949d;
    --accent:#1e7f8c; --ok:#2c7a3f; --ok-bg:#e2f2e5; --warn:#92600f; --warn-bg:#f7ecd6;
    --bad:#b03540; --bad-bg:#f8e2e4; --sched:#2a6396; --sched-bg:#dfeaf5;
    --chip-on:#d8ecef; --chip-on-ink:#175560; --chip-off:#eceeef; --chip-off-ink:#a9b1b8;
  } }
  body{background:var(--bg);color:var(--ink);font-family:var(--sans);margin:0;line-height:1.5;font-size:15px}
  .wrap{max-width:1080px;margin:0 auto;padding:40px 24px 80px}
  header{border-bottom:1px solid var(--line);padding-bottom:20px;margin-bottom:28px}
  .kicker{font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);margin:0 0 10px}
  h1{font-size:26px;margin:0 0 8px;letter-spacing:-.01em;text-wrap:balance}
  .meta{font-family:var(--mono);font-size:12px;color:var(--ink-3)} .meta b{color:var(--ink-2);font-weight:600}
  h2{font-size:15px;margin:40px 0 10px} h2 .n{font-family:var(--mono);color:var(--accent);font-size:12px;margin-right:8px}
  .tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:24px 0 8px}
  .tile{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:12px 14px}
  .tile .v{font-family:var(--mono);font-size:24px;font-weight:700;font-variant-numeric:tabular-nums}
  .tile .l{font-size:11px;color:var(--ink-2);margin-top:2px;letter-spacing:.04em;text-transform:uppercase}
  .tile.ok .v{color:var(--ok)} .tile.sched .v{color:var(--sched)} .tile.warn .v{color:var(--warn)} .tile.bad .v{color:var(--bad)}
  .tblwrap{overflow-x:auto;border:1px solid var(--line);border-radius:6px;background:var(--panel)}
  table{border-collapse:collapse;width:100%;min-width:880px;font-size:13px}
  th{font-family:var(--mono);font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--ink-3);text-align:left;padding:9px 12px;border-bottom:1px solid var(--line);background:var(--panel-2)}
  td{padding:8px 12px;border-bottom:1px solid var(--line);vertical-align:top}
  tr:last-child td{border-bottom:none} td.acc{min-width:240px;max-width:340px}
  td.note{color:var(--ink-2);font-size:12.5px;min-width:220px}
  .refs{display:block;font-family:var(--mono);font-size:11px;margin-top:4px}
  .refs a{margin-right:8px}
  .lv{display:inline-flex;gap:4px}
  .lv a,.lv span{font-family:var(--mono);font-size:10px;padding:2px 6px;border-radius:3px;letter-spacing:.04em;text-decoration:none}
  .lv .on{background:var(--chip-on);color:var(--chip-on-ink)} .lv a.on:hover{outline:1px solid var(--accent)}
  .lv .off{background:var(--chip-off);color:var(--chip-off-ink);text-decoration:line-through}
  .st{font-family:var(--mono);font-size:10.5px;padding:2.5px 8px;border-radius:10px;white-space:nowrap}
  .st.ci{background:var(--ok-bg);color:var(--ok)} .st.sched{background:var(--sched-bg);color:var(--sched)}
  .st.live{background:var(--warn-bg);color:var(--warn)} .st.none{background:var(--bad-bg);color:var(--bad)}
  .st.fail{background:var(--bad);color:var(--bg);font-weight:700}
  .panel{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--warn);border-radius:6px;padding:16px 18px;margin:14px 0;font-size:13.5px}
  .panel.red{border-left-color:var(--bad)} .panel h3{margin:0 0 8px;font-size:13px}
  .panel ul{margin:6px 0 0;padding-left:18px} .panel li{margin:4px 0}
  a{color:var(--accent);text-decoration:none} a:hover{text-decoration:underline}
  code{font-family:var(--mono);font-size:12px;background:var(--panel-2);padding:1px 5px;border-radius:3px}
  footer{margin-top:48px;border-top:1px solid var(--line);padding-top:14px;font-size:12px;color:var(--ink-3)}
"""


def esc(s: str) -> str:
    return html.escape(str(s or ""), quote=True)


def render(matrix: Matrix, links: LinkBuilder, stamp: str) -> str:
    from collections import Counter

    rows = matrix.rows
    counts = Counter(r.status for r in rows)
    caps: dict[str, list[Row]] = {}
    for r in rows:
        caps.setdefault(r.capability, []).append(r)

    def ref_link(ref: str) -> str:
        repo, path, _ = split_ref(ref)
        return f'<a href="{esc(links.url(ref))}">{esc(repo)}:{esc(Path(path).name)}</a>'

    out = [
        f"<title>Acceptance coverage — {esc(links.own_repo)}</title>\n<style>{CSS}</style>",
        '<div class="wrap"><header>',
        f'<p class="kicker">{esc(links.own_repo)} · quality engineering · generated</p>',
        "<h1>Business-level acceptance tests × verification level</h1>",
        f'<p class="meta">{esc(stamp)} · generated by <code>fr acceptance report</code> '
        f"from <code>docs/acceptance/matrix.yaml</code> ({len(rows)} rows)</p></header>",
    ]

    tiles = [
        ("ok", counts.get("ci", 0), "automated per-PR"),
        ("sched", counts.get("scheduled", 0), "automated scheduled"),
        ("warn", counts.get("skipped", 0), "skipped — backfill owed"),
        ("bad", counts.get("not-implemented", 0), "not implemented"),
        ("bad", counts.get("failing", 0), "failing"),
    ]
    out.append(
        '<div class="tiles">'
        + "".join(
            f'<div class="tile {c}"><div class="v">{n}</div><div class="l">{esc(label)}</div></div>'
            for c, n, label in tiles
        )
        + "</div>"
    )

    for i, (cap, cap_rows) in enumerate(caps.items(), 1):
        out.append(f'<h2><span class="n">{i:02d}</span>{esc(cap)}</h2>')
        out.append(
            '<div class="tblwrap"><table>'
            "<tr><th>Acceptance</th><th>Origin</th><th>Levels</th>"
            "<th>Automation</th><th>Evidence / notes</th></tr>"
        )
        for r in cap_rows:
            label, cls = STATUS_LABEL[r.status]
            chips = []
            for lv in LEVELS:
                refs = r.levels[lv]
                if refs:
                    chips.append(
                        f'<a class="on" href="{esc(links.url(refs[0]))}" '
                        f'title="{esc(refs[0])}">{LEVEL_LABEL[lv]}</a>'
                    )
                else:
                    chips.append(f'<span class="off">{LEVEL_LABEL[lv]}</span>')
            origins = " ".join(ref_link(o) for o in r.origin) or "—"
            evidence = " ".join(ref_link(x) for lv in LEVELS for x in r.levels[lv])
            note = esc(r.notes)
            if evidence:
                note += f'<span class="refs">{evidence}</span>'
            out.append(
                f'<tr><td class="acc">{esc(r.acceptance)}</td>'
                f'<td class="note">{origins}</td>'
                f'<td><span class="lv">{"".join(chips)}</span></td>'
                f'<td><span class="st {cls}">{esc(label)}</span></td>'
                f'<td class="note">{note}</td></tr>'
            )
        out.append("</table></div>")

    def panel(title: str, status: str, cls: str = "") -> None:
        items = [r for r in rows if r.status == status]
        if not items:
            return
        lis = "".join(
            f"<li><b>{esc(r.id)}</b> — {esc(r.acceptance)}. <i>{esc(r.notes)}</i></li>"
            for r in items
        )
        out.append(f'<div class="panel {cls}"><h3>{esc(title)}</h3><ul>{lis}</ul></div>')

    out.append('<h2><span class="n">§</span>The sharp line — where drift can hide</h2>')
    panel("Failing — the workflow is red until these are fixed or re-classified", "failing", "red")
    panel("Skipped — verification exists but does not run in CI (backfill owed)", "skipped")
    panel("Not implemented — no test or surface yet", "not-implemented", "red")
    out.append(
        "<footer>Statuses: ci / scheduled cannot drift silently; skipped and "
        "not-implemented are CI warnings gated by the backfill rule; "
        "failing fails CI.</footer></div>"
    )
    return "\n".join(out)


def md_cell(s: str) -> str:
    """Make a string safe inside a GitHub-flavored-markdown table cell: escape
    pipes and flatten newlines so a stray `|` or line break can't break the
    table grid."""
    return str(s or "").replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").strip()


def render_markdown(matrix: Matrix, links: LinkBuilder, stamp: str) -> str:
    """The matrix as GitHub-flavored Markdown — same information as `render()`
    but a format github.com renders inline (committed `.html` is shown as
    source). Links use `[repo:name](url)` via the same LinkBuilder."""
    from collections import Counter

    rows = matrix.rows
    counts = Counter(r.status for r in rows)
    caps: dict[str, list[Row]] = {}
    for r in rows:
        caps.setdefault(r.capability, []).append(r)

    def ref_link(ref: str) -> str:
        repo, path, _ = split_ref(ref)
        # Angle-bracket the destination (CommonMark `<...>` form) so a URL with
        # a space or unbalanced paren can't break the link.
        return f"[{md_cell(repo)}:{md_cell(Path(path).name)}](<{links.url(ref)}>)"

    out = [
        f"# Acceptance coverage — {md_cell(links.own_repo)}",
        "",
        "Business-level acceptance tests × verification level.",
        "",
        f"_{md_cell(stamp)} · generated by `fr acceptance report` from "
        f"`docs/acceptance/matrix.yaml` ({len(rows)} rows)._",
        "",
        "| status | count |",
        "| --- | ---: |",
    ]
    for count, label in (
        (counts.get("ci", 0), "CI · per-PR"),
        (counts.get("scheduled", 0), "CI · scheduled"),
        (counts.get("skipped", 0), "skipped — backfill owed"),
        (counts.get("not-implemented", 0), "not implemented"),
        (counts.get("failing", 0), "FAILING"),
    ):
        out.append(f"| {label} | {count} |")
    out.append("")

    for i, (cap, cap_rows) in enumerate(caps.items(), 1):
        out.append(f"## {i:02d} · {md_cell(cap)}")
        out.append("")
        out.append("| Acceptance | Origin | Levels | Automation | Evidence / notes |")
        out.append("| --- | --- | --- | --- | --- |")
        for r in cap_rows:
            label, _ = STATUS_LABEL[r.status]
            chips = []
            for lv in LEVELS:
                refs = r.levels[lv]
                if refs:
                    chips.append(f"[{LEVEL_LABEL[lv]}](<{links.url(refs[0])}>)")
                else:
                    chips.append(f"~~{LEVEL_LABEL[lv]}~~")
            origins = " ".join(ref_link(o) for o in r.origin) or "—"
            evidence = " ".join(ref_link(x) for lv in LEVELS for x in r.levels[lv])
            note = md_cell(r.notes)
            if evidence:
                note = f"{note}<br>{evidence}" if note else evidence
            out.append(
                f"| {md_cell(r.acceptance)} | {origins} | {' '.join(chips)} "
                f"| {md_cell(label)} | {note} |"
            )
        out.append("")

    def section(title: str, status: str) -> None:
        items = [r for r in rows if r.status == status]
        if not items:
            return
        out.append(f"### {md_cell(title)}")
        out.append("")
        for r in items:
            out.append(f"- **{md_cell(r.id)}** — {md_cell(r.acceptance)}. _{md_cell(r.notes)}_")
        out.append("")

    out.append("## § The sharp line — where drift can hide")
    out.append("")
    section("Failing — the workflow is red until these are fixed or re-classified", "failing")
    section("Skipped — verification exists but does not run in CI (backfill owed)", "skipped")
    section("Not implemented — no test or surface yet", "not-implemented")
    out.append(
        "_Statuses: ci / scheduled cannot drift silently; skipped and not-implemented are "
        "CI warnings gated by the backfill rule; failing fails CI._"
    )
    return "\n".join(out) + "\n"


def _identity(matrix: Matrix, root: Path) -> tuple[str, str]:
    # Local import: check.py and report.py both sit under fr.acceptance; keep
    # the import lazy so neither module has to import the other at load time.
    from fr.acceptance.check import resolve_identity

    return resolve_identity(matrix, root)


def render_deterministic(
    matrix: Matrix,
    root: Path,
    out_dir: Path,
    sibling_root: str,
    link_mode: str = "local",
    fmt: str = "html",
) -> str:
    """Render as a pure function of `matrix.yaml`: a matrix-derived stamp (no
    git date/hash) and probe=False links (no filesystem twin-probing). This is
    the committed-report and drift-check rendering — reproducible from the
    matrix alone, so the tripwire only fires on a genuine matrix change.

    `root`/`out_dir` are resolved to canonical paths so callers passing
    unresolved or symlinked paths (`add` via `resolve_repo_root()` vs. the
    tripwire via `__file__.resolve()`) render byte-identically — otherwise a
    sibling-repo relative link could differ and `add` would emit a report the
    tripwire rejects."""
    root = root.resolve()
    out_dir = out_dir.resolve()
    org, own_repo = _identity(matrix, root)
    links = LinkBuilder(
        mode=link_mode,
        ref="main",
        root=root,
        out_dir=out_dir,
        sibling_root=sibling_root,
        org=org,
        own_repo=own_repo,
        probe=False,
    )
    stamp = f"{len(matrix.rows)} rows · links: {link_mode}"
    renderer = render_markdown if fmt == "md" else render
    return renderer(matrix, links, stamp)


# The committed report SET: one deterministic file per (link mode, format). This
# mapping is the single source of truth — the CLI (`report --deterministic` /
# `--check`), `add`, `init`, the `check` gate, and the sync tripwire all iterate
# it, so the file list lives in exactly one place.
#   report_local.html  — local links, HTML (viewable from a checkout)
#   report_linked.html — github links, HTML
#   report_linked.md   — github links, Markdown (github.com renders it inline;
#                        committed .html is shown as source, not rendered)
REPORT_SET: dict[str, tuple[str, str]] = {
    "docs/acceptance/report_local.html": ("local", "html"),
    "docs/acceptance/report_linked.html": ("github", "html"),
    "docs/acceptance/report_linked.md": ("github", "md"),
}

# `report.html` is the ad-hoc/uncommitted file now; `report.github.html` is the
# pre-formats committed name, never produced anymore. The deterministic writers
# delete a stale copy of the latter on regenerate so a migrating repo cleans up.
STALE_LEGACY_REPORTS: tuple[str, ...] = ("docs/acceptance/report.github.html",)


def render_committed_set(matrix: Matrix, root: Path) -> dict[str, str]:
    """`{repo-relative path: rendered}` for every committed report — one per
    entry in `REPORT_SET`, each a deterministic render of `matrix.yaml`. All
    live in `docs/acceptance/`, so a shared `out_dir` keeps their relative links
    consistent. A pure matrix→content function: no filesystem writes/deletes."""
    out_dir = root / "docs" / "acceptance"
    return {
        rel: render_deterministic(matrix, root, out_dir, "..", link_mode, fmt)
        for rel, (link_mode, fmt) in REPORT_SET.items()
    }


def prune_stale_reports(root: Path) -> list[str]:
    """Delete any legacy report file superseded by the current set (e.g. the
    renamed `report.github.html`), returning the ones removed. Called by the
    deterministic writers so a regenerate migrates a repo forward."""
    removed = []
    for rel in STALE_LEGACY_REPORTS:
        p = root / rel
        if p.exists():
            p.unlink()
            removed.append(rel)
    return removed


def render_report(
    matrix: Matrix,
    root: Path,
    out_dir: Path,
    sibling_root: str,
    link_mode: str,
    ref: str,
) -> str:
    """Ad-hoc local render: git-stamped (last-commit date/hash) and
    twin-probing links. Non-deterministic by design — for a throwaway local
    view, never the committed artifact."""
    import subprocess

    org, own_repo = _identity(matrix, root)
    links = LinkBuilder(
        mode=link_mode,
        ref=ref,
        root=root,
        out_dir=out_dir,
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
    return render(matrix, links, stamp)
