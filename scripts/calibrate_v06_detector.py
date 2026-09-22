#!/usr/bin/env python3

import argparse
import hashlib
import json
from pathlib import Path

from otshield.calibration import (
    calibrate_robust_interval_threshold,
)


EXPECTED_SCHEMA = (
    "OTB-LAB-RESILIENCE-OBSERVATIONS/0.1"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def canonical_path(path: Path) -> str:
    """Serialize repository-relative paths consistently on every platform."""
    return path.as_posix()


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--source",
        type=Path,
        default=Path(
            "evidence/repeatability/"
            "20260920T182506Z"
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "research/v0.6_calibration.json"
        ),
    )

    args = parser.parse_args()

    source = args.source
    historical = Path("evidence/repeatability/20260920T182506Z")
    if source.resolve() != historical.resolve():
        raise SystemExit("Only the preregistered historical source is permitted")

    observation_files = sorted(
        source.glob(
            "trial-*/clean/observations.json"
        )
    )

    if len(observation_files) != 5:
        raise SystemExit(
            "Expected exactly five historical "
            "v0.5 clean observation files; "
            f"found {len(observation_files)}"
        )

    intervals = []
    file_records = []

    for path in observation_files:
        protocol_path = path.parent / "protocol.json"
        protocol = json.loads(protocol_path.read_text())
        if protocol.get("condition", {}).get("name") != "clean":
            raise SystemExit(f"Not a clean condition: {protocol_path}")
        document = json.loads(
            path.read_text()
        )

        if document.get("schema") != EXPECTED_SCHEMA:
            raise SystemExit(
                f"Unexpected schema in {path}"
            )

        eligible = []

        for record in document.get(
            "records",
            [],
        ):
            interval = record.get(
                "observed_interval_ms"
            )

            if (
                record.get("expected_anomaly")
                is False
                and record.get(
                    "transport_status"
                )
                == "matched"
                and isinstance(
                    interval,
                    (int, float),
                )
                and not isinstance(
                    interval,
                    bool,
                )
                and interval > 0
            ):
                eligible.append(
                    float(interval)
                )

        intervals.extend(eligible)

        file_records.append(
            {
                "path": canonical_path(path),
                "sha256": sha256(path),
                "protocol_sha256": sha256(protocol_path),
                "eligible_intervals":
                    len(eligible),
            }
        )

    calibration = (
        calibrate_robust_interval_threshold(
            intervals,
            multiplier=3.5,
            scale_factor=1.4826,
            min_samples=30,
        )
    )

    study_path = source / "study.json"

    if not study_path.is_file():
        raise SystemExit(
            "Missing source study.json"
        )

    study = json.loads(
        study_path.read_text()
    )

    output = {
        "schema":
            "OTB-V06-CALIBRATION/0.1",

        "detector":
            "robust-polling-burst-v1",

        "calibration_policy": {
            "condition":
                "clean",

            "expected_anomaly":
                False,

            "transport_status":
                "matched",

            "interval_requirement":
                "observed_interval_ms > 0",

            "method":
                "median - 3.5 * "
                "(1.4826 * MAD)",

            "multiplier":
                3.5,

            "mad_scale_factor":
                1.4826,

            "minimum_samples":
                30,

            "v06_test_data_used":
                False,
        },

        "source_study": {
            "root":
                canonical_path(source),

            "study_json":
                canonical_path(study_path),

            "study_json_sha256":
                sha256(study_path),

            "execution_git_commit":
                study.get(
                    "execution_git_commit"
                ),

            "aggregation_git_commit":
                study.get(
                    "aggregation_git_commit"
                ),

            "study_timestamp":
                study.get(
                    "study_timestamp"
                ),
        },

        "source_files":
            file_records,

        "calibration":
            calibration.to_dict(),
    }

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    serialized = json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with args.output.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(serialized)

    print(
        "Eligible intervals:",
        calibration.sample_count,
    )

    print(
        "Median ms:",
        calibration.median_ms,
    )

    print(
        "MAD ms:",
        calibration.mad_ms,
    )

    print(
        "Robust sigma ms:",
        calibration.robust_sigma_ms,
    )

    print(
        "Threshold ms:",
        calibration.threshold_ms,
    )

    print(
        "Evidence:",
        args.output,
    )


if __name__ == "__main__":
    main()
