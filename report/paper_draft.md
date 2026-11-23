# Measuring Obsolete Writes After Mid-Task Goal Revisions

## Abstract

A user may replace a target or withdraw part of an instruction while a tool-using agent is working. An end-state evaluator can accept a trajectory in which the agent first carried out a withdrawn action and later reverted it. We study this distinction in AppWorld using Swap and partial Drop interventions from InterventionBench. On 34 independent task families with verified opportunities for an obsolete write, direct continuation, full replanning, and local plan revision achieved 16, 20, and 14 strict successes under the frozen evaluators. Two of 102 branches committed an obsolete write. Both failed their end-state checks, yielding a miss count of 0/50 among final passes. In the pooled comparison, local revision trailed full replanning by 17.6 percentage points (95% task-family bootstrap interval [−32.4, −5.9]). Failures to produce a valid edit list account for four of the six discordant pairs.

## Introduction

Consider an agent asked to move a sleep alarm and disable several other alarms. The user withdraws the second requirement while the agent is working. A final set of enabled alarms is consistent with both leaving those alarms alone and disabling them before turning them back on. The two histories differ in whether the agent respected the revised instruction at the time of action. We ask how often end-state acceptance hides an obsolete write and whether local plan revision changes strict success relative to full replanning.

## Related Work

InterventionBench studies goal changes during tool use in AppWorld and WebArena. Its released evaluation checks end states for Swap and partial Drop, and uses a trajectory stopping rule for complete cancellation. We use its AppWorld tasks and revised-task assertions to study a narrower setting in which an obsolete write is already pending when the intervention arrives. AppWorld provides simulated app APIs, database-state checks, and checkpoint restoration for replaying an identical start across strategies. [Lee et al., 2026](https://aclanthology.org/2026.findings-emnlp.698/) · [InterventionBench code](https://github.com/jhn25/InterventionBench) · [Trivedi et al., 2024](https://aclanthology.org/2024.acl-long.850/)

## Method

### Shared prefix and intervention

We annotate each candidate with the tool operations, targets, and arguments that would carry out the withdrawn part of the old goal. The model initially sees the original goal and a fixed task-specific tool list. It generates a numbered plan and continues through native function calls. The runner stops immediately before a proposed write matches the annotated effect, saves the simulator state, and retains the proposed call as an unexecuted item in the shared history. A candidate qualifies if that boundary occurs within the prefix budget and the pending write is confirmed to commit when replayed on an independent copy of the checkpoint. This rule uses only data from the old-goal trajectory and its replay. Pilot task families are excluded from the final pool.

### Paired strategies

The runner restores the checkpoint for each strategy and verifies a digest of the monitored database records. Each strategy receives the same intervention text and has access to the same tool list. A continues its native tool loop. B uses one model call to write a new remaining plan. C uses one call to provide keep, delete, or replace operations on the numbered old plan. B and C then use the same execution prompt and the same native tool loop. The planning call counts against the same post-update model-call and token allowances. The order of A, B, and C is rotated across the frozen task list.

### Trajectory and end-state scoring

For every monitored write, the harness records the requested operation, its arguments, its response status, and a digest of the relevant simulator records before and after the call. The effect mapping spans app boundaries where a tool changes a different app. For example, downloading a Gmail attachment writes to the file system even though the endpoint uses HTTP GET. A post-update violation requires evidence that a forbidden effect committed. Rejected requests are counted separately, and ambiguous outcomes are marked indeterminate. The model receives tool responses and the user intervention. Effect labels and scorer assertions stay on the evaluator side.

Final pass combines the revised AppWorld assertions with a successful task-completion status. Strict success additionally requires satisfaction of the separately annotated retained constraints and zero committed forbidden effects. The final-state miss rate is the fraction of final passes with a committed forbidden effect among trials with a determinate trajectory verdict. The primary comparison is paired strict success for C against B. The report also gives paired results against A, denominators, missing traces, and model usage.

## Experiments and Results

### Setup

The evaluation consists of two separately frozen batches. The first screened 24 task families and retained 13. The second used an independent pool of 50 families and screened 32 before crossing the target of 30 combined families. It retained 21 from the completed screening waves. Candidate selection used the original goal and at most 20 model calls including the initial plan. In the second batch, six candidates hit the prefix limit, four stopped before the boundary, and one proposed write was rejected during offline replay. The final sample comprised 19 Swap and 15 partial Drop cases. Fifteen shared checkpoints already contained at least one successful write.

Both batches used DeepSeek Flash with thinking disabled and temperature zero. Each strategy ran once per case. The continuation allowance was 24 model calls, 180,000 input tokens, and 12,288 output tokens, with at most 512 output tokens per response. A plan-format error ended the branch. Transient provider errors had up to two retries, with all attempts metered. We obtained all 102 branch scores.

### End-state and trajectory outcomes

| Strategy | Final pass | Committed violation | Strict success | Misses among final passes |
| --- | ---: | ---: | ---: | ---: |
| A. Direct continuation | 16/34 | 0/34 | 16/34 | 0/16 |
| B. Full replanning | 20/34 | 2/34 | 20/34 | 0/20 |
| C. Local plan revision | 14/34 | 0/34 | 14/34 | 0/14 |

For strict success, C lost six pairs and gained none relative to B, a difference of −17.6 percentage points (95% task-family bootstrap interval [−32.4, −5.9]). The extension alone accounted for five of the six losses (−23.8 percentage points, interval [−42.9, −4.8]). C stopped on invalid edit lists in nine cases across the two batches, including four of the six discordant pairs. In the reminder-draft Swap, the old plan had four numbered steps and C returned three edits. The runner stopped before any post-update app call. These outcomes reflect the edit interface as part of the implemented strategy.

Direct continuation used 64 post-update model calls. Full replanning used 100 and local revision used 88, including their plan calls. The conservative peak-rate costs of the three sets of continuations were $0.1233, $0.1671, and $0.1573. Early stops contributed to the observed usage. Screening cost $1.3261 and was shared across strategies.

Both committed violations occurred under full replanning in partial Drop tasks. When the user narrowed an export to one note, B created a file for another note. When the user narrowed payment requests to the first coworker, B submitted a request to a different coworker. Both tool calls returned HTTP 200 and changed the monitored state. The end-state check rejected both branches. In the controlled alarm and playlist probes, an obsolete write followed by reversion left the same monitored final state as a clean trajectory. The trajectory scorer detected those writes.

[Combined results and stratified counts](combined_results.md) · [Extension-only results](expansion_results.md) · [First-batch results](results.md) · [First manifest](../protocol/formal-v1.json) · [Extension manifest](../protocol/formal-expansion-v1.json)

### Sensitivity to an upstream evaluator error

The first-batch evaluator for the resignation-draft case used `gmail.EmailAttachment`, a model name absent from the pinned AppWorld schema. We corrected both references to `gmail.Attachment` and replayed the scorer on all 39 first-batch final states. Only A and B on that task changed from failure to success. C had already stopped on a malformed plan. The corrected combined strict counts were 17/34, 21/34, and 14/34 for A, B, and C. The corrected C–B difference was −20.6 percentage points (95% interval [−35.3, −8.8]). The observed miss count was 0/52. [Combined sensitivity table](combined_results_corrected.md)

## Limitations

The study is conditional on the old-goal agent proposing an observable obsolete write. Tasks that did not reach the boundary contribute to coverage statistics. Candidate construction was manual, and the extension prioritized cases with smaller tool sets within intervention types. The extension was motivated by the initial sample size and frozen before its continuations. The pooled comparison is descriptive of these batches. Task-specific tools and effect mappings restrict observable violations. AppWorld simplifies external side effects, and the study uses one hosted model.

Strict success incorporates the plan format and the supervisor completion call. The comparison therefore covers the implemented strategies, including their interfaces. The extension stores raw planning responses even when validation fails. The first batch stores the validation reason and preceding operations. Retained-constraint rates use the independently annotated subset. The intervals reflect resampling within the screened sample, with limited information about performance on other tasks.

## Conclusion

The paired evaluation identified two successful obsolete writes. Both failed the end-state checks. Full replanning produced six more strict successes than local revision under the frozen evaluators and seven more after the first-batch correction. The local-edit interface contributed substantially to the observed gap. Controlled reversion traces show how a final state can hide a committed action, while the live sample establishes the frequency observed under the particular model, tools, and checkpoints in this study.

<!-- Draft self-review
Contribution: The endpoint and trajectory outcomes are defined separately and compared on the same branches.
Clarity: The shared prefix, inclusion rule, intervention, and three continuation policies are stated in execution order.
Experimental strength: The counts and paired interval are explicit. The paper reports separate extension results and avoids a general ranking.
Evaluation completeness: The paper gives denominators, branch failures, and audited real traces. Standalone revised-goal runs are outside this design.
Method soundness: Eligibility depends only on the old-goal prefix. Each strategy pays for any planning call under the same ceiling.
Claim-evidence map: 0/50 frozen final misses and the strict-success difference come from the rebuilt combined table. The committed writes are case 275/B at operation 7 and case 267/B at operation 9. The reversion claim comes from the two offline probes. Case 335/C has four old steps, three raw edits, and zero post-update calls.
-->
