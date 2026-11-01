#!/usr/bin/env bash
# Row fr-ops-gate-probes: `fr ops gate` stage 1 refuses an ops gap (spec
# 2026-11-01-ops-gate-probes R5) — a devops-gated run whose Test Plan carries command
# steps and whose plan declares no op — before any workspace exists, and a `none:`
# acknowledgement in the plan's ops.yaml (R4) lets it past the check.
#
# Credential free and forge free: the same harness as fr-ops-gate-stage.sh (host-worktree
# mode, a fake forge inside a driver running the candidate's own python, a local bare
# origin reached by a `file://localhost/...` URL). The driver below is that scenario's,
# narrowed to one PR (#7).
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

work="$(mktemp -d)"
export HOME="$work/home" MARKS="$work/marks" FR_OPS_TRUST_DIR="$work/trust" FR_OPS_GATE_DIR="$work/gate"
export FR_ISOLATION_TARGET=worktree FR_PROFILE=ops KUBERNETES_SERVICE_HOST=10.0.0.1
mkdir -p "$HOME" "$MARKS" "$FR_OPS_TRUST_DIR"
py="$(candidate_python)"
ORIGIN="$work/derio-net/fixture.git"

# --- smoke: the candidate runs and carries the gate ----------------------------------
run_fr out --version
require_exit 0 "$out"
run_fr out ops gate --help
require_exit 0 "$out"
expect_grep '--run' "$out" "fr ops gate takes --run"

git init -q --bare "$ORIGIN" || fail "bare origin"
git init -q . && git symbolic-ref HEAD refs/heads/main || fail "git init"
git remote add origin "file://localhost$ORIGIN"
mkdir -p .devcontainer .fr docs/superpowers/specs
cat > .devcontainer/fr-profiles.yaml <<'YAML'
schema_version: 2
profiles:
  ops: {purpose: operate, secrets: [], ops: true}
default: ops
forge: {type: github}
tracking: {type: none}
YAML
printf 'env_passthrough: [MARKS]\n' > .fr/ops.yaml
"$py" - <<'PY' || fail "could not write the matrix"
from pathlib import Path
from fr.artifacts.registry import ARTIFACT_KINDS
path = Path("docs/acceptance/matrix.yaml")
path.parent.mkdir(parents=True, exist_ok=True)
version = ARTIFACT_KINDS["matrix"].current_version
path.write_text(f"schema_version: {version}\norg: derio-net\nrepo: fixture\nrows: []\n")
PY
run_fr out init validator-wrapper
require_exit 0 "$out"
git add -A && git commit -qm base && git push -q origin main || fail "seed main"
git remote set-head origin main || fail "origin/HEAD"

# --- the delivered feature: devops-gated, a command step, a plan with no op ------------
git switch -q -c feat/x
mkdir -p docs/superpowers/plans/g
cat > docs/superpowers/specs/2026-11-01-g-design.md <<'MD'
# Fixture

## Verification

strategy: none
gate: devops

## Test Plan

- converge the stack with `pulumi up --yes`
- [tester] click the page with `make check`
MD
printf 'the plan folder, with no ops carrier\n' > docs/superpowers/plans/g/README.md
"$py" - <<'PY' || fail "could not write the run cursor"
from pathlib import Path
from fr.run.model import RunState, StepRecord, save_run_state
save_run_state(Path.cwd(), RunState(
    run="run-g", workflow="fr-goal@1", branch="feat/x",
    started="2026-11-01T00:00:00+00:00", cursor="deliver",
    steps={
        "brainstorm": StepRecord(state="done", emitted={"spec": "docs/superpowers/specs/2026-11-01-g-design.md"}),
        "plan": StepRecord(state="done", emitted={"plan": "docs/superpowers/plans/g"}),
        "deliver": StepRecord(state="done", emitted={"pr": "https://github.com/derio-net/fixture/pull/7"}),
    }))
PY
git add -A && git commit -qm feature && git push -q origin feat/x || fail "push the feature"

# gate <run> <answers…>: `fr ops gate --run <run> --yes` against the fake forge, the
# operator answering each terminal question in turn (y = confirm; text = a step's outcome).
cat > "$work/drive.py" <<'PY'
import json, os, subprocess, sys
from pathlib import Path

from typer.testing import CliRunner

from fr.cli import app
from fr.commands import archive_cmd, gate_cmd, ops_gate_cmd
from fr.triage import gitseam

work = Path(os.environ["WORK"])
run_id, answers = sys.argv[1], list(sys.argv[2:])
MINE = {"run-g": 7, "run-h": 8}[run_id]
state_file = work / "forge.json"
prs = json.loads(state_file.read_text())


def save():
    state_file.write_text(json.dumps(prs))


class Forge:
    def _pr(self, n):
        return prs[str(n)]

    def pr_view(self, repo, n):
        p = self._pr(n)
        return {**p, "draft": False, "mergeable": "MERGEABLE", "title": "t", "body": "b"}

    def default_branch(self, *, cwd, run=None):
        return "main"

    def pr_required_checks(self, repo, n):
        return [{"name": "ci", "bucket": "pass"}]

    def pr_checks(self, repo, n):
        return [{"name": "ci", "bucket": "pass"}]

    def repo_merge_methods(self, repo):
        return {"default": "merge", "allowed": ["merge"]}

    def pr_merge(self, repo, n, *, head_sha, method):
        p = self._pr(n)
        assert p["head_oid"] == head_sha, "merged a head the stage did not pin"
        subprocess.run(["git", "--git-dir", os.environ["ORIGIN"], "update-ref",
                        "refs/heads/main", head_sha], check=True)
        p["state"] = "MERGED"
        p.setdefault("events", []).append("merged")
        save()

    def open_pr_for_head(self, repo, branch):
        return prs.get("housekeeping", {}).get(branch)

    def pr_create(self, repo, *, head, base, title, body):
        prs.setdefault("housekeeping", {})[head] = {"number": 9, "url": "u"}
        save()
        print(f"FAKE-FORGE pr_create head={head} base={base}")
        return 9

    def pr_for_branch(self, branch, cwd=None, run=None):  # verify-merge's lookup
        p = self._pr(MINE)
        return {"state": p["state"], "url": "u", "mergedAt": "2026-10-22T12:00:00Z"}

    def edit_pr_labels(self, repo, n, *, add, remove):
        p = self._pr(n)
        p["labels"] = sorted((set(p["labels"]) | set(add)) - set(remove))
        save()

    def list_issue_comments(self, repo, n):
        return []

    def ensure_labels(self, repo, names):
        pass

    def comment_pr(self, repo, n, body):
        print(f"FAKE-FORGE comment #{n}: {body}")


class Prompt:
    def confirm(self, text):
        print(f"PROMPT {text.splitlines()[0]}")
        return (answers.pop(0) if answers else "y") == "y"

    def ask(self, text):
        print(f"ASK {text.splitlines()[0]}")
        if os.environ.get("DRIFT_ON_ASK"):  # the world moves while the operator walks a step
            (Path(os.environ["MARKS"]) / "drift").touch()
        return answers.pop(0) if answers else ""


def in_process(args, cwd, *, terminal=False):
    if args[:2] == ["isolation", "exec"]:  # the ops run as real processes in the workspace
        done = subprocess.run(["fr", *args], cwd=cwd, stdout=subprocess.PIPE, text=True)
        return done.returncode, done.stdout
    here = os.getcwd()
    os.chdir(cwd)
    try:
        result = CliRunner().invoke(app, list(args))
    finally:
        os.chdir(here)
    sys.stdout.write(result.output)
    if result.exception and not isinstance(result.exception, SystemExit):
        raise result.exception
    return result.exit_code, result.stdout


forge = Forge()
ops_gate_cmd._interactive = lambda: True
ops_gate_cmd._forge = lambda url: forge
ops_gate_cmd._prompt = lambda: Prompt()
gate_cmd.client_for_url = lambda url: forge
archive_cmd._make_gh_client = lambda: forge
import fr.isolation.local as isolation_local  # noqa: E402

isolation_local.client_for = lambda cwd: forge
gitseam.run_this_fr = in_process
result = CliRunner().invoke(app, ["ops", "gate", "--run", run_id, "--yes"])
print(result.output)
if result.exception and not isinstance(result.exception, SystemExit):
    raise result.exception
sys.exit(result.exit_code)
PY
forge_at() {  # forge_at <head sha>: the fake PR #7, open, at that head
  printf '{"7": {"state": "OPEN", "head_oid": "%s", "head_ref": "feat/x", "base_ref": "main", "labels": ["gate:devops"]}}\n' "$1" > "$work/forge.json"
}
export WORK="$work" ORIGIN
gate() { local __out; __out="$(unset CI; "$py" "$work/drive.py" "$@" 2>&1)"; RC=$?; OUT="$__out"; }

# --- the ops gap: stage 1 refuses before any workspace exists (R5) ---------------------
forge_at "$(git rev-parse HEAD)"
gate run-g
require_exit 2 "$OUT"
expect_grep 'ops gap' "$OUT" "stage 1 names the ops gap"
expect_grep 'step 1: `pulumi up --yes`' "$OUT" "the refusal names the step and its command"
expect_grep 'fr ops stub' "$OUT" "the refusal names fr ops stub"
expect_grep 'none:' "$OUT" "the refusal names the none: acknowledgement"
refuse_grep 'make check' "$OUT" "a [tester] step was counted"
refuse_grep 'ops workspace chore/ops-g up' "$OUT" "an ops workspace was brought up"
[ "$(git worktree list | wc -l | tr -d ' ')" = 1 ] || fail "a worktree exists: $(git worktree list)"

# --- `none:` on the PR branch lets stage 1 past the check (R4) -------------------------
printf 'schema_version: 2\nnone: the stack is converged by hand on purpose\n' > docs/superpowers/plans/g/ops.yaml
git add -A && git commit -qm "ops: none" && git push -q origin feat/x || fail "push the acknowledgement"
forge_at "$(git rev-parse HEAD)"
# (the op set's trust grant is the next check, and no grant is written here: stage 1 stops
# there, past the gap check, which is all this asserts)
gate run-g
refuse_grep 'ops gap' "$OUT" "a none: acknowledgement is still refused"
expect_grep 'ops workspace chore/ops-g up' "$OUT" "stage 1 brings the workspace up past the gap check"

# --- a pointed step is probed; the grammar re-prompts an unpointed one (R8, R10) ---------
mkdir -p docs/superpowers/plans/h
cat > docs/superpowers/specs/2026-11-01-h-design.md <<'MD'
# Fixture

## Verification

strategy: none
gate: developer

## Test Plan

- [devops] (op: good) converge the stack
- [devops] look at the dashboard
- [devops] (op: bad) confirm nothing drifted
MD
cat > docs/superpowers/plans/h/ops.yaml <<'YAML'
schema_version: 2
ops:
  - id: good
    summary: converge
    phase: post-merge
    ready: 'true'
    check: 'test -f "$MARKS/good" && { echo checking the stack; echo converged 3 of 3; }'
    apply: 'touch "$MARKS/good"'
  - id: bad
    summary: no drift
    phase: post-merge
    check: 'test -f "$MARKS/applied" && ! test -f "$MARKS/drift" || { echo drift found; false; }'
    apply: 'touch "$MARKS/applied"'
YAML
"$py" - <<'PY' || fail "could not write the run cursor"
from pathlib import Path
from fr.run.model import RunState, StepRecord, save_run_state
save_run_state(Path.cwd(), RunState(
    run="run-h", workflow="fr-goal@1", branch="feat/x",
    started="2026-11-01T00:00:00+00:00", cursor="deliver",
    steps={
        "brainstorm": StepRecord(state="done", emitted={"spec": "docs/superpowers/specs/2026-11-01-h-design.md"}),
        "plan": StepRecord(state="done", emitted={"plan": "docs/superpowers/plans/h"}),
        "deliver": StepRecord(state="done", emitted={"pr": "https://github.com/derio-net/fixture/pull/8"}),
    }))
PY
git add -A && git commit -qm "feature h" && git push -q origin feat/x || fail "push feature h"
HEAD_H="$(git rev-parse HEAD)"
"$py" - <<'PY' || fail "could not write the trust grant"
from pathlib import Path
from fr.ops.load import load_ops, load_ops_config
from fr.ops.trust import fingerprint, grant_trust, head_tree, tree_digest
root = Path.cwd()
tree = head_tree(root)
ops = load_ops(root / "docs/superpowers/plans/h", root).ops
fp = fingerprint(ops, load_ops_config(root), root, code_tree=tree_digest(tree))
grant_trust(root, "h", fp, tree=tree)
PY
git reset -q --hard "$HEAD_H" && git clean -fdq
printf '{"8": {"state": "OPEN", "head_oid": "%s", "head_ref": "feat/x", "base_ref": "main", "labels": ["gate:devops"]}}\n' "$HEAD_H" > "$work/forge.json"
# stages 1-4 run unprompted but for the merge; stage 5: the pointed `good` step is probed
# (no question), the dashboard step is answered `ran` (re-prompted) then `ran: walked`, the
# world drifts while it is walked, and the pointed `bad` step is answered `owed`.
DRIFT_ON_ASK=1 gate run-h y y y "ran" "ran: walked" "owed drift to chase"
expect_grep 'stage 4 \(post-merge ops\): done' "$OUT" "stage 4 closes the post-merge ops"
expect_grep 'stage 5 \(devops steps\): done' "$OUT" "stage 5 completes"
refuse_grep 'ASK Test Plan step 1' "$OUT" "the passing pointed step was asked about"
expect_grep 'converged 3 of 3' "$OUT" "the probe's output is shown"
expect_grep "Not understood: 'ran'" "$OUT" "a bare keyword is re-prompted"
expect_grep 'ASK Test Plan step 2' "$OUT" "the unpointed step is asked"
expect_grep 'drift found' "$OUT" "the failing probe's reason is shown"
expect_grep 'stage 6 \(gate pass\) failed' "$OUT" "the owed pointed step stops stage 6"

echo "ok: fr-ops-gate-probes"
