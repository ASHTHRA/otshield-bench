"""Evaluation of predeclared read-only timing experiments."""

from dataclasses import replace
import hashlib
import json
import platform
import time
import tracemalloc
from typing import Any

from .core import Event
from .detectors import PollingBurstDetector
from .evaluation import evaluate
from .results import (
    BenchmarkResultManifest,
    DegradedConnectivity,
    ResourceCostMetrics,
)


PROTOCOL_SCHEMA = "OTB-LAB-TIMING-PROTOCOL/0.1"


def _sha(document: dict[str, Any]) -> str:
    payload = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()

    return hashlib.sha256(payload).hexdigest()


def validate_timing_protocol(
    protocol: dict[str, Any],
) -> dict[int, dict[str, Any]]:
    if protocol.get("schema") != PROTOCOL_SCHEMA:
        raise ValueError(f"protocol schema must be {PROTOCOL_SCHEMA}")

    threshold = protocol.get("threshold_ms")

    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or threshold <= 0
    ):
        raise ValueError("threshold_ms must be positive")

    requests = protocol.get("requests")

    if not isinstance(requests, list) or not requests:
        raise ValueError("protocol requests must be a nonempty list")

    result = {}

    for item in requests:
        if not isinstance(item, dict):
            raise ValueError("request plan entry must be an object")

        tid = item.get("transaction_id")
        anomaly = item.get("expected_anomaly")
        phase = item.get("phase")

        if (
            isinstance(tid, bool)
            or not isinstance(tid, int)
            or tid <= 0
        ):
            raise ValueError("transaction_id must be positive integer")

        if tid in result:
            raise ValueError("duplicate transaction_id in protocol")

        if type(anomaly) is not bool:
            raise ValueError("expected_anomaly must be boolean")

        if not isinstance(phase, str) or not phase:
            raise ValueError("phase must be nonempty string")

        planned = item.get("planned_interval_ms")

        if planned is not None:
            if (
                isinstance(planned, bool)
                or not isinstance(planned, (int, float))
                or planned < 0
            ):
                raise ValueError(
                    "planned_interval_ms must be nonnegative or null"
                )

        result[tid] = item

    return result


def evaluate_timing_capture(
    normalized: dict[str, Any],
    protocol: dict[str, Any],
):
    if normalized.get("schema") != "OTB-INGEST/0.1":
        raise ValueError("expected OTB-INGEST/0.1 dataset")

    provenance = normalized.get("provenance")

    if (
        not isinstance(provenance, dict)
        or provenance.get("evidence_type") != "lab_capture"
    ):
        raise ValueError("timing experiment requires lab_capture provenance")

    plan = validate_timing_protocol(protocol)

    records = normalized.get("records")

    if not isinstance(records, list) or not records:
        raise ValueError("normalized dataset must contain records")

    truth = []
    observed_ids = set()
    details = []

    for record in records:
        try:
            metadata = record["context"]["value_metadata"]
            transaction_id = int(metadata["transaction_id"])
            telemetry = Event(**record["telemetry"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("malformed normalized record") from None

        if transaction_id in observed_ids:
            raise ValueError("duplicate observed transaction_id")

        observed_ids.add(transaction_id)

        if transaction_id not in plan:
            raise ValueError(
                f"transaction {transaction_id} absent from protocol"
            )

        expected = plan[transaction_id]["expected_anomaly"]

        truth_event = replace(
            telemetry,
            label=expected,
        )

        truth.append(truth_event)

    if observed_ids != set(plan):
        missing = sorted(set(plan) - observed_ids)
        raise ValueError(
            f"protocol transactions missing from capture: {missing}"
        )

    threshold = float(protocol["threshold_ms"])
    detector = PollingBurstDetector(threshold)

    tracemalloc.start()
    wall_start = time.perf_counter_ns()
    cpu_start = time.process_time_ns()

    detections = detector.predict(truth)

    cpu_ms = (time.process_time_ns() - cpu_start) / 1_000_000
    wall_ms = (time.perf_counter_ns() - wall_start) / 1_000_000

    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    metrics = evaluate(
        truth,
        truth,
        detections,
    )

    detection_by_id = {
        item.event_id: item
        for item in detections
    }

    for event, record in zip(truth, records):
        metadata = record["context"]["value_metadata"]
        tid = int(metadata["transaction_id"])
        detection = detection_by_id[event.event_id]

        details.append(
            {
                "transaction_id": tid,
                "phase": plan[tid]["phase"],
                "planned_interval_ms": (
                    plan[tid].get("planned_interval_ms")
                ),
                "observed_interval_ms": event.interval_ms,
                "expected_anomaly": event.label,
                "alert": detection.alert,
            }
        )

    manifest = BenchmarkResultManifest(
        benchmark_version="0.3.0-alpha",
        detector_adapter=detector.name,
        protocol="modbus-tcp-readonly-timing",
        seed=0,
        provenance={
            "source": provenance["source"],
            "dataset_id": provenance["dataset_id"],
            "evidence_type": provenance["evidence_type"],
        },
        environment={
            "python": platform.python_version(),
            "platform": platform.platform(),
            "experiment_protocol_schema": PROTOCOL_SCHEMA,
            "experiment_protocol_sha256": _sha(protocol),
            "label_source": (
                "predeclared transaction-id experiment protocol"
            ),
            "threshold_ms": threshold,
            "sample_count": len(truth),
        },
        effectiveness=metrics,
        resource_cost=ResourceCostMetrics(
            wall_time_ms=wall_ms,
            cpu_time_ms=cpu_ms,
            peak_memory_mb=peak_bytes / (1024 * 1024),
        ),
        degraded_connectivity=DegradedConnectivity(
            loss=0.0,
            latency_ms=0.0,
            jitter_ms=0.0,
        ),
    )

    return manifest, details
