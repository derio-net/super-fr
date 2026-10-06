# Captured fixtures for `fr.bindings`

Never composed by hand, with one labelled exception below.

- `opencode-models-verbose.txt` — `opencode models github-copilot --verbose`,
  captured 2026-10-06 from the real OpenCode CLI and trimmed to four whole
  blocks (header line plus its JSON object, unaltered). Provider is the public
  GitHub Copilot catalogue.
- `opencode-run-live.{stdout,stderr}` and `opencode-run-not-found.{stdout,stderr}` —
  the two streams of `opencode run --pure --print-logs --log-level ERROR --format
  json -m <model> "Reply with exactly: OK"`, captured 2026-10-06 from the real CLI (with `-m <model>`; fr itself now passes the one token `--model=<model>`)
  with stdin closed (`</dev/null`; with stdin left open the CLI waits on it
  forever). `live` is a model the provider serves; `not-found` is a model it no
  longer serves (`ProviderModelNotFoundError` with a `Did you mean` hint on stderr,
  an `UnknownError` event on stdout, exit 1).
- `opencode-run-not-supported.stderr` — **transcribed from super-fr#591, not
  captured here**: the retired-but-still-in-the-catalogue shape
  (`Error: The requested model is not supported.`).
