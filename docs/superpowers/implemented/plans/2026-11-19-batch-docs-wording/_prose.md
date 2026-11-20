# Docs, help and skill wording sweep (batch docs-wording)

Implements spec `2026-11-19-batch-docs-wording-design.md` (R1–R15) in three phases, one per ask:

1. **Help text and skill prose (R1–R10).** Help strings, hints and three skills say what the code does; a test guards Rich markup eating bracketed help; the CLI reference loses its writing-standard exemption; mirrors and the change fragment land here. Skeleton phase: its first task is the smoke.
2. **Site build and pages (R11–R13).** `fill_pages` fills the marker only on its own line; the build refuses a fence that does not render as a code block; four page fences are re-indented.
3. **Top bar (R14–R15).** Two rows on a phone, text aligned with the content, proven with screenshots at 320/390/1280 px.

Every phase ends with `fr docs check` clean and the full suite green, and moves its own acceptance rows. No member issue is a phase tracking issue.
