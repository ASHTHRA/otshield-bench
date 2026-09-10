"""Backward-compatible context around unchanged OTB-TELEMETRY/0.1 events."""

from dataclasses import asdict, dataclass
from typing import Any

from ..core import Event

PROVENANCE_SOURCES = frozenset({"synthetic", "grfics", "other"})
EVIDENCE_TYPES = frozenset({"synthetic", "sanitized_fixture", "lab_capture", "other"})


def _optional_text(name: str, value: str | None) -> None:
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ValueError(f"{name} must be null or a nonempty string")


@dataclass(frozen=True)
class Provenance:
    source: str
    dataset_id: str
    evidence_type: str

    def __post_init__(self):
        if self.source not in PROVENANCE_SOURCES:
            raise ValueError(f"provenance source must be one of {sorted(PROVENANCE_SOURCES)}")
        if self.evidence_type not in EVIDENCE_TYPES:
            raise ValueError(f"evidence_type must be one of {sorted(EVIDENCE_TYPES)}")
        if not isinstance(self.dataset_id, str) or not self.dataset_id.strip():
            raise ValueError("dataset_id must be a nonempty string")
        if self.source == "synthetic" and self.evidence_type != "synthetic":
            raise ValueError("synthetic provenance requires synthetic evidence_type")


@dataclass(frozen=True)
class ObservationContext:
    source_endpoint: str | None = None
    destination_endpoint: str | None = None
    protocol: str | None = None
    operation: str | None = None
    target_type: str | None = None
    asset_id: str | None = None
    scenario_id: str | None = None
    value_metadata: dict[str, Any] | None = None

    def __post_init__(self):
        for name in ("source_endpoint", "destination_endpoint", "protocol", "operation",
                     "target_type", "asset_id", "scenario_id"):
            _optional_text(name, getattr(self, name))
        if self.value_metadata is not None and not isinstance(self.value_metadata, dict):
            raise ValueError("value_metadata must be null or an object")


@dataclass(frozen=True)
class IngestedEvent:
    telemetry: Event
    context: ObservationContext

    def to_dict(self) -> dict:
        return {"telemetry": self.telemetry.to_dict(), "context": asdict(self.context)}


@dataclass(frozen=True)
class IngestedDataset:
    provenance: Provenance
    records: tuple[IngestedEvent, ...]
    schema: str = "OTB-INGEST/0.1"

    def __post_init__(self):
        if self.schema != "OTB-INGEST/0.1":
            raise ValueError("invalid ingestion schema")
        if not self.records:
            raise ValueError("ingestion dataset must contain at least one record")
        event_ids = [record.telemetry.event_id for record in self.records]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("duplicate event IDs")

    @property
    def events(self) -> list[Event]:
        return [record.telemetry for record in self.records]

    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "provenance": asdict(self.provenance),
            "records": [record.to_dict() for record in self.records],
        }
