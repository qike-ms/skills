## What it does

`code-review` reviews the diff between `HEAD` and a fixed point you name. Two independent high-reasoning reviewers inspect the same evidence: Pi with an OpenAI model and OpenCode with an Anthropic model. Both check **Spec** and **Standards and engineering**, so agreement reflects independent reasoning rather than different task assignments.

The skill keeps findings evidence-based. Every retained issue needs a location, concrete impact, and a useful fix. Style already enforced by tools, speculative redesigns, pre-existing problems, and generic advice are excluded.

## When to reach for it

Type `/code-review`, or the agent reaches for it automatically when you ask to review a branch, PR, work in progress, or changes "since X".

| Situation | Reach for |
| --- | --- |
| A diff exists and you want spec plus engineering review | `code-review` |
| Nothing is written and you want test-first implementation | [tdd](https://aihero.dev/skills-tdd) |
| A whole spec needs implementing and reviewing | [implement](https://aihero.dev/skills-implement) |
| The whole codebase needs architectural improvement | [improve-codebase-architecture](https://aihero.dev/skills-improve-codebase-architecture) |
| A failure needs diagnosis before review | [diagnosing-bugs](https://aihero.dev/skills-diagnosing-bugs) |

You must supply a fixed point such as `main`, a tag, or a commit. The skill verifies that ref and refuses an empty diff before starting reviewers.

## Prerequisites

The Spec axis needs an originating issue or spec. The skill searches commit references, a path you supply, and matching files under `docs/`, `specs/`, or `.scratch/`. Without a spec it reports the gap rather than inventing requirements.

The Standards and engineering axis reads repository instructions and coding standards. Repository rules override generic advice.

## The two axes

| Axis | Checks |
| --- | --- |
| Spec | Missing or partial requirements, scope creep, wrong behavior, and absent user or error paths |
| Standards and engineering | Repository rules, correctness, errors, concurrency, data handling, interfaces, compatibility, design patterns, security, performance, and behavioral tests |

Both reviewers inspect both axes. The orchestrator then verifies their claims against the diff, retains evidence-backed findings from either reviewer, and resolves disagreements explicitly. This is not majority voting.

## The reviewer pair

The pair is fixed:

- OpenCode using `copilot-proxy-gpt/gpt-5.6-sol-high` with the high variant.
- Isolated Pi using `amazon-bedrock/us.anthropic.claude-opus-4-6-v1` with high reasoning.

Both run in fresh sessions. Pi is read-only. OpenCode's plan agent denies edits, and the skill compares repository HEAD and status before and after to catch shell-based mutation. A missing reviewer is a failed review, not permission to substitute a weaker model, a same-family model, or a third reviewer.

## Common questions

**Do both reviewers need to approve?**

Yes. Only plain `APPROVE` from both reviewers passes. `APPROVE-WITH-CHANGES`, `REJECT`, or a missing verdict blocks. A finding from one reviewer still matters when its evidence is correct.

**Can I trust a finding because both models reported it?**

No. Agreement is useful signal, but the orchestrator still checks every material claim against the code and spec.

**Does it review uncommitted changes?**

Not by default. The standard target is `<fixed-point>...HEAD`. Include staged or working-tree changes only when requested and label them separately.

**Will it keep producing endless nits?**

It should not. Findings below 80 confidence, style handled by tools, generic cleanup, and subjective redesigns are excluded. Re-review is for material fixes, not for manufacturing a clean-looking report.

## It's working if

- Both pinned model families review the same current diff at high reasoning.
- Every finding names an axis, severity, confidence, `file:line`, evidence, impact, and fix.
- The report separates consensus, unique verified findings, and disagreements.
- Missing specifications or test evidence remain visible as residual risk.
- The final verdict is approval only after both reviewers approve the current revision.

## Where it fits

`code-review` is the review step near the end of the build chain: `grill-with-docs → to-spec → to-tickets → implement → code-review → retro`. It also works as a standalone review for any branch or PR.

[implement](https://aihero.dev/skills-implement) calls it after building. [pr](https://aihero.dev/skills-pr) shapes the pull request after review. [retro](https://aihero.dev/skills-retro) turns repeated review failures into better deterministic checks or repository standards. [ask-matt](https://aihero.dev/skills-ask-matt) routes across the full set.
