#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from otshield.lab_resilience import (
    evaluate_resilience_capture,
)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("normalized", type=Path)
    parser.add_argument("protocol", type=Path)

    parser.add_argument(
        "--result-json",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--result-markdown",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--observations",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    normalized = json.loads(
        args.normalized.read_text()
    )

    protocol = json.loads(
        args.protocol.read_text()
    )

    manifest, details = evaluate_resilience_capture(
        normalized,
        protocol,
    )

    manifest.write(
        args.result_json,
        args.result_markdown,
    )

    args.observations.write_text(
        json.dumps(
            {
                "schema":
                "OTB-LAB-RESILIENCE-OBSERVATIONS/0.1",
                "records": details,
            },
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )

    m = manifest.effectiveness

    print("TOTAL =", m["total"])
    print("OBSERVED =", m["observed"])
    print("DROPPED =", m["dropped"])
    print("COVERAGE =", m["coverage"])
    print("TP =", m["tp"])
    print("FP =", m["fp"])
    print("FN =", m["fn"])
    print("TN =", m["tn"])
    print("PRECISION =", m["precision"])
    print("RECALL =", m["recall"])
    print("F1 =", m["f1"])
    print(
        "END_TO_END_RECALL =",
        m["end_to_end_recall"],
    )


if __name__ == "__main__":
    main()
