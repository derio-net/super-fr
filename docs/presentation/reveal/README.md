# The deck

`slides.md` is the source of truth for every word. `index.html` is generated
from it and is the file you open to present.

```bash
python3 build.py            # rebuild index.html after editing slides.md
python3 build.py --check    # what CI asks: is index.html current?
```

`tests/unit/test_tripwire_deck_fresh.py` fails if `index.html` is stale, so an
edit to `slides.md` that never got rebuilt cannot merge.

Open `index.html` directly — no server needed. `Esc` for the overview grid,
`S` for speaker view with the notes, `?` for all keys.

## Writing a slide

Slides are separated by `---` on its own line, and a slide's vertical detours
by `--`. Both are ignored inside fenced code blocks, so a YAML `---` in a
sample is safe.

```markdown
<!-- .slide: class="split" -->

<div class="col">
<div class="crumb">Stages &gt; <strong>Upgrades</strong> &gt; Run it</div>

## Slide title

- a point
- another point

<p class="nav"><a href="#/8/1">detail ↓</a></p>
</div>

<img class="side" src="../diagrams/up-cage.png" alt="">

Note: everything after `Note:` is speaker notes.
```

Raw HTML is welcome — that is how the two-column layout, breadcrumbs, side
portraits and detour links are expressed. Markdown handles the prose.

`<!-- .slide: ... -->` sets attributes on the slide (`class="split"`,
`class="title"`, `class="divider"`, `data-background-image="..."`).
`<!-- .element: class="chain" -->` on the line after a fenced block styles it
as an ASCII flow.

## Two traps this deck has already fallen into

**`Note:` must be last.** Reveal's notes separator is greedy — everything after
it becomes speaker notes. An `<img class="side">` placed below the note gets
swallowed into it, then renders inside a collapsed `<p>`, where
`img.side { width: 34% }` resolves to 34% of zero and the portrait silently
disappears. `build.py` refuses a slide shaped that way.

**Never hand-write `<section data-markdown>` without the `<script>` wrapper.**
The plugin reads `section.textContent` for an inline markdown slide, and by
then the browser has already parsed your raw HTML into elements, so every tag
is discarded — layout, images, links and slide classes all vanish at render
time while the deck still *looks* fine on screen. `build.py` always emits the
wrapper; the tripwire pins that it did.

## Navigation links

Detour links are absolute indices (`#/8/1` = 9th stack, 2nd vertical slide).
Adding or reordering a horizontal slide shifts every index after it, so
re-check the `<p class="nav">` links when you do.

## Files

| file | role |
|---|---|
| `slides.md` | all prose — **edit this** |
| `template.html` | the page shell: head, theme, `Reveal.initialize` |
| `build.py` | `slides.md` + `template.html` → `index.html` |
| `index.html` | generated — do not hand-edit |
| `theme-industrial.css` | the look |
| `vendor/reveal/` | pinned reveal.js runtime, so the deck works offline |
