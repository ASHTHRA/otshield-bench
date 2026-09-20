# Architecture and v0.3 roadmap

OTShield Bench measures OT anomaly detectors on controlled synthetic or normalized
offline observations. Its trust boundary is local Python data: no live industrial
system is involved.

```text
Bundled scenario JSON -> seeded generator -> immutable truth -----------------+
                                        |                              |
                                  loss/delay faults                    |
                                        |                              |
                                    observations -> detector -> identity join
                                                       |               |
Separate normal training stream -> Isolation Forest      +-----> metrics + JSON

Offline normalized JSON -> adapter -> OTB-INGEST envelope
                                     | unchanged OTB-TELEMETRY events
                                     +-----------------------> detector / evaluation

Docker OpenPLC -> capture_grfics.py -> OTB-INGEST-SOURCE/0.1
                                        | deterministic polling pattern
                                        | Modbus TCP transactions
                                        +-> JsonTelemetryAdapter -> OTB-INGEST/0.1
```

`core.py` owns event validation, generation, and fault simulation. `detectors.py`
owns the feature boundary and detector results. `evaluation.py` aligns identities
and calculates metrics. `cli.py` orchestrates runs and records evidence. Resource
files are packaged so installed wheels work outside the repository. `adapters/`
validates source-specific offline formats and attaches context around unchanged
telemetry records.

Local random generators avoid global RNG mutation. Different seeds separate
training (+1), evaluation (+0), and observation faults (+2). Ground truth is
retained before faults. Model scores use no truth labels. Synthetic anomalies
do not modify the subsequent process state; this is not a digital twin.

## Implemented

- Five deterministic, safe scenarios and documented versioned contracts.
- Rule and Isolation Forest baselines with explicit training and scoring behavior.
- Packet loss, fixed latency, jitter, arrival reordering, and coverage-aware metrics.
- CLI JSON export, pytest regression suite, installable wheel, and CI.
- Strict offline JSON ingestion with deterministic output and explicit provenance.
- A passive GRFICSv3/OpenPLC normalization boundary tested with sanitized fixture data.
- **(v0.3)** Docker-based OpenPLC integration for real Modbus TCP traffic generation.
- **(v0.3)** Deterministic capture script with seeded polling patterns and provenance.
- **(v0.3)** PCAP-to-OTB-INGEST-SOURCE conversion via tshark.
- **(v0.3)** End-to-end test suite with live OpenPLC server (25 new tests).

## v0.3 GRFICS/OpenPLC integration

v0.3 adds the smallest reproducible Docker-based integration needed to generate
and capture real Modbus traffic from a running OpenPLC server:

1. **Docker Compose** (`docker/docker-compose.grfics.yml`): Runs the GRFICSv3
   OpenPLC container on a local bridge network with health checks.

2. **Capture script** (`scripts/capture_grfics.py`): Polls the Modbus TCP server
   with a deterministic, seeded pattern and records transactions as
   `OTB-INGEST-SOURCE/0.1` JSON.

3. **Pipeline script** (`scripts/run_grfics_capture.sh`): Orchestrates the full
   lifecycle: start container, wait for health, capture, normalize, cleanup.

4. **Provenance**: Each capture records the tool version, host, seed, timestamp,
   and platform. A `.provenance.json` sidecar file preserves metadata outside the
   strict schema contract.

The full GRFICSv3 lab (simulation, SCADA HMI, attacker, router, Caldera, Wazuh)
is NOT deployed because it requires macvlan networking and ~8 GB RAM. The minimal
OpenPLC setup is sufficient for real Modbus TCP traffic capture and validation.

## Planned

1. Add machine-readable JSON Schemas and validated external scenario loading.
2. Add repeated-seed experiment suites, aggregate metrics, and confidence intervals.
3. Calibrate anomaly thresholds on a separate validation stream and record provenance.
4. Add episode detection delay and scenario parameter sweeps without label leakage.
5. Expand abstract Modbus transaction semantics and process-state consistency.
6. Design raw PCAP decoding, capture provenance, and clock/correlation rules before
   running a genuine authorized GRFICS capture experiment.
7. Full GRFICSv3 lab deployment with simulation container and process dynamics.

Keep these extensions offline by default. Live capture, active lab control, and
deployment claims require a separately specified scope and are not v0.2 features.
