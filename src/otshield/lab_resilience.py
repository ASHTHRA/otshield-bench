"""Evaluation of OTShield timing detection under degraded connectivity."""

from dataclasses import replace
import hashlib
import json
import math
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


PROTOCOL_SCHEMA = "OTB-LAB-RESILIENCE-PROTOCOL/0.1"


def _hash(document: dict[str, Any]) -> str:
    payload = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()

    return hashlib.sha256(payload).hexdigest()


def _finite_nonnegative(name, value):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(f"{name} must be finite and nonnegative")


def validate_protocol(protocol: dict[str, Any]):
    if protocol.get("schema") != PROTOCOL_SCHEMA:
        raise ValueError(f"protocol schema must be {PROTOCOL_SCHEMA}")

    condition = protocol.get("condition")

    if not isinstance(condition, dict):
        raise ValueError("condition object is required")

    for key in ("delay_ms", "jitter_ms", "loss_percent", "threshold_ms"):
        if key not in condition:
            raise ValueError(f"condition missing {key}")

        _finite_nonnegative(
            key,
            condition[key],
        )

    if condition["loss_percent"] > 100:
        raise ValueError("loss_percent must be <= 100")

    if condition["threshold_ms"] <= 0:
        raise ValueError("threshold_ms must be positive")

    requests = protocol.get("requests")

    if not isinstance(requests, list) or not requests:
        raise ValueError("protocol requests must be nonempty")

    plan = {}

    for item in requests:
        tid = item.get("transaction_id")

        if (
            isinstance(tid, bool)
            or not isinstance(tid, int)
            or tid <= 0
        ):
            raise ValueError("transaction_id must be positive integer")

        if tid in plan:
            raise ValueError("duplicate transaction_id")

        if type(item.get("expected_anomaly")) is not bool:
            raise ValueError("expected_anomaly must be boolean")

        phase = item.get("phase")

        if not isinstance(phase, str) or not phase:
            raise ValueError("phase must be nonempty")

        address = item.get("address")

        if (
            isinstance(address, bool)
            or not isinstance(address, int)
            or not 0 <= address <= 65535
        ):
            raise ValueError("address must be valid integer")

        interval = item.get("planned_interval_ms")

        if interval is not None:
            _finite_nonnegative(
                "planned_interval_ms",
                interval,
            )

        plan[tid] = item

    return plan


def _evaluate_resilience_capture(
    normalized: dict[str, Any],
    protocol: dict[str, Any],
    detector=None,
):
    if normalized.get("schema") != "OTB-INGEST/0.1":
        raise ValueError("expected OTB-INGEST/0.1")

    provenance = normalized.get("provenance")

    if (
        not isinstance(provenance, dict)
        or provenance.get("evidence_type") != "lab_capture"
    ):
        raise ValueError(
            "resilience experiment requires lab_capture provenance"
        )

    plan = validate_protocol(protocol)
    condition = protocol["condition"]

    truth = []

    for tid in sorted(plan):
        item = plan[tid]

        truth.append(
            Event(
                event_id=f"tid:{tid:04d}",
                timestamp_ms=float(tid),
                function_code=3,
                address=item["address"],
                value=0.0,
                interval_ms=float(
                    item["planned_interval_ms"] or 0.0
                ),
                latency_ms=0.0,
                label=item["expected_anomaly"],
            )
        )

    records = normalized.get("records")

    if not isinstance(records, list):
        raise ValueError("records must be a list")

    observed = []
    observed_by_tid = {}
    transport_status = {}

    for record in records:
        try:
            metadata = record["context"]["value_metadata"]
            tid = int(metadata["transaction_id"])
            status = metadata["status"]
            raw_event = Event(**record["telemetry"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("malformed normalized record") from None

        if tid not in plan:
            raise ValueError(
                f"transaction {tid} absent from protocol"
            )

        if tid in transport_status:
            raise ValueError(
                f"duplicate transaction {tid} in normalized dataset"
            )

        transport_status[tid] = status

        if status != "matched":
            continue

        event = replace(
            raw_event,
            event_id=f"tid:{tid:04d}",
            label=plan[tid]["expected_anomaly"],
        )

        observed.append(event)
        observed_by_tid[tid] = event

    prediction_events = observed if detector is None else [replace(event, label=False) for event in observed]
    if detector is None:
        detector = PollingBurstDetector(float(condition["threshold_ms"]))

    tracemalloc.start()

    wall_start = time.perf_counter_ns()
    cpu_start = time.process_time_ns()

    detections = detector.predict(prediction_events)

    cpu_ms = (
        time.process_time_ns() - cpu_start
    ) / 1_000_000

    wall_ms = (
        time.perf_counter_ns() - wall_start
    ) / 1_000_000

    _, peak_bytes = tracemalloc.get_traced_memory()

    tracemalloc.stop()

    metrics = evaluate(
        truth,
        observed,
        detections,
    )

    detection_by_id = {
        detection.event_id: detection
        for detection in detections
    }

    details = []

    for tid in sorted(plan):
        item = plan[tid]
        event = observed_by_tid.get(tid)

        event_id = f"tid:{tid:04d}"
        detection = detection_by_id.get(event_id)

        details.append(
            {
                "transaction_id": tid,
                "phase": item["phase"],
                "expected_anomaly": item["expected_anomaly"],
                "planned_interval_ms": item[
                    "planned_interval_ms"
                ],
                "transport_status": transport_status.get(
                    tid,
                    "not_observed",
                ),
                "observed_interval_ms": (
                    None if event is None
                    else event.interval_ms
                ),
                "observed_latency_ms": (
                    None if event is None
                    else event.latency_ms
                ),
                "alert": (
                    None if detection is None
                    else detection.alert
                ),
            }
        )

    manifest = BenchmarkResultManifest(
        benchmark_version="0.4.0-alpha",
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
            "experiment_protocol_sha256": _hash(protocol),
            "label_source": (
                "predeclared transaction-id experiment protocol"
            ),
            "impairment_direction": "client-egress",
            "sample_count": len(truth),
            "threshold_ms": detector.threshold_ms,
        },
        effectiveness=metrics,
        resource_cost=ResourceCostMetrics(
            wall_time_ms=wall_ms,
            cpu_time_ms=cpu_ms,
            peak_memory_mb=(
                peak_bytes / (1024 * 1024)
            ),
        ),
        degraded_connectivity=DegradedConnectivity(
            loss=float(
                condition["loss_percent"]
            ) / 100.0,
            latency_ms=float(
                condition["delay_ms"]
            ),
            jitter_ms=float(
                condition["jitter_ms"]
            ),
        ),
    )

    return manifest, details


def evaluate_resilience_capture(normalized, protocol):
    """Existing v0.5 interface and protocol-selected threshold."""
    return _evaluate_resilience_capture(normalized, protocol)
