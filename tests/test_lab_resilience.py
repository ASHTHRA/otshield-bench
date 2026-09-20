import pytest

from otshield.lab_resilience import (
    evaluate_resilience_capture,
)


def _protocol():
    return {
        "schema":
        "OTB-LAB-RESILIENCE-PROTOCOL/0.1",
        "dataset_id": "test",
        "condition": {
            "name": "loss-test",
            "delay_ms": 20.0,
            "jitter_ms": 5.0,
            "loss_percent": 5.0,
            "threshold_ms": 50.0,
        },
        "requests": [
            {
                "transaction_id": 1,
                "phase": "normal",
                "address": 0,
                "planned_interval_ms": None,
                "expected_anomaly": False,
            },
            {
                "transaction_id": 2,
                "phase": "burst",
                "address": 1,
                "planned_interval_ms": 10.0,
                "expected_anomaly": True,
            },
            {
                "transaction_id": 3,
                "phase": "burst",
                "address": 2,
                "planned_interval_ms": 10.0,
                "expected_anomaly": True,
            },
            {
                "transaction_id": 4,
                "phase": "normal",
                "address": 3,
                "planned_interval_ms": 100.0,
                "expected_anomaly": False,
            },
            {
                "transaction_id": 5,
                "phase": "normal",
                "address": 4,
                "planned_interval_ms": 100.0,
                "expected_anomaly": False,
            },
        ],
    }


def _record(tid, interval, status="matched"):
    return {
        "telemetry": {
            "event_id": f"pcap:{tid:04d}",
            "timestamp_ms": float(tid * 100),
            "function_code": 3,
            "address": tid - 1,
            "value": 0.0,
            "interval_ms": float(interval),
            "latency_ms": 1.0,
            "label": False,
            "schema": "OTB-TELEMETRY/0.1",
        },
        "context": {
            "value_metadata": {
                "transaction_id": tid,
                "status": status,
                "duplicate_count": 0,
            }
        },
    }


def _dataset():
    return {
        "schema": "OTB-INGEST/0.1",
        "provenance": {
            "source": "grfics",
            "dataset_id": "test",
            "evidence_type": "lab_capture",
        },
        "records": [
            _record(1, 0),
            _record(2, 10),
            # transaction 3 intentionally absent
            _record(4, 100),
            _record(5, 100),
        ],
    }


def test_resilience_accounts_for_missing_positive():
    manifest, details = (
        evaluate_resilience_capture(
            _dataset(),
            _protocol(),
        )
    )

    m = manifest.effectiveness

    assert m["total"] == 5
    assert m["observed"] == 4
    assert m["dropped"] == 1
    assert m["coverage"] == 0.8

    assert m["tp"] == 1
    assert m["fp"] == 0
    assert m["fn"] == 0
    assert m["tn"] == 3

    # Conditional recall among observed anomalies.
    assert m["recall"] == 1.0

    # End-to-end recall includes the missing anomaly.
    assert m["end_to_end_recall"] == 0.5

    assert len(details) == 5

    missing = next(
        row for row in details
        if row["transaction_id"] == 3
    )

    assert (
        missing["transport_status"]
        == "not_observed"
    )

    assert missing["alert"] is None


@pytest.mark.parametrize(
    "loss",
    [-1, 101],
)
def test_bad_loss_rejected(loss):
    protocol = _protocol()
    protocol["condition"]["loss_percent"] = loss

    with pytest.raises(ValueError):
        evaluate_resilience_capture(
            _dataset(),
            protocol,
        )
