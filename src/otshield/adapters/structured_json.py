"""Strict JSON adapter for normalized, offline Modbus observations."""

import json
from pathlib import Path
from typing import Any

from ..core import Event
from .model import IngestedDataset, IngestedEvent, ObservationContext, Provenance

SOURCE_SCHEMA = "OTB-INGEST-SOURCE/0.1"
_ROOT_FIELDS = frozenset({"schema", "provenance", "records"})
_PROVENANCE_FIELDS = frozenset({"source", "dataset_id", "evidence_type"})
_REQUIRED_RECORD_FIELDS = frozenset({
    "id", "timestamp_ms", "function_code", "address", "value", "interval_ms",
    "latency_ms", "label",
})
_CONTEXT_FIELDS = frozenset({
    "source_endpoint", "destination_endpoint", "protocol", "operation", "target_type",
    "asset_id", "scenario_id", "value_metadata",
})
_RECORD_FIELDS = _REQUIRED_RECORD_FIELDS | _CONTEXT_FIELDS

_OPERATIONS = {
    1: ("read_coils", "coil"),
    2: ("read_discrete_inputs", "discrete_input"),
    3: ("read_holding_registers", "register"),
    4: ("read_input_registers", "register"),
    5: ("write_single_coil", "coil"),
    6: ("write_single_register", "register"),
    15: ("write_multiple_coils", "coil"),
    16: ("write_multiple_registers", "register"),
}


def _reject_constant(value: str):
    raise ValueError(f"non-finite JSON number {value} is not allowed")


def _object(value: Any, location: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be an object")
    return value


def _exact_fields(value: dict, allowed: frozenset[str], location: str) -> None:
    unknown = value.keys() - allowed
    if unknown:
        raise ValueError(f"{location} has unknown field(s): {', '.join(sorted(unknown))}")


class JsonTelemetryAdapter:
    """Load OTB-INGEST-SOURCE/0.1 JSON without network or lab access."""

    def load(self, path: Path) -> IngestedDataset:
        try:
            with Path(path).open(encoding="utf-8") as stream:
                source = json.load(stream, parse_constant=_reject_constant)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot read ingestion JSON: {exc}") from exc

        root = _object(source, "root")
        _exact_fields(root, _ROOT_FIELDS, "root")
        if root.get("schema") != SOURCE_SCHEMA:
            raise ValueError(f"root.schema must be {SOURCE_SCHEMA}")

        raw_provenance = _object(root.get("provenance"), "root.provenance")
        _exact_fields(raw_provenance, _PROVENANCE_FIELDS, "root.provenance")
        missing_provenance = _PROVENANCE_FIELDS - raw_provenance.keys()
        if missing_provenance:
            raise ValueError(f"root.provenance missing field(s): {', '.join(sorted(missing_provenance))}")
        provenance = Provenance(**raw_provenance)

        raw_records = root.get("records")
        if not isinstance(raw_records, list):
            raise ValueError("root.records must be an array")

        records = []
        for index, raw_record in enumerate(raw_records):
            location = f"root.records[{index}]"
            record = _object(raw_record, location)
            _exact_fields(record, _RECORD_FIELDS, location)
            missing = _REQUIRED_RECORD_FIELDS - record.keys()
            if missing:
                raise ValueError(f"{location} missing field(s): {', '.join(sorted(missing))}")
            try:
                telemetry = Event(
                    event_id=record["id"],
                    timestamp_ms=record["timestamp_ms"],
                    function_code=record["function_code"],
                    address=record["address"],
                    value=record["value"],
                    interval_ms=record["interval_ms"],
                    latency_ms=record["latency_ms"],
                    label=record["label"],
                )
                derived = _OPERATIONS.get(telemetry.function_code, (None, None))
                context = ObservationContext(
                    **{name: record.get(name) for name in _CONTEXT_FIELDS
                       if name not in {"operation", "target_type"}},
                    operation=record["operation"] if "operation" in record else derived[0],
                    target_type=record["target_type"] if "target_type" in record else derived[1],
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{location}: {exc}") from exc
            records.append(IngestedEvent(telemetry, context))

        try:
            return IngestedDataset(provenance, tuple(records))
        except ValueError as exc:
            raise ValueError(f"invalid ingestion dataset: {exc}") from exc
