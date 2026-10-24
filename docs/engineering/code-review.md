## What it does

`code-review` checks a declared diff against its spec and repository standards.
A fresh, read-only Pi reviewer uses direct GitHub Copilot GPT-6.1 SOL with high
reasoning. It does not use OpenCode or silently switch providers or models.

Every retained finding needs concrete evidence, impact, and a useful fix. Style
already enforced by tools, speculative redesigns, pre-existing problems, and
generic advice are excluded.

## When to reach for it

Type `/code-review`, or the agent reaches for it automatically when you ask to
review a branch, PR, explicitly scoped work in progress, or changes "since X".

| Situation | Reach for |
| --- | --- |
| A diff exists and you want spec plus engineering review | `code-review` |
| Nothing is written and you want test-first implementation | [tdd](https://aihero.dev/skills-tdd) |
| A whole spec needs implementing and reviewing | [implement-spec](https://aihero.dev/skills-implement-spec) |
| The whole codebase needs architectural improvement | [improve-codebase-architecture](https://aihero.dev/skills-improve-codebase-architecture) |
| A failure needs diagnosis before review | [diagnosing-bugs](https://aihero.dev/skills-diagnosing-bugs) |

## Prerequisites

Supply a fixed point such as `main`, a tag, or a commit, plus a declared scope.
The skill resolves its exact revision and refuses a bad ref or empty evidence.
The reviewer needs existing native GitHub Copilot authentication; credentials are
never copied into a review directory.

The Spec axis needs an originating issue or spec. The Standards and engineering
axis uses repository rules and coding standards. Missing context is a visible
limitation, not permission to invent requirements.

## The two axes

| Axis | Checks |
| --- | --- |
| Spec | Missing or partial requirements, scope creep, wrong behavior, and absent user or error paths |
| Standards and engineering | Repository rules, correctness, errors, concurrency, data handling, interfaces, compatibility, design, security, performance, and behavioral tests |

One independent reviewer checks both axes. Its claims are then verified against
source and deterministic evidence. A confident model assertion is not proof.

## Immutable evidence

| Target | Evidence |
| --- | --- |
| Committed branch or PR | Fixed-point-to-HEAD diff and exact revisions |
| Explicitly requested work in progress | Declared staged/unstaged patches, included untracked content, and content hashes |

There is no commit-before-review requirement. Unrelated changes stay outside the
scope, and review preparation must not stash, reset, commit, or clean the checkout.
The launcher uses the installed Pi SDK, not a reparsed caller CLI. Native and
project model/settings/system-prompt overrides are ignored. Existing native OAuth
is read in place; refreshed tokens stay in memory for the bounded run. No
credential files are copied or written. An explicit `{path, sha256}` manifest
freezes every input, and snapshot-only tools cannot open undeclared files.

## Common questions

**Which model runs the review?**

Exactly Pi with direct `github-copilot/gpt-6.1-sol:high`, through `review-pi`.
An unavailable model or authentication failure blocks the review rather than
falling back to a proxy, weaker model, or OpenCode.

**What counts as approval?**

Only plain `APPROVE` on the current immutable revision. `APPROVE-WITH-CHANGES`,
`REJECT`, missing output, timeout, or unverified process cleanup does not pass.
Fix material issues, rerun relevant checks, and request a fresh review.

**Does it review uncommitted changes?**

Yes, when explicitly scoped and frozen as work-in-progress evidence. It never
mixes other agents' unrelated edits into the review.

**Will it keep producing endless nits?**

It should not. Findings below 80 confidence, tool-enforced style, generic cleanup,
and subjective redesigns are excluded. Re-review is for material fixes.

## It's working if

- The trace shows Pi, direct GitHub Copilot, GPT-6.1 SOL, and high reasoning.
- Each finding names an axis, severity, confidence, location, evidence, impact, and fix.
- The report distinguishes verified findings from rejected claims and missing evidence.
- Reviews finish under a deadline, with no surviving reviewer or modified input.
- Approval follows source verification and relevant test evidence, not just exit zero.

## Where it fits

`code-review` closes the build chain: `grill-with-docs → to-spec → to-tickets →
implement → code-review → retro`. It also works as a standalone branch or PR review.

[implement](https://aihero.dev/skills-implement) calls it after building.
[pr](https://aihero.dev/skills-pr) shapes the PR body, not the review dispatch.
[retro](https://aihero.dev/skills-retro) turns repeated failures into better checks.
[ask-matt](https://aihero.dev/skills-ask-matt) routes across the full set.
