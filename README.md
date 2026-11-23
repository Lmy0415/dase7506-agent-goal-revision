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
Offline checks do not require a model API key.

## Offline verification

Run from the project directory. The simulator is local and the probe uses
scripted tool calls with evaluator data. Its result is a measurement check,
separate from the planned A/B/C model runs.

```sh
.venv/bin/python -m unittest discover -s tests -v
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

## DeepSeek Flash pilot

The pilot uses the official `deepseek-flash` model with thinking disabled and
temperature 0, plus a fixed same-case tool list for A, B, and C. Five independent
base tasks are used for debugging only. The model receives the AppWorld task
instruction, visible tool outputs, and the intervention text. Ground-truth
data and trajectory scoring stay local.

```sh
export APPWORLD_ROOT="$PWD/.appworld"
export APPWORLD_CACHE="$APPWORLD_ROOT/cache"
export IPYTHONDIR="$APPWORLD_ROOT/ipython"
mkdir -p "$IPYTHONDIR"
.venv/bin/python -m scripts.pilot --validate-local
.venv/bin/python -u -m scripts.pilot
```

The last command requires authorized API access. Set `DEEPSEEK_API_KEY` in the
local `.env`. The runner checks a cumulative $1 pilot budget before each call
using peak, non-cached input and output prices. Use the same command to resume
with `artifacts/pilot-flash/` intact. Completed prefixes and branches are
reused, and `usage.jsonl` carries forward prior calls, including any unresolved
reservations. `r2/status.json` records the per-branch results. The pilot uses an
eight-turn common-prefix limit, an eighteen-turn continuation limit, and
records the actual injection boundary for each case. When the API proposes
multiple calls in one turn, the runner considers the first and records how
many other calls were proposed. Each branch keeps its final snapshot and raw
trace even if scoring stops.

## Formal evaluation

The candidate screen uses only the original goal. A case qualifies when the
model proposes the obsolete write and the runner can pause before executing it.
The manifest records all exclusion reasons, task families, and the saved prefix
digests. The post-update budget is 24 model calls including any plan call, with
a 180,000-input-token ceiling and 512 output tokens per call. All workers share
one separate $3 campaign ledger across screening and formal execution.

```sh
export APPWORLD_ROOT="$PWD/.appworld"
export APPWORLD_CACHE="$APPWORLD_ROOT/cache"
export IPYTHONDIR="$APPWORLD_ROOT/ipython"
mkdir -p "$IPYTHONDIR" artifacts/formal-flash
.venv/bin/python -m scripts.screen_candidates --validate-local
.venv/bin/python -m scripts.probe_formal_writes
.venv/bin/python -u -m scripts.screen_candidates --workers 4
.venv/bin/python -m scripts.screen_candidates --verify-boundaries --workers 4
.venv/bin/python -m scripts.formal --freeze protocol/formal-v1.json
.venv/bin/python -u -m scripts.formal --run protocol/formal-v1.json --workers 4
.venv/bin/python -m scripts.analyze_formal protocol/formal-v1.json --output report/results.md
.venv/bin/python -m scripts.rescore_formal protocol/formal-v1.json --output report/results_corrected.md
```

The screening and formal execution commands require API authorization. Resume
with the same commands and local artifacts. After freezing, reuse the manifest
and run command. The formal runner verifies the manifest's implementation,
dataset, and prefix digests before calling the model. The [paper draft](report/paper_draft.md)
describes the research question, method, and results. The [frozen table](report/results.md)
and [offline sensitivity table](report/results_corrected.md) are separately reproducible.

## Held-out extension

The extension keeps the first batch's frozen files intact and adds one candidate
per unused AppWorld task family. It uses the same A/B/C continuation budgets, a
separate freeze manifest, and the existing cumulative $3 ledger. After local
preflight, candidates are screened in small waves. The script freezes when
the first and second batches contain at least 30 verified cases, or when the
candidate pool or authorized screening budget is exhausted.

```sh
export APPWORLD_ROOT="$PWD/.appworld"
export APPWORLD_CACHE="$APPWORLD_ROOT/cache"
export IPYTHONDIR="$APPWORLD_ROOT/ipython"
mkdir -p "$IPYTHONDIR"
.venv/bin/python -u -m scripts.expand --workers 5
.venv/bin/python -m scripts.export_metrics
```

Use the same extension command to resume. The script retains old-goal
checkpoints, verifies pending writes in copies of those checkpoints, and
skips already recorded branches. It rebuilds the extension and combined
tables and updates `progress.md` and the machine-readable status. Raw traces
remain under `artifacts/formal-flash/expansion-v1/`. The export adds one row
per branch, including usage and the local trace index. Elapsed time is
available for the extension, where it is measured by a monotonic clock.

[Combined table](report/combined_results.md) ·
[Corrected combined table](report/combined_results_corrected.md) ·
[Branch metrics and trace index](report/branch_metrics.json).
