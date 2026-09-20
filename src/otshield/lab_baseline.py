"""Deterministic descriptive summaries for lab-derived OTShield captures."""

from collections import Counter
import json
import math
from pathlib import Path
from typing import Any


LAB_BASELINE_SCHEMA = "OTB-LAB-BASELINE/0.1"


def _finite(values):
    result = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("measurement must be numeric")
        if not math.isfinite(value):
            raise ValueError("measurement must be finite")
        result.append(float(value))
    return result


def _percentile(values: list[float], p: float) -> float:
    """Linear-interpolated percentile over sorted finite values."""
    if not values:
        raise ValueError("percentile requires at least one value")

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    position = (len(ordered) - 1) * p
    lower = int(math.floor(position))
    upper = int(math.ceil(position))

    if lower == upper:
        return ordered[lower]

    fraction = position - lower

    return (
        ordered[lower]
        + (ordered[upper] - ordered[lower]) * fraction
    )


def _stats(values) -> dict[str, float | int]:
    values = _finite(values)

    if not values:
        raise ValueError("statistics require at least one value")

    ordered = sorted(values)

    return {
        "count": len(values),
        "min": min(values),
        "mean": sum(values) / len(values),
        "p50": _percentile(ordered, 0.50),
        "p95": _percentile(ordered, 0.95),
        "max": max(values),
    }


def summarize_lab_dataset(document: dict[str, Any]) -> dict[str, Any]:
    if document.get("schema") != "OTB-INGEST/0.1":
        raise ValueError("expected OTB-INGEST/0.1 input")

    provenance = document.get("provenance")

    if not isinstance(provenance, dict):
        raise ValueError("dataset provenance is required")

    records = document.get("records")

    if not isinstance(records, list) or not records:
        raise ValueError("dataset must contain records")

    statuses = Counter()
    function_codes = Counter()
    addresses = Counter()

    duplicate_packets = 0
    latencies = []
    intervals = []
    values = []

    for index, record in enumerate(records):
        try:
            telemetry = record["telemetry"]
            metadata = record["context"]["value_metadata"]
        except (KeyError, TypeError):
            raise ValueError("malformed normalized record") from None

        status = metadata.get("status")

        if not isinstance(status, str) or not status:
            raise ValueError("transaction status is required")

        statuses[status] += 1

        duplicate_count = metadata.get("duplicate_count", 0)

        if (
            isinstance(duplicate_count, bool)
            or not isinstance(duplicate_count, int)
            or duplicate_count < 0
        ):
            raise ValueError("duplicate_count must be nonnegative integer")

        duplicate_packets += duplicate_count

        function_codes[int(telemetry["function_code"])] += 1
        addresses[int(telemetry["address"])] += 1

        latencies.append(telemetry["latency_ms"])
        values.append(telemetry["value"])

        # The first record has no previous request from which an interval
        # can be derived. Later zero intervals, if any, remain measurements.
        if index > 0:
            intervals.append(telemetry["interval_ms"])

    matched = statuses.get("matched", 0)

    return {
        "schema": LAB_BASELINE_SCHEMA,
        "measurement_scope": (
            "descriptive transport/application observations from one "
            "read-only OpenPLC lab capture"
        ),
        "provenance": {
            "source": provenance.get("source"),
            "dataset_id": provenance.get("dataset_id"),
            "evidence_type": provenance.get("evidence_type"),
        },
        "transactions": {
            "total": len(records),
            "matched": matched,
            "matched_ratio": matched / len(records),
            "status_counts": dict(sorted(statuses.items())),
            "duplicate_packet_count": duplicate_packets,
        },
        "protocol": {
            "name": "modbus-tcp",
            "function_code_counts": {
                str(key): value
                for key, value in sorted(function_codes.items())
            },
            "address_counts": {
                str(key): value
                for key, value in sorted(addresses.items())
            },
        },
        "latency_ms": _stats(latencies),
        "inter_request_interval_ms": _stats(intervals),
        "first_interval_unavailable": True,
        "observed_values": {
            "unique": sorted(set(float(v) for v in _finite(values))),
        },
        "limitations": [
            "single short capture",
            "read-only Function Code 3 traffic",
            "normal baseline only; no anomaly-effectiveness measurement",
            "first transaction may include connection/container warm-up cost",
            "not a full GRFICSv3 process-simulation experiment",
        ],
    }


def render_lab_markdown(summary: dict[str, Any]) -> str:
    tx = summary["transactions"]
    latency = summary["latency_ms"]
    interval = summary["inter_request_interval_ms"]
    protocol = summary["protocol"]
    provenance = summary["provenance"]

    lines = [
        "# OTShield OpenPLC Lab Baseline",
        "",
        f"- Schema: `{summary['schema']}`",
        f"- Dataset: `{provenance['dataset_id']}`",
        f"- Source: `{provenance['source']}`",
        f"- Evidence type: `{provenance['evidence_type']}`",
        "",
        "## Transaction integrity",
        "",
        f"- Total transactions: `{tx['total']}`",
        f"- Matched transactions: `{tx['matched']}`",
        f"- Matched ratio: `{tx['matched_ratio']:.6f}`",
        f"- Duplicate packets: `{tx['duplicate_packet_count']}`",
        "",
        "## Protocol coverage",
        "",
        f"- Protocol: `{protocol['name']}`",
        f"- Function-code counts: `{json.dumps(protocol['function_code_counts'], sort_keys=True)}`",
        f"- Address counts: `{json.dumps(protocol['address_counts'], sort_keys=True)}`",
        "",
        "## Response latency",
        "",
        f"- Minimum: `{latency['min']:.6f} ms`",
        f"- Mean: `{latency['mean']:.6f} ms`",
        f"- Median (p50): `{latency['p50']:.6f} ms`",
        f"- p95: `{latency['p95']:.6f} ms`",
        f"- Maximum: `{latency['max']:.6f} ms`",
        "",
        "## Inter-request interval",
        "",
        f"- Samples: `{interval['count']}`",
        f"- Minimum: `{interval['min']:.6f} ms`",
        f"- Mean: `{interval['mean']:.6f} ms`",
        f"- Median (p50): `{interval['p50']:.6f} ms`",
        f"- p95: `{interval['p95']:.6f} ms`",
        f"- Maximum: `{interval['max']:.6f} ms`",
        "",
        "The first transaction has no preceding request, so its interval is not included.",
        "",
        "## Evidence interpretation",
        "",
        "This is a descriptive baseline from a real isolated OpenPLC capture.",
        "It is not an anomaly-detector effectiveness result.",
        "",
        "## Limitations",
        "",
    ]

    for item in summary["limitations"]:
        lines.append(f"- {item}")

    lines.append("")

    return "\n".join(lines)


def write_lab_report(
    document: dict[str, Any],
    json_path: Path,
    markdown_path: Path,
) -> dict[str, Any]:
    summary = summarize_lab_dataset(document)

    Path(json_path).write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )

    Path(markdown_path).write_text(
        render_lab_markdown(summary)
    )

    return summary
