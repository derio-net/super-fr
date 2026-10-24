<!-- fr:journal-schema=3 -->
# Journal: opencode-v2-recovery-launch

<!-- fr:journal kind=repro scope=debug id=root-model-flag-rejected created=2026-10-24T11:58:46+00:00 -->
### root-model-flag-rejected · repro · OpenCode 2.1.4 rejects the managed recovery launch flags

Host OpenCode v2.1.4 reproduces the recovery-launch failure: `opencode --model openai/gpt-6.1-sol --auto --fr-probe-unsupported-option` exits 1 with `Unrecognized flag: --model in command opencode`. Its `mini --help` exposes --model but not --auto; `mini --model ... --auto` rejects --auto. Pinned fr-herdr launch_args emits [--model, model, --auto] and runner passes that after `herdr agent start ... --`, producing the rejected root command. No prompt/session or auth was used. V2 CLI docs: https://opencode.ai/v2/docs/cli/ and https://opencode.ai/v2/docs/cli/commands/ . Isolated environment initially lacked opencode; installed official pinned 2.1.4 in disposable container to continue.
