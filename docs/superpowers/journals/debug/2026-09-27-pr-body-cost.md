# Journal: 2026-09-27-pr-body-cost

<!-- fr:journal kind=repro scope=debug id=b871f47369cb created=2026-09-27T19:28:22+00:00 -->
### b871f47369cb · repro · deliver's PR Cost table shows only the first capture's steps

Seen on PR #678 (gh#680): the Cost table showed brainstorm 6 turns and '—' for every later step, while the usage file committed by the same deliver had turns for spec-review/plan/implement/deliver. Repro: a run whose usage file holds only a resolve:brainstorm capture, then render_pr_body at deliver — later steps render '—'.
