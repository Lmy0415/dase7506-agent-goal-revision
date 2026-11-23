"""Freeze screened prefixes or run the registered A/B/C comparison."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import fcntl
from hashlib import sha256
import json
from multiprocessing import get_context
from pathlib import Path
import random
import shutil

from flash import MODEL, ModelServiceError, conservative_input_tokens, request_body
from formal_cases import candidates_from
from scripts.pilot import DATASET, BranchBudgetError, run_branch, write_json
from scripts.screen_candidates import (
    CAMPAIGN_CAP, PREFIX_MODEL_CALLS, ROOT, SCREEN, WORKERS, FormalTools, model_client,
)


PROTOCOL = {
    "revision": "formal-v1",
    "seed": 7506,
    "model": MODEL,
    "thinking": "disabled",
    "temperature": 0,
    "prefix_model_calls": PREFIX_MODEL_CALLS,
    "post_update_model_calls": 24,
    "post_update_input_tokens": 180_000,
    "output_tokens_per_call": 512,
    "post_update_output_tokens": 24 * 512,
    "transient_retries_per_call": 2,
    "format_retries": 0,
    "campaign_cap_usd": CAMPAIGN_CAP / 1e9,
}


class BranchModel:
    def __init__(self, client):
        self.client = client
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0

    def request(self, label, messages, *, tools=None, json_mode=False):
        if self.calls == PROTOCOL["post_update_model_calls"]:
            raise BranchBudgetError("total model-call allowance reached")
        available_output = PROTOCOL["post_update_output_tokens"] - self.output_tokens
        response_limit = min(available_output, PROTOCOL["output_tokens_per_call"])
        if response_limit <= 0:
            raise BranchBudgetError("output-token allowance reached")
        body = request_body(messages, tools=tools, json_mode=json_mode, max_tokens=response_limit)
        if self.input_tokens + conservative_input_tokens(body) > PROTOCOL["post_update_input_tokens"]:
            raise BranchBudgetError("next request would exceed input-token allowance")
        answer = self.client.request(
            label, messages, tools=tools, json_mode=json_mode, max_tokens=response_limit,
        )
        self.calls += 1
        self.input_tokens += int(answer["usage"]["prompt_tokens"])
        self.output_tokens += int(answer["usage"]["completion_tokens"])
        return answer


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def hashes():
    paths = ("formal_cases.py", "flash.py", "scoring.py", "scripts/pilot.py",
             "scripts/offline_probe.py", "scripts/screen_candidates.py", "scripts/formal.py",
             "scripts/analyze_formal.py")
    return {path: digest(Path(path)) for path in paths}


def frozen_manifest():
    candidates = candidates_from(DATASET)
    screen = json.loads((SCREEN / "status.json").read_text())
    boundary_file = SCREEN / "boundaries.json"
    verified = json.loads(boundary_file.read_text())
    if set(screen) != {str(case.index) for case in candidates}:
        raise ValueError("Complete candidate screening before freezing the task set")
    chosen = []
    excluded = []
    for case in candidates:
        row = screen[str(case.index)]
        prefix = SCREEN / str(case.index) / "prefix.json"
        identity = {"intervention_idx": case.index, "base_task_id": case.row["base_task_id"],
                    "type": case.row["type"], "family": case.family}
        if row["checkpoint_reason"] != "before_revoked_write":
            excluded.append(identity | {"reason": row["checkpoint_reason"]})
            continue
        boundary = verified[str(case.index)]
        if boundary["outcome"] != "committed":
            excluded.append(identity | {"reason": f"pending_write_{boundary['outcome']}",
                                        "tool_status": boundary["status"]})
            continue
        chosen.append(identity | {"prefix_sha256": digest(prefix), "prefix_commits": row["prefix_commits"]})
    if not any("Drop" in row["type"] for row in chosen) or not any("Swap" in row["type"] for row in chosen):
        raise ValueError("The screened set does not cover both research strata, Swap and partial Drop")
    random.Random(PROTOCOL["seed"]).shuffle(chosen)
    orders = ("ABC", "BCA", "CAB", "ACB", "CBA", "BAC")
    for i, row in enumerate(chosen):
        row["strategy_order"] = orders[i % len(orders)]
    return {
        "protocol": PROTOCOL, "dataset_sha256": digest(DATASET), "implementation": hashes(),
        "offline_boundary_evidence_sha256": digest(boundary_file),
        "chosen": chosen, "excluded": excluded,
    }


def write_frozen(path):
    if path.exists():
        raise ValueError(f"Frozen manifest already exists: {path}")
    data = frozen_manifest()
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, data)
    print(f"Froze {len(data['chosen'])} cases. Excluded {len(data['excluded'])}.", flush=True)


def run_case(case, row, directory):
    source = SCREEN / str(case.index)
    if digest(source / "prefix.json") != row["prefix_sha256"]:
        raise ValueError(f"{case.index}: frozen prefix does not match screen record")
    prefix = json.loads((source / "prefix.json").read_text())
    target = directory / str(case.index)
    target.mkdir(exist_ok=True)
    if not (target / "checkpoint").exists():
        temporary = target / "checkpoint.partial"
        shutil.copytree(source / "checkpoint", temporary, dirs_exist_ok=True)
        temporary.rename(target / "checkpoint")
    result = {}
    client = None
    for strategy in row["strategy_order"]:
        scored = target / f"{strategy}.json"
        if scored.exists():
            branch = json.loads(scored.read_text())
        else:
            if client is None:
                client = model_client()
            branch = run_branch(
                case, BranchModel(client), target, prefix, strategy, tools_type=FormalTools,
                revision=PROTOCOL["revision"], max_steps=PROTOCOL["post_update_model_calls"],
                keep_service_failures=True,
            )
            write_json(scored, branch)
        result[strategy] = branch["score"]
        print(case.index, strategy, branch["termination"], branch["score"], flush=True)
    return case.index, result


def run(path, *, workers=WORKERS):
    frozen = json.loads(path.read_text())
    if frozen["implementation"] != hashes() or frozen["dataset_sha256"] != digest(DATASET):
        raise ValueError("Frozen implementation or benchmark data do not match the current checkout")
    if frozen["protocol"] != PROTOCOL:
        raise ValueError("Frozen protocol does not match this runner")
    manifest_hash = digest(path)
    directory = ROOT / f"formal-v1-{manifest_hash[:12]}"
    directory.mkdir(parents=True, exist_ok=True)
    cases = {case.index: case for case in candidates_from(DATASET)}
    with (ROOT / "campaign.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        records = {}

        def update(result):
            index, branches = result
            records[index] = branches
            status = {
                "manifest_sha256": manifest_hash, "updated_utc": datetime.now(timezone.utc).isoformat(),
                "planned_pairs": len(frozen["chosen"]), "finished_pairs": len(records),
                "cases": records,
            }
            write_json(directory / "status.json", status)

        work = [(cases[row["intervention_idx"]], row, directory) for row in frozen["chosen"]]
        if workers == 1:
            for args in work:
                update(run_case(*args))
        else:
            with ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn")) as executor:
                futures = [executor.submit(run_case, *args) for args in work]
                try:
                    for future in as_completed(futures):
                        update(future.result())
                finally:
                    for future in futures:
                        future.cancel()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", type=Path)
    action.add_argument("--run", type=Path)
    parser.add_argument("--workers", type=int, choices=range(1, WORKERS + 1), default=WORKERS)
    args = parser.parse_args()
    if args.freeze:
        write_frozen(args.freeze)
    else:
        run(args.run, workers=args.workers)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, ModelServiceError, BlockingIOError) as error:
        raise SystemExit(str(error)) from None
