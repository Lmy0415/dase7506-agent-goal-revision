# Measuring Obsolete Writes After Mid-Task Goal Revisions

## Abstract

A user may replace a target or withdraw part of an instruction while a tool-using agent is working. An end-state evaluator can accept a trajectory in which the agent first carried out a withdrawn action and later reverted it. We study this distinction in AppWorld using Swap and partial Drop interventions from InterventionBench. On 13 tasks with verified opportunities for an obsolete write, direct continuation, full replanning, and local plan revision achieved 6, 7, and 6 strict successes under the frozen evaluator. One of 39 branches committed an obsolete write and failed its end-state checks. The observed miss rate among final passes was 0/19. Controlled traces separately established that reversion can hide an obsolete write from the end-state checks.

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

We screened 24 independent task families with DeepSeek Flash using the original goal, at most 20 model calls including the initial plan, and no revised instructions. Thirteen reached the intended boundary and the pending old write committed on an isolated replay. The other 11 cases reached the prefix call limit (10) or ended before the boundary (1). The frozen evaluation included 4 Swap and 9 partial Drop cases. Nine checkpoints already contained at least one successful write.

Each strategy ran once per case with thinking disabled and temperature zero. The continuation allowance was 24 model calls, 180,000 input tokens, and 12,288 output tokens, with at most 512 output tokens per response. A plan-format error ended the branch. Transient provider errors had up to two retries, with all attempts metered. We obtained all 39 branch scores.

### End-state and trajectory outcomes

| Strategy | Final pass | Committed violation | Strict success | Misses among final passes |
| --- | ---: | ---: | ---: | ---: |
| A. Direct continuation | 6/13 | 0/13 | 6/13 | 0/6 |
| B. Full replanning | 7/13 | 1/13 | 7/13 | 0/7 |
| C. Local plan revision | 6/13 | 0/13 | 6/13 | 0/6 |

These are the frozen-evaluator counts. The primary comparison had one strict-success loss and no gain for C relative to B, a difference of −7.7 percentage points (95% task-family bootstrap interval [−23.1, 0.0]). C stopped on invalid plan edits in three cases. The strict-success difference came from the alarm-snooze Swap, where B updated the weekend alarm and C failed to provide one valid edit per old step. The two other format failures occurred on tasks where B also failed its end-state checks. Replanning and local revision used 36 and 31 post-update model calls, respectively, including plan calls. Direct continuation used 21. Early stops can reduce these usage counts.

The single committed violation occurred when a user narrowed an export to one note. B then created a file for another note. The API returned 200, the file-system digest changed, and the end-state evaluator rejected the result. In a separate partial Drop case, A preserved ten earlier text-message deletions and completed the revised task without issuing the pending voice-message deletion. In offline measurement checks for an alarm Swap and a playlist Drop, the clean trace and the trace with a successful obsolete write followed by reversion produced equal monitored final states. The trajectory scorer distinguished both pairs.

[Rebuilt results and stratified counts](results.md) · [Frozen manifest](../protocol/formal-v1.json)

### Sensitivity to an upstream evaluator error

The evaluator for the resignation-draft case used `gmail.EmailAttachment`, a model name absent from the pinned AppWorld schema. The correct model name is `gmail.Attachment`. We corrected the two references and replayed the scorer on all 39 saved final states. Only A and B on that case changed from failure to success. C had already stopped on a malformed plan. The corrected strict counts were 7/13, 8/13, and 6/13 for A, B, and C. The corrected C–B difference was −15.4 percentage points (95% interval [−38.5, 0.0]). The counts of forbidden commits remained 0, 1, and 0, and the observed miss rate was 0/21. [Sensitivity table](results_corrected.md)

## Limitations

The study is conditional on the old-goal agent proposing an observable obsolete write. Tasks that ran out of prefix calls contribute to coverage statistics. Candidate construction was manual, the final sample was small, and the two intervention types were unevenly represented. Task-specific tool lists and effect mappings restrict the violations that can be observed. AppWorld simplifies external side effects, and the study uses one hosted model.

Strict success incorporates the plan format and the supervisor completion call. The comparison therefore covers the implemented strategies, including their interfaces. For a malformed plan, the trace records the validation failure and any preceding operations. The discarded response text is unavailable for finer error analysis. Retained-constraint rates use the independently annotated subset of constraints. The intervals reflect resampling within the screened sample, with limited information about performance on other tasks.

## Conclusion

The paired evaluation identified one successful obsolete write that also failed the end-state checks. No live end-state pass concealed a committed violation in either scoring analysis. Full replanning had one more strict success than local revision under the frozen evaluator and two more after the schema correction. Both intervals reached zero. Together with the controlled reversion cases, these results specify what the trajectory measurement can detect and where a larger comparison is needed.

<!-- Draft self-review
Contribution: The endpoint and trajectory outcomes are defined separately and compared on the same branches.
Clarity: The shared prefix, inclusion rule, intervention, and three continuation policies are stated in execution order.
Experimental strength: The counts and paired interval are explicit. The text avoids a general ranking.
Evaluation completeness: The paper gives denominators, branch failures, and two audited real traces. Standalone revised-goal runs are outside this design.
Method soundness: Eligibility depends only on the old-goal prefix. Each strategy pays for any planning call under the same ceiling.
Claim-evidence map: 0/19 frozen final misses comes from the rebuilt table. The committed write example is case 275/B at operation 7. The reversion claim comes from the two offline probes. The format failure example is case 386/C.
-->
