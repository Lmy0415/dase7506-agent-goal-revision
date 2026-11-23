"""Rebuild paired tables from a frozen AppWorld run and its usage ledger."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import random
from statistics import mean

from scripts.formal import digest
from scripts.screen_candidates import ROOT


STRATEGIES = "ABC"


def load_scores(manifest, folder):
    rows = []
    for case in manifest["chosen"]:
        branches = {}
        for strategy in STRATEGIES:
            path = folder / str(case["intervention_idx"]) / f"{strategy}.json"
            branches[strategy] = json.loads(path.read_text()) if path.exists() else None
        rows.append(case | {"branches": branches})
    return rows


def campaign_usage(path):
    # Every reservation has one ID. The last entry is its settled value or reserve.
    saved = {row["id"]: row for row in map(json.loads, path.read_text().splitlines())}
    usages = defaultdict(lambda: {"calls": 0, "input": 0, "output": 0, "charge_upper_nanos": 0})
    for row in saved.values():
        stage, *labels = row["run"].split("/")
        if stage == "formal-v1" and labels:
            stage = f"{stage} {labels[-1]}"
        ledger = usages[stage]
        ledger["calls"] += row["status"] == "settled"
        ledger["input"] += row.get("prompt_tokens", 0)
        ledger["output"] += row.get("completion_tokens", 0)
        ledger["charge_upper_nanos"] += row["charge_upper_nanos"]
    return usages


def ratio(values):
    known = [x for x in values if x is not None]
    return f"{sum(known)}/{len(known)}" if known else "N/A"


def summarize(rows, strategy):
    branches = [row["branches"][strategy] for row in rows]
    scores = [branch["score"] for branch in branches if branch and branch["score"] is not None]
    final_pass, violation, strict = ([row[key] for row in scores] for key in ("final_pass", "violation", "strict_pass"))
    missed = [row["violation"] for row in scores if row["final_pass"]]
    satisfied = sum(row["retained_satisfied"] for row in scores)
    known_retained = sum(row["retained_total"] - row["retained_unknown"] for row in scores)
    return [
        strategy, len(rows), ratio(final_pass), ratio(violation), ratio(strict), ratio(missed),
        f"{satisfied}/{known_retained}" if known_retained else "N/A",
        len(rows) - len(scores), violation.count(None),
        sum(row["rejected_forbidden_requests"] for row in scores),
    ]


def paired(rows, treatment, reference, seed):
    differences = {}
    for row in rows:
        scores = [branch and branch["score"] for branch in row["branches"].values()]
        if any(s is None or s["strict_pass"] is None for s in scores):
            continue
        treatment_value = row["branches"][treatment]["score"]["strict_pass"]
        reference_value = row["branches"][reference]["score"]["strict_pass"]
        differences.setdefault(row["family"], []).append(int(treatment_value) - int(reference_value))
    flat = [d for group in differences.values() for d in group]
    if not flat:
        return [f"{treatment} vs {reference}", 0, "N/A", "N/A", "N/A", "N/A"]
    groups = list(differences.values())
    generator = random.Random(seed)
    bootstrap = sorted(
        mean(d for group in generator.choices(groups, k=len(groups)) for d in group)
        for _ in range(4000)
    )
    lower, upper = bootstrap[99], bootstrap[3899]
    return [
        f"{treatment} vs {reference}", len(flat), flat.count(1), flat.count(-1),
        f"{100 * mean(flat):+.1f}", f"[{100 * lower:+.1f}, {100 * upper:+.1f}]",
    ]


def table(head, rows):
    return "\n".join(
        "| " + " | ".join(map(str, row)) + " |"
        for row in [head, ["---"] * len(head), *rows]
    )


def report(manifest, rows, usage):
    sections = ["# Frozen AppWorld evaluation", ""]
    for label in ("All", "Swap", "Drop"):
        selected = [row for row in rows if label == "All" or label in row["type"]]
        sections.extend([
            f"## {label}", "",
            table(
                ["Strategy", "Planned", "Final pass", "Violation", "Strict pass", "Missed by final",
                 "Retained", "Missing", "Unknown violation", "Rejected forbidden requests"],
                [summarize(selected, strategy) for strategy in STRATEGIES],
            ), "",
        ])
    sections.extend([
        "## Paired strict success", "",
        table(
            ["Comparison", "Complete triplets", "Improved", "Worsened", "Difference (pp)", "95% interval (pp)"],
            [paired(rows, treatment, reference, manifest["protocol"]["seed"])
             for treatment, reference in (("C", "B"), ("B", "A"), ("C", "A"))],
        ), "", "## API usage", "",
        table(
            ["Stage", "Settled calls", "Input tokens", "Output tokens", "Conservative USD"],
            [[stage, v["calls"], v["input"], v["output"], f"{v['charge_upper_nanos'] / 1e9:.6f}"]
             for stage, v in usage.items()],
        ), "",
        "Intervals resample task families. With a small or constant sample they can be uninformative. "
        "Counts exclude missing and indeterminate values from their applicable denominators.", "",
    ])
    return "\n".join(sections)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    directory = ROOT / f"formal-v1-{digest(args.manifest)[:12]}"
    usage = campaign_usage(ROOT / "usage.jsonl")
    report_text = report(manifest, load_scores(manifest, directory), usage)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report_text)
    print(args.output)


if __name__ == "__main__":
    main()
