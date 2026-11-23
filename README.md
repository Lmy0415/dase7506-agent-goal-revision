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

## Offline verification

Run from the project directory. The simulator is local and the probe uses
scripted tool calls with evaluator data. Its result is a measurement check,
separate from the planned A/B/C model runs.

```sh
python3 -m unittest discover -s tests -v
export APPWORLD_ROOT="$PWD/.appworld"
export APPWORLD_CACHE="$APPWORLD_ROOT/cache"
export IPYTHONDIR="$APPWORLD_ROOT/ipython"
mkdir -p "$IPYTHONDIR"
.venv/bin/python -m scripts.offline_probe \
  .upstream/InterventionBench/data/appworld_interventions.jsonl
```

The probe writes `artifacts/offline-probe.json` with tool names, request
parameters, response statuses, and before/after state digests. It excludes
simulator credentials from this file. It runs each revised task evaluator
directly from the checksum-verified upstream JSONL.

For a fresh setup, check out the two upstream revisions above into
`.upstream/InterventionBench` and `.upstream/appworld`, with Git LFS enabled for
AppWorld. Then run the following on a fresh environment with Python 3.11 and
`uv`. The data command replaces an existing AppWorld data directory, so the
conditional preserves an already downloaded copy.

```sh
export APPWORLD_ROOT="$PWD/.appworld"
export APPWORLD_CACHE="$APPWORLD_ROOT/cache"
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e .upstream/appworld -c constraints-appworld.txt
.venv/bin/appworld install
if [ ! -d "$APPWORLD_ROOT/data/tasks" ]; then
  .venv/bin/appworld download data
fi
```
