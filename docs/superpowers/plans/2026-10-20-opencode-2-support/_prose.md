# Approach

The work is one port with five reviewable slices. The plugin is restored first,
because every other OpenCode surface sits on it and because a broken entrypoint
makes every later claim untestable. The shell gate follows the edit gate rather
than joining it: it is a new enforcement surface with its own drift risk (two
decision engines), and it needs the pipeline sentinel to exist before it can do
anything. The status line is third because it is the only piece whose delivery
mechanism is unproven — a TUI entrypoint that OpenCode will not load without
consumer-side peer packages is a real possibility, and the phase is written so
that outcome is a recorded decision rather than a silent failure. The readers
are fourth because they are independent of the plugin: `fr` must read 2.0's
store whether or not the plugin is installed, and the loud 1.x refusal is what
keeps the V2-only choice honest. Parity, the matrix, the prose and the release
fragment close the plan, because they must describe what actually shipped.

Phase 1 carries the one genuinely unknown premise: where V2's session id
comes from. The plan measured it in a real binary before anything depended on
it and found the answer was already there — OpenCode 2 sets
`OPENCODE_SESSION_ID` on every command it spawns, naming the issuing session —
so the designed correlation queue was built, measured redundant, and deleted
in the same phase (spec R6/§C record the measurement). The stated failure
outcome stays "export nothing and say so", never a guess, because
`deliver-tests-provenance` trusts the attribution.

Two engines decide the shell gate after phase 2 (the shipped bash script and
the TypeScript port). They are held together by one verdict table captured from
the bash script by running it, loaded by both test suites. A change to one that
is not a change to both goes red.

Nothing here changes `fr isolation`, the marker, the sentinel's JSON shape or
the run cursor. The plugin is transport; the artifacts stay put.
