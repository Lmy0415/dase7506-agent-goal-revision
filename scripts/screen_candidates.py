"""Screen AppWorld candidates using only a common prefix under the old goal."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import fcntl
import json
from multiprocessing import get_context
from pathlib import Path
from uuid import uuid4

from appworld import AppWorld

from flash import DeepSeekFlash, ModelServiceError, TransientModelError
from formal_cases import candidates_from
from scripts.offline_probe import evaluate_revised
from scripts.pilot import (
    DATASET, SYSTEM, AgentOutputError, Tools, ask_json, message, native_step,
    old_plan_message, plan_list, restore_snapshot, save_snapshot, write_json,
)


ROOT = Path("artifacts/formal-flash")
SCREEN = ROOT / "screen-v1"
CAMPAIGN_CAP = 3_000_000_000  # separate from the previous US$1 pilot
PREFIX_MODEL_CALLS = 20  # includes the initial plan
WORKERS = 4  # AppWorld state is isolated in separate processes


class FormalTools(Tools):
    def is_mutating(self, doc):
        return super().is_mutating(doc) or (doc["app_name"], doc["api_name"]) == ("gmail", "download_attachment")

    def decode(self, call):
        function = call["function"]
        doc = self.docs.get(function["name"])
        if doc and function["arguments"] in ("", None) and not any(
            p["required"] and not p["name"].endswith("access_token") for p in doc["parameters"]
        ):
            call = call | {"function": function | {"arguments": "{}"}}
        return super().decode(call)


def model_client():
    return DeepSeekFlash(ROOT / "usage.jsonl", cap=CAMPAIGN_CAP)


def screen_candidate(case, model, directory):
    label = f"screen-v1/{case.index}/prefix"
    with AppWorld(task_id=case.row["base_task_id"], experiment_name=f"screen-{uuid4().hex}",
                  load_ground_truth=True) as world:
        tools = FormalTools(world, case)
        history = [message("system", SYSTEM), message("user", world.task.instruction)]
        audit = []
        old_plan = None
        pending = None
        reason = "prefix_call_limit"

        def at_boundary(doc, args, rows):
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
            for _ in range(PREFIX_MODEL_CALLS - 1):
                result = native_step(model, label, history, tools, audit, should_stop=at_boundary)
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

        if pending:
            history.append(message(
                "assistant", f"Proposed next tool, still pending and not executed: {json.dumps(pending)}",
            ))
            save_snapshot(world, directory, "checkpoint")
        return {
            "intervention_idx": case.index, "base_task_id": case.row["base_task_id"],
            "type": case.row["type"], "family": case.family,
            "digest": case.signature(world), "history": history, "audit": audit,
            "old_plan": old_plan, "pending": pending, "checkpoint_reason": reason,
        }


def load_or_screen(case):
    directory = SCREEN / str(case.index)
    directory.mkdir(exist_ok=True)
    path = directory / "prefix.json"
    if path.exists():
        return json.loads(path.read_text())
    prefix = screen_candidate(case, model_client(), directory)
    write_json(path, prefix)
    return prefix


def verify_boundary(case):
    source = SCREEN / str(case.index)
    prefix = json.loads((source / "prefix.json").read_text())
    pending = prefix["pending"]
    with AppWorld(task_id=case.row["base_task_id"], experiment_name=f"boundary-{uuid4().hex}",
                  load_ground_truth=True) as world:
        restore_snapshot(world, source, "checkpoint")
        if case.signature(world) != prefix["digest"]:
            raise RuntimeError(f"{case.index}: boundary snapshot does not match its prefix")
        tools = FormalTools(world, case)
        doc = tools.docs[pending["tool"]]
        if not tools.is_mutating(doc) or not case.revoked(
            world, f"{doc['app_name']}.{doc['api_name']}", pending["arguments"]
        ):
            raise RuntimeError(f"{case.index}: pending write does not match the revoked effect")
        event = tools.run(doc, pending["arguments"], len(prefix["audit"]) + 1)
    return case.index, {
        "operation": pending["tool"], "status": event["status"], "outcome": event["outcome"],
        "before": event["before"], "after": event["after"],
    }


def verify_boundaries(workers):
    source = json.loads((SCREEN / "status.json").read_text())
    cases = [case for case in candidates_from(DATASET)
             if source.get(str(case.index), {}).get("checkpoint_reason") == "before_revoked_write"]
    results = {}

    def update(result):
        index, outcome = result
        results[str(index)] = outcome
        print(index, outcome["operation"], outcome["status"], outcome["outcome"], flush=True)

    if workers == 1:
        for case in cases:
            update(verify_boundary(case))
    else:
        with ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn")) as executor:
            for result in executor.map(verify_boundary, cases):
                update(result)
    write_json(SCREEN / "boundaries.json", results)


def run(*, validate_local, workers=WORKERS):
    cases = candidates_from(DATASET)
    if validate_local:
        for case in cases:
            with AppWorld(task_id=case.row["base_task_id"], experiment_name=f"check-{uuid4().hex}",
                          load_ground_truth=True) as world:
                tools = FormalTools(world, case)
                digest = case.signature(world)[:12]
                retained = case.retained(world)
                assertions = evaluate_revised(world, case.row)
                if sum(assertions) == 0:
                    raise RuntimeError(f"{case.index}: revised evaluator recorded no assertions")
                print(case.index, len(tools.definitions), digest, retained, assertions, flush=True)
        return
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / "campaign.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        SCREEN.mkdir(exist_ok=True)
        status = {}
        status_path = SCREEN / "status.json"

        def update(prefix):
            index = prefix["intervention_idx"]
            status[str(index)] = {
                "base_task_id": prefix["base_task_id"], "type": prefix["type"],
                "checkpoint_reason": prefix["checkpoint_reason"],
                "prefix_commits": sum(r.get("outcome") == "committed" for r in prefix["audit"]),
            }
            write_json(status_path, status)
            print(index, status[str(index)], flush=True)

        pending = []
        for case in cases:
            if (SCREEN / str(case.index) / "prefix.json").exists():
                update(load_or_screen(case))
            else:
                pending.append(case)
        if workers == 1:
            for case in pending:
                update(load_or_screen(case))
        elif pending:
            with ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn")) as executor:
                futures = [executor.submit(load_or_screen, case) for case in pending]
                try:
                    for future in as_completed(futures):
                        update(future.result())
                finally:
                    for future in futures:
                        future.cancel()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--validate-local", action="store_true")
    action.add_argument("--verify-boundaries", action="store_true")
    parser.add_argument("--workers", type=int, choices=range(1, WORKERS + 1), default=WORKERS)
    args = parser.parse_args()
    try:
        if args.verify_boundaries:
            verify_boundaries(args.workers)
        else:
            run(validate_local=args.validate_local, workers=args.workers)
    except (ModelServiceError, BlockingIOError) as error:
        raise SystemExit(str(error)) from None
