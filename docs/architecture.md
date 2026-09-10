# Architecture and v0.2 roadmap

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
Separate normal training stream -> Isolation Forest          +-----> metrics + JSON

Offline normalized JSON -> adapter -> OTB-INGEST envelope
                                      | unchanged OTB-TELEMETRY events
                                      +-----------------------> detector / evaluation
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

## Planned

1. Add machine-readable JSON Schemas and validated external scenario loading.
2. Add repeated-seed experiment suites, aggregate metrics, and confidence intervals.
3. Calibrate anomaly thresholds on a separate validation stream and record provenance.
4. Add episode detection delay and scenario parameter sweeps without label leakage.
5. Expand abstract Modbus transaction semantics and process-state consistency.
6. Design raw PCAP decoding, capture provenance, and clock/correlation rules before
   running a genuine authorized GRFICS capture experiment.

Keep these extensions offline by default. Live capture, active lab control, and
deployment claims require a separately specified scope and are not v0.2 features.
