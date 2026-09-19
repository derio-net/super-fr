# Third-party privacy — evidence without identity

Adapted from `derio-net/frank`'s `agents/rules/third-party-privacy.md`, which
states the principle:

> Any org or repo hosted or handled by Frank that lives outside the `derio-net`
> GitHub org is third-party (private, customer, partner). Treat as such — don't
> volunteer details about contents, business logic, or structure beyond what's
> already documented in this repo.

super-fr needs a longer version, because it has a leak vector frank does not:
**its own skills capture live evidence, and this repo is public.**

## Why this repo is different

`fr-goal`, `fr-debugging` and `fr-acceptance` are built on the principle that a
claim is worthless until a real system confirms it. That is correct, and it is
exactly how third-party detail gets in. Live verification produces transcripts,
and those transcripts land in artifacts that are **committed and pushed**:

| Surface | What leaks |
|---|---|
| spec `## Background` | "verified live against `<host>`" |
| plan step notes (`fr plan edit --tick --note`) | pasted command output |
| journals (`fr journal add`) | findings quoting real URLs |
| captured test fixtures | error strings carrying the API host |
| `docs/acceptance/matrix.yaml` notes | "live-verified against `<host>`" |
| the three generated acceptance reports | whatever the notes said |
| **PR bodies** | the whole transcript |
| **commit messages** | the hardest to scrub afterwards |

The operator's employer, a customer's instance, a partner's repo: none of it
belongs in a public tool repo, however incidentally it arrived.

## The rule

**Redact at capture time, not later.** The moment you paste real output into an
artifact, replace the identity and keep the shape. An artifact that reached a
commit has already been pushed by the time anyone reads it back.

Third-party means anything outside the `derio-net` org: an employer's GitLab, a
customer's Gitea, a partner's repo, a colleague's account. The operator's own
public `derio-net` identity is not third-party.

### Keep the shape, drop the identity

A captured fixture is evidence of an API's **shape** — the status code, the
JSON envelope, the route, the wrapping. None of that requires the real host.

```
redact                          keep
──────────────────────────────  ────────────────────────────────────────────
instance hostname               `glab: HTTP 400`
org / group / namespace         `{"error":"ref is missing, ref is empty"}`
repo or project name            `/-/work_items/<n>` as a route shape
usernames, display names        rich's box padding and mid-phrase wrapping
internal ticket ids, URLs       status codes, header names, field names
```

Use RFC 2606 reserved names so a reader can tell at a glance that it is
fictional: `example.com`, `example.org`, `.example`, `.invalid`, `.test`. This
repo's existing test fixtures already use `gitlab.corp`, `gitlab.local.corp` and
`gitlab.mycorp.com`; those stay, but new redactions should prefer the reserved
forms.

State the redaction rather than hiding it. "Captured live 2026-09-19 against a
self-hosted GitLab (host redacted)" is honest evidence. Silently rewriting a
transcript so it *looks* captured is the fixture-composition defect this repo
already has a rule-shaped scar from.

### Scope discipline

Do not volunteer a third party's structure, business logic, project names or
internal conventions beyond what the technical point requires. "A self-hosted
GitLab whose default branch is `master`" is the whole technically-relevant fact
about the instance that proved `ref=HEAD`. Its hostname proves nothing extra.

## If it already leaked

Ordered by what actually reduces exposure:

1. **Scrub the working tree** — every tracked file, including generated ones.
   Regenerate derived artifacts (`fr acceptance report --deterministic`) rather
   than hand-editing them.
2. **Edit the PR body** (`gh pr edit --body-file`), which is served immediately
   and is usually the most-read surface.
3. **Rewrite the commit messages** if they carry it, and force-push with
   `--force-with-lease`. Keep a local backup ref; never push the backup.
4. **Know the limit, and say it out loud.** A force-push does *not* unpublish.
   GitHub keeps the orphaned commits reachable by SHA — the PR timeline even
   records the old SHA — until they are garbage-collected, which for a public
   repo may need GitHub Support. Deleting the branch and closing the PR helps;
   nothing short of support makes it certain. Tell the operator this rather
   than letting a green scrub imply more than it achieved.

A scrub that reports success while the data is still reachable is the same
defect class as a test that asserts the code calls the function it calls.

## Enforcement

**Prose only, today — there is no tripwire.** Stated plainly because this repo's
convention is that standing rules are enforced by tests, and this one is not
yet.

A tripwire is buildable but needs a design decision first: it would flag
private-looking hostnames (`.local`, `.internal`, `.corp`, RFC 1918 literals) in
tracked docs and tests, and that requires a curated allowlist of the fictional
names the repo legitimately uses — otherwise it fires on `gitlab.corp` in the
existing fixtures. Worth doing; not worth guessing at.

Until then the checks are human: before `git commit`, grep your diff for the
host you actually ran against.
