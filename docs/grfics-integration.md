# GRFICSv3/OpenPLC passive ingestion

## Purpose and boundary

[GRFICSv3](https://github.com/djformby/GRFICSv3) is independent upstream research
infrastructure for industrial-control-system security experiments. OTShield does
not vendor, modify, launch, or control GRFICS. It uses GRFICS as an optional source
of Modbus observations from an explicitly authorized, isolated laboratory.

OTShield v0.2 adds the normalization and evaluation boundary: a researcher can
export decoded observations from a lab, convert them to a documented offline JSON
format, validate them, and produce existing OTB-TELEMETRY/0.1 records with explicit
provenance. The normal test suite uses a sanitized GRFICS-like fixture and requires
no GRFICS installation, PLC, packet capture, network access, or attacker tooling.
The fixture is illustrative test data; it is not represented as a live capture.

## Supported input

The implemented input is `OTB-INGEST-SOURCE/0.1` structured JSON. See
[the normative ingestion specification](../specs/OTB-INGEST.md) for its exact fields.
Each record supplies the complete numeric and label fields required by
OTB-TELEMETRY/0.1. Optional endpoint, protocol, operation, target, asset, scenario,
and value metadata fields are preserved. Missing optional values become explicit
`null` values in normalized output. No endpoints are resolved or contacted.

Normalize a file with:

```sh
otshield ingest observations.json --output normalized.json
```

The command validates the complete dataset before writing deterministic,
key-sorted `OTB-INGEST/0.1` JSON. Each output record wraps an unchanged
OTB-TELEMETRY/0.1 object plus context. Existing detectors can operate directly on
the telemetry objects. Provenance distinguishes source (`synthetic`, `grfics`, or
`other`) from evidence type (`synthetic`, `sanitized_fixture`, `lab_capture`, or
`other`), so fixture data cannot be mistaken for measured lab evidence.

## Normalization rules

- Input `id` becomes `event_id`; it must be unique and is never regenerated.
- Timestamps, function codes, addresses, values, intervals, latencies, and labels
  are validated by the unchanged OTB-TELEMETRY/0.1 implementation.
- Known Modbus operations and target types are derived from function codes only
  when those optional fields are absent. Supplied context is preserved.
- Core OTB-TELEMETRY fields cannot be omitted. Requiring them avoids fabricated
  measurements or ground truth.
- Unknown fields, non-finite numbers, empty datasets, and malformed records fail
  with a root or record location.

## Connecting a future authorized lab

A researcher may passively capture traffic inside an authorized GRFICSv3/OpenPLC
lab using independently selected tooling, decode Modbus transactions, assign ground
truth from the experiment protocol, and export OTB-INGEST-SOURCE/0.1 JSON. OTShield
then operates only on that offline export. Record the lab topology, upstream GRFICS
revision, capture and decoder versions, time basis, label procedure, and dataset ID
alongside the experiment so results can be reproduced.

No live lab was executed for this milestone. OTShield currently provides no capture
agent, PCAP decoder, clock synchronization, transaction correlation, automatic
ground-truth derivation, or process-state reconstruction. Raw PCAP support remains
planned until it can be added with clear decoding semantics and without bloating the
default installation.

## Safety

This integration is passive ingestion and normalization only. It contains no
scanning, exploitation, credential handling, PLC manipulation, vulnerability
triggering, attacker automation, or production-system access. Any future active
experiment must be separately specified and confined to an explicitly authorized,
isolated research laboratory.
