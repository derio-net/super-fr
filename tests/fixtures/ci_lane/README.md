# ci_lane fixtures

Captured 2026-11-24 from this repo's own `GET repos/derio-net/super-fr/actions/runs`
with `gh api`, projected with `jq` to the fields `scripts/ci_lane.py` reads (`id`, `name`,
`path`, `head_branch`, `head_sha`, `event`, `status`, `conclusion`, `run_attempt`):

- `runs_main_push.json` — `?head_sha=d52f788…&event=push&per_page=100`: the CI,
  Release and acceptance-report runs of one push to `main`.
- `run_pull_request.json` — `actions/runs/45430010148`: one CI run of a pull request.

No `fr-queue/**` run existed yet when these were taken, so the tests derive one from the
captured CI run by changing `head_branch` only (and `conclusion` or `id` where a case says).
