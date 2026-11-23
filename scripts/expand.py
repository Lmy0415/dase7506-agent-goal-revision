"""Resume held-out screening, freeze the extension, run A/B/C, and rebuild tables."""

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import fcntl
from hashlib import sha256
import json
from multiprocessing import get_context
from pathlib import Path
import random
import shutil
from time import CLOCK_MONOTONIC, clock_gettime
from uuid import uuid4
from zoneinfo import ZoneInfo

from appworld import AppWorld

from expansion_cases import expansion_candidates
from flash import DeepSeekFlash, ModelServiceError, TransientModelError
from scripts.analyze_formal import load_scores, report
from scripts.formal import BranchModel
from scripts.offline_probe import evaluate_revised
from scripts.pilot import (
    DATASET, SYSTEM, AgentOutputError, ask_json, message, native_step, old_plan_message,
    plan_list, restore_snapshot, run_branch, save_snapshot, write_json,
)
from scripts.screen_candidates import CAMPAIGN_CAP, FormalTools, ROOT


FIRST = Path("protocol/formal-v1.json")
FROZEN = Path("protocol/formal-expansion-v1.json")
WORK = ROOT / "expansion-v1"
LEDGER = ROOT / "usage.jsonl"
PROGRESS = Path("progress.md")
TARGET_TOTAL = 30
WAVE = 8
WORKERS = 5
SCREEN_CAP = CAMPAIGN_CAP - 300_000_000
ORDERS = ("ABC", "BCA", "CAB", "ACB", "CBA", "BAC")
PREFIX_LIMIT = 20
STRATEGY_LIMIT = 24


class ExpandedTools(FormalTools):
    def is_mutating(self, doc):
        return super().is_mutating(doc) or (
            doc["app_name"], doc["api_name"]
        ) == ("venmo", "download_transaction_receipt")


class TraceModel:
    """Retain the returned plan or tool proposal even when validation fails."""

    def __init__(self, client, path):
        self.client = client
        self.path = path

    def request(self, label, messages, **options):
        started = clock_gettime(CLOCK_MONOTONIC)
        try:
            response = self.client.request(label, messages, **options)
        except ModelServiceError as error:
            self.log({"run": label, "error": str(error)}, started)
            raise
        self.log({"run": label, "response": response}, started)
        return response

    def log(self, data, started):
        data["elapsed_s"] = round(clock_gettime(CLOCK_MONOTONIC) - started, 4)
        with self.path.open("a", encoding="utf-8") as out:
            out.write(json.dumps(data, ensure_ascii=False, default=str) + "\n")


def case_directory(case):
    path = WORK / "cases" / str(case.index)
    path.mkdir(parents=True, exist_ok=True)
    return path


def world_for(case, stage):
    return AppWorld(task_id=case.row["base_task_id"], load_ground_truth=True,
                    experiment_name=f"expand-{stage}-{uuid4().hex}")


def preflight(case):
    path = case_directory(case) / "preflight.json"
    if path.exists():
        return case.index, json.loads(path.read_text())
    started = clock_gettime(CLOCK_MONOTONIC)
    try:
        with world_for(case, "preflight") as world:
            tools = ExpandedTools(world, case)
            case.signature(world)
            retained = case.retained(world)
            passes, failures = evaluate_revised(world, case.row)
            if passes + failures == 0:
                raise ValueError("revised evaluator has no assertions")
            row = {"ready": True, "tools": len(tools.definitions), "retained": list(retained),
                   "assertions": passes + failures}
    except Exception as error:
        row = {"ready": False, "error": f"{type(error).__name__}: {error}"}
    row["elapsed_s"] = round(clock_gettime(CLOCK_MONOTONIC) - started, 3)
    write_json(path, row)
    return case.index, row


def screen(case):
    directory = case_directory(case)
    path = directory / "screen.json"
    if path.exists():
        return case.index, json.loads(path.read_text())
    started = clock_gettime(CLOCK_MONOTONIC)
    model = TraceModel(DeepSeekFlash(LEDGER, cap=SCREEN_CAP), directory / "prefix-model.jsonl")
    label = f"expansion-screen-v1/{case.index}/prefix"
    with world_for(case, "prefix") as world:
        tools = ExpandedTools(world, case)
        history = [message("system", SYSTEM), message("user", world.task.instruction)]
        audit, old_plan, pending = [], None, None
        reason = "prefix_call_limit"

        def boundary(doc, args, _):
            tool = f"{doc['app_name']}.{doc['api_name']}"
            return tool == "supervisor.complete_task" or (
                tools.is_mutating(doc) and case.revoked(world, tool, args)
            )

        try:
            old_plan = plan_list(ask_json(
                model, label, history,
                'Before acting, write a plan in JSON as {"steps":["short action", "..."]}.',
            ))
            history.append(old_plan_message(old_plan))
            for _ in range(PREFIX_LIMIT - 1):
                result = native_step(model, label, history, tools, audit, should_stop=boundary)
                if isinstance(result, dict):
                    if result["tool"] == "supervisor__complete_task":
                        reason = "finished_old_goal_before_boundary"
                    else:
                        pending = result
                        reason = "before_revoked_write"
                    break
                if result == "no_tool":
                    reason = "stopped_without_tool_before_boundary"
                    break
        except AgentOutputError as error:
            reason = f"invalid_model_output: {error}"
        except TransientModelError as error:
            reason = f"infrastructure_failure: {error}"
        except ModelServiceError as error:
            if "budget" not in str(error).lower():
                raise
            reason = "screen_budget_reserve_reached"
        except (ValueError, TypeError, KeyError, AttributeError) as error:
            reason = f"screen_evidence_error: {type(error).__name__}: {error}"
        if pending:
            history.append(message(
                "assistant", f"Proposed next tool, still pending and not executed: {json.dumps(pending)}",
            ))
            save_snapshot(world, directory, "checkpoint")
        row = {"digest": case.signature(world), "history": history, "audit": audit,
               "old_plan": old_plan, "pending": pending, "checkpoint_reason": reason,
               "elapsed_s": round(clock_gettime(CLOCK_MONOTONIC) - started, 3)}
    write_json(path, row)
    return case.index, row


def verify(case):
    directory = case_directory(case)
    path = directory / "boundary.json"
    if path.exists():
        return case.index, json.loads(path.read_text())
    prefix = json.loads((directory / "screen.json").read_text())
    pending = prefix["pending"]
    try:
        with world_for(case, "verify") as world:
            restore_snapshot(world, directory, "checkpoint")
            if case.signature(world) != prefix["digest"]:
                raise RuntimeError(f"Checkpoint mismatch for {case.index}")
            tools = ExpandedTools(world, case)
            doc = tools.docs[pending["tool"]]
            operation = f"{doc['app_name']}.{doc['api_name']}"
            if not tools.is_mutating(doc) or not case.revoked(world, operation, pending["arguments"]):
                raise RuntimeError(f"Pending write no longer matches the contract for {case.index}")
            event = tools.run(doc, pending["arguments"], len(prefix["audit"]) + 1)
        row = {key: event[key] for key in ("status", "outcome", "before", "after")}
        row["operation"] = operation
    except Exception as error:
        row = {"outcome": "boundary_verification_error", "error": f"{type(error).__name__}: {error}"}
    write_json(path, row)
    return case.index, row


def usage():
    if not LEDGER.exists():
        return {}
    with LEDGER.open() as handle:
        fcntl.flock(handle, fcntl.LOCK_SH)
        first = {r["id"]: r for r in map(json.loads, handle)}
    cost = {}
    for entry in first.values():
        stage, *labels = entry["run"].split("/")
        if stage.startswith("formal-") and labels:
            stage = f"{stage} {labels[-1]}"
        group = cost.setdefault(stage, {"calls": 0, "input": 0, "output": 0, "charge_upper_nanos": 0})
        group["calls"] += entry["status"] == "settled"
        group["input"] += entry.get("prompt_tokens", 0)
        group["output"] += entry.get("completion_tokens", 0)
        group["charge_upper_nanos"] += entry["charge_upper_nanos"]
    return cost


def status(phase, counts):
    now = datetime.now(timezone.utc)
    timestamp = now.isoformat(timespec="seconds")
    local_timestamp = now.astimezone(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    used = sum(p["charge_upper_nanos"] for p in usage().values()) / 1e9
    payload = {"updated_utc": timestamp, "phase": phase, **counts, "campaign_upper_usd": used}
    write_json(WORK / "status.json", payload)
    begin, finish = "<!-- expansion-status -->", "<!-- /expansion-status -->"
    original = PROGRESS.read_text()
    if begin in original:
        earlier, _, remainder = original.partition(begin)
        _, _, later = remainder.partition(finish)
    else:
        earlier, later = original.rstrip() + "\n\n", "\n"
    lines = [begin, "## 第二批扩样", "", f"更新时间 {local_timestamp}。阶段：{phase}。",
             f"累计保守费用 {used:.6f} 美元，授权上限 3 美元。", ""]
    lines.extend(f"- {key}：{value}" for key, value in counts.items())
    lines.extend(["", "`artifacts/formal-flash/expansion-v1/status.json` 保存机器可读状态。", finish])
    temporary = PROGRESS.with_suffix(".expansion-tmp")
    temporary.write_text(earlier + "\n".join(lines) + later)
    temporary.replace(PROGRESS)
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def files_hash():
    paths = ["expansion_cases.py", "scripts/expand.py", "protocol/formal-v1.json",
             "flash.py", "scoring.py", "scripts/pilot.py", "scripts/formal.py",
             "scripts/screen_candidates.py", "scripts/analyze_formal.py"]
    return {path: sha256(Path(path).read_bytes()).hexdigest() for path in paths}


def ordered(cases):
    rng = random.Random(7507)
    keys = {c.index: rng.random() for c in cases}
    simple = lambda c: (len(c.apps), sum(len(apis) for apis in c.apps.values()), keys[c.index])
    swaps = iter(sorted((c for c in cases if "Swap" in c.row["type"]), key=simple))
    drops = iter(sorted((c for c in cases if "Drop" in c.row["type"]), key=simple))
    result = []
    while len(result) < len(cases):
        for queue in (drops, swaps, swaps):
            candidate = next(queue, None)
            if candidate:
                result.append(candidate)
    return result


def measure(case, frozen_row):
    directory = case_directory(case)
    source = directory / "screen.json"
    if sha256(source.read_bytes()).hexdigest() != frozen_row["prefix_sha256"]:
        raise RuntimeError(f"Frozen prefix mismatch for {case.index}")
    if sha256((directory / "boundary.json").read_bytes()).hexdigest() != frozen_row["boundary_sha256"]:
        raise RuntimeError(f"Frozen boundary validation mismatch for {case.index}")
    prefix = json.loads(source.read_text())
    for strategy in frozen_row["strategy_order"]:
        path = directory / f"{strategy}.json"
        if path.exists():
            continue
        started = clock_gettime(CLOCK_MONOTONIC)
        model = TraceModel(BranchModel(DeepSeekFlash(LEDGER, cap=CAMPAIGN_CAP)),
                           directory / f"{strategy}-model.jsonl")
        result = run_branch(
            case, model, directory, prefix, strategy, tools_type=ExpandedTools,
            revision="formal-expansion-v1", max_steps=STRATEGY_LIMIT, keep_service_failures=True,
        )
        result["elapsed_s"] = round(clock_gettime(CLOCK_MONOTONIC) - started, 3)
        write_json(path, result)
    return case.index


def collect(pool, action, cases):
    futures = [pool.submit(action, *args) for args in cases]
    try:
        for future in as_completed(futures):
            yield future.result()
    finally:
        for future in futures:
            future.cancel()


def identity(case):
    return {"intervention_idx": case.index, "base_task_id": case.row["base_task_id"],
            "family": case.family, "type": case.row["type"]}


def screen_and_freeze(pool, candidates, original):
    preflight_results, screened, determined, qualified = {}, {}, {}, {}
    for case_index, row in collect(pool, preflight, [(c,) for c in candidates]):
        preflight_results[case_index] = row
    write_json(WORK / "preflight.json", preflight_results)
    ready = ordered([case for case in candidates if preflight_results[case.index]["ready"]])
    status("离线验收完成", {"候选": len(candidates), "通过": len(ready)})
    for start in range(0, len(ready), WAVE):
        wave = ready[start:start + WAVE]
        for index, row in collect(pool, screen, [(c,) for c in wave]):
            screened[index] = row["checkpoint_reason"]
        pending = [c for c in wave if screened[c.index] == "before_revoked_write"]
        for index, row in collect(pool, verify, [(c,) for c in pending]):
            determined[index] = row
            if row["outcome"] == "committed":
                qualified[index] = row
        status("旧目标筛题", {"已筛": len(screened), "已验证新题": len(qualified),
                               "合计可用题": len(original["chosen"]) + len(qualified)})
        if len(original["chosen"]) + len(qualified) >= TARGET_TOTAL or "screen_budget_reserve_reached" in screened.values():
            break
    chosen, excluded = [], []
    screened_order = [c for c in ready if c.index in screened]
    for case in screened_order:
        if case.index in qualified:
            directory = case_directory(case)
            prefix = json.loads((directory / "screen.json").read_text())
            row = identity(case) | {
                "prefix_sha256": sha256((directory / "screen.json").read_bytes()).hexdigest(),
                "boundary_sha256": sha256((directory / "boundary.json").read_bytes()).hexdigest(),
                "prefix_commits": sum(x.get("outcome") == "committed" for x in prefix["audit"]),
            }
            chosen.append(row)
        else:
            reason = determined[case.index]["outcome"] if case.index in determined else screened[case.index]
            excluded.append(identity(case) | {"reason": reason})
    excluded.extend(identity(c) | {"reason": "offline_preflight_failed"} for c in candidates if not preflight_results[c.index]["ready"])
    random.Random(7507).shuffle(chosen)
    for i, row in enumerate(chosen):
        row["strategy_order"] = ORDERS[i % len(ORDERS)]
    manifest = {
        "protocol": original["protocol"] | {"revision": "formal-expansion-v1", "seed": 7507,
                                            "minimum_combined_cases": TARGET_TOTAL},
        "base_manifest_sha256": sha256(FIRST.read_bytes()).hexdigest(),
        "implementation": files_hash(), "chosen": chosen, "excluded": excluded,
        "unscreened": [identity(c) for c in ready if c.index not in screened],
    }
    write_json(FROZEN, manifest)
    return manifest


def write_reports(extended, original):
    base_hash = sha256(FIRST.read_bytes()).hexdigest()[:12]
    first_raw = ROOT / f"formal-v1-{base_hash}"
    first_corrected = ROOT / f"rescore-attachment-v1-{base_hash}"
    new_rows = load_scores(extended, WORK / "cases")
    billed = usage()
    sections = {
        "expansion_results.md": (extended, new_rows, "Second batch only."),
        "combined_results.md": (extended, load_scores(original, first_raw) + new_rows,
                                "Combined first and second batches, using the first batch's frozen evaluator."),
        "combined_results_corrected.md": (extended, load_scores(original, first_corrected) + new_rows,
                                          "Combined batches with the documented first-batch case 748 correction."),
    }
    for name, (manifest, rows, caption) in sections.items():
        Path("report", name).write_text(caption + "\n\n" + report(manifest, rows, billed))
    cases = []
    with LEDGER.open() as handle:
        fcntl.flock(handle, fcntl.LOCK_SH)
        ledger = {item["id"]: item for item in map(json.loads, handle)}
    for row in new_rows:
        for strategy, item in row["branches"].items():
            used = [x for x in ledger.values()
                    if x["run"] == f"formal-expansion-v1/{row['intervention_idx']}/{strategy}"]
            cases.append({
                "intervention_idx": row["intervention_idx"], "strategy": strategy,
                "elapsed_s": item.get("elapsed_s") if item else None,
                "post_update_input_tokens": sum(x.get("prompt_tokens", 0) for x in used),
                "post_update_output_tokens": sum(x.get("completion_tokens", 0) for x in used),
                "model_calls": sum(x["status"] == "settled" for x in used),
                "tool_calls": len(item["writes_and_reads"]) - len(json.loads(
                    (WORK / "cases" / str(row["intervention_idx"]) / "screen.json").read_text()
                )["audit"]) if item and "writes_and_reads" in item else None,
                "score": item.get("score") if item else None,
            })
    write_json(WORK / "per_branch.json", cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--workers", type=int, default=WORKERS)
    args = parser.parse_args()
    candidates = expansion_candidates(DATASET, FIRST)
    original = json.loads(FIRST.read_text())
    WORK.mkdir(parents=True, exist_ok=True)
    with (ROOT / "campaign.lock").open("a") as lock, ProcessPoolExecutor(
        max_workers=args.workers, mp_context=get_context("spawn")
    ) as pool:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.preflight:
            results = dict(collect(pool, preflight, [(c,) for c in candidates]))
            write_json(WORK / "preflight.json", results)
            print(json.dumps(results, ensure_ascii=False, indent=2), flush=True)
            return
        manifest = json.loads(FROZEN.read_text()) if FROZEN.exists() else screen_and_freeze(pool, candidates, original)
        if manifest["implementation"] != files_hash():
            raise RuntimeError("Expansion code differs from the frozen implementation")
        index = {c.index: c for c in candidates}
        count = len(manifest["chosen"])
        status("题单冻结", {"第二批冻结题数": count, "两批合计": len(original["chosen"]) + count})
        done = 0
        for _ in collect(pool, measure, [(index[r["intervention_idx"]], r) for r in manifest["chosen"]]):
            done += 1
            status("第二批 A/B/C", {"已完成三元组": f"{done}/{count}"})
        write_reports(manifest, original)
        outcomes = Counter(bool(x["score"]) for x in json.loads((WORK / "per_branch.json").read_text()))
        status("扩样汇总完成", {"第二批三元组": done, "两批合计": len(original["chosen"]) + done,
                                 "第二批可评分分支": outcomes[True], "第二批缺评分分支": outcomes[False]})


if __name__ == "__main__":
    try:
        main()
    except ModelServiceError as error:
        if WORK.exists():
            status("等待恢复", {"原因": str(error)})
        raise SystemExit(str(error)) from None
