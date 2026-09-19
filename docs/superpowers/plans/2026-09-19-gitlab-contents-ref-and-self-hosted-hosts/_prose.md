# GitLab contents `ref` and self-hosted host targeting

Spec: `docs/superpowers/specs/2026-09-19-gitlab-contents-ref-and-self-hosted-hosts-design.md`
Issue: [super-fr#486](https://github.com/derio-net/super-fr/issues/486)

## What this plan is really fixing

Not one bug — one **failure of evidence**, which produced three bugs.

`RealGlabClient.file_exists` and `.read_file` omitted GitLab's mandatory `ref`
query parameter. They therefore failed against every real GitLab instance, and
the unit suite was green the whole time, because every mock in
`tests/unit/test_real_glabclient.py` is `lambda args: <json>` — the mock
**discards the request**. The tests asserted that the code calls the function
it calls.

Then `file_exists` made it worse by design: it caught every `GlabError` and
returned `False`, so a **400 was indistinguishable from an absent file**. The
fail-soft posture that is right for a genuine 404 turned a protocol bug into a
wrong answer, silently, in the direction callers trust.

And underneath both, `.devcontainer/fr-profiles.yaml`'s `host:` key — written
by `fr init scaffold --host`, read back by `_hosts.host_for`, unit-tested three
ways — is consumed by **nothing**. A dead last mile, so a self-hosted GitLab
shop had no supported route at all.

The acceptance matrix said `status: ci` for all of it.

## The discipline this plan is built around

Every phase either **asserts the request** or **runs against a real instance**.
That is not extra rigor; it is the specific gap that let this ship.

- Phase 1 exists to build `_CapturingGlab` and retrofit the arg-blind mocks.
  The test that proves the fix is a test that can *see the URL*.
- Phase 2's `list_dir` change is gated on live proof **before** it is kept: the
  tree endpoint works today without a `ref`, and a working call is not changed
  on a hunch (P2.T2.S1 will skip P2.T2.S2 if the live check disagrees).
- Phase 3's `is_not_found` patterns are pinned to strings **captured from
  glab 1.89.0 against the live instance**, not composed from documentation:

  ```
  400  glab: HTTP 400\n{"error":"ref is missing, ref is empty"}
  404  glab: 404 File Not Found (HTTP 404)\n{"message":"404 File Not Found"}
  404  glab: 404 Project Not Found (HTTP 404)\n{"message":"404 Project Not Found"}
  404  glab: 404 invalid revision or path Not Found (HTTP 404)\n{"message":...}
  401  ERROR\n\n  Unauthenticated.
  ```

  Two things follow from having the real strings. The `Unauthenticated.` case
  carries **no HTTP code at all**, so a code-sniffing predicate would have
  mis-filed it. And the patterns are anchored on `http 404` / `"message":"404 `
  rather than a bare `"404"`, because the probed path is echoed in some glab
  errors and `errors/404.md` would otherwise make a genuine 400 read as absent
  — the very bug class being closed.

  A third thing is a relief rather than a task: glab writes the API's error
  body to **both** stdout and stderr, so `GlabError.stderr` already carries
  `{"error":"ref is missing, ref is empty"}`. A propagated error is diagnosable
  with no change to `_run_glab`'s message.
- Phase 6 does the thing the issue insisted on: live proof in the PR, including
  an **idempotent second `fr apply`** (the first apply proves writes work; the
  second proves `observe`/`diff` read GitLab's shapes correctly) and a full
  account of every object created and removed on the operator's instance.

## Order, and why

Phases 2, 3 and 4 all depend only on Phase 1, so they are independent of each
other — Phase 1 is the shared harness, not a queue. Phase 5 needs Phase 4's
`declared_host`/`host_for` split to warn correctly. Phase 6 needs 2, 3 and 5:
it cannot verify what has not shipped, and it must run against the version the
PR will contain, docs and version bump included.

## Two decisions worth re-reading before you start

**The warning fires only for a DECLARED host.** With `host_for` falling back to
the git remote, a GitHub Enterprise repo resolves a host for a backend fr does
not thread — and works perfectly, because `gh` derives the same host itself.
Warning there would nag about a correct configuration. So provenance matters,
`_hosts` exposes `declared_host` beside `host_for`, and the warning lives in
`client_for` (the only layer that knows the difference) rather than in
`client_for_backend` (which must stay blind, so `fr_vk.pr_observe` deriving a
host from a PR URL stays silent).

**`GITLAB_HOST`, not `--hostname`.** Verified live: `glab api` accepts
`--hostname`, `glab label create` does not. Only the environment variable is
honoured by every subcommand, so it is the only mechanism that can cover all of
`fr.glab`'s call sites. It is built per `subprocess.run` call and never assigned
to `os.environ`, so one repo's host cannot leak into another's call in the same
process.

## No manual phase, and why that is a change

fr-plan normally back-loads manual work into a `[manual]` phase. There is none
here: the operator chose (spec §3 d1) to have the live verification run
**inside** the pipeline against a project they named, rather than owing it as a
manual step after the PR. That is what lets the acceptance row move on evidence
in the same PR as the fix — and it is the direct answer to the issue's
complaint that "unit-level evidence was accepted for an integration claim".

The one sanctioned mutation is enabling Issues on that project, which P6.T2.S1
records and P6.T2.S4 restores.

## What this plan deliberately does NOT do

- **`fr.gh` / GitHub Enterprise.** No host threading. There is no evidence of a
  GHE user, `fr.gh` is the highest-traffic module in the package, and churning
  it without proof is exactly how this bug got in. `client_for` warns instead.
- **Gitea.** Out of scope per the issue. `tea` stays explicitly unproven.
- **`fr_dispatch.reachability`'s error rendering.** `_missing_remotely` now lets
  a non-404 propagate, and the gate has no caller that would render it
  (`apply_cmd.py:141` passes no `gh=`; `check_reachable` is test-only). P3.T3.S2
  records this as an **open** plan-journal finding rather than fixing an absent
  caller.
- **Ticking the 2026-07-09 plan's Phase 9.** Its Task 1 also asks for MR-linking
  verification (`list_linked_prs` against a real MR), which this spec does not
  cover. The GitLab contents and Issue-tracking halves will be proven; the step
  stays unticked, and the residue is recorded so a later session can close it
  honestly instead of inheriting a half-true tick.
