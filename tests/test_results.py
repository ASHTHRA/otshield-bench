from dataclasses import replace
import json
import math

import pytest

from otshield.core import generate
from otshield.detectors import RuleDetector
from otshield.evaluation import evaluate
from otshield.results import (
    BenchmarkResultManifest,
    DegradedConnectivity,
    ResourceCostMetrics,
)


def _manifest():
    truth = generate("value_spike", count=20, seed=42)
    metrics = evaluate(
        truth,
        truth,
        RuleDetector().predict(truth),
    )

    return BenchmarkResultManifest(
        benchmark_version="0.3.0-alpha",
        detector_adapter="rules-v1",
        protocol="modbus-tcp",
        seed=42,
        provenance={
            "source": "synthetic",
            "dataset_id": "synthetic-value-spike-42",
            "evidence_type": "synthetic",
        },
        environment={
            "python": "3.12",
            "platform": "test-fixture",
        },
        effectiveness=metrics,
        resource_cost=ResourceCostMetrics(),
        degraded_connectivity=DegradedConnectivity(
            loss=0.2,
            latency_ms=5.0,
            jitter_ms=10.0,
        ),
    )


def test_manifest_is_deterministic():
    manifest = _manifest()

    assert manifest.to_json() == manifest.to_json()
    assert manifest.to_markdown() == manifest.to_markdown()

    payload = json.loads(manifest.to_json())

    assert payload["schema"] == "OTB-RESULT/0.1"
    assert payload["detector_adapter"] == "rules-v1"
    assert payload["protocol"] == "modbus-tcp"
    assert payload["seed"] == 42


def test_unmeasured_resource_values_remain_null():
    manifest = _manifest()
    payload = manifest.to_dict()

    assert payload["resource_cost"] == {
        "wall_time_ms": None,
        "cpu_time_ms": None,
        "peak_memory_mb": None,
    }

    report = manifest.to_markdown()
    assert report.count("unmeasured") == 3


def test_measured_resource_values_are_preserved():
    manifest = replace(
        _manifest(),
        resource_cost=ResourceCostMetrics(
            wall_time_ms=12.5,
            cpu_time_ms=7.0,
            peak_memory_mb=44.25,
        ),
    )

    payload = manifest.to_dict()["resource_cost"]

    assert payload["wall_time_ms"] == 12.5
    assert payload["cpu_time_ms"] == 7.0
    assert payload["peak_memory_mb"] == 44.25


def test_write_produces_json_and_markdown(tmp_path):
    manifest = _manifest()
    json_path = tmp_path / "result.json"
    md_path = tmp_path / "result.md"

    manifest.write(json_path, md_path)

    assert json_path.read_text() == manifest.to_json()
    assert md_path.read_text() == manifest.to_markdown()


@pytest.mark.parametrize(
    "change",
    [
        {"schema": "bad"},
        {"benchmark_version": ""},
        {"detector_adapter": ""},
        {"protocol": ""},
        {"seed": -1},
        {"seed": True},
        {"provenance": {"source": "synthetic"}},
        {"environment": {}},
    ],
)
def test_manifest_rejects_invalid_metadata(change):
    with pytest.raises(ValueError):
        replace(_manifest(), **change)


def test_manifest_rejects_missing_effectiveness_field():
    metrics = dict(_manifest().effectiveness)
    metrics.pop("f1")

    with pytest.raises(ValueError, match="missing required fields"):
        replace(_manifest(), effectiveness=metrics)


@pytest.mark.parametrize(
    "key,value",
    [
        ("coverage", -0.1),
        ("precision", 1.1),
        ("recall", math.nan),
        ("total", -1),
        ("tp", 1.5),
    ],
)
def test_manifest_rejects_invalid_effectiveness(key, value):
    metrics = dict(_manifest().effectiveness)
    metrics[key] = value

    with pytest.raises(ValueError):
        replace(_manifest(), effectiveness=metrics)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"loss": -0.1},
        {"loss": 1.1},
        {"latency_ms": -1},
        {"jitter_ms": -1},
        {"loss": math.nan},
    ],
)
def test_degraded_connectivity_validation(kwargs):
    with pytest.raises(ValueError):
        DegradedConnectivity(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"wall_time_ms": -1},
        {"cpu_time_ms": math.inf},
        {"peak_memory_mb": -0.1},
    ],
)
def test_resource_cost_validation(kwargs):
    with pytest.raises(ValueError):
        ResourceCostMetrics(**kwargs)
