"""Build architecture/pipeline.html: the 5.5.0 diagram with open issues pinned on the
steps they break, plus the old page's nine diagram snapshots as an evolution tab set."""
import html, json, os, re

SP = os.path.dirname(os.path.abspath(__file__))
D = os.path.dirname(SP)  # the triage state directory this folder sits in
OLD = os.path.join(SP, "old", "architecture-2026-10-02.html")
esc = lambda s: html.escape(str(s), quote=True)
GH = "https://github.com/derio-net/super-fr/issues/"

facts = json.load(open(f"{D}/facts.json"))
open_issues = {i["number"]: i["title"] for i in facts["issues"] if i["state"] == "open"}

# kind: d = defect (behaves wrong today), g = gap (missing capability / unproven claim)
DRIVER = [
    ("judge + board", "fr triage collect · render", [
        (985, "d", "partial in Done")]),
    ("batches + waves", "create · wave · after", [
        (884, "g", "weak cap tests"), (990, "d", "wave-less unadopted")]),
    ("dispatch", "herdr runner", [
        (878, "d", "only in herdr"), (931, "d", "busy-pane race"),
        (956, "d", "brief not sent"), ]),
    ("session", "fr-goal / fr-debugging", [
        (959, "g", "manual conflicts")]),
    ("merge train", "update · CI · merge", [
        (962, "d", "moved head"),
        (937, "d", "archive vs refs"), (921, "d", "degraded forge")]),
    ("post_merge", "install.sh", [
        (964, "g", "stale sessions"), (998, "d", "new config key")]),
    ("close-out + archive", "fr pickup --run", [
        (883, "d", "double close-out"), (991, "d", "phantom close-out"),
        (1004, "d", "archive base"), (930, "g", "unpriced usage"),
        (528, "d", "matrix refs"), (458, "g", "file open ends")]),
]
PIPE = [
    ("brainstorm", []),
    ("spec-review", []),
    ("plan", [(552, "g", "no add-phase")]),
    ("plan-review", []),
    ("implement-phase", []),
    ("review-phase", []),
    ("journal-check", []),
    ("deliver", [(868, "d", "false keyword"), (869, "d", "split keyword"),
                 (822, "g", "live-walk close"), (838, "g", "tiers in PR body")]),
]
STRIPS = [
    ("RUN CURSOR · RECORDS · TELEMETRY", [
        ]),
    ("COST + TELEMETRY (measurement owed)", [
        (593, "g", "main-session cost"), (597, "g", "perf measures"),
        (627, "g", "handoff quality"), (793, "g", "per-phase overhead"),
        (509, "g", "OpenCode/Hermes readers"), (511, "g", "no-usage record"),
        (623, "g", "live Hermes db")]),
    ("HOST · INSTALL · ISOLATION", [
        (924, "d", "Pages deploy"), (1014, "d", "glab token: no gate"),
        (1015, "d", "GH_HOST not applied"), (1013, "d", "refusal by text"), (580, "g", "gc --stop-idle"),
        (1003, "d", "sync symlink race")]),
]

placed = {n for _, _, ps in DRIVER for n, _, _ in ps} | {n for _, ps in PIPE for n, _, _ in ps} \
    | {n for _, ps in STRIPS for n, _, _ in ps}
missing_closed = sorted(placed - set(open_issues))
assert not missing_closed, f"pinned issues no longer open: {missing_closed}"
other = sorted(set(open_issues) - placed)

COL = {"d": "var(--warn)", "g": "var(--gap)"}

def pin(x, y, n, kind, label, anchor="middle"):
    title = esc(f"#{n} {open_issues[n]}")
    return (f'<a class="gh" href="{GH}{n}"><title>{title}</title>'
            f'<text x="{x}" y="{y}" font-size="10" text-anchor="{anchor}" font-family="var(--mono)" fill="{COL[kind]}">'
            f'<tspan font-weight="600">#{n}</tspan> {esc(label)}</text></a>')

out = []
W = 1086
# ---- driver band
out.append('<text x="10" y="18" font-size="11" fill="var(--muted)" font-family="var(--mono)" letter-spacing=".06em">'
           'WAVE DRIVER · fr triage batch drive · fr 5.1 → 5.5 · one pass per minute, waves in order</text>')
bw, gap, x0, y0 = 142, 12, 10, 30
maxpins = max(len(p) for _, _, p in DRIVER)
for i, (name, sub, pins) in enumerate(DRIVER):
    x = x0 + i * (bw + gap); cx = x + bw / 2
    session = name == "session"
    out.append(f'<rect x="{x}" y="{y0}" width="{bw}" height="46" rx="5" fill="{"var(--new-soft)" if session else "var(--box)"}" '
               f'stroke="{"var(--new)" if session else "currentColor"}"/>')
    out.append(f'<text x="{cx}" y="{y0+20}" font-size="12.5" text-anchor="middle" fill="currentColor">{esc(name)}</text>')
    out.append(f'<text x="{cx}" y="{y0+36}" font-size="10" text-anchor="middle" font-family="var(--mono)" fill="var(--muted)">{esc(sub)}</text>')
    if i:
        out.append(f'<path d="M{x-gap+1} {y0+23} L{x-2} {y0+23}" stroke="currentColor" stroke-width="1.2" fill="none" marker-end="url(#now-a)"/>')
    if not pins:
        out.append(f'<text x="{cx}" y="{y0+64}" font-size="10.5" text-anchor="middle" font-family="var(--mono)" fill="var(--new)">no open pins</text>')
    for k, (n, kind, label) in enumerate(pins):
        out.append(pin(x + 2, y0 + 64 + k * 16, n, kind, label, "start"))
yb = y0 + 64 + maxpins * 16 + 8
# loop-back arrow: next wave
out.append(f'<path d="M{x0+6*(bw+gap)+bw/2} {yb-2} L{x0+6*(bw+gap)+bw/2} {yb+8} L{x0+bw/2} {yb+8} L{x0+bw/2} {yb-2}" '
           f'stroke="var(--muted)" stroke-dasharray="4 3" fill="none" marker-end="url(#now-a)"/>')
out.append(f'<text x="{W/2}" y="{yb+22}" font-size="10.5" text-anchor="middle" font-family="var(--mono)" fill="var(--muted)">'
           'next wave starts when every batch of this one is archived</text>')
# session opened
sx = x0 + 3 * (bw + gap)
ys = yb + 44
out.append(f'<path d="M{sx} {y0+46} L{sx} {yb+26} L10 {ys-6}" stroke="var(--new)" stroke-dasharray="3 3" fill="none"/>')
out.append(f'<path d="M{sx+bw} {y0+46} L{sx+bw} {yb+26} L1076 {ys-6}" stroke="var(--new)" stroke-dasharray="3 3" fill="none"/>')
out.append(f'<text x="18" y="{ys+8}" font-size="11" fill="var(--muted)" font-family="var(--mono)" letter-spacing=".06em">'
           'ONE SESSION, OPENED · fr-goal@1 workflow steps · each agent step hands one record to fr run resolve --record</text>')
py = ys + 18
for i, (name, pins) in enumerate(PIPE):
    x = 10 + i * 134; cx = x + 62
    dashed = name in ("plan-review", "journal-check")
    out.append(f'<rect x="{x}" y="{py}" width="124" height="40" rx="5" fill="{"none" if dashed else "var(--box)"}" stroke="currentColor"'
               f'{" stroke-dasharray=\"4 3\"" if dashed else ""}/>')
    out.append(f'<text x="{cx}" y="{py+25}" font-size="12.5" text-anchor="middle" fill="currentColor">{esc(name)}</text>')
    if i:
        out.append(f'<path d="M{x-9} {py+20} L{x-2} {py+20}" stroke="currentColor" stroke-width="1.2" fill="none" marker-end="url(#now-a)"/>')
    if not pins:
        out.append(f'<text x="{cx}" y="{py+58}" font-size="10.5" text-anchor="middle" font-family="var(--mono)" fill="var(--new)">no open pins</text>')
    for k, (n, kind, label) in enumerate(pins):
        out.append(pin(x, py + 58 + k * 16, n, kind, label, "start"))
y = py + 58 + max(len(p) for _, p in PIPE) * 16 + 14
# strips
sw = (W - 20 - 2 * 14) / 3
for i, (title, pins) in enumerate(STRIPS):
    x = 10 + i * (sw + 14)
    h = 30 + len(pins) * 16
    out.append(f'<rect x="{x}" y="{y}" width="{sw}" height="{max(h, 30 + 7*16)}" rx="6" fill="none" stroke="var(--rule)"/>')
    out.append(f'<text x="{x+12}" y="{y+18}" font-size="10.5" fill="var(--muted)" font-family="var(--mono)" letter-spacing=".05em">{esc(title)}</text>')
    for k, (n, kind, label) in enumerate(pins):
        out.append(pin(x + 12, y + 38 + k * 16, n, kind, label, "start"))
H = int(y + 30 + 7 * 16 + 12)

ndef = sum(1 for g in (DRIVER,) for _, _, ps in g for _, k, _ in ps if k == "d") \
    + sum(1 for _, ps in PIPE for _, k, _ in ps if k == "d") + sum(1 for _, ps in STRIPS for _, k, _ in ps if k == "d")
aria = (f"fr 5.5.0. Top: the wave driver's loop, collect and judge, batches and waves, dispatch through herdr, "
        f"the session, the merge train, post_merge and close-out with archive; each step lists the open issues on it. "
        f"Below: the session opened into fr-goal's eight workflow steps with their open issues, then three strips "
        f"for the run cursor and acceptance, cost measurement, and host and install. {len(placed)} open issues placed, "
        f"{len(other)} elsewhere.")
SVGSTYLE = "display:block;width:100%;min-width:780px;height:auto;color:var(--ink);font-family:var(--sans)"
now_svg = (f'<svg class="dia" style="{SVGSTYLE}" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(aria)}">'
           '<defs><marker id="now-a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
           'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>'
           + "".join(out) + "</svg>")

# ---- old snapshots
src = open(OLD).read()
M = json.loads(re.search(r"const M=(\[.*?\]);", src, re.S).group(1))
panels_src = re.findall(r'<div class="evo-panel" data-i="(\d+)"[^>]*><div class="svgwrap">(<svg.*?</svg>)</div></div>', src, re.S)
assert len(panels_src) == len(M) == 9, (len(panels_src), len(M))
panels = []
for (i, svg), m in zip(panels_src, M):
    svg = svg.replace('<svg class="dia"', f'<svg class="dia" style="{SVGSTYLE}"', 1)
    panels.append((f"p{i}", f'{m["d"]} · {m["v"]}', svg, m["c"]))
panels.append(("now", "2026-10-05 · fr 5.5.0 (now)", now_svg,
               "This page: the driver loop added in 5.1–5.5, the session opened into fr-goal's steps, today's open issues pinned."))

def tabs(group, label, items, selected):
    tb, pb = [], []
    for i, (key, text, body, cap) in enumerate(items):
        on = i == selected
        tid, pid = f"{group}-tab-{key}", f"{group}-panel-{key}"
        tb.append(f'<button type="button" role="tab" id="{tid}" data-key="{key}" aria-controls="{pid}" '
                  f'aria-selected="{"true" if on else "false"}" tabindex="{0 if on else -1}">{esc(text)}</button>')
        pb.append(f'<div role="tabpanel" id="{pid}" aria-labelledby="{tid}" tabindex="0"><h3 class="panel-label">{esc(text)}</h3>'
                  f'<div style="overflow-x:auto">{body}</div><p style="font-size:13px;color:var(--muted);margin:6px 0 0">{esc(cap)}</p></div>')
    return (f'<div class="tabs" data-tabs><div role="tablist" aria-label="{esc(label)}" hidden>{"".join(tb)}</div>'
            f'{"".join(pb)}</div>')

TOK = ("--new:var(--accent);--new-soft:color-mix(in srgb,var(--accent) 14%,transparent);"
       "--warn:var(--sev-1);--warn-soft:color-mix(in srgb,var(--sev-1) 12%,transparent);"
       "--gap:var(--sev-2);--gap-soft:color-mix(in srgb,var(--sev-2) 14%,transparent);"
       "--box:color-mix(in srgb,var(--ink) 6%,transparent);--panel:var(--surface);--rule:var(--line);"
       "--bg:var(--ground);--faint:var(--sev-4);--accent-soft:color-mix(in srgb,var(--accent) 12%,transparent);"
       "--c-open:var(--sev-1);--c-closed:var(--sev-3)")
other_html = ", ".join(f'<a class="gh" href="{GH}{n}" title="{esc(open_issues[n])}">#{n}</a>' for n in other)
frag = f'''<div style="{TOK}">
<h2>The pipeline and its driver, with open issues on the steps they break</h2>
<p style="color:var(--muted);max-width:75ch">Authored, not measured: each pin is a judgement of where an open issue acts,
made on 2026-10-05 from the issue titles and bodies. <span style="color:var(--warn)">Red</span> behaves wrong today;
<span style="color:var(--gap)">amber</span> is a missing capability or an unproven claim. Hover a pin for the issue's
title; click it to open the issue. The tabs step through every version of this diagram, from the first architecture
page on 2026-09-25 to now; the older ones show issues as they stood that day.</p>
{tabs("pipeline", "Diagram versions", panels, len(panels) - 1)}
<p style="font-size:13px;color:var(--muted)">{len(placed)} of {len(open_issues)} open issues are pinned above
({ndef} defects). The other {len(other)} act on no pipeline or driver step (docs, harness parity, forges, other
runners, live-evidence owed): {other_html}.</p>
</div>
'''
open(f"{D}/architecture/pipeline.html", "w").write(frag)
print("placed", len(placed), "other", len(other), "defects", ndef, "H", H)
