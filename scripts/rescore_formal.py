"""Regrade all stored branches with the case-748 attachment model name fixed."""

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
import json
from multiprocessing import get_context
from pathlib import Path
from uuid import uuid4

from appworld import AppWorld

from formal_cases import candidates_from
from scripts.analyze_formal import campaign_usage, load_scores, report
from scripts.formal import digest
from scripts.pilot import DATASET, restore_snapshot, score_branch, write_json
from scripts.screen_candidates import ROOT, SCREEN, WORKERS


def rescore_case(case, original, revised):
    if case.index == 748:
        original_code = case.row["evaluation_code"]
        corrected = original_code.replace("gmail.EmailAttachment", "gmail.Attachment")
        if corrected == original_code:
            raise ValueError("The pinned case no longer contains the expected evaluator typo")
        case = replace(case, row=case.row | {"evaluation_code": corrected})
    prefix = json.loads((SCREEN / str(case.index) / "prefix.json").read_text())
    original = original / str(case.index)
    revised = revised / str(case.index)
    revised.mkdir(exist_ok=True)
    changes = []
    for strategy in "ABC":
        previous = json.loads((original / f"{strategy}.json").read_text())
        with AppWorld(task_id=case.row["base_task_id"], experiment_name=f"rescore-{uuid4().hex}",
                      load_ground_truth=True) as world:
            restore_snapshot(world, original, f"{strategy}-final")
            trial = json.loads((original / f"{strategy}-unscored.json").read_text())
            result = score_branch(case, world, prefix, trial)
        before, after = previous["score"], result["score"]
        keys = {key for key in before if before[key] != after[key]}
        if keys:
            if case.index != 748 or keys - {"final_pass", "strict_pass"}:
                raise RuntimeError(f"Unexpected score changes for {case.index}/{strategy}: {keys}")
            changes.append({"case": case.index, "strategy": strategy,
                            "before": before, "after": after})
        write_json(revised / f"{strategy}.json", result)
    print(case.index, f"regraded 3 branches, {len(changes)} changed", flush=True)
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    original = ROOT / f"formal-v1-{digest(args.manifest)[:12]}"
    revised = ROOT / f"rescore-attachment-v1-{digest(args.manifest)[:12]}"
    revised.mkdir(exist_ok=True)
    index = {c.index: c for c in candidates_from(DATASET)}
    cases = [index[r["intervention_idx"]] for r in manifest["chosen"]]
    with ProcessPoolExecutor(max_workers=WORKERS, mp_context=get_context("spawn")) as executor:
        futures = [executor.submit(rescore_case, case, original, revised) for case in cases]
        changes = [change for future in futures for change in future.result()]
    write_json(revised / "changes.json", changes)
    overview = (
        "# Sensitivity analysis for a Gmail model name\n\n"
        "In case 748 the upstream evaluator refers to `gmail.EmailAttachment`, while the pinned "
        "AppWorld model is `gmail.Attachment`. This secondary analysis changes that name in both "
        "assertions and regrades all saved final states. The primary frozen table and model traces "
        "are preserved. No model calls are made.\n\n"
    )
    args.output.write_text(
        overview + report(manifest, load_scores(manifest, revised), campaign_usage(ROOT / "usage.jsonl"))
    )
    print(args.output)


if __name__ == "__main__":
    main()
