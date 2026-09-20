#!/usr/bin/env python3
"""Evaluate one normalized laboratory capture with both frozen v0.6 detectors."""
import argparse
from pathlib import Path
from otshield.paired_v06 import write_paired_capture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("normalized", type=Path)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("--calibration", type=Path, default=Path("research/v0.6_calibration.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    write_paired_capture(args.normalized, args.protocol, args.calibration, args.output)


if __name__ == "__main__":
    main()
