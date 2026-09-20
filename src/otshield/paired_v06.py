"""Paired v0.6 evaluation; never calibrates on evaluated observations."""
import hashlib
import json
from dataclasses import replace
from pathlib import Path

from .detectors import PollingBurstDetector, RobustPollingBurstDetector
from .lab_resilience import _evaluate_resilience_capture, _hash

CALIBRATION_SHA256 = "d8676d4670ba44c0f4b1045e5e07dd2d251ccb4a63ed8089b9b9aada729ea234"
DETECTORS = ("polling-burst-v1", "robust-polling-burst-v1")


def load_calibration(path):
    """Accept only the exact independently frozen evidence, including provenance."""
    payload = Path(path).read_bytes()
    if hashlib.sha256(payload).hexdigest() != CALIBRATION_SHA256:
        raise ValueError("invalid or changed frozen v0.6 calibration")
    return json.loads(payload)


def evaluate_paired_capture(normalized, protocol, calibration_path):
    calibration = load_calibration(calibration_path)
    if protocol.get("condition", {}).get("threshold_ms") != 50.0:
        raise ValueError("v0.6 baseline threshold must be 50 ms")
    if normalized.get("provenance", {}).get("dataset_id") != protocol.get("dataset_id"):
        raise ValueError("capture and protocol dataset_id mismatch")
    records = normalized.get("records")
    if not isinstance(records, list):
        raise ValueError("normalized records must be a list")
    for record in records:
        try:
            metadata = record["context"]["value_metadata"]
            tid = metadata["transaction_id"]
            if type(tid) is not int or metadata["status"] not in (
                    "matched", "unmatched_request", "unmatched_response"):
                raise ValueError("invalid transaction or transport status")
        except (KeyError, TypeError):
            raise ValueError("malformed normalized record") from None
    output = {}
    for detector in (PollingBurstDetector(50.0), RobustPollingBurstDetector(
            calibration["calibration"]["threshold_ms"])):
        result, observations = _evaluate_resilience_capture(normalized, protocol, detector)
        result = replace(result, benchmark_version="0.6.0-alpha", environment={
            **result.environment,
            "normalized_capture_sha256": _hash(normalized),
            "calibration_sha256": CALIBRATION_SHA256,
            "paired_detectors": list(DETECTORS),
        })
        output[detector.name] = (result, observations)
    return output


def write_paired_capture(normalized_path, protocol_path, calibration_path, output):
    normalized_path, protocol_path, output = map(Path, (normalized_path, protocol_path, output))
    normalized = json.loads(normalized_path.read_text())
    paired = evaluate_paired_capture(normalized,
                                    json.loads(protocol_path.read_text()), calibration_path)
    output.mkdir(parents=True, exist_ok=True)
    for name, (result, observations) in paired.items():
        result.write(output / f"{name}.result.json", output / f"{name}.result.md")
        (output / f"{name}.observations.json").write_text(json.dumps({
            "schema": "OTB-LAB-RESILIENCE-OBSERVATIONS/0.1",
            "detector": name, "normalized_capture_sha256": _hash(normalized),
            "records": observations,
        }, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return paired
