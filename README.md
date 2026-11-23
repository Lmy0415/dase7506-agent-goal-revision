# Mid-task goal revision in AppWorld

DASE7506 final project. We study how often the final state passes despite a
successful post-update action that conflicts with the revised request. We compare
native continuation (A), full replanning (B), and local plan revision (C) from a
shared prefix and simulator checkpoint. The primary comparison is C versus B.

- [Execution plan](DASE7506_Agent实验执行方案.md)
- [Progress and verified results](progress.md)

## Upstream versions

| Upstream | Revision | Benchmark data |
| --- | --- | --- |
| [InterventionBench](https://github.com/jhn25/InterventionBench) | `7fe53126b93e8d3ef7e28bafbf8db6c6060e679e` | v1.1 |
| [AppWorld](https://github.com/StonyBrookNLP/appworld) | `42b5bcf3cd334fee33f0c37c02070a9f5807add5` | 0.2.0 |

Benchmark data, simulator state, and raw execution logs stay out of Git.
The model provider and trial budget are pending. Offline checks do not require a
model API key.
