# Seed prompt — run C (plain + an explicit planning pass)

Identical to `goal.md`, plus one instruction. That single added paragraph is
the whole treatment difference between run B and run C: no fr tooling, no
artifacts on disk, just an instruction to plan first.

---

Implement issue #429 in this repository (derio-net/super-fr):
"fr acceptance and fr journal can create state but not update it — statuses and
finding states are effectively immutable".

The issue body is the brief; read it from GitHub. #431 is a duplicate of it and
should be closed by the same work.

Before writing any implementation code, produce a written implementation plan:
the design decisions you are making and why, the phases you will work in, and
what you will test. Ask me about anything genuinely ambiguous, then wait for my
go-ahead before implementing.

Deliver it as a pull request against main.
