# OTShield OpenPLC Lab Evidence

Dataset: `openplc-readonly-20260920T171404Z`

This bundle records a real, isolated OpenPLC Docker laboratory run performed
for OTShield Bench.

## Scope

- Environment: local WSL2 + Docker laboratory
- Source: OpenPLC container from the GRFICS integration image
- Protocol: Modbus/TCP
- Traffic policy: read-only Function Code 3 requests
- Raw evidence: classic PCAP
- Normalization: OTShield `PcapTelemetryAdapter`
- Evidence type: `lab_capture`

## Files

- `raw.pcap` — raw captured Modbus/TCP traffic
- `normalized.json` — OTShield OTB-INGEST/0.1 representation
- `provenance.json` — environment and capture metadata
- `SHA256SUMS` — integrity hashes

## Evidence boundary

This demonstrates a real isolated OpenPLC execution and passive capture path.

It does **not** constitute:

- a full GRFICSv3 process-simulation validation;
- production OT testing;
- external independent validation;
- peer review;
- publication.

Full GRFICS experimental evaluation remains a separate milestone.
