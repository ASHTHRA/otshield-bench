import json

import pytest

from otshield.lab_baseline import (
    render_lab_markdown,
    summarize_lab_dataset,
    write_lab_report,
)


def _dataset():
    return {
        "schema": "OTB-INGEST/0.1",
        "provenance": {
            "source": "grfics",
            "dataset_id": "lab-test",
            "evidence_type": "lab_capture",
        },
        "records": [
            {
                "telemetry": {
                    "function_code": 3,
                    "address": 0,
                    "value": 10.0,
                    "interval_ms": 0.0,
                    "latency_ms": 1.0,
                },
                "context": {
                    "value_metadata": {
                        "status": "matched",
                        "duplicate_count": 0,
                    }
                },
            },
            {
                "telemetry": {
                    "function_code": 3,
                    "address": 1,
                    "value": 11.0,
                    "interval_ms": 100.0,
                    "latency_ms": 2.0,
                },
                "context": {
                    "value_metadata": {
                        "status": "matched",
                        "duplicate_count": 1,
                    }
                },
            },
            {
                "telemetry": {
                    "function_code": 3,
                    "address": 2,
                    "value": 12.0,
                    "interval_ms": 110.0,
                    "latency_ms": 3.0,
                },
                "context": {
                    "value_metadata": {
                        "status": "unmatched_request",
                        "duplicate_count": 0,
                    }
                },
            },
        ],
    }


def test_lab_summary():
    result = summarize_lab_dataset(_dataset())

    assert result["schema"] == "OTB-LAB-BASELINE/0.1"
    assert result["transactions"]["total"] == 3
    assert result["transactions"]["matched"] == 2
    assert result["transactions"]["duplicate_packet_count"] == 1
    assert result["latency_ms"]["p50"] == 2.0
    assert result["inter_request_interval_ms"]["count"] == 2
    assert result["inter_request_interval_ms"]["p50"] == 105.0


def test_lab_summary_preserves_protocol_counts():
    result = summarize_lab_dataset(_dataset())

    assert result["protocol"]["function_code_counts"] == {"3": 3}
    assert result["protocol"]["address_counts"] == {
        "0": 1,
        "1": 1,
        "2": 1,
    }


def test_markdown_does_not_claim_detector_effectiveness():
    report = render_lab_markdown(
        summarize_lab_dataset(_dataset())
    )

    assert "descriptive baseline" in report
    assert "not an anomaly-detector effectiveness result" in report


def test_report_write_is_deterministic(tmp_path):
    json_path = tmp_path / "baseline.json"
    md_path = tmp_path / "baseline.md"

    first = write_lab_report(
        _dataset(),
        json_path,
        md_path,
    )

    json_first = json_path.read_bytes()
    md_first = md_path.read_bytes()

    second = write_lab_report(
        _dataset(),
        json_path,
        md_path,
    )

    assert first == second
    assert json_path.read_bytes() == json_first
    assert md_path.read_bytes() == md_first

    parsed = json.loads(json_path.read_text())
    assert parsed["provenance"]["evidence_type"] == "lab_capture"


@pytest.mark.parametrize(
    "document",
    [
        {},
        {"schema": "wrong"},
        {
            "schema": "OTB-INGEST/0.1",
            "provenance": {},
            "records": [],
        },
    ],
)
def test_invalid_dataset_rejected(document):
    with pytest.raises(ValueError):
        summarize_lab_dataset(document)
