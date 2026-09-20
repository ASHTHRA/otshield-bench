import pytest

from otshield.core import Event
from otshield.detectors import PollingBurstDetector
from otshield.lab_timing import evaluate_timing_capture


def _event(i, interval):
    return {
        "event_id": f"pcap:{i:04d}",
        "timestamp_ms": float(i * 100),
        "function_code": 3,
        "address": (i - 1) % 10,
        "value": 0.0,
        "interval_ms": float(interval),
        "latency_ms": 0.3,
        "label": False,
        "schema": "OTB-TELEMETRY/0.1",
    }


def _dataset():
    intervals = [0, 100, 100, 10, 12, 100]

    records = []

    for i, interval in enumerate(intervals, start=1):
        records.append(
            {
                "telemetry": _event(i, interval),
                "context": {
                    "value_metadata": {
                        "transaction_id": i,
                        "status": "matched",
                        "duplicate_count": 0,
                    }
                },
            }
        )

    return {
        "schema": "OTB-INGEST/0.1",
        "provenance": {
            "source": "grfics",
            "dataset_id": "timing-test",
            "evidence_type": "lab_capture",
        },
        "records": records,
    }


def _protocol():
    return {
        "schema": "OTB-LAB-TIMING-PROTOCOL/0.1",
        "dataset_id": "timing-test",
        "threshold_ms": 50.0,
        "requests": [
            {
                "transaction_id": 1,
                "phase": "normal",
                "planned_interval_ms": None,
                "expected_anomaly": False,
            },
            {
                "transaction_id": 2,
                "phase": "normal",
                "planned_interval_ms": 100,
                "expected_anomaly": False,
            },
            {
                "transaction_id": 3,
                "phase": "normal",
                "planned_interval_ms": 100,
                "expected_anomaly": False,
            },
            {
                "transaction_id": 4,
                "phase": "burst",
                "planned_interval_ms": 10,
                "expected_anomaly": True,
            },
            {
                "transaction_id": 5,
                "phase": "burst",
                "planned_interval_ms": 10,
                "expected_anomaly": True,
            },
            {
                "transaction_id": 6,
                "phase": "normal",
                "planned_interval_ms": 100,
                "expected_anomaly": False,
            },
        ],
    }


def test_polling_detector_ignores_unknown_first_interval():
    events = [
        Event("a", 0, 3, 0, 0, 0, 0.3, False),
        Event("b", 1, 3, 0, 0, 100, 0.3, False),
        Event("c", 2, 3, 0, 0, 10, 0.3, True),
    ]

    result = PollingBurstDetector().predict(events)

    assert [item.alert for item in result] == [
        False,
        False,
        True,
    ]


def test_timing_experiment_known_confusion_matrix():
    manifest, details = evaluate_timing_capture(
        _dataset(),
        _protocol(),
    )

    metrics = manifest.effectiveness

    assert metrics["tp"] == 2
    assert metrics["fp"] == 0
    assert metrics["fn"] == 0
    assert metrics["tn"] == 4

    assert metrics["precision"] == 1
    assert metrics["recall"] == 1
    assert metrics["f1"] == 1

    assert len(details) == 6


def test_missing_protocol_transaction_is_rejected():
    protocol = _protocol()
    protocol["requests"] = protocol["requests"][:-1]

    with pytest.raises(ValueError):
        evaluate_timing_capture(
            _dataset(),
            protocol,
        )


@pytest.mark.parametrize(
    "threshold",
    [0, -1, float("inf"), True],
)
def test_bad_polling_threshold(threshold):
    with pytest.raises(ValueError):
        PollingBurstDetector(threshold)
