#!/usr/bin/env python3
"""Generate a descriptive OTShield lab baseline report."""

import argparse
import json
from pathlib import Path

from otshield.lab_baseline import write_lab_report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    args = parser.parse_args()

    document = json.loads(args.input.read_text())

    summary = write_lab_report(
        document,
        args.json,
        args.markdown,
    )

    print("Dataset:", summary["provenance"]["dataset_id"])
    print("Transactions:", summary["transactions"]["total"])
    print("Matched:", summary["transactions"]["matched"])
    print("Latency p50 ms:", summary["latency_ms"]["p50"])
    print("Latency p95 ms:", summary["latency_ms"]["p95"])
    print("Latency max ms:", summary["latency_ms"]["max"])


if __name__ == "__main__":
    main()
