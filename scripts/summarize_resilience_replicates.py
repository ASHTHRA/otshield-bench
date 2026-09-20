#!/usr/bin/env python3

import argparse
import json
import math
import statistics
from pathlib import Path


# Two-sided 95% Student-t critical values.
T95 = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    11: 2.201,
    12: 2.179,
    13: 2.160,
    14: 2.145,
    15: 2.131,
    16: 2.120,
    17: 2.110,
    18: 2.101,
    19: 2.093,
    20: 2.086,
    21: 2.080,
    22: 2.074,
    23: 2.069,
    24: 2.064,
    25: 2.060,
    26: 2.056,
    27: 2.052,
    28: 2.048,
    29: 2.045,
    30: 2.042,
}


def stats(values):
    values = [float(v) for v in values]

    n = len(values)

    if n == 0:
        raise ValueError("no measurements")

    mean = statistics.mean(values)

    if n == 1:
        return {
            "n": 1,
            "mean": mean,
            "sd": None,
            "min": values[0],
            "max": values[0],
            "ci95_low": None,
            "ci95_high": None,
        }

    sd = statistics.stdev(values)
    df = n - 1

    if df not in T95:
        raise ValueError(
            "95% t interval currently supports 2-31 samples"
        )

    margin = T95[df] * sd / math.sqrt(n)

    return {
        "n": n,
        "mean": mean,
        "sd": sd,
        "min": min(values),
        "max": max(values),
        "ci95_low": mean - margin,
        "ci95_high": mean + margin,
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "root",
        type=Path,
        help="root containing trial-*/condition/result.json",
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    grouped = {}

    for result_path in sorted(
        args.root.glob("trial-*/*/result.json")
    ):
        trial = result_path.parents[1].name
        condition = result_path.parent.name

        result = json.loads(
            result_path.read_text()
        )

        m = result["effectiveness"]

        grouped.setdefault(
            condition,
            [],
        ).append(
            {
                "trial": trial,
                "coverage": m["coverage"],
                "precision": m["precision"],
                "recall": m["recall"],
                "f1": m["f1"],
                "end_to_end_recall":
                    m["end_to_end_recall"],
                "tp": m["tp"],
                "fp": m["fp"],
                "fn": m["fn"],
                "tn": m["tn"],
            }
        )

    if not grouped:
        raise SystemExit(
            "No trial result.json files found"
        )

    conditions = {}

    for condition, runs in sorted(
        grouped.items()
    ):
        conditions[condition] = {
            "trials": len(runs),
            "coverage": stats(
                r["coverage"] for r in runs
            ),
            "precision": stats(
                r["precision"] for r in runs
            ),
            "recall": stats(
                r["recall"] for r in runs
            ),
            "f1": stats(
                r["f1"] for r in runs
            ),
            "end_to_end_recall": stats(
                r["end_to_end_recall"]
                for r in runs
            ),
            "raw_runs": runs,
        }

    output = {
        "schema":
            "OTB-RESILIENCE-REPLICATES/0.1",
        "confidence_interval":
            "two-sided 95% Student-t interval over run-level metrics",
        "interpretation":
            "exploratory repeatability analysis",
        "conditions": conditions,
    }

    args.output.write_text(
        json.dumps(
            output,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )

    print()
    print(
        "Condition".ljust(28),
        "N",
        "Recall mean",
        "SD",
        "95% CI",
    )

    print("-" * 82)

    for condition, result in conditions.items():
        r = result["recall"]

        print(
            condition.ljust(28),
            str(r["n"]).rjust(2),
            f'{r["mean"]:.3f}'.rjust(11),
            f'{r["sd"]:.3f}'.rjust(7),
            (
                f'[{r["ci95_low"]:.3f}, '
                f'{r["ci95_high"]:.3f}]'
            ),
        )


if __name__ == "__main__":
    main()
