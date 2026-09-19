# GRFICSv3/OpenPLC passive ingestion

## Purpose and boundary

[GRFICSv3](https://github.com/Fortiphyd/GRFICSv3) is independent upstream research
infrastructure for industrial-control-system security experiments. OTShield does
not vendor, modify, launch, or control GRFICS. It uses GRFICS as an optional source
of Modbus observations from an explicitly authorized, isolated laboratory.

OTShield v0.2 added the normalization and evaluation boundary: a researcher can
export decoded observations from a lab, convert them to a documented offline JSON
format, validate them, and produce existing OTB-TELEMETRY/0.1 records with explicit
provenance. The normal test suite uses a sanitized GRFICS-like fixture and requires
no GRFICS installation, PLC, packet capture, network access, or attacker tooling.
The fixture is illustrative test data; it is not represented as a live capture.

**OTShield v0.3** adds Docker-based OpenPLC integration for generating and
capturing real Modbus TCP traffic from a running OpenPLC server, with
deterministic reproducibility and explicit provenance recording.

## Docker-based OpenPLC integration (v0.3)

### Architecture

v0.3 runs the GRFICSv3 OpenPLC container (`fortiphyd/grfics-plc`) on a local
Docker bridge network. The full GRFICSv3 lab (simulation, SCADA HMI, attacker,
router, etc.) is NOT started because it requires macvlan networking with a
dedicated host NIC and substantial resources (~8 GB RAM).

The minimal setup runs:
- **OpenPLC container**: Real Modbus TCP server on port 502, web UI on port 8080
- **Bridge network**: Isolated `192.168.100.0/24` network for traffic capture

### Prerequisites

- Docker and Docker Compose
- Python 3.10+ with `pymodbus` (`pip install pymodbus`)
- OpenPLC container image: `docker pull fortiphyd/grfics-plc:latest`

### Running the capture pipeline

```sh
# Full pipeline: start OpenPLC, capture traffic, normalize, stop
./scripts/run_grfics_capture.sh

# Or manually:
cd docker
docker compose -f docker-compose.grfics.yml up -d openplc
# Wait for health check to pass (~30s), then:
python scripts/capture_grfics.py \
    --host 127.0.0.1 --port 502 \
    --output captures/grfics_capture.json \
    --duration 10 --poll-interval 0.1
# Normalize:
otshield ingest captures/grfics_capture.json --output captures/normalized.json
# Cleanup:
docker compose -f docker-compose.grfics.yml down -v
```

### Capture script options

```
python scripts/capture_grfics.py --help

Options:
  --host          OpenPLC Modbus TCP host (default: 127.0.0.1)
  --port          OpenPLC Modbus TCP port (default: 502)
  --output        Output OTB-INGEST-SOURCE JSON path
  --duration      Capture duration in seconds (default: 10)
  --poll-interval Polling interval in seconds (default: 0.1)
  --seed          RNG seed for deterministic traffic (default: 42)
  --dataset-id    Dataset identifier (auto-generated if omitted)
  --pcap          Existing PCAP file to convert instead of live capture
  --evidence-type Evidence type for provenance (default: lab_capture)
```

### Traffic pattern

The capture script generates a deterministic Modbus polling pattern:
- **Normal operations** (80%): Read holding registers 0-9 at regular intervals
- **Normal writes** (16%): Write single register to addresses 0-9
- **Anomalous register scan** (3%): Read from out-of-policy addresses (1000, 5000, etc.)
- **Anomalous burst** (1%): Rapid burst of 3 reads at 5ms intervals

All operations are seeded and reproducible. Same seed + same host = same records.

### Provenance

Each capture produces:
- `OTB-INGEST-SOURCE/0.1` JSON with strict `OTB-INGEST/0.1` provenance
- A `.provenance.json` sidecar file with capture metadata (tool, host, seed, timestamps)
- A SHA-256 hash of the dataset for integrity verification

### Supported input formats

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

### PCAP conversion

The capture script can also convert existing PCAP files:

```sh
python scripts/capture_grfics.py \
    --pcap captures/traffic.pcap \
    --output captures/from_pcap.json \
    --evidence-type lab_capture
```

This requires `tshark` (Wireshark CLI) to be installed.

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

## What v0.3 does NOT include

The following remain outside the v0.3 scope and are planned for future milestones:
- Full GRFICSv3 lab deployment (requires macvlan + ~8 GB RAM)
- Simulation container integration (chemical plant dynamics)
- Automatic ground-truth derivation from experiment protocol
- Process-state reconstruction
- Clock synchronization across containers
- Raw PCAP decoding with transaction correlation

## Safety

This integration is passive ingestion and normalization only. It contains no
scanning, exploitation, credential handling, PLC manipulation, vulnerability
triggering, attacker automation, or production-system access. Any future active
experiment must be separately specified and confined to an explicitly authorized,
isolated research laboratory.
