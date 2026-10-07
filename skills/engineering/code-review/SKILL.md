---
name: code-review
description: Review a branch, PR, or work-in-progress diff against a fixed point using two independent high-reasoning reviewers from different model families. Both reviewers check repository standards, spec compliance, correctness, design, security, and tests.
---

# Code Review

Review `git diff <fixed-point>...HEAD` with exactly two independent reviewers. Both inspect the same evidence and rubric, so agreement reflects independent reasoning rather than different task assignments.

## Reviewer pair

| Reviewer | Runtime | Model | Reasoning |
| --- | --- | --- | --- |
| OpenAI camp | OpenCode | `copilot-proxy-gpt/gpt-5.6-sol-high` | `--variant high` |
| Anthropic camp | Pi | `amazon-bedrock/us.anthropic.claude-opus-4-6-v1` | `high` |

Use fresh sessions and pin every field. Do not use aliases, default or weak models, a third reviewer, or two models from one camp. If either reviewer is unavailable, the review is incomplete.

## 1. Pin the target and evidence

Require a fixed point such as `main`, a tag, or a commit. Fail early on a bad ref, empty diff, or dirty repository. Commit the intended work before dispatch so content-sensitive mutation is detectable from HEAD; do not review staged or working-tree changes with this workflow.

```bash
set -e
REPO="<absolute-repository-path>"
FIXED="<fixed-point>"
RUN="$HOME/tmp/code-review/$(date -u +%Y%m%dT%H%M%SZ)-$$"
umask 077
mkdir -p "$RUN"
git -C "$REPO" rev-parse "$FIXED"
git -C "$REPO" log "$FIXED"..HEAD --oneline > "$RUN/commits.txt"
git -C "$REPO" diff --check "$FIXED"...HEAD
git -C "$REPO" diff "$FIXED"...HEAD > "$RUN/change.diff"
test -s "$RUN/change.diff"
git -C "$REPO" rev-parse HEAD > "$RUN/head.before"
git -C "$REPO" status --porcelain=v1 -uall > "$RUN/status.before"
test ! -s "$RUN/status.before"
```

Find the originating issue or spec and repository rules such as `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, and coding standards. Missing context is residual risk, not permission to invent requirements.

## 2. Give both reviewers one prompt

Save `"$RUN/prompt.md"` with paths to the diff, task/spec, repository rules, and current test results. End it with:

```text
Review only changes introduced by this diff, except where surrounding code is
needed to prove impact.

SPEC
- Every requirement and acceptance criterion is implemented.
- No unrequested behavior, scope creep, or missing user/error path.

STANDARDS AND ENGINEERING
- Repository rules and established local patterns are followed.
- Logic, boundaries, errors, concurrency, state, and data handling are correct.
- Interfaces remain minimal and compatible; migrations and rollout are safe.
- Dependencies point in the intended direction; abstractions have real callers.
- Security and realistic performance risks are addressed.
- Tests verify observable behavior, including relevant failure and boundary cases.

Report only material findings with confidence >= 80. Every finding needs
severity, confidence, axis, file:line, evidence, impact, and smallest useful fix.
Exclude tool-enforced style, speculative redesign, pre-existing issues, praise,
and generic advice. Do not edit, delegate, or invoke another review skill.
Your final line must be exactly one bare token with no prefix or Markdown: APPROVE, APPROVE-WITH-CHANGES, or REJECT
```

Run both deadline wrappers before waiting:

```bash
set -e
CODE_REVIEW_DIR="<absolute directory containing this loaded SKILL.md>"
RUNNER="$CODE_REVIEW_DIR/scripts/run_with_deadline.py"
VALIDATOR="$CODE_REVIEW_DIR/scripts/validate_review_outputs.py"
test -x "$RUNNER" && test -x "$VALIDATOR"

python3 "$RUNNER" \
  --name pi-anthropic --timeout-seconds 600 --progress-seconds 120 \
  --status-file "$RUN/pi.status.json" \
  --stdout-file "$RUN/pi-anthropic.md" --stderr-file "$RUN/pi-anthropic.err" -- \
  env PI_CODING_AGENT_DIR="$HOME/.pi/review-agent" \
  pi --no-session --no-context-files --no-skills --no-extensions \
    --no-prompt-templates --tools read,grep,find,ls \
    --provider amazon-bedrock --model us.anthropic.claude-opus-4-6-v1:high -p \
    @"$RUN/prompt.md" "Review the repository at $REPO." &
pi_pid=$!

python3 "$RUNNER" \
  --name opencode-openai --timeout-seconds 600 --progress-seconds 120 \
  --status-file "$RUN/opencode.status.json" \
  --stdout-file "$RUN/opencode-openai.md" \
  --stderr-file "$RUN/opencode-openai.err" -- \
  opencode run "Follow the attached review prompt." \
    --pure --agent plan \
    -m copilot-proxy-gpt/gpt-5.6-sol-high --variant high \
    --dir "$REPO" -f "$RUN/prompt.md" </dev/null &
oc_pid=$!

set +e
wait "$pi_pid"; pi_status=$?
wait "$oc_pid"; oc_status=$?
set -e
printf 'pi=%s opencode=%s\n' "$pi_status" "$oc_status"
python3 "$VALIDATOR" --require-verdict APPROVE \
  --review pi-anthropic "$RUN/pi.status.json" "$RUN/pi-anthropic.md" \
  --review opencode-openai "$RUN/opencode.status.json" "$RUN/opencode-openai.md"
```

Pi is read-only. OpenCode's plan agent denies edits but can still invoke shell commands. Detect reviewer mutation instead of assuming safety:

```bash
git -C "$REPO" rev-parse HEAD > "$RUN/head.after"
git -C "$REPO" status --porcelain=v1 -uall > "$RUN/status.after"
cmp "$RUN/head.before" "$RUN/head.after"
cmp "$RUN/status.before" "$RUN/status.after"
```

Any repository mutation, timeout, empty output, malformed response, or missing verdict fails that reviewer.

## 3. Reconcile, do not vote

Verify every material claim against the diff and source. One reviewer can catch a real blocker. Agreement is signal, not proof. Produce a neutral synthesis with consensus, unique verified findings, disagreements, rejected findings, and final verdict.

For non-personal repositories, keep runtime, provider, model, and reviewer names out of commits, PRs, issues, branches, code, and repository-visible review files. Keep named raw artifacts under `~/tmp`.

Only plain `APPROVE` passes. After fixes, rerun both fresh reviewers against the updated diff. Do not loop on subjective nits.

## Completion

Both pinned model families ran at high reasoning under hard deadlines; neither changed the repository; every retained finding has source evidence; relevant tests passed or their absence is explicit; and both reviewers returned plain `APPROVE` on the current revision.
