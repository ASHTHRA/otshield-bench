# OTB-INGEST/0.1

Status: alpha. OTB-INGEST is a backward-compatible envelope for passive, offline
telemetry ingestion. It does not change OTB-TELEMETRY/0.1. Each output record has:

- `telemetry`: an unchanged OTB-TELEMETRY/0.1 object accepted by existing detectors;
- `context`: nullable source/destination endpoints, protocol, operation, target type,
  asset ID, scenario ID, and value metadata;
- dataset-level `provenance`: `source`, `dataset_id`, and `evidence_type`.

Allowed provenance sources are `synthetic`, `grfics`, and `other`. Evidence types
are `synthetic`, `sanitized_fixture`, `lab_capture`, and `other`. A `grfics` source
does not by itself assert that data came from a live capture; `evidence_type` makes
that distinction explicit. Synthetic sources must use synthetic evidence type.

## OTB-INGEST-SOURCE/0.1 JSON input

The root object contains exactly `schema`, `provenance`, and `records`. `schema` is
`OTB-INGEST-SOURCE/0.1`. Provenance contains all three fields described above.

Every record must supply `id`, `timestamp_ms`, `function_code`, `address`, numeric
`value`, `interval_ms`, `latency_ms`, and boolean `label`. These fields are required
because OTB-TELEMETRY/0.1 requires them; the adapter never invents defaults. Optional
context fields may be omitted and become JSON `null` in normalized output.

For Modbus function codes 1–6, 15, and 16, `operation` and `target_type` are derived
from the function code only when omitted. Unknown operations remain `null`. Supplied
values are preserved. Endpoint strings are opaque identifiers and are not resolved
or contacted. Duplicate event IDs, unknown fields, empty datasets, non-finite values,
and values invalid under OTB-TELEMETRY/0.1 are rejected with record locations.

This format is deliberately normalized rather than a raw PCAP format. Capture tools
must decode transactions and supply the required fields before ingestion. PCAP
decoding is outside v0.2 to avoid adding a packet-processing dependency or implying
support for live traffic capture.
