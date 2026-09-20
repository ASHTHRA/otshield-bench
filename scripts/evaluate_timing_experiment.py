#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from otshield.lab_timing import evaluate_timing_capture


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("normalized", type=Path)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("--result-json", type=Path, required=True)
    parser.add_argument("--result-markdown", type=Path, required=True)
    parser.add_argument("--details", type=Path, required=True)

    args = parser.parse_args()

    normalized = json.loads(args.normalized.read_text())
    protocol = json.loads(args.protocol.read_text())

    manifest, details = evaluate_timing_capture(
        normalized,
        protocol,
    )

    manifest.write(
        args.result_json,
        args.result_markdown,
    )

    args.details.write_text(
        json.dumps(
            {
                "schema": "OTB-LAB-TIMING-OBSERVATIONS/0.1",
                "records": details,
            },
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )

    metrics = manifest.effectiveness

    print("Total:", metrics["total"])
    print("TP:", metrics["tp"])
    print("FP:", metrics["fp"])
    print("FN:", metrics["fn"])
    print("TN:", metrics["tn"])
    print("Precision:", metrics["precision"])
    print("Recall:", metrics["recall"])
    print("F1:", metrics["f1"])


if __name__ == "__main__":
    main()
