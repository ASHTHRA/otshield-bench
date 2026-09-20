"""Versioned, deterministic OTShield benchmark result manifests."""

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
from typing import Any, Mapping


RESULT_SCHEMA = "OTB-RESULT/0.1"

_EFFECTIVENESS_KEYS = (
    "total",
    "observed",
    "dropped",
    "coverage",
    "tp",
    "fp",
    "fn",
    "tn",
    "precision",
    "recall",
    "f1",
    "false_positive_rate",
    "end_to_end_recall",
)


def _text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")


def _nonnegative(name: str, value: float | int | None) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric or null")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and nonnegative")


@dataclass(frozen=True)
class ResourceCostMetrics:
    """Measured execution costs.

    None means the metric was not measured. It must not be replaced with an
    invented value.
    """

    wall_time_ms: float | None = None
    cpu_time_ms: float | None = None
    peak_memory_mb: float | None = None

    def __post_init__(self):
        _nonnegative("wall_time_ms", self.wall_time_ms)
        _nonnegative("cpu_time_ms", self.cpu_time_ms)
        _nonnegative("peak_memory_mb", self.peak_memory_mb)


@dataclass(frozen=True)
class DegradedConnectivity:
    loss: float = 0.0
    latency_ms: float = 0.0
    jitter_ms: float = 0.0

    def __post_init__(self):
        for name, value in (
            ("loss", self.loss),
            ("latency_ms", self.latency_ms),
            ("jitter_ms", self.jitter_ms),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be numeric")
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")

        if not 0 <= self.loss <= 1:
            raise ValueError("loss must be in [0,1]")
        if self.latency_ms < 0 or self.jitter_ms < 0:
            raise ValueError("latency and jitter must be nonnegative")


@dataclass(frozen=True)
class BenchmarkResultManifest:
    benchmark_version: str
    detector_adapter: str
    protocol: str
    seed: int
    provenance: Mapping[str, Any]
    environment: Mapping[str, Any]
    effectiveness: Mapping[str, Any]
    resource_cost: ResourceCostMetrics
    degraded_connectivity: DegradedConnectivity
    schema: str = RESULT_SCHEMA

    def __post_init__(self):
        if self.schema != RESULT_SCHEMA:
            raise ValueError(f"schema must be {RESULT_SCHEMA}")

        _text("benchmark_version", self.benchmark_version)
        _text("detector_adapter", self.detector_adapter)
        _text("protocol", self.protocol)

        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError("seed must be a nonnegative integer")

        if not isinstance(self.provenance, Mapping):
            raise ValueError("provenance must be an object")

        for key in ("source", "dataset_id", "evidence_type"):
            if key not in self.provenance:
                raise ValueError(f"provenance missing required field: {key}")
            _text(f"provenance.{key}", self.provenance[key])

        if not isinstance(self.environment, Mapping) or not self.environment:
            raise ValueError("environment must be a nonempty object")

        if not isinstance(self.effectiveness, Mapping):
            raise ValueError("effectiveness must be an object")

        missing = [key for key in _EFFECTIVENESS_KEYS if key not in self.effectiveness]
        if missing:
            raise ValueError(
                "effectiveness missing required fields: " + ", ".join(missing)
            )

        for key in _EFFECTIVENESS_KEYS:
            value = self.effectiveness[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"effectiveness.{key} must be numeric")
            if not math.isfinite(value):
                raise ValueError(f"effectiveness.{key} must be finite")

        for key in ("total", "observed", "dropped", "tp", "fp", "fn", "tn"):
            value = self.effectiveness[key]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"effectiveness.{key} must be a nonnegative integer")

        for key in (
            "coverage",
            "precision",
            "recall",
            "f1",
            "false_positive_rate",
            "end_to_end_recall",
        ):
            value = self.effectiveness[key]
            if not 0 <= value <= 1:
                raise ValueError(f"effectiveness.{key} must be in [0,1]")

        if not isinstance(self.resource_cost, ResourceCostMetrics):
            raise ValueError("resource_cost must be ResourceCostMetrics")

        if not isinstance(self.degraded_connectivity, DegradedConnectivity):
            raise ValueError(
                "degraded_connectivity must be DegradedConnectivity"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "benchmark_version": self.benchmark_version,
            "detector_adapter": self.detector_adapter,
            "protocol": self.protocol,
            "seed": self.seed,
            "provenance": dict(self.provenance),
            "environment": dict(self.environment),
            "effectiveness": dict(self.effectiveness),
            "resource_cost": asdict(self.resource_cost),
            "degraded_connectivity": asdict(self.degraded_connectivity),
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ) + "\n"

    def to_markdown(self) -> str:
        resource = asdict(self.resource_cost)

        lines = [
            "# OTShield Benchmark Result",
            "",
            f"- Schema: `{self.schema}`",
            f"- Benchmark version: `{self.benchmark_version}`",
            f"- Detector adapter: `{self.detector_adapter}`",
            f"- Protocol: `{self.protocol}`",
            f"- Seed: `{self.seed}`",
            "",
            "## Provenance",
            "",
        ]

        for key in sorted(self.provenance):
            lines.append(f"- {key}: `{self.provenance[key]}`")

        lines.extend(["", "## Environment", ""])

        for key in sorted(self.environment):
            lines.append(f"- {key}: `{self.environment[key]}`")

        lines.extend(["", "## Effectiveness", ""])

        for key in _EFFECTIVENESS_KEYS:
            lines.append(f"- {key}: `{self.effectiveness[key]}`")

        lines.extend(["", "## Resource cost", ""])

        for key in ("wall_time_ms", "cpu_time_ms", "peak_memory_mb"):
            value = resource[key]
            rendered = "unmeasured" if value is None else str(value)
            lines.append(f"- {key}: `{rendered}`")

        degraded = self.degraded_connectivity
        lines.extend(
            [
                "",
                "## Degraded connectivity",
                "",
                f"- loss: `{degraded.loss}`",
                f"- latency_ms: `{degraded.latency_ms}`",
                f"- jitter_ms: `{degraded.jitter_ms}`",
                "",
            ]
        )

        return "\n".join(lines)

    def write(self, json_path: Path, markdown_path: Path) -> None:
        Path(json_path).write_text(self.to_json())
        Path(markdown_path).write_text(self.to_markdown())
