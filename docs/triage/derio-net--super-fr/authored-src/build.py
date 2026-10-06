"""Build the authored fragments of the architecture and history pages from this directory's
sources (spec 2026-10-05-triage-pages-goal R15: the dated fragments live on the history page).

  pipeline.html       - architecture/, by pipeline.py: the diagram with open issues pinned (pin table in the
                        script; pins naming a closed issue fail the build), plus the nine
                        2026-10-02 diagram versions as tabs.
  closing-order.html  - history/: the 2026-10-02 board's closing-order section, with each batch's
                        outcome looked up live with gh.
  origins-2026-10-02.html, history-2026-10-02.html
                      - history/: sections of the 2026-10-02 hand-built pages, extracted with their
                        styles inlined (extracted/*.json, made by extract.js in a browser).

Run from anywhere: python3 build.py   (then: fr triage architecture render ... and
fr triage history render ...)
"""
import html, json, os, subprocess, runpy

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "history")  # the dated fragments; pipeline.py writes architecture/
os.makedirs(OUT, exist_ok=True)
esc = lambda s: html.escape(str(s), quote=True)

ARCH_TOK = ("--new:var(--accent);--new-soft:color-mix(in srgb,var(--accent) 14%,transparent);"
            "--warn:var(--sev-1);--warn-soft:color-mix(in srgb,var(--sev-1) 12%,transparent);"
            "--gap:var(--sev-2);--gap-soft:color-mix(in srgb,var(--sev-2) 14%,transparent);"
            "--box:color-mix(in srgb,var(--ink) 6%,transparent);--panel:var(--surface);--rule:var(--line);"
            "--bg:var(--ground);--faint:var(--sev-4);--accent-soft:color-mix(in srgb,var(--accent) 12%,transparent);"
            "--c-open:var(--sev-1);--c-closed:var(--sev-3);")
ORIG_TOK = ARCH_TOK + ("--c-latent:var(--accent);--c-regression:var(--sev-1);--c-new:var(--sev-2);"
                       "--c-leftover:var(--sev-3);--c-gap:var(--sev-4);--c-dup:var(--line);")

def load(name):
    return json.load(open(os.path.join(HERE, "extracted", f"extract-{name}.json")))

def frame(tok, title, lede, body):
    return (f'<div style="{tok}"><h2>{esc(title)}</h2>'
            f'<p style="color:var(--muted);max-width:75ch">{lede}</p>{body}</div>\n')

def write(name, text):
    with open(os.path.join(OUT, name), "w") as f:
        f.write(text)
    print("wrote", name, len(text))

# 1. pipeline diagram
runpy.run_path(os.path.join(HERE, "pipeline.py"), run_name="__main__")

# 2. closing order + outcome
board = load("board")["closing"]
BATCHES = ["isolation-reap-names", "release-confidence", "closing-keywords", "usage-accuracy",
           "opencode-observe-2", "acceptance-integrity", "plan-and-records", "gate-ordering",
           "forge-honesty", "verify-merge-false-landed", "ci-health", "housekeeping"]
prs = json.loads(subprocess.run(
    ["gh", "pr", "list", "-R", "derio-net/super-fr", "--state", "all", "--limit", "400",
     "--search", "batch in:head", "--json", "number,headRefName,state,mergedAt"],
    capture_output=True, text=True, check=True).stdout)
def find(prefixes):
    for p in prs:
        if p["headRefName"] in prefixes:
            return p
rows = []
for b in BATCHES:
    pr = find([f"fix/batch-{b}", f"feat/batch-{b}"])
    co = find([f"chore/closeout-fix-batch-{b}", f"chore/closeout-feat-batch-{b}"])
    pr_cell = (f'<a href="https://github.com/derio-net/super-fr/pull/{pr["number"]}">#{pr["number"]}</a> '
               f'{esc(pr["state"].lower())} {esc((pr["mergedAt"] or "")[:10])}') if pr else "—"
    co_cell = f'<a href="https://github.com/derio-net/super-fr/pull/{co["number"]}">#{co["number"]}</a>' if co else "—"
    rows.append(f"<tr><td><code>{esc(b)}</code></td><td>{pr_cell}</td><td>{co_cell}</td></tr>")
outcome = ('<h3>How it went</h3><table><thead><tr><th>Batch</th><th>PR</th><th>Close-out</th></tr></thead>'
           f'<tbody>{"".join(rows)}</tbody></table>'
           '<p style="color:var(--muted);font-size:13px">Looked up with <code>gh</code> when this fragment was built. '
           'The close-out of a batch that has none listed went through an archive PR instead (opencode-observe-2: #953).</p>')
write("closing-order.html", frame(
    "", "The 2026-10-02 closing order, and how it went",
    "Written on the board by hand after the talk (fr 5.0.1); the board itself has no place for it "
    "(<a href=\"https://github.com/derio-net/super-fr/issues/968\">#968</a>), so it lives here. "
    "The plan below is as published; the table after it is the outcome.", board + outcome))

# 3. origins analysis, 09-24 to 09-29
o = load("origins")
write("origins-2026-10-02.html", frame(
    ORIG_TOK, "Defect origins 09-24 → 09-29: the 2026-10-02 analysis",
    "The hand-built origins page's argument, as published. Its 142 classifications now sit in "
    "<code>origins.yaml</code> and feed the generated counts; the analysis below is frozen at 10-02.",
    "".join(o[k] for k in ["intro", "made", "live", "cut", "who", "reading", "method"])))

# 4. history: waves 1-9, take 10, the cut
a = load("architecture")
write("history-2026-10-02.html", frame(
    ARCH_TOK, "History to 2026-10-02: waves 1–9, take 10 and the cut",
    "The hand-built architecture page's sections, as published on 2026-10-02 (fr 5.0.1). "
    "Costs are <code>fr usage</code> figures captured then; nothing here is re-measured.",
    "".join(a[k] for k in ["intro", "one-phase", "wave1", "wave2", "wave34", "wave5", "wave6",
                           "walk", "wave79", "relay", "lean", "detours", "promises", "shipping"])))
