"""Export one anonymized record per branch, with links to the local evidence."""

import fcntl
from hashlib import sha256
import json
from pathlib import Path

from scripts.pilot import write_json
from scripts.screen_candidates import ROOT


def load(path):
    return json.loads(path.read_text())


def bill(ledger, label):
    matches = [entry for entry in ledger.values() if entry["run"] == label]
    return {
        "attempts": len(matches),
        "settled_model_calls": sum(r["status"] == "settled" for r in matches),
        "input_tokens": sum(r.get("prompt_tokens", 0) for r in matches),
        "output_tokens": sum(r.get("completion_tokens", 0) for r in matches),
        "upper_cost_nanos": sum(r["charge_upper_nanos"] for r in matches),
    }


def batch(manifest, branches, prefixes, prefix_stage, prefix_filename, ledger, correction=None):
    policy = manifest["protocol"]["revision"]
    data = []
    for case in manifest["chosen"]:
        index = str(case["intervention_idx"])
        prefix_path = prefixes / index / prefix_filename
        prefix = load(prefix_path)
        prefix_size = len(prefix["audit"])
        prefix_usage = bill(ledger, f"{prefix_stage}/{index}/prefix")
        for strategy in "ABC":
            result_path = branches / index / f"{strategy}.json"
            result = load(result_path) if result_path.exists() else {}
            trace = result.get("writes_and_reads")
            row = {
                "policy_version": policy, "base_task_id": case["base_task_id"],
                "intervention_idx": case["intervention_idx"], "type": case["type"],
                "strategy": strategy, "post_update_elapsed_s": result.get("elapsed_s"),
                "post_update_tool_calls": len(trace) - prefix_size if trace is not None else None,
                "post_update_usage": bill(ledger, f"{policy}/{index}/{strategy}"),
                "common_prefix_tool_calls": prefix_size, "common_prefix_elapsed_s": prefix.get("elapsed_s"),
                "common_prefix_usage": prefix_usage, "score": result.get("score"),
                "termination": result.get("termination", "missing"),
                "trace_path": str(result_path), "common_prefix_path": str(prefix_path),
            }
            if correction:
                corrected_path = correction / index / f"{strategy}.json"
                row["score_after_case_748_correction"] = load(corrected_path)["score"]
            data.append(row)
    return data


def main():
    ledger_path = ROOT / "usage.jsonl"
    with ledger_path.open() as file:
        fcntl.flock(file, fcntl.LOCK_SH)
        ledger = {entry["id"]: entry for entry in map(json.loads, file)}
    original_path = Path("protocol/formal-v1.json")
    original = load(original_path)
    original_hash = sha256(original_path.read_bytes()).hexdigest()[:12]
    rows = batch(original, ROOT / f"formal-v1-{original_hash}", ROOT / "screen-v1",
                 "screen-v1", "prefix.json", ledger, ROOT / f"rescore-attachment-v1-{original_hash}")
    expansion_path = Path("protocol/formal-expansion-v1.json")
    if expansion_path.exists():
        expansion = load(expansion_path)
        directory = ROOT / "expansion-v1/cases"
        rows.extend(batch(expansion, directory, directory, "expansion-screen-v1", "screen.json", ledger))
    write_json(Path("report/branch_metrics.json"), rows)
    print(f"Exported {len(rows)} branch records to report/branch_metrics.json")


if __name__ == "__main__":
    main()
