// Section extractor for the 2026-10-02 hand-built pages (authored-src/old/*.html).
// Serve the folder (python3 -m http.server), open a page in a browser and evaluate:
//   (async () => { const f = <this function>; return await f(PICK); })()
// with PICK, per page (what build.py expects in extracted/extract-<page>.json):
//   architecture: {"intro":{"sel":"header"},"one-phase":{"sel":"#one-phase"},"wave1":{"sel":"#wave1"},
//     "wave2":{"sel":"#wave2"},"wave34":{"sel":"#wave34"},"wave5":{"sel":"#wave5"},"wave6":{"sel":"#wave6"},
//     "walk":{"sel":"#walk"},"wave79":{"sel":"#wave79"},"relay":{"sel":"#relay"},
//     "promises":{"h2":"What the Next page promised"},"lean":{"h2":"The first lean run"},
//     "detours":{"h2":"Fewer detours"},"shipping":{"h2":"Where the shipping went"}}
//   origins: {"intro":{"sel":"header"},"made":{"h2":"Regressions:"},"live":{"h2":"Six closed fixes"},
//     "cut":{"h2":"The input layer answered"},"who":{"h2":"87% came from"},
//     "reading":{"h2":"A filing and first-release"},"method":{"h2":"How this was classified"}}
//   board: {"closing":{"sel":"section.cp"}}
// It returns {key: html}: each picked section after the page's own script ran, with every
// stylesheet declaration that matches an element copied into its style attribute (var()
// references kept, so the target page's tokens still drive light and dark), and classes,
// scripts, buttons and inputs removed.
async (PICK) => {
  const rules = [];
  const walk = (list, inDark) => { for (const r of list) {
    if (r.type === 1) { if (!inDark && !/^(:root|\*|html|body)/.test(r.selectorText)) rules.push(r); }
    else if (r.cssRules) walk(r.cssRules, inDark || /dark/.test(r.conditionText || r.media?.mediaText || ''));
  } };
  for (const s of document.styleSheets) { try { walk(s.cssRules, false); } catch (e) {} }
  const inline = (root) => {
    for (const el of [root, ...root.querySelectorAll('*')]) {
      let decl = '';
      for (const r of rules) {
        let ok = false;
        try { ok = el.matches(r.selectorText); } catch (e) {}
        if (ok) decl += r.style.cssText + ';';
      }
      if (decl) el.setAttribute('style', decl + (el.getAttribute('style') || ''));
    }
  };
  const out = {};
  for (const [key, how] of Object.entries(PICK)) {
    let nodes = [];
    if (how.sel) nodes = [...document.querySelectorAll(how.sel)];
    if (how.h2) nodes = [...document.querySelectorAll('section')].filter(s => (s.querySelector('h2')?.textContent || '').startsWith(how.h2));
    out[key] = nodes.map(n => { inline(n); const c = n.cloneNode(true);
      c.querySelectorAll('script,button,input,.filters,[role=group]').forEach(x => x.remove());
      c.querySelectorAll('[class]').forEach(x => x.removeAttribute('class'));
      c.removeAttribute('class'); c.removeAttribute('id');
      c.querySelectorAll('[id]').forEach(x => { if (x.tagName !== 'marker' && !x.closest('defs')) x.removeAttribute('id'); });
      return c.outerHTML; }).join('\n');
  }
  return out;
}
