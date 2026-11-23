# Measuring Obsolete Writes After Mid-Task Goal Revisions

## Abstract

A user may replace a target or withdraw part of an instruction while a tool-using agent is working. An end-state evaluator can accept a trajectory in which the agent first carried out a withdrawn action and later reverted it. We study this distinction in AppWorld using Swap and partial Drop interventions from InterventionBench. We compare direct continuation, full replanning, and local plan revision from the same simulator checkpoint. The evaluation records successful post-update writes, revised-task completion, and model usage.

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

Formal results will be filled from the frozen manifest, per-task report files, and usage ledger.

## Limitations

The study is conditional on the old-goal agent proposing an observable obsolete write. Tasks that do not reach the boundary within the prefix budget provide information about coverage and do not enter the paired comparison. The task-specific tool lists and effect mappings restrict the settings in which violations can be observed. AppWorld simplifies external side effects, and this study uses one model. Each retained constraint has a separate denominator when the case has an independently annotated assertion.

## Conclusion

The paired evaluation connects end-state outcomes to evidence about when an agent performed an operation. Conclusions about the relative performance of the three strategies will follow the frozen run.
