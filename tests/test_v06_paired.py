import copy
import json
from pathlib import Path

import pytest
from otshield.paired_v06 import evaluate_paired_capture, load_calibration, write_paired_capture, DETECTORS
from test_lab_resilience import _dataset, _protocol

CALIBRATION = Path("research/v0.6_calibration.json")


def test_same_capture_and_frozen_threshold():
    dataset, protocol = _dataset(), _protocol()
    before = copy.deepcopy((dataset, protocol))
    paired = evaluate_paired_capture(dataset, protocol, CALIBRATION)
    baseline, robust = [paired[name] for name in DETECTORS]
    assert baseline[0].environment["threshold_ms"] == 50.0
    assert robust[0].environment["threshold_ms"] == 100.23721899414062
    assert baseline[0].environment["normalized_capture_sha256"] == robust[0].environment["normalized_capture_sha256"]
    assert [{k: v for k, v in row.items() if k != "alert"} for row in baseline[1]] == [
        {k: v for k, v in row.items() if k != "alert"} for row in robust[1]]
    assert (dataset, protocol) == before
    assert baseline[1][-1]["alert"] is False
    assert robust[1][-1]["alert"] is True


def test_no_label_or_planned_interval_leakage():
    dataset, protocol = _dataset(), _protocol()
    original = evaluate_paired_capture(dataset, protocol, CALIBRATION)
    for row in dataset["records"]:
        row["telemetry"]["label"] = True
    for row in protocol["requests"]:
        row["expected_anomaly"] = not row["expected_anomaly"]
        row["planned_interval_ms"] = 1.0
    changed = evaluate_paired_capture(dataset, protocol, CALIBRATION)
    for name in DETECTORS:
        assert [r["alert"] for r in original[name][1]] == [r["alert"] for r in changed[name][1]]


@pytest.mark.parametrize("payload", [b"{}", b"NaN", b"", b"not json"])
def test_invalid_calibration_fails_closed(tmp_path, payload):
    path = tmp_path / "bad.json"
    path.write_bytes(payload)
    with pytest.raises(ValueError, match="calibration"):
        evaluate_paired_capture(_dataset(), _protocol(), path)


def test_tuned_calibration_rejected(tmp_path):
    data = json.loads(CALIBRATION.read_text())
    data["calibration"]["threshold_ms"] = 99.0
    path = tmp_path / "tuned.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_calibration(path)
    protocol = _protocol()
    protocol["condition"]["threshold_ms"] = 99.0
    with pytest.raises(ValueError):
        evaluate_paired_capture(_dataset(), protocol, CALIBRATION)


def test_separate_artifacts(tmp_path):
    normalized, protocol = tmp_path / "normalized.json", tmp_path / "protocol.json"
    normalized.write_text(json.dumps(_dataset()))
    protocol.write_text(json.dumps(_protocol()))
    write_paired_capture(normalized, protocol, CALIBRATION, tmp_path)
    for name in DETECTORS:
        for suffix in ("result.json", "result.md", "observations.json"):
            assert (tmp_path / f"{name}.{suffix}").is_file()


def test_detectors_receive_no_ground_truth(monkeypatch):
    from otshield.detectors import PollingBurstDetector
    original = PollingBurstDetector.predict
    seen = []
    def inspect(self, events):
        assert all(event.label is False for event in events)
        seen.append(events)
        return original(self, events)
    monkeypatch.setattr(PollingBurstDetector, "predict", inspect)
    evaluate_paired_capture(_dataset(), _protocol(), CALIBRATION)
    assert len(seen) == 2
    assert seen[0] == seen[1]


def test_v05_protocol_threshold_behavior_unchanged():
    from otshield.lab_resilience import evaluate_resilience_capture
    protocol = _protocol()
    protocol["condition"]["threshold_ms"] = 101.0
    result, details = evaluate_resilience_capture(_dataset(), protocol)
    assert result.environment["threshold_ms"] == 101.0
    assert details[-1]["alert"] is True
    assert result.detector_adapter == "polling-burst-v1"
