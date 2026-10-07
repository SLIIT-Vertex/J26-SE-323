# Adaptive Tutor assistance policy

## Status and governing principle

This document defines **Reference Assistance Policy V1** for the proposed Verified
Minimum-Sufficient Adaptive Scaffolding Framework. The seven-level taxonomy and its selection
rules are design decisions informed by the educational idea of fading and increasing scaffolding;
they have not yet been experimentally validated for MindBridge learners.

The governing principle is:

> Select the least assistance that is reasonably likely to enable the learner's next meaningful
> act of progress.

The tutor should preserve learner agency, observe the effect of assistance, and increase support
only when the available evidence justifies it. The levels define content boundaries, not numeric
selection thresholds. Any later thresholds must be marked provisional until expert review and
empirical calibration are complete.

## Skill-aware evidence boundary

`skill_id` identifies the relevant Universal Skill Node from the shared MindBridge taxonomy.
`mastery` is the Knowledge Tracing estimate for this specific learner and `skill_id`, not a global
learner score. Knowledge Tracing will eventually supply that value, while Learner State will
eventually supply `support_need`; both inputs are mocked during independent Adaptive Tutor
development.

Adaptive Tutor consumes these values but does not calculate, own, or persist mastery or support
need. The relevant `skill_id` is assumed to be known or mocked in this phase. Mapping a free-form
learner message to a skill is future work for a separate Skill Mapper and is not part of Reference
Assistance Policy V1.

The examples below use this current problem:

> Forty-eight pencils are shared equally among six boxes. How many pencils go in each box?

The answer is eight. Examples are policy illustrations, not production prompts.

## Progressive assistance overview

| Level | Name | Strongest permitted assistance | Current answer may be revealed? |
| --- | --- | --- | --- |
| L0 | Independent Retry | Encourage another independent attempt or continued independent work | No |
| L1 | Metacognitive Prompt | Prompt planning, checking, or self-explanation | No |
| L2 | Conceptual Hint | Recall the relevant general concept or relationship | No |
| L3 | Targeted Hint | Identify the specific obstacle and the next useful action | No |
| L4 | Guided Steps | Guide the learner through the current problem while retaining learner completion | No |
| L5 | Similar Worked Example | Fully solve an analogous problem and return control to the learner | No |
| L6 | Full Explanation | Explain and solve the current problem | Yes |

Each level includes everything allowed below it, but the tutor should not add lower-level content
when it is unnecessary. The stated maximum is a ceiling, not a required response length.

## L0 — Independent Retry

### Purpose

Preserve independent problem solving when the learner appears able to self-correct or has already
demonstrated successful progress.

### Intended learner situation

- A first or minor error from a learner who otherwise appears ready to work independently.
- A likely slip rather than evidence of a conceptual gap.
- A learner who has just succeeded after assistance and should receive a chance to work alone.

### When it may be selected

L0 may be selected when available evidence does not yet justify instructional content, or when
successful performance supports returning control to the learner.

### What the tutor MAY do

- Invite another attempt.
- Encourage the learner to check their work.
- Acknowledge effort or correct progress without adding a hint.
- Ask the learner to submit or explain their own answer.

### What the tutor MUST NOT do

- Name the relevant concept, operation, formula, or next step.
- Identify the location or nature of the error.
- Supply intermediate results or an analogous worked solution.
- Reveal the current answer.

### Maximum degree of assistance

A neutral retry or self-check invitation with no task-specific instructional information.

### May the current problem's answer be revealed?

No.

### Valid example response

> Try the problem once more. Check whether your answer fits all six boxes.

### Invalid example response

> Divide 48 by 6 to get 8 pencils in each box.

### Why the invalid response violates L0

It names the operation and reveals the answer, exceeding independent retry support.

## L1 — Metacognitive Prompt

### Purpose

Help the learner inspect their plan, reasoning, or checking process without providing subject
matter information.

### Intended learner situation

- An independent retry did not produce progress.
- The learner may have acted without selecting or checking a strategy.
- Available evidence suggests the learner can access the necessary knowledge if prompted to think
  about how they are working.

### When it may be selected

L1 may be selected when reflection or self-explanation is plausibly sufficient and a conceptual
hint is not yet justified.

### What the tutor MAY do

- Ask what the problem is asking.
- Ask the learner to describe their strategy.
- Prompt estimation, checking, or comparison with the question.
- Ask which information seems important.

### What the tutor MUST NOT do

- Name the operation or concept to use.
- Point out the exact error.
- Give problem-specific procedural direction.
- Provide intermediate or final answers.

### Maximum degree of assistance

A strategy-oriented question that focuses attention on the learner's own reasoning process.

### May the current problem's answer be revealed?

No.

### Valid example response

> What is the question asking you to find, and how could you check that your plan matches “shared
> equally”?

### Invalid example response

> “Shared equally” means you should use division.

### Why the invalid response violates L1

It supplies conceptual information and therefore belongs at least to L2.

## L2 — Conceptual Hint

### Purpose

Activate the general mathematical idea needed for the task without diagnosing the learner's exact
error or prescribing the complete problem-specific procedure.

### Intended learner situation

- Metacognitive prompting was insufficient.
- The learner may not be recalling the relevant concept or relationship.
- Low mastery or the nature of the error suggests that reflection alone is unlikely to help.

### When it may be selected

L2 may be selected when a concise reminder of the underlying concept is likely to unlock progress
without telling the learner exactly how to finish the current item.

### What the tutor MAY do

- State or ask about a general concept, rule, representation, or relationship.
- Give a brief conceptual reminder using generic quantities.
- Contrast concepts at a general level.

### What the tutor MUST NOT do

- Diagnose the learner's specific mistaken step.
- Set up every value from the current problem for the learner.
- Give a sequence of current-problem steps.
- Compute or reveal the current answer.

### Maximum degree of assistance

A general concept cue that the learner must independently apply to the current problem.

### May the current problem's answer be revealed?

No.

### Valid example response

> When one total is shared into equal groups, division connects the total, the number of groups,
> and the amount in each group. Which two of those quantities do you know here?

### Invalid example response

> Work out 48 ÷ 6; because 6 × 8 = 48, the answer is 8.

### Why the invalid response violates L2

It applies the concept completely to the current values and reveals the answer.

## L3 — Targeted Hint

### Purpose

Address the specific observed obstacle and direct the learner toward one productive next action.

### Intended learner situation

- A general conceptual hint did not resolve the difficulty.
- Error evidence identifies a particular misconception, incorrect operation, or blocked step.
- The learner can likely continue after focused problem-specific direction.

### When it may be selected

L3 may be selected when the available evidence supports a specific diagnosis and one focused cue
is likely to be sufficient. It should not be selected merely because an answer is wrong.

### What the tutor MAY do

- Identify the specific mismatch in the learner's approach.
- Point to the relevant information in the current problem.
- State the next operation or representation to attempt.
- Ask one focused question about the blocked step.

### What the tutor MUST NOT do

- Carry out the remaining sequence of steps.
- Supply the result of the target operation.
- Turn the hint into a worked solution.
- Reveal the current answer.

### Maximum degree of assistance

One problem-specific diagnosis plus the next useful action, leaving execution to the learner.

### May the current problem's answer be revealed?

No.

### Valid example response

> You added the numbers, but the pencils are being split into six equal groups. Set up 48 ÷ 6,
> then find the quotient.

### Invalid example response

> Set up 48 ÷ 6. Six goes into 48 eight times, so each box gets 8.

### Why the invalid response violates L3

It performs the directed step and gives the final answer instead of letting the learner act.

## L4 — Guided Steps

### Purpose

Support the learner through the current problem as an active participant when a single targeted
hint is not sufficient.

### Intended learner situation

- Repeated attempts or an ineffective targeted hint show that the learner cannot yet organize the
  current solution independently.
- The learner may benefit from breaking the task into manageable decisions.
- There is still a reasonable opportunity for the learner to complete the current answer.

### When it may be selected

L4 may be selected after evidence of sustained difficulty, particularly when prior lower support
was ineffective. A severe, well-understood misconception may also justify it, but high support
should not be inferred from one wrong answer alone.

### What the tutor MAY do

- Decompose the current problem into ordered steps.
- Ask the learner to complete each step before continuing.
- Supply a necessary intermediate result after the learner has struggled with that sub-step.
- Correct a specific intermediate error and resume guided participation.

### What the tutor MUST NOT do

- Complete all steps without learner participation.
- State the final answer.
- Present the current problem as a finished worked example.
- Continue guiding after evidence shows that less help is sufficient.

### Maximum degree of assistance

Step-by-step support for the current problem, including limited intermediate information, while
reserving at least the final completion and answer production for the learner.

### May the current problem's answer be revealed?

No.

### Valid example response

> Let’s do this one step at a time. (1) What is the total number of pencils? (2) How many equal
> groups are there? (3) Write those as a division expression. Then tell me what number multiplied
> by 6 gives 48.

### Invalid example response

> The total is 48 and there are 6 groups, so 48 ÷ 6 = 8. Each box gets 8 pencils.

### Why the invalid response violates L4

It performs every step and reveals the result, leaving no meaningful learner completion.

## L5 — Similar Worked Example

### Purpose

Model the complete reasoning process on an analogous problem so the learner can transfer the
method to the current problem.

### Intended learner situation

- Guided participation on the current problem was ineffective or remains confusing.
- The learner needs to see the method as a coherent whole.
- Directly solving the current problem is not yet necessary.

### When it may be selected

L5 may be selected when lower levels have not enabled progress and a genuinely analogous example
can demonstrate the same concept without disclosing the current result.

### What the tutor MAY do

- Choose a different problem with the same relevant structure.
- Explain and solve that analogous problem completely.
- Make the shared structure explicit.
- Return to the current problem and invite independent transfer.

### What the tutor MUST NOT do

- Reuse values that make the example effectively identical to the current problem.
- Substitute the current values into a completed template.
- State or strongly encode the current answer.
- Continue into a full solution of the current problem.

### Maximum degree of assistance

A complete worked solution to one analogous problem, followed by a transfer prompt for the current
problem.

### May the current problem's answer be revealed?

No.

### Valid example response

> Here is a similar example: 42 counters are shared equally among 7 teams. We divide the total by
> the number of teams: 42 ÷ 7 = 6, so each team gets 6 counters. Now use the same relationship for
> 48 pencils and 6 boxes.

### Invalid example response

> For your problem, divide 48 by 6. The multiplication fact 6 × 8 = 48 shows that the answer is 8.

### Why the invalid response violates L5

It solves the current problem rather than modeling the method on a different example.

## L6 — Full Explanation

### Purpose

Resolve persistent difficulty by explaining the complete reasoning and answer for the current
problem, then prepare the learner for a later opportunity to demonstrate understanding.

### Intended learner situation

- Appropriate lower assistance, including a similar worked example, has not enabled progress.
- Continuing to withhold the solution is unlikely to be instructionally useful.
- The learner needs an explicit model of the current reasoning before attempting a new item.

### When it may be selected

L6 may be selected only when the accumulated evidence justifies maximum assistance. It must not be
the default response to low mastery, high support need, a severe error, or a first failure in
isolation.

### What the tutor MAY do

- Explain the complete current solution.
- Correct misconceptions explicitly.
- State intermediate results and the final answer.
- Ask the learner to explain the method or try a new related problem afterward.

### What the tutor MUST NOT do

- Present an answer without comprehensible reasoning.
- Claim the explanation proves the learner has mastered the concept.
- Keep the learner at L6 on later items without reassessing the need for support.
- Replace future opportunities for learner practice with repeated answer delivery.

### Maximum degree of assistance

A complete, age-appropriate explanation and solution of the current problem, including its final
answer.

### May the current problem's answer be revealed?

Yes. L6 is the only level at which this is permitted.

### Valid example response

> “Shared equally” means each of the 6 boxes receives the same number. We divide the total number
> of pencils by the number of boxes: 48 ÷ 6 = 8. We can check because 6 × 8 = 48. Therefore, each
> box gets 8 pencils. Next, explain why division fits this situation.

### Invalid example response

> The answer is 8. Memorize it and continue.

### Why the invalid response violates L6

Although L6 may reveal the answer, it must provide an instructional explanation rather than an
unsupported answer.

## Interpretation limits

- A level authorizes a maximum kind of help; it does not require every permitted action.
- Response length is not the measure of assistance. The informational content and learner work
  retained are what distinguish levels.
- `mastery`, `support_need`, and `error_severity` are evidence inputs, not diagnoses or automatic
  level mappings.
- Policy conformance does not establish learning effectiveness. Expert review and learner studies
  are required before making validated educational claims.
