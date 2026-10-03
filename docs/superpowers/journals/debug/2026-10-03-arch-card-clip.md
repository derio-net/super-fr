# Journal: 2026-10-03-arch-card-clip

<!-- fr:journal kind=repro scope=debug id=6002fa93f6f6 created=2026-10-03T21:02:52+00:00 -->
### 6002fa93f6f6 · repro · Subsystem card content overflows its card at 400px on a long unbreakable title

Rendered the architecture page (test fixture `_page()`) with three issue titles carrying a 120-char unbreakable test-name token, then measured it in headless Chrome at a 400x800 viewport. The `Other` card is 366px wide with a 972px scrollWidth, and `main` is 989px wide in a 400px viewport. `html { overflow-x: hidden }` stops the page scrolling, so the title is clipped instead. This matches #901 (454px of content in a 366px card).
