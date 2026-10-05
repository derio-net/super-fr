"""Defect origins: where did the issues filed in a window come from (wave-driver R10, R20).

The same engine-and-skill split as the rest of `fr triage`:

- **collect** reads the issues created since a date through the existing `Forge` seam
  and writes `origins-facts.json` (state, closing PRs, hours to close). Nothing is
  classified here.
- **origins.yaml** is the agent's: per issue a category (what the defect IS), a source
  (who found it), the PR it relates to, a severity and a reason; plus optional
  `causes:` whose `batches:` the page's conclusion links to the triage batches that
  address them.
- **check** names the issues with no classification, and classifications for issues the
  facts do not hold (never pruned). **render** writes `origins.html` on the shared page
  components (`fr.triage.components`).

A figure the inputs do not support is an em dash, never a zero. Pure render: no clock,
no forge, same inputs give the same bytes.
"""

from __future__ import annotations

import json
import math
import re
import statistics
import urllib.parse
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from fr.triage.collect import ORIGINS_ISSUE_LIST_FIELDS, REPO_LIMIT, Forge, parse_prs, scope_repos
from fr.triage.components import CHROME_CSS, GUTTER_CSS, TOKENS_CSS, collapsed, page_header
from fr.triage.errors import ForgeError, TriageError
from fr.triage.fragments import Entry, Resolved, splice
from fr.triage.model import KEY_RE, Judgements, Scope, issue_key, normalize_key
from fr.triage.render import FONTS, esc, plural

CATEGORIES = ("latent", "regression", "new-feature", "leftover", "gap", "duplicate")
SOURCES = ("pipeline", "recording", "hand")
SEVERITIES = ("low", "med", "high")
Category = Literal["latent", "regression", "new-feature", "leftover", "gap", "duplicate"]
Source = Literal["pipeline", "recording", "hand"]
Severity = Literal["low", "med", "high"]
LEADERBOARDS: tuple[Category, ...] = ("new-feature", "leftover")

FACTS_FILE = "origins-facts.json"
CLASSIFICATION_FILE = "origins.yaml"
PAGE_FILE = "origins.html"
ORIGINS_DIR = "origins"
# The generated sections, in the order R7 gives; fragments interleave where the manifest says.
GENERATED = (
    "origin-counts",
    "conclusion",
    "filings-per-day",
    "time-to-fix",
    "leaderboards",
    "issues",
)
FACTS_SCHEMA = 1  # origins-facts.json: unchanged by schema 2 of the classification
CLASSIFICATION_SCHEMA = 2  # origins.yaml: what fr writes; 1 still loads
CLASSIFICATION_READS = (1, 2)
ISSUE_LIMIT = 1000
PR_LIMIT = 1000
DASH = "—"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# ---------------------------------------------------------------- facts


class ClosingPr(_Strict):
    repo: str
    number: int
    title: str
    url: str


class OriginIssue(_Strict):
    key: str
    repo: str
    number: int
    title: str
    labels: list[str] = []
    url: str
    created_at: str
    closed_at: str | None = None
    state: Literal["open", "closed"]
    reason: Literal["completed", "not_planned"] | None = None
    closing_prs: list[ClosingPr] = []
    hours_to_close: float | None = None


class OriginsFacts(_Strict):
    scope: str
    since: str
    collected_at: str
    issues: list[OriginIssue]
    warnings: list[str] = []


def parse_since(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise TriageError(f"--since must be a date YYYY-MM-DD, got {text!r}") from exc


def _parse_time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC)


def collect_origins(
    forge: Forge,
    scope: Scope,
    *,
    since: date,
    now: datetime,
    issue_limit: int = ISSUE_LIMIT,
    pr_limit: int = PR_LIMIT,
    repo_limit: int = REPO_LIMIT,
) -> OriginsFacts:
    """The issues created on or after *since* in *scope*, with how each one ended.

    Closing PRs are the MERGED PRs whose closing references name the issue (a PR closed
    unmerged closed nothing). In org and group scope a repo that cannot be read is a
    warning and the rest collect; in repo scope it is the error.
    """
    repos, truncations = scope_repos(forge, scope, repo_limit=repo_limit)
    cutoff = datetime(since.year, since.month, since.day, tzinfo=UTC)
    out: list[OriginIssue] = []
    warnings: list[str] = [
        f"{t.target}: repo list hit its limit ({t.limit}); repos may be missing"
        for t in truncations
    ]
    collected = 0
    for repo in repos:
        try:
            raw_issues = forge.list_issues(
                repo=repo, state="all", limit=issue_limit, fields=ORIGINS_ISSUE_LIST_FIELDS
            )
            raw_prs = forge.list_prs(repo=repo, state="all", limit=pr_limit)
        except ForgeError as exc:
            if scope.kind == "repo":
                raise
            warnings.append(f"skipped {repo}: {exc}")
            continue
        collected += 1
        if len(raw_issues) == issue_limit:
            warnings.append(
                f"{repo}: issue list hit its limit ({issue_limit}); rows may be missing"
            )
        if len(raw_prs) == pr_limit:
            warnings.append(
                f"{repo}: PR list hit its limit ({pr_limit}); closing PRs may be missing"
            )
        closing: dict[int, list[ClosingPr]] = {}
        owner, name = repo.lower().split("/", 1)
        for pr, refs in parse_prs(repo, raw_prs):
            if pr.state != "MERGED":
                continue
            for ref_owner, ref_name, number in refs:
                if (ref_owner, ref_name) == (owner, name):
                    closing.setdefault(number, []).append(
                        ClosingPr(repo=repo, number=pr.number, title=pr.title, url=pr.url)
                    )
        for raw in raw_issues:
            created = raw.get("createdAt")
            if not created or _parse_time(created) < cutoff:
                continue
            out.append(_origin_issue(repo, raw, closing.get(raw["number"], [])))
    if not collected:
        raise ForgeError(f"no repo of {scope.target} could be read: " + "; ".join(warnings))
    out.sort(key=lambda i: (i.repo.lower(), i.number))
    return OriginsFacts(
        scope=scope.target,
        since=since.isoformat(),
        collected_at=now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        issues=out,
        warnings=warnings,
    )


def _origin_issue(repo: str, raw: dict[str, Any], closing: list[ClosingPr]) -> OriginIssue:
    closed = raw.get("closedAt") or None
    is_closed = str(raw.get("state", "")).upper() == "CLOSED" or closed is not None
    reason_raw = str(raw.get("stateReason") or "").upper()
    reason = (
        {"COMPLETED": "completed", "NOT_PLANNED": "not_planned"}.get(reason_raw)
        if is_closed
        else None
    )
    hours = (
        round((_parse_time(closed) - _parse_time(raw["createdAt"])).total_seconds() / 3600, 2)
        if closed
        else None
    )
    return OriginIssue(
        key=issue_key(repo, raw["number"]),
        repo=repo,
        number=raw["number"],
        title=raw["title"],
        labels=[label["name"] for label in raw.get("labels") or []],
        url=raw["url"],
        created_at=raw["createdAt"],
        closed_at=closed,
        state="closed" if is_closed else "open",
        reason=reason,  # type: ignore[arg-type]
        closing_prs=closing,
        hours_to_close=hours,
    )


def write_facts(path: Path, facts: OriginsFacts) -> None:
    body = {"schema": FACTS_SCHEMA, **facts.model_dump(mode="json")}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_origins_facts(path: Path) -> OriginsFacts:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.pop("schema", None) != FACTS_SCHEMA:
            raise TriageError(f"{path}: not origins facts of schema {FACTS_SCHEMA}")
        return OriginsFacts.model_validate(data)
    except (OSError, ValueError) as exc:
        raise TriageError(f"{path}: cannot read origins facts: {exc}") from exc
    except ValidationError as exc:
        raise TriageError(f"{path}: invalid origins facts: {exc}") from exc


# ------------------------------------------------------- classification


class Origin(_Strict):
    category: Category
    source: Source
    pr: str | None = None
    severity: Severity
    reason: str = Field(min_length=1)
    evidence: str | None = None
    # Schema 2 (triage-pages-goal R10): optional on both schemas, like `kind` on judgements.
    duplicate_of: str | None = None
    fixed_by: str | None = None
    introduced_in: str | None = None

    @model_validator(mode="after")
    def _regression_names_its_pr(self) -> Origin:
        if self.category == "regression" and not self.pr:
            raise ValueError("a regression must name the PR that broke it (`pr:`)")
        return self

    @model_validator(mode="after")
    def _duplicate_and_introduced_fit_the_category(self) -> Origin:
        if self.duplicate_of and self.category != "duplicate":
            raise ValueError("`duplicate_of` needs `category: duplicate`")
        if self.introduced_in and self.category == "regression":
            raise ValueError(
                "`introduced_in` is refused on a regression: its `pr:` already names the PR"
            )
        return self

    @field_validator("duplicate_of")
    @classmethod
    def _normalise_duplicate_of(cls, v: str | None) -> str | None:
        # Held to the key grammar like `Judgement.duplicate_of` (review p3-r1).
        if v and not KEY_RE.match(v):
            raise ValueError(f"`duplicate_of` {v!r} is not an issue key (`<repo>#<number>`)")
        return normalize_key(v) if v else v


class Cause(_Strict):
    title: str = Field(min_length=1)
    categories: list[Category] = []
    batches: list[str] = []
    process_change: str = ""


class Origins(_Strict):
    issues: dict[str, Origin] = {}
    causes: list[Cause] = []

    @model_validator(mode="after")
    def _no_entry_duplicates_itself(self) -> Origins:
        selves = sorted(k for k, o in self.issues.items() if o.duplicate_of == normalize_key(k))
        if selves:
            raise ValueError(f"`duplicate_of` names the issue itself: {', '.join(selves)}")
        return self


def load_origins(path: Path) -> Origins:
    """`origins.yaml`; absent is an empty classification, a bad one is refused with *path*."""
    if not path.exists():
        return Origins()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise TriageError(f"{path}: cannot read origins: {exc}") from exc
    if not isinstance(data, dict) or data.pop("schema", None) not in CLASSIFICATION_READS:
        raise TriageError(f"{path}: origins.yaml needs `schema: 1` or `schema: 2`")
    try:
        origins = Origins.model_validate(data)
    except ValidationError as exc:
        raise TriageError(f"{path}: invalid origins: {exc}") from exc
    return origins.model_copy(
        update={"issues": {normalize_key(k): v for k, v in origins.issues.items()}}
    )


class OriginsCheck(_Strict):
    unclassified: list[OriginIssue]
    unknown: list[str]
    # Issues whose `duplicate_of` names an issue the facts do not hold (outside the window).
    duplicate_outside: list[str] = []


def check_origins(facts: OriginsFacts, origins: Origins) -> OriginsCheck:
    """Facts with no classification, and classifications the facts do not hold."""
    held = {i.key for i in facts.issues}
    return OriginsCheck(
        unclassified=[i for i in facts.issues if i.key not in origins.issues],
        unknown=sorted(k for k in origins.issues if k not in held),
        duplicate_outside=sorted(
            k
            for k, o in origins.issues.items()
            if k in held and o.duplicate_of and o.duplicate_of not in held
        ),
    )


# --------------------------------------------------------------- rollups


class FixTime(_Strict):
    """Time to fix for one category; `median` is None when no close was completed."""

    category: str
    median: float | None
    open: int
    not_planned: int
    unknown: int


def day_buckets(facts: OriginsFacts) -> list[tuple[str, int]]:
    """Filings per UTC day from `since` to the last filing, empty days included (a real 0)."""
    if not facts.issues:
        return []
    per = Counter(_parse_time(i.created_at).date().isoformat() for i in facts.issues)
    day = date.fromisoformat(facts.since)
    last = max(date.fromisoformat(d) for d in per)
    days: list[tuple[str, int]] = []
    while day <= last:
        days.append((day.isoformat(), per.get(day.isoformat(), 0)))
        day += timedelta(days=1)
    return days


def fix_times(facts: OriginsFacts, origins: Origins) -> list[FixTime]:
    rows: list[FixTime] = []
    for cat in CATEGORIES:
        issues = [i for i in facts.issues if (o := origins.issues.get(i.key)) and o.category == cat]
        done = [
            i.hours_to_close
            for i in issues
            if i.reason == "completed" and i.hours_to_close is not None
        ]
        rows.append(
            FixTime(
                category=cat,
                median=statistics.median(done) if done else None,
                open=sum(1 for i in issues if i.state == "open"),
                not_planned=sum(1 for i in issues if i.reason == "not_planned"),
                unknown=sum(1 for i in issues if i.state == "closed" and i.reason is None),
            )
        )
    return rows


def leaderboard(
    facts: OriginsFacts, origins: Origins, category: str
) -> tuple[list[tuple[str, int]], int]:
    """`(pr, issues)` most first for *category*, and how many named no PR."""
    prs: Counter[str] = Counter()
    unnamed = 0
    for i in facts.issues:
        o = origins.issues.get(i.key)
        if o is None or o.category != category:
            continue
        if o.pr:
            prs[o.pr] += 1
        else:
            unnamed += 1
    return sorted(prs.items(), key=lambda kv: (-kv[1], kv[0])), unnamed


# ---------------------------------------------------------------- render

CSS = (
    TOKENS_CSS
    + """
* { box-sizing: border-box; }
html, body { margin: 0; overflow-x: hidden; }
body { background: var(--ground); color: var(--ink); font: 15px/1.5 var(--sans); }
main { max-width: 1040px; margin: 0 auto; padding: 0 16px 48px; }
[hidden] { display: none !important; }
a { color: var(--accent); }
code { font-family: var(--mono); font-size: .92em; overflow-wrap: anywhere; }
header.mast { padding: 28px 0 16px; border-bottom: 2px solid var(--ink); }
header.mast h1 { margin: 0 0 6px; font-size: 1.6rem; font-weight: 600; overflow-wrap: anywhere; }
.meta { color: var(--muted); font-size: .88rem; display: flex; flex-wrap: wrap; gap: 4px 16px; }
.notes { margin: 12px 0 0; padding: 0; list-style: none; font-size: .85rem; color: var(--sev-2); }
section { margin-top: 28px; }
section > h2 { margin: 0 0 8px; font-size: 1.15rem; font-weight: 600; }
.lede { color: var(--muted); font-size: .9rem; margin: 0 0 10px; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 6px 0; }
.chip { background: var(--surface); border: 1px solid var(--line); border-radius: 999px;
  padding: 2px 10px; font-size: .85rem; }
.chip b { font-family: var(--mono); font-weight: 500; }
table { width: 100%; min-width: 760px; border-collapse: collapse; background: var(--surface);
  border: 1px solid var(--line); font-size: .88rem; }
th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--line);
  vertical-align: top; }
td.wrap, th.wrap { overflow-wrap: break-word; min-width: 180px; }
th { color: var(--muted); font-weight: 500; }
td.n, th.n { text-align: right; font-family: var(--mono); }
.scroll { overflow-x: auto; }
svg.chart { display: block; height: auto; }
svg.chart text { font-family: var(--mono); font-size: 10px; }
.bar { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }
.btn { font: inherit; font-size: .82rem; color: var(--muted); background: var(--surface);
  border: 1px solid var(--line); border-radius: 999px; padding: 3px 10px; cursor: pointer; }
.btn[aria-pressed="true"] { color: var(--surface); background: var(--accent);
  border-color: var(--accent); }
.cause { background: var(--surface); border: 1px solid var(--line); border-radius: 8px;
  padding: 10px 14px; margin: 10px 0; }
.cause h3 { margin: 0 0 4px; font-size: 1rem; }
.unresolved { color: var(--sev-1); font-family: var(--mono); }
.sev-high { color: var(--sev-1); } .sev-med { color: var(--sev-2); }
.sev-low { color: var(--muted); }
"""
    + CHROME_CSS
    + GUTTER_CSS
)

FILTER_SCRIPT = """
(function () {
  var bar = document.querySelector("[data-filter-bar]");
  if (!bar) { return; }
  var rows = Array.prototype.slice.call(document.querySelectorAll("tr[data-category]"));
  var buttons = Array.prototype.slice.call(bar.querySelectorAll("button[data-filter]"));
  buttons.forEach(function (b) {
    b.addEventListener("click", function () {
      var want = b.getAttribute("data-filter");
      buttons.forEach(function (o) {
        o.setAttribute("aria-pressed", o === b ? "true" : "false");
      });
      rows.forEach(function (r) {
        r.hidden = want !== "all" && r.getAttribute("data-category") !== want;
      });
    });
  });
  bar.hidden = false;
})();
"""

_PR_REF = re.compile(r"^([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#(\d+)$")


def _pct(n: int, total: int) -> str:
    return f"{round(100 * n / total)}%" if total else DASH


def _hours(h: float | None) -> str:
    return DASH if h is None else f"{h:.1f} h"


def _pr_link(pr: str | None) -> str:
    if not pr:
        return DASH
    m = _PR_REF.match(pr)
    if not m:
        return esc(pr)
    return f'<a href="https://github.com/{esc(m.group(1))}/pull/{m.group(2)}">{esc(pr)}</a>'


def _counts(facts: OriginsFacts, origins: Origins) -> str:
    classified = [o for i in facts.issues if (o := origins.issues.get(i.key))]
    total = len(classified)
    cats: Counter[str] = Counter(o.category for o in classified)
    srcs: Counter[str] = Counter(o.source for o in classified)
    cat_chips = "".join(
        f'<span class="chip">{c} <b data-category-count="{c}">{cats[c]}</b> '
        f'<span data-category-share="{c}">{_pct(cats[c], total)}</span></span>'
        for c in CATEGORIES
    )
    src_chips = "".join(
        f'<span class="chip">{s} <b data-source-count="{s}">{srcs[s]}</b> '
        f'<span data-source-share="{s}">{_pct(srcs[s], total)}</span></span>'
        for s in SOURCES
    )
    return (
        '<section id="origin-counts"><h2>Where the issues came from</h2>'
        f'<p class="lede">{plural(total, "classified issue")} of {len(facts.issues)} filed '
        "(shares are of the classified ones).</p>"
        f'<div class="chips" aria-label="By category">{cat_chips}</div>'
        f'<div class="chips" aria-label="By source">{src_chips}</div></section>'
    )


MIN_CHART_W = 280
LABEL_W, LABEL_GAP = 30, 6  # a "09-01" label at 10px monospace, and the air between two


def _chart(facts: OriginsFacts) -> str:
    days = day_buckets(facts)
    head = '<section id="filings-per-day"><h2>Filings per day</h2>'
    if not days:
        return head + f'<p class="lede">{DASH} no issues were filed in the window.</p></section>'
    slot, width, plot, pad = 28, 20, 100.0, 8
    peak = max(c for _, c in days)
    # Drawn at natural size: one 28px slot per day, never scaled to the container. A label
    # is five 10px monospace glyphs (about 30px), so label every Nth day, N fixed by the
    # slot and the label width, not by how many days there are.
    step = math.ceil((LABEL_W + LABEL_GAP) / slot)
    total_w = max(MIN_CHART_W, slot * len(days) + 2 * pad)
    parts = [
        f'<div class="scroll"><svg class="chart" width="{total_w}" height="150" '
        f'viewBox="0 0 {total_w} 150" style="max-width:{total_w}px" role="img" '
        f'aria-label="Issues filed per day, {days[0][0]} to {days[-1][0]}">',
        f'<line x1="0" y1="124" x2="{total_w}" y2="124" style="stroke:var(--line)"/>',
    ]
    for pos, (day, count) in enumerate(days):
        h = plot * count / peak if peak else 0.0
        x = pad + pos * slot
        parts.append(
            f'<rect class="bar-rect" style="fill:var(--accent)" data-day="{day}" '
            f'data-count="{count}" x="{x}" '
            f'y="{124 - h:.2f}" width="{width}" height="{h:.2f}">'
            f"<title>{day}: {plural(count, 'issue')}</title></rect>"
            f'<text style="fill:var(--muted)" x="{x + width / 2}" y="{118 - h:.2f}" '
            f'text-anchor="middle">{count}</text>'
        )
        if pos % step == 0:
            parts.append(
                f'<text style="fill:var(--muted)" x="{x + width / 2}" y="140" '
                f'text-anchor="middle">{day[5:]}</text>'
            )
    parts.append("</svg></div>")
    return head + "".join(parts) + "</section>"


def _time_to_fix(facts: OriginsFacts, origins: Origins) -> str:
    rows = "".join(
        f'<tr data-ttf="{f.category}"><td>{f.category}</td><td class="n">{_hours(f.median)}</td>'
        f'<td class="n">{f.open}</td><td class="n">{f.not_planned}</td>'
        f'<td class="n">{f.unknown}</td></tr>'
        for f in fix_times(facts, origins)
    )
    return (
        '<section id="time-to-fix"><h2>Median hours to fix</h2>'
        '<p class="lede">Completed closes only. Open issues and closes as not planned are '
        f"counted apart; {DASH} means no completed close.</p>"
        '<div class="scroll"><table><thead><tr><th>Category</th><th class="n">Median</th>'
        '<th class="n">Open</th><th class="n">Not planned</th>'
        f'<th class="n">Closed, no reason</th></tr></thead><tbody>{rows}</tbody></table></div>'
        "</section>"
    )


def _leaderboards(facts: OriginsFacts, origins: Origins) -> str:
    boards = []
    for cat in LEADERBOARDS:
        ranked, unnamed = leaderboard(facts, origins, cat)
        body = "".join(
            f'<tr data-pr="{esc(pr)}" data-n="{n}"><td>{_pr_link(pr)}</td>'
            f'<td class="n">{n}</td></tr>'
            for pr, n in ranked
        )
        if not body:
            body = f'<tr><td colspan="2">{DASH} no PR named</td></tr>'
        note = f'<p class="lede">{plural(unnamed, "issue")} named no PR.</p>' if unnamed else ""
        boards.append(
            f'<div data-board="{cat}"><h3>{cat}: PRs that produced them</h3>'
            f'<div class="scroll"><table><thead><tr><th>PR</th><th class="n">Issues</th></tr>'
            f"</thead><tbody>{body}</tbody></table></div>{note}</div>"
        )
    return (
        '<section id="pr-leaderboards"><h2>Which PRs left work behind</h2>'
        + "".join(boards)
        + "</section>"
    )


def _original_link(issue: OriginIssue, target: str, held: Mapping[str, OriginIssue]) -> str:
    """The duplicate's original: its table row when in the window, else (same repo) the
    duplicate's own url with the number replaced, else the key as plain text."""
    if target in held:
        frag = urllib.parse.quote(f"origin-{target}", safe="-_.")
        return f'<a href="#{frag}">{esc(target)}</a>'
    name, _, number = target.rpartition("#")
    if (
        number.isdigit()
        and name == issue.repo.split("/", 1)[1].lower()
        and issue.url.startswith("https://")
    ):
        base = issue.url.rsplit("/", 1)[0]
        return f'<a href="{esc(base)}/{number}">{esc(target)}</a>'
    return esc(target)


def _related_pr(o: Origin | None) -> str:
    if o is None:
        return DASH
    lines = [_pr_link(o.pr)] if o.pr or not (o.introduced_in or o.fixed_by) else []
    if o.introduced_in:
        lines.append(f"introduced in {_pr_link(o.introduced_in)}")
    if o.fixed_by:
        lines.append(f"fixed by {_pr_link(o.fixed_by)}")
    return "<br>".join(lines)


def _issue_table(facts: OriginsFacts, origins: Origins) -> str:
    buttons = "".join(
        f'<button type="button" class="btn" data-filter="{v}" aria-pressed="false">{v}</button>'
        for v in ("all", *CATEGORIES, "unclassified")
    ).replace('data-filter="all" aria-pressed="false"', 'data-filter="all" aria-pressed="true"')
    rows = []
    held = {i.key: i for i in facts.issues}
    for i in facts.issues:
        o = origins.issues.get(i.key)
        cat = o.category if o else "unclassified"
        cat_cell: str = cat
        if o and o.duplicate_of:
            cat_cell = f"{cat} of {_original_link(i, o.duplicate_of, held)}"
        closed = (
            f"closed {i.reason or DASH} in {_hours(i.hours_to_close)}"
            if i.state == "closed"
            else "open"
        )
        by = ", ".join(f"#{p.number}" for p in i.closing_prs)
        detail = (
            f"{esc(o.reason)}" + (f"<br><small>{esc(o.evidence)}</small>" if o.evidence else "")
            if o
            else DASH
        )
        rows.append(
            f'<tr data-category="{cat}" data-key="{esc(i.key)}" id="origin-{esc(i.key)}">'
            f'<td><a href="{esc(i.url) if i.url.startswith("https://") else "#"}">'
            f'{esc(i.key)}</a></td><td class="wrap">{esc(i.title)}</td><td>{cat_cell}</td>'
            f"<td>{o.source if o else DASH}</td>"
            f'<td class="sev-{o.severity if o else "low"}">{o.severity if o else DASH}</td>'
            f"<td>{_related_pr(o)}</td>"
            f'<td>{closed}{f" by {esc(by)}" if by else ""}</td><td class="wrap">{detail}</td></tr>'
        )
    body = (
        f'<div class="bar" data-filter-bar hidden>{buttons}</div>'
        '<div class="scroll"><table><thead><tr><th>Issue</th>'
        '<th class="wrap">Title</th><th>Category</th><th>Source</th><th>Severity</th>'
        '<th>Related PR</th><th>Ended</th><th class="wrap">Why</th></tr>'
        f"</thead><tbody>{''.join(rows)}</tbody></table></div>"
    )
    return (
        f'<section id="issue-table">'
        f"{collapsed('issue-table-fold', 'Every issue', len(rows), body)}</section>"
    )


def _batch_ref(batch_id: str, titles: Mapping[str, str]) -> str:
    if batch_id in titles:
        frag = urllib.parse.quote(f"batch-{batch_id}", safe="-_.")
        return f'<a href="triage.html#{frag}">{esc(batch_id)}</a> {esc(titles[batch_id])}'
    return (
        f'<span class="unresolved" title="no such batch in judgements.yaml">'
        f"{esc(batch_id)}</span> (unresolved: no such batch in judgements.yaml)"
    )


def _conclusion(facts: OriginsFacts, origins: Origins, titles: Mapping[str, str]) -> str:
    cats: Counter[str] = Counter(
        o.category for i in facts.issues if (o := origins.issues.get(i.key))
    )
    cards = []
    for cause in origins.causes:
        n = sum(cats[c] for c in set(cause.categories))
        covers = ", ".join(cause.categories) or DASH
        batches = (
            "<ul>" + "".join(f"<li>{_batch_ref(b, titles)}</li>" for b in cause.batches) + "</ul>"
            if cause.batches
            else "<p>Addressed by: no batch yet.</p>"
        )
        change = (
            f"<p><b>Process change:</b> {esc(cause.process_change)}</p>"
            if cause.process_change
            else ""
        )
        cards.append(
            f'<article class="cause"><h3>{esc(cause.title)}</h3>'
            f'<p class="lede">{esc(covers)}: {plural(n, "issue")}</p>{change}{batches}</article>'
        )
    covered = {c for cause in origins.causes for c in cause.categories}
    loose = [c for c in CATEGORIES if cats[c] and c not in covered]
    tail = (
        f'<p class="lede">No cause names: {esc(", ".join(loose))}.</p>'
        if origins.causes and loose
        else ""
    )
    body = "".join(cards) or (
        f'<p class="lede">{DASH} no causes recorded yet: add `causes:` to origins.yaml.</p>'
    )
    return (
        '<section id="conclusion"><h2>Conclusion: causes and the batches that address them</h2>'
        f"{body}{tail}</section>"
    )


def render_origins(
    facts: OriginsFacts,
    origins: Origins,
    judgements: Judgements | None = None,
    resolved: Resolved | None = None,
    notes: Sequence[str] = (),
) -> str:
    """The defect-origins page: same inputs, same bytes. The generated sections (R7) and the
    authored fragments in the order *resolved* (the manifest) gives; with none, the default
    order and no fragments."""
    titles = {b.id: b.title for b in judgements.batches} if judgements else {}
    missing = check_origins(facts, origins)
    resolved = resolved or Resolved(order=[Entry(g) for g in GENERATED])
    generated = {
        "origin-counts": lambda: _counts(facts, origins),
        "conclusion": lambda: _conclusion(facts, origins, titles),
        "filings-per-day": lambda: _chart(facts),
        "time-to-fix": lambda: _time_to_fix(facts, origins),
        "leaderboards": lambda: _leaderboards(facts, origins),
        "issues": lambda: _issue_table(facts, origins),
    }
    body = splice(resolved, generated)
    note_items = "".join(f"<li>{esc(w)}</li>" for w in [*facts.warnings, *notes])
    title = f"Defect origins · {facts.scope} · since {facts.since}"
    return (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{esc(title)}</title>\n{FONTS}\n<style>{CSS}</style>\n</head>\n<body>\n<main>\n"
        f'<header class="mast"><h1>{esc(title)}</h1><div class="meta">'
        f"<span>{plural(len(facts.issues), 'issue')} filed</span>"
        f"<span>{len(missing.unclassified)} unclassified</span>"
        f"<span>collected {esc(facts.collected_at)}</span>"
        "<span>rendered by <code>fr triage origins render</code></span></div>"
        f'<ul class="notes">{note_items}</ul></header>\n'
        f"{page_header('origins')}\n" + "\n".join(body) + "\n"
        f"</main>\n<script>{FILTER_SCRIPT}</script>\n</body>\n</html>\n"
    )
