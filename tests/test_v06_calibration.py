from dataclasses import replace

import pytest

from otshield.calibration import (
    calibrate_robust_interval_threshold,
)
from otshield.core import Event
from otshield.detectors import (
    RobustPollingBurstDetector,
)


def event(interval, label=False):
    return Event(
        event_id=f"event:{interval}",
        timestamp_ms=1.0,
        function_code=3,
        address=0,
        value=50.0,
        interval_ms=float(interval),
        latency_ms=0.0,
        label=label,
    )


def test_robust_detector_threshold_behavior():
    detector = RobustPollingBurstDetector(
        100.0
    )

    events = [
        event(0),
        event(99.9),
        event(100.0),
        event(101.0),
    ]

    alerts = [
        item.alert
        for item in detector.predict(events)
    ]

    assert alerts == [
        False,
        True,
        False,
        False,
    ]

    assert detector.name == (
        "robust-polling-burst-v1"
    )


def test_robust_detector_has_no_label_leakage():
    detector = RobustPollingBurstDetector(
        100.0
    )

    events = [
        event(50.0, False),
        event(150.0, True),
    ]

    flipped = [
        replace(
            item,
            label=not item.label,
        )
        for item in events
    ]

    assert (
        detector.predict(events)
        ==
        detector.predict(flipped)
    )


def test_robust_calibration_formula():
    values = (
        [98.0, 99.0, 100.0, 101.0, 102.0]
        * 6
    )

    result = (
        calibrate_robust_interval_threshold(
            values
        )
    )

    assert result.sample_count == 30
    assert result.median_ms == 100.0
    assert result.mad_ms == 1.0
    assert result.robust_sigma_ms == pytest.approx(
        1.4826
    )

    assert result.threshold_ms == pytest.approx(
        100.0
        - 3.5 * 1.4826
    )


def test_calibration_fails_closed():
    with pytest.raises(ValueError):
        calibrate_robust_interval_threshold(
            [100.0] * 29
        )

    with pytest.raises(ValueError):
        calibrate_robust_interval_threshold(
            [100.0] * 30
        )

    with pytest.raises(ValueError):
        calibrate_robust_interval_threshold(
            [100.0] * 29
            + [float("nan")]
        )


def test_frozen_historical_calibration(tmp_path):
    import hashlib
    import json
    from pathlib import Path
    import subprocess
    import sys

    output = tmp_path / "calibration.json"
    subprocess.run([sys.executable, "scripts/calibrate_v06_detector.py",
                    "--output", str(output)], check=True)
    frozen = Path("research/v0.6_calibration.json")
    assert output.read_bytes() == frozen.read_bytes()
    data = json.loads(output.read_text())
    assert data["calibration"]["sample_count"] == 195
    assert data["calibration"]["threshold_ms"] == 100.23721899414062
    assert data["calibration_policy"]["v06_test_data_used"] is False
    for record in data["source_files"]:
        assert hashlib.sha256(Path(record["path"]).read_bytes()).hexdigest() == record["sha256"]
    rejected = subprocess.run([sys.executable, "scripts/calibrate_v06_detector.py",
                               "--source", str(tmp_path), "--output", str(output)],
                              capture_output=True)
    assert rejected.returncode != 0


def test_formula_cannot_be_tuned():
    with pytest.raises(ValueError, match="fixed"):
        calibrate_robust_interval_threshold(range(90, 120), multiplier=2)
